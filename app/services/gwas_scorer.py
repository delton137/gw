"""GWAS-hit PRS scorer — scores curated GWAS studies for a user.

Follows the PolyRiskScore (PRSKB) scoring approach exactly:
  1. Compute actual dosage for matched variants
  2. Impute unmatched variants with population MAF (expected dosage under HWE)
  3. Normalize: score = combined / (2 × N_total)
  4. For OR-type studies: score = exp(score)
  5. Percentile via empirical p0-p100 from PRSKB 1000G cohort data

Reference: existing_tools/PolyRiskScore/static/downloadables/calculate_score.py
"""

from __future__ import annotations

import json
import logging
from math import exp
from pathlib import Path

import polars as pl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.gwas import (
    GwasAssociation,
    GwasPrsResult,
    GwasStudy,
)
from app.services.scorer import compute_dosage

log = logging.getLogger(__name__)

# Map ancestry codes to gwas_associations column names
_ANCESTRY_AF_COL = {
    "EUR": "eur_af",
    "AFR": "afr_af",
    "EAS": "eas_af",
    "SAS": "sas_af",
    "AMR": "amr_af",
}

# Load empirical percentile data from PRSKB (1000G cohort, p0-p100 per study per ancestry)
_PERCENTILES_PATH = Path(__file__).resolve().parent.parent / "data" / "gwas_percentiles.json"
_EMPIRICAL_PERCENTILES: dict[str, dict[str, dict[str, float]]] = {}
if _PERCENTILES_PATH.exists():
    with open(_PERCENTILES_PATH) as _f:
        _EMPIRICAL_PERCENTILES = json.load(_f)


def _get_af(assoc: GwasAssociation, ancestry_group: str) -> float | None:
    """Get population-specific allele frequency for imputation.

    Uses only population-specific AFs (from 1000G PRSKB data).
    Does NOT fall back to risk_allele_frequency (GWAS catalog discovery cohort)
    because PRSKB uses mafVal=0 for SNPs not in their MAF files.
    Returns None if no population-specific AF available.
    """
    pop_col = _ANCESTRY_AF_COL.get(ancestry_group)
    if not pop_col:
        return None
    af = getattr(assoc, pop_col, None)
    if af is not None and (af <= 0 or af >= 1):
        return None
    return af


def empirical_percentile(
    score: float,
    percentile_dict: dict[str, float],
) -> float:
    """Look up empirical percentile from PRSKB p0-p100 table.

    Follows PRSKB getPercentile() logic (calculate_score.py:325-351):
    iterate p0→p100, find highest percentile where score >= threshold.
    Returns midpoint when score falls in a range of tied percentile values.
    """
    lb = 0
    ub = 0
    for i in range(101):
        p_val = percentile_dict[f"p{i}"]
        if score >= p_val and p_val != percentile_dict[f"p{lb}"]:
            lb = i
            ub = i
        elif score >= p_val:
            ub = i
        else:
            break

    # Return midpoint of range (PRSKB returns "lb-ub" string; we return numeric)
    return (lb + ub) / 2.0


async def score_gwas(
    user_df: pl.DataFrame,
    session: AsyncSession,
    ancestry_group: str,
    genome_build: str,
    user_id: str,
    analysis_id: str,
) -> list[GwasPrsResult]:
    """Score all GWAS-hit PRS for a user. Called after PRS scoring in analysis.py.

    Follows PolyRiskScore approach:
    - Matched variants: actual dosage × beta
    - Unmatched variants: imputed as 2 × MAF × beta (expected dosage under HWE)
    - Normalized: combined / (2 × N_total)
    - OR-type studies: exp(score) after normalization
    - Percentile from empirical PRSKB 1000G cohort data
    """
    # Load all studies (with value_type for OR vs beta distinction)
    studies_result = await session.execute(select(GwasStudy))
    studies = studies_result.scalars().all()
    if not studies:
        log.info(f"[{analysis_id}] No GWAS studies in database — skipping GWAS scoring")
        return []

    # Load all associations in one query (small dataset: ~3000 total rows)
    assoc_result = await session.execute(select(GwasAssociation))
    all_assocs = assoc_result.scalars().all()

    # Group by study_id
    assocs_by_study: dict[str, list[GwasAssociation]] = {}
    for a in all_assocs:
        assocs_by_study.setdefault(a.study_id, []).append(a)

    results = []
    for study in studies:
        assocs = assocs_by_study.get(study.study_id, [])
        if not assocs:
            continue

        # Filter out zero-effect variants (PRSKB excludes from nonMissingSnps)
        assocs = [a for a in assocs if a.beta != 0]
        n_total = len(assocs)
        if n_total == 0:
            continue

        # Build weights DataFrame for this study
        weights_df = pl.DataFrame({
            "rsid": [a.rsid for a in assocs],
            "effect_allele": [a.risk_allele for a in assocs],
            "weight": [a.beta for a in assocs],
        })

        # Step 1: Compute actual dosage for matched variants
        scored = compute_dosage(user_df, weights_df)
        n_matched = len(scored)
        matched_contribution = float(scored["contribution"].sum()) if n_matched > 0 else 0.0

        # Build set of matched rsids
        matched_rsids = set(scored["rsid"].to_list()) if n_matched > 0 else set()

        # Step 2: Impute unmatched variants with MAF (PRSKB approach)
        # Each missing allele contributes beta × MAF; both alleles missing = 2 × beta × MAF
        imputed_contribution = 0.0
        for a in assocs:
            if a.rsid in matched_rsids:
                continue
            af = _get_af(a, ancestry_group)
            if af is not None:
                imputed_contribution += 2 * af * a.beta

        # Step 3: Normalize (PRSKB: combined / (ploidy × nonMissingSnps))
        combined = matched_contribution + imputed_contribution
        score = combined / (2 * n_total)

        # Step 4: OR-type studies → exp() (PRSKB calculate_score.py:318-319)
        if study.value_type == "or":
            score = exp(score)

        # Step 5: Empirical percentile from PRSKB 1000G cohort data
        pct_data = _EMPIRICAL_PERCENTILES.get(study.study_id, {}).get(ancestry_group)
        if pct_data:
            percentile = empirical_percentile(score, pct_data)
            ref_mean = pct_data["p50"]
            # IQR-based std estimate: (p75 - p25) / 1.349
            iqr = pct_data["p75"] - pct_data["p25"]
            ref_std = iqr / 1.349 if iqr > 0 else 0.0
            z = (score - ref_mean) / ref_std if ref_std > 0 else None
        else:
            log.warning(
                f"[{analysis_id}] No empirical percentiles for {study.study_id}/{ancestry_group}"
            )
            percentile = None
            ref_mean = None
            ref_std = None
            z = None

        result = GwasPrsResult(
            user_id=user_id,
            analysis_id=analysis_id,
            study_id=study.study_id,
            raw_score=score,
            percentile=percentile,
            z_score=z,
            ref_mean=ref_mean,
            ref_std=ref_std,
            ancestry_group_used=ancestry_group,
            n_variants_matched=n_matched,
            n_variants_total=n_total,
        )
        session.add(result)
        results.append(result)

    return results
