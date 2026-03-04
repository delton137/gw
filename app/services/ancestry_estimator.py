"""Ancestry estimation using Aeon's probabilistic MLE on 128K AILs.

Uses Maximum Likelihood Estimation to estimate admixture fractions across
26 populations from 1000 Genomes Phase 3. The MLE minimizes the negative
log-likelihood of a Hardy-Weinberg genotype model with population mixture
allele frequencies — same algorithm as Aeon (Warren 2023), reimplemented
in scipy for lightweight deployment (no PyTorch/Pyro dependency).

Reference data: app/data/aeon_reference.parquet (128,097 AILs × 26 populations).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import polars as pl
from scipy.optimize import minimize

log = logging.getLogger(__name__)

SUPERPOPULATIONS = ["EUR", "AFR", "EAS", "SAS", "AMR"]
ADMIXED_THRESHOLD = 0.80  # Below this → flagged as admixed
MIN_MARKERS = 500  # With 128K panel, we should match thousands; 500 is very conservative
_VCF_HOM_REF_MIN_MATCH_FRAC = 0.03  # Need ≥3% position match to trust coordinates for hom-ref imputation

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_REFERENCE_PATH = _DATA_DIR / "aeon_reference.parquet"
_POP_MAP_PATH = _DATA_DIR / "pop_to_superpop.json"

# Lazy singleton caches
_CACHED_REF: pl.DataFrame | None = None
_CACHED_POP_MAP: dict[str, str] | None = None
_CACHED_POP_ORDER: list[str] | None = None


def _load_reference() -> tuple[pl.DataFrame | None, dict[str, str] | None, list[str] | None]:
    """Load and cache reference data (lazy singleton)."""
    global _CACHED_REF, _CACHED_POP_MAP, _CACHED_POP_ORDER

    if _CACHED_REF is not None:
        return _CACHED_REF, _CACHED_POP_MAP, _CACHED_POP_ORDER

    if not _REFERENCE_PATH.exists():
        log.error("Aeon reference not found: %s", _REFERENCE_PATH)
        return None, None, None
    if not _POP_MAP_PATH.exists():
        log.error("Population map not found: %s", _POP_MAP_PATH)
        return None, None, None

    _CACHED_REF = pl.read_parquet(_REFERENCE_PATH)
    with open(_POP_MAP_PATH) as f:
        _CACHED_POP_MAP = json.load(f)

    # Population column order (matches reference parquet columns)
    _CACHED_POP_ORDER = [
        c for c in _CACHED_REF.columns
        if c not in ("rsid", "var_id", "chrom", "position", "position_grch37", "ref", "alt")
    ]

    log.info(
        "Loaded Aeon reference: %d markers, %d populations",
        len(_CACHED_REF), len(_CACHED_POP_ORDER),
    )
    return _CACHED_REF, _CACHED_POP_MAP, _CACHED_POP_ORDER


def _genotype_to_dosage(allele1: str, allele2: str, ref: str, alt: str) -> int:
    """Convert diploid genotype to ALT allele dosage (0, 1, or 2).

    Counts the number of ALT alleles in the user's genotype.
    Returns 0 (homozygous reference) if alleles don't match ref/alt.
    """
    count = 0
    for a in (allele1, allele2):
        if a == alt:
            count += 1
        elif a != ref:
            # Unknown allele — treat as ref (conservative)
            pass
    return count


def _mle_ancestry(dosages: np.ndarray, allele_freqs: np.ndarray) -> tuple[np.ndarray, float]:
    """Maximum likelihood estimation of population mixture proportions.

    Implements the same probabilistic model as Aeon's PopulationMixtureModelRandom.est_mle():
    - Assume individual is a mixture of K populations with proportions p_k
    - At each locus j, mixture allele frequency r_j = Σ_k (p_k × AF_kj)
    - Genotype probability follows Hardy-Weinberg: P(0)=(1-r)², P(1)=2r(1-r), P(2)=r²
    - Maximize log-likelihood over p subject to simplex constraint (p_k ≥ 0, Σp_k = 1)

    Args:
        dosages: (n_loci,) array with values in {0, 1, 2}
        allele_freqs: (n_loci, n_populations) array of ALT allele frequencies

    Returns:
        (proportions, neg_log_likelihood) tuple
    """
    n_pops = allele_freqs.shape[1]

    def neg_log_likelihood(p: np.ndarray) -> float:
        r = allele_freqs @ p  # (n_loci,) mixture allele freq per locus
        r = np.clip(r, 1e-10, 1 - 1e-10)  # avoid log(0)

        # Hardy-Weinberg genotype probabilities: [hom_ref, het, hom_alt]
        probs = np.column_stack([(1 - r) ** 2, 2 * r * (1 - r), r ** 2])

        # Select the probability for each observed dosage
        ll = np.sum(np.log(probs[np.arange(len(dosages)), dosages]))
        return -ll

    # Simplex constraint: proportions sum to 1, each in [0, 1]
    result = minimize(
        neg_log_likelihood,
        x0=np.ones(n_pops) / n_pops,
        method="SLSQP",
        bounds=[(0.0, 1.0)] * n_pops,
        constraints=[{"type": "eq", "fun": lambda p: np.sum(p) - 1.0}],
        options={"maxiter": 1000, "ftol": 1e-10},
    )

    return result.x, result.fun


@dataclass
class AncestryResult:
    """Result of ancestry estimation."""

    proportions: dict[str, float]  # 26 populations → fractions (backward-compat field name)
    best_pop: str  # best superpopulation (for PRS compat)
    confidence: float  # max superpopulation fraction
    n_markers_used: int
    is_admixed: bool
    # New fields
    populations: dict[str, float] = field(default_factory=dict)  # 26 populations
    superpopulations: dict[str, float] = field(default_factory=dict)  # 5 aggregated
    n_markers_total: int = 128097
    coverage_quality: str = "high"  # "high"/"medium"/"low"


def estimate_ancestry(
    user_df: pl.DataFrame,
    is_vcf: bool = False,
    genome_build: str = "GRCh38",
) -> AncestryResult | None:
    """Estimate ancestry using MLE on 128K ancestry-informative loci.

    Matches user genotypes to the Aeon reference panel by chromosome+position,
    using the correct position column for the detected genome build.
    Falls back to rsid-based matching if position matching is poor.

    For VCF files with sufficient position matches, unmatched reference
    positions are treated as homozygous reference (dosage 0).

    Args:
        user_df: Parsed genotype DataFrame [rsid, chrom, position, allele1, allele2].
        is_vcf: If True, VCF file (enables hom-ref imputation for unmatched positions).
        genome_build: Detected genome build ("GRCh37", "GRCh38", or "unknown").

    Returns:
        AncestryResult with 26-population proportions, or None if too few markers.
    """
    try:
        ref_df, pop_map, pop_order = _load_reference()
        if ref_df is None or pop_map is None or pop_order is None:
            return None

        # --- Step 1: Match user variants to reference ---
        user_slim = user_df.select(["rsid", "chrom", "position", "allele1", "allele2"])

        # Normalize chrom: strip "chr" prefix for consistent matching
        user_norm = user_slim.with_columns(
            pl.col("chrom").str.replace("^chr", "").alias("chrom_norm")
        )
        ref_norm = ref_df.with_columns(
            pl.col("chrom").str.replace("^chr", "").alias("chrom_norm")
        )

        # Pick the correct reference position column for the user's build
        ref_pos_col = "position_grch37" if genome_build == "GRCh37" else "position"
        has_build_positions = ref_pos_col in ref_norm.columns
        log.info(f"Ancestry: matching with {genome_build} positions (column={ref_pos_col})")

        # Strategy 1: Position-based matching (primary)
        if has_build_positions:
            ref_for_match = ref_norm.filter(pl.col(ref_pos_col).is_not_null())
            matched = user_norm.join(
                ref_for_match.select(["chrom_norm", ref_pos_col, "ref", "alt"] + pop_order),
                left_on=["chrom_norm", "position"],
                right_on=["chrom_norm", ref_pos_col],
                how="inner",
            )
        else:
            # No GRCh37 column available, try GRCh38 positions as fallback
            matched = user_norm.join(
                ref_norm.select(["chrom_norm", "position", "ref", "alt"] + pop_order),
                left_on=["chrom_norm", "position"],
                right_on=["chrom_norm", "position"],
                how="inner",
            )
        n_matched = len(matched)
        log.info(f"Ancestry: matched {n_matched} markers by chrom+position ({genome_build})")

        # Strategy 2: rsid-based matching (fallback — build-independent)
        if n_matched < MIN_MARKERS:
            ref_with_rsid = ref_df.filter(pl.col("rsid").is_not_null())
            if len(ref_with_rsid) > 0:
                log.info("Trying rsid-based matching...")
                matched_rsid = user_slim.join(
                    ref_with_rsid.select(["rsid", "ref", "alt"] + pop_order),
                    on="rsid",
                    how="inner",
                )
                if len(matched_rsid) > n_matched:
                    log.info(f"rsid matching found {len(matched_rsid)} markers (vs {n_matched} by position)")
                    matched = matched_rsid
                    n_matched = len(matched)

        if n_matched < MIN_MARKERS:
            log.warning(
                f"Matched only {n_matched} markers (minimum {MIN_MARKERS}) — "
                "ancestry estimation skipped"
            )
            return None

        # --- Step 2: Compute dosages ---
        dosages = np.array([
            _genotype_to_dosage(a1, a2, ref, alt)
            for a1, a2, ref, alt in zip(
                matched["allele1"].to_list(),
                matched["allele2"].to_list(),
                matched["ref"].to_list(),
                matched["alt"].to_list(),
            )
        ], dtype=np.int64)

        # --- Step 3: Extract allele frequency matrix ---
        af_matrix = matched.select(pop_order).to_numpy().astype(np.float64)

        # --- Step 3b: For VCF, missing reference positions are hom-ref (dosage 0) ---
        # Only apply when match rate is high enough to trust coordinate alignment (≥3%).
        # Low match rate suggests build mismatch → don't assume hom-ref.
        match_frac = n_matched / len(ref_df)
        if is_vcf and match_frac >= _VCF_HOM_REF_MIN_MATCH_FRAC:
            # Use the build-appropriate position column for anti-join
            if has_build_positions and ref_pos_col != "position":
                # For GRCh37: anti-join on user positions vs ref GRCh37 positions
                matched_positions = matched.select(
                    pl.col("chrom_norm"),
                    pl.col("position"),  # user's position
                )
                unmatched_ref = ref_for_match.join(
                    matched_positions,
                    left_on=["chrom_norm", ref_pos_col],
                    right_on=["chrom_norm", "position"],
                    how="anti",
                )
            else:
                unmatched_ref = ref_norm.join(
                    matched.select("chrom_norm", "position").unique(),
                    on=["chrom_norm", "position"],
                    how="anti",
                )
            n_unmatched = len(unmatched_ref)
            if n_unmatched > 0:
                log.info(f"VCF mode: adding {n_unmatched} hom-ref positions from reference")
                unmatched_af = unmatched_ref.select(pop_order).to_numpy().astype(np.float64)
                dosages = np.concatenate([dosages, np.zeros(n_unmatched, dtype=np.int64)])
                af_matrix = np.vstack([af_matrix, unmatched_af])
                n_matched += n_unmatched
        elif is_vcf:
            log.info(
                f"VCF mode: low match rate ({match_frac:.1%}), "
                f"skipping hom-ref imputation"
            )

        # --- Step 4: Run MLE ---
        log.info(f"Running MLE ancestry estimation with {len(dosages)} markers...")
        proportions_arr, nll = _mle_ancestry(dosages, af_matrix)

        # --- Step 5: Build result ---
        populations = {}
        for i, pop in enumerate(pop_order):
            val = round(float(proportions_arr[i]), 4)
            if val > 0.0001:  # Skip negligible
                populations[pop] = val
            else:
                populations[pop] = 0.0

        # Renormalize after rounding/zeroing so proportions sum to 1.0
        pop_total = sum(populations.values())
        if pop_total > 0:
            populations = {k: round(v / pop_total, 4) for k, v in populations.items()}

        # Aggregate to superpopulations
        superpopulations: dict[str, float] = {sp: 0.0 for sp in SUPERPOPULATIONS}
        for pop, frac in populations.items():
            sp = pop_map.get(pop)
            if sp:
                superpopulations[sp] = round(superpopulations[sp] + frac, 4)

        # Renormalize superpopulations
        sp_total = sum(superpopulations.values())
        if sp_total > 0:
            superpopulations = {k: round(v / sp_total, 4) for k, v in superpopulations.items()}

        # Best superpopulation
        best_pop = max(superpopulations, key=lambda k: superpopulations[k])
        confidence = superpopulations[best_pop]
        is_admixed = confidence < ADMIXED_THRESHOLD

        # Coverage quality
        coverage_frac = n_matched / len(ref_df)
        if coverage_frac >= 0.20:
            coverage_quality = "high"
        elif coverage_frac >= 0.05:
            coverage_quality = "medium"
        else:
            coverage_quality = "low"

        log.info(
            f"Ancestry estimated from {n_matched} markers: "
            f"{best_pop} ({confidence:.0%})"
            + (f" [admixed]" if is_admixed else "")
            + f" | coverage={coverage_quality} ({coverage_frac:.1%})"
        )

        return AncestryResult(
            proportions=populations,  # backward compat: now 26 keys instead of 5
            best_pop=best_pop,
            confidence=confidence,
            n_markers_used=n_matched,
            is_admixed=is_admixed,
            populations=populations,
            superpopulations=superpopulations,
            n_markers_total=len(ref_df),
            coverage_quality=coverage_quality,
        )

    except Exception as e:
        log.error(f"Ancestry estimation failed: {e}", exc_info=True)
        return None
