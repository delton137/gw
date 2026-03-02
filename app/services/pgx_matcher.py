"""Pharmacogenomics matcher — infers star alleles, diplotypes, and metabolizer phenotypes.

Takes a user's parsed genotype DataFrame and queries pgx_star_allele_definitions
to call star alleles, build diplotypes, and assign phenotypes using CPIC-based
activity score or function-pair lookup methods.
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

BATCH_SIZE = 5000

# ---------------------------------------------------------------------------
# Genes to exclude from results (definitions kept for future use)
# GSTM1: ~50% of Europeans carry a whole-gene deletion (*Null) that is
# undetectable from genotype data, making results unreliable.
# SULT1A1: ~25% of people carry gene duplications undetectable from
# genotype data, making activity predictions unreliable.
# CYP2D6: included with caveat — CNV affects phenotype assignment in ~2%
# of patients (Bousman et al. 2024), but SNP-based calling is still
# informative for the ~90-98% without clinically relevant CNV.
# ---------------------------------------------------------------------------
PGX_SKIP_GENES: set[str] = {"GSTM1", "SULT1A1"}

# ---------------------------------------------------------------------------
# Activity score thresholds (CPIC-based)
# ---------------------------------------------------------------------------

ACTIVITY_SCORE_THRESHOLDS: dict[str, list[tuple[float, float, str]]] = {
    # (min_inclusive, max_exclusive, phenotype)
    # CPIC-established thresholds for well-characterized genes
    "CYP2D6": [
        (0, 0.001, "Poor Metabolizer"),
        (0.001, 1.0, "Intermediate Metabolizer"),
        (1.0, 2.26, "Normal Metabolizer"),
        (2.26, 100, "Ultra-rapid Metabolizer"),
    ],
    "CYP2C19": [
        (0, 0.001, "Poor Metabolizer"),
        (0.001, 0.75, "Likely Poor Metabolizer"),
        (0.75, 1.25, "Intermediate Metabolizer"),
        (1.25, 1.75, "Likely Intermediate Metabolizer"),
        (1.75, 2.001, "Normal Metabolizer"),
        (2.001, 2.75, "Rapid Metabolizer"),
        (2.75, 100, "Ultrarapid Metabolizer"),
    ],
    "CYP2C9": [
        (0, 0.001, "Poor Metabolizer"),
        (0.001, 2.0, "Intermediate Metabolizer"),
        (2.0, 100, "Normal Metabolizer"),
    ],
    "DPYD": [
        (0, 1.0, "Poor Metabolizer"),
        (1.0, 2.0, "Intermediate Metabolizer"),
        (2.0, 100, "Normal Metabolizer"),
    ],
}

# Default thresholds from Stargazer phenotyper.py for genes without CPIC-specific ranges
_DEFAULT_METABOLIZER: list[tuple[float, float, str]] = [
    (0, 0.001, "Poor Metabolizer"),
    (0.001, 1.25, "Intermediate Metabolizer"),
    (1.25, 2.001, "Normal Metabolizer"),
    (2.001, 2.5, "Rapid Metabolizer"),
    (2.5, 100, "Ultra-rapid Metabolizer"),
]

_DEFAULT_TRANSPORTER: list[tuple[float, float, str]] = [
    (0, 1.001, "Poor Function"),
    (1.001, 1.5, "Decreased Function"),
    (1.5, 2.001, "Normal Function"),
    (2.001, 100, "Increased Function"),
]

# Genes that use transporter thresholds instead of metabolizer
_TRANSPORTER_GENES = {"SLCO1B1", "SLCO1B3", "SLCO2B1"}

# Default activity score for the *1 (wild-type) allele
DEFAULT_ALLELE_SCORE = 1.0


# ---------------------------------------------------------------------------
# Drug annotations cache 
# ---------------------------------------------------------------------------

_DRUG_CACHE: dict[str, list[str]] | None = None

# Cache for PGx rsid → (chrom, position) from stargazer_alleles.json, keyed by genome build
_PGX_POS_CACHE: dict[str, dict[str, tuple[str, int]]] = {}

# Cache for PGx rsid → ref_allele from stargazer_alleles.json
_PGX_REF_CACHE: dict[str, str] | None = None


def _load_pgx_positions(genome_build: str = "GRCh38") -> dict[str, tuple[str, int]]:
    """Load rsid → (chrom, position) mapping from stargazer_alleles.json."""
    if genome_build in _PGX_POS_CACHE:
        return _PGX_POS_CACHE[genome_build]

    pgx_path = Path(__file__).parent.parent / "data" / "pgx_alleles.json"
    if not pgx_path.exists():
        _PGX_POS_CACHE[genome_build] = {}
        return _PGX_POS_CACHE[genome_build]

    pos_field = "position_grch37" if genome_build == "GRCh37" else "position"

    data = json.loads(pgx_path.read_text())
    cache: dict[str, tuple[str, int]] = {}
    for v in data.get("variants", []):
        rsid = v.get("rsid")
        chrom = v.get("chrom")
        pos = v.get(pos_field)
        if rsid and chrom and pos:
            cache[rsid] = (str(chrom), int(pos))
    _PGX_POS_CACHE[genome_build] = cache
    return cache


def _load_pgx_ref_alleles() -> dict[str, str]:
    """Load rsid → ref_allele mapping from stargazer_alleles.json."""
    global _PGX_REF_CACHE
    if _PGX_REF_CACHE is not None:
        return _PGX_REF_CACHE

    pgx_path = Path(__file__).parent.parent / "data" / "pgx_alleles.json"
    if not pgx_path.exists():
        _PGX_REF_CACHE = {}
        return _PGX_REF_CACHE

    data = json.loads(pgx_path.read_text())
    _PGX_REF_CACHE = {}
    for v in data.get("variants", []):
        rsid = v.get("rsid")
        ref = v.get("ref_allele")
        if rsid and ref:
            _PGX_REF_CACHE[rsid] = ref
    return _PGX_REF_CACHE


def _load_drug_cache() -> dict[str, list[str]]:
    """Load per-gene drug lists from CPIC/DPWG guidelines."""
    global _DRUG_CACHE
    if _DRUG_CACHE is not None:
        return _DRUG_CACHE

    _DRUG_CACHE = {}
    guidelines_path = Path(__file__).parent.parent / "data" / "cpic_dpwg_guidelines.json"
    if not guidelines_path.exists():
        log.warning("CPIC/DPWG guidelines not found at %s", guidelines_path)
        return _DRUG_CACHE

    try:
        guidelines = json.loads(guidelines_path.read_text())
        for g in guidelines:
            gene = g.get("gene", "")
            drug = g.get("drug", "")
            if gene and drug:
                if gene not in _DRUG_CACHE:
                    _DRUG_CACHE[gene] = set()
                _DRUG_CACHE[gene].add(drug)
        # Convert sets to sorted lists
        _DRUG_CACHE = {k: sorted(v) for k, v in _DRUG_CACHE.items()}
    except Exception as e:
        log.warning("Failed to load drug cache: %s", e)

    return _DRUG_CACHE


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PgxResult:
    """A single pharmacogenomics result for one gene."""
    gene: str
    diplotype: str           # "*1/*4"
    allele1: str             # "*1"
    allele2: str             # "*4"
    allele1_function: str    # "normal_function"
    allele2_function: str    # "no_function"
    phenotype: str           # "Intermediate Metabolizer"
    activity_score: float | None
    n_variants_tested: int
    n_variants_total: int
    calling_method: str
    confidence: str          # "high" | "medium" | "low"
    drugs_affected: str | None
    clinical_note: str | None
    variant_genotypes: dict[str, str] | None  # {rsid: "A/G", ...}


# ---------------------------------------------------------------------------
# Star allele calling logic
# ---------------------------------------------------------------------------

def _score_to_phenotype(gene: str, score: float) -> str:
    """Map an activity score to a phenotype using gene-specific thresholds."""
    thresholds = ACTIVITY_SCORE_THRESHOLDS.get(gene)
    if thresholds is None:
        # Use default thresholds based on gene category
        thresholds = _DEFAULT_TRANSPORTER if gene in _TRANSPORTER_GENES else _DEFAULT_METABOLIZER
    for lo, hi, phenotype in thresholds:
        if lo <= score < hi:
            return phenotype
    return "Normal Metabolizer"


def _compute_confidence(n_tested: int, n_total: int) -> str:
    """Compute confidence based on variant coverage ratio."""
    if n_total == 0:
        return "low"
    ratio = n_tested / n_total
    if ratio >= 0.8:
        return "high"
    elif ratio >= 0.5:
        return "medium"
    return "low"


def _generate_clinical_note(gene: str, diplotype: str, phenotype: str, calling_method: str) -> str:
    """Generate a consumer-friendly clinical note."""
    if calling_method == "binary":
        if "Positive" in phenotype:
            return f"You carry a genetic marker associated with {gene.replace('_', '*')} risk."
        return f"You do not carry the {gene.replace('_', '*')} risk marker tested."

    if calling_method == "count":
        return f"Your NAT2 acetylator status is: {phenotype}. This affects how you metabolize isoniazid, hydralazine, and sulfonamides."

    return f"Your {gene} result is {diplotype} ({phenotype})."


def call_star_alleles_for_gene(
    gene: str,
    calling_method: str,
    default_allele: str,
    allele_defs: list[dict],
    user_lookup: dict[str, tuple[str, str]],
) -> tuple[list[tuple[str, str, int]], int, int]:
    """Call star alleles for a single gene given user genotypes.

    Returns:
        (detected_alleles, n_tested, n_total)
        detected_alleles: list of (star_allele, function, copy_count)
    """
    # Group definitions by star allele
    allele_groups: dict[str, list[dict]] = defaultdict(list)
    all_rsids: set[str] = set()
    for defn in allele_defs:
        allele_groups[defn["star_allele"]].append(defn)
        all_rsids.add(defn["rsid"])

    n_total = len(all_rsids)
    tested_rsids = all_rsids & set(user_lookup.keys())
    n_tested = len(tested_rsids)

    if calling_method == "binary":
        return _call_binary(allele_groups, user_lookup, n_tested, n_total)

    if calling_method == "count":
        return _call_count(allele_groups, user_lookup, n_tested, n_total)

    # For activity_score and simple: call each star allele
    detected: list[tuple[str, str, int]] = []  # (star_allele, function, copies)

    for star_allele, defs in allele_groups.items():
        if len(defs) == 1:
            # Single-SNP allele (most common case)
            d = defs[0]
            rsid = d["rsid"]
            if rsid not in user_lookup:
                continue
            a1, a2 = user_lookup[rsid]
            var = d["variant_allele"]
            copies = (a1 == var) + (a2 == var)
            if copies > 0:
                detected.append((star_allele, d["function"], copies))
        else:
            # Multi-SNP allele (e.g., TPMT *3A)
            # Check if ALL defining variants are present
            min_copies = float("inf")
            all_present = True
            for d in defs:
                rsid = d["rsid"]
                if rsid not in user_lookup:
                    all_present = False
                    break
                a1, a2 = user_lookup[rsid]
                var = d["variant_allele"]
                copies = (a1 == var) + (a2 == var)
                if copies == 0:
                    all_present = False
                    break
                min_copies = min(min_copies, copies)

            if all_present and min_copies > 0:
                detected.append((star_allele, defs[0]["function"], int(min_copies)))

    return detected, n_tested, n_total


def _call_binary(
    allele_groups: dict[str, list[dict]],
    user_lookup: dict[str, tuple[str, str]],
    n_tested: int,
    n_total: int,
) -> tuple[list[tuple[str, str, int]], int, int]:
    """Binary calling for HLA markers — presence/absence of any tag SNP."""
    total_copies = 0
    for star_allele, defs in allele_groups.items():
        for d in defs:
            rsid = d["rsid"]
            if rsid not in user_lookup:
                continue
            a1, a2 = user_lookup[rsid]
            var = d["variant_allele"]
            copies = (a1 == var) + (a2 == var)
            total_copies += copies

    if total_copies > 0:
        return [("positive", "risk", min(total_copies, 2))], n_tested, n_total
    return [("negative", "normal_function", 0)], n_tested, n_total


def _call_count(
    allele_groups: dict[str, list[dict]],
    user_lookup: dict[str, tuple[str, str]],
    n_tested: int,
    n_total: int,
) -> tuple[list[tuple[str, str, int]], int, int]:
    """Count-based calling for NAT2 — count slow-allele chromosomes.

    For each distinct slow star-allele (e.g. *5, *6, *14), we take
    the max variant copies across its defining SNPs (handles multi-SNP
    haplotypes like *5B without double-counting).  Then we sum across
    alleles to detect compound heterozygotes (*5/*6 → 1+1 = 2 → Slow).
    Result is capped at 2 (diploid).
    """
    slow_copies_per_allele: dict[str, int] = {}
    for star_allele, defs in allele_groups.items():
        max_copies = 0
        for d in defs:
            if d["function"] == "normal_function":
                continue  # Skip rapid allele tags
            rsid = d["rsid"]
            if rsid not in user_lookup:
                continue
            a1, a2 = user_lookup[rsid]
            var = d["variant_allele"]
            copies = (a1 == var) + (a2 == var)
            max_copies = max(max_copies, copies)
        if max_copies > 0:
            slow_copies_per_allele[star_allele] = max_copies

    total_slow = min(sum(slow_copies_per_allele.values()), 2)
    return [("count", "count", total_slow)], n_tested, n_total


def assign_diplotype(
    gene: str,
    calling_method: str,
    default_allele: str,
    detected: list[tuple[str, str, int]],
    allele_defs: list[dict],
) -> tuple[str, str, str, str, float | None]:
    """Assign diplotype and phenotype from detected alleles.

    Returns:
        (allele1, allele2, allele1_function, allele2_function, activity_score|None)
    """
    if calling_method == "binary":
        star, func, copies = detected[0]
        if star == "positive":
            return "positive", "positive" if copies >= 2 else "negative", "risk", "risk" if copies >= 2 else "normal_function", None
        return "negative", "negative", "normal_function", "normal_function", None

    if calling_method == "count":
        _, _, slow_count = detected[0]
        # Represent as allele pair for display
        if slow_count == 0:
            return "rapid", "rapid", "normal_function", "normal_function", None
        elif slow_count == 1:
            return "rapid", "slow", "normal_function", "no_function", None
        else:
            return "slow", "slow", "no_function", "no_function", None

    # Activity score and simple: greedy diplotype assignment
    # Build lookup for activity scores
    score_lookup: dict[str, float | None] = {}
    for d in allele_defs:
        if d["star_allele"] not in score_lookup:
            score_lookup[d["star_allele"]] = d.get("activity_score")

    # Filter to alleles with copies > 0, resolve multi-SNP conflicts
    # Sort by specificity: multi-SNP alleles first (more defining SNPs = more specific),
    # then by function severity (no_function > decreased > normal > increased)
    func_order = {"no_function": 0, "decreased_function": 1, "normal_function": 2,
                  "increased_function": 3, "uncertain_function": 4, "risk": 0}

    # Deduplicate: keep the most severe interpretation for each allele
    allele_map: dict[str, tuple[str, int]] = {}  # star_allele -> (function, copies)
    for star, func, copies in detected:
        if star not in allele_map or func_order.get(func, 5) < func_order.get(allele_map[star][0], 5):
            allele_map[star] = (func, copies)

    # Build the two-allele assignment
    assigned: list[tuple[str, str]] = []  # (star_allele, function)

    for star, (func, copies) in sorted(allele_map.items(), key=lambda x: func_order.get(x[1][0], 5)):
        for _ in range(min(copies, 2 - len(assigned))):
            assigned.append((star, func))
        if len(assigned) >= 2:
            break

    # Fill remaining with default
    default_func = "normal_function"
    while len(assigned) < 2:
        assigned.append((default_allele, default_func))

    a1_name, a1_func = assigned[0]
    a2_name, a2_func = assigned[1]

    # Sort alleles for canonical display (default first, then alphabetically)
    if a1_name != default_allele and a2_name == default_allele:
        a1_name, a2_name = a2_name, a1_name
        a1_func, a2_func = a2_func, a1_func
    elif a1_name != default_allele and a2_name != default_allele and a1_name > a2_name:
        a1_name, a2_name = a2_name, a1_name
        a1_func, a2_func = a2_func, a1_func

    # Activity score
    activity_score = None
    if calling_method == "activity_score":
        s1 = score_lookup.get(a1_name)
        s1 = s1 if s1 is not None else DEFAULT_ALLELE_SCORE
        s2 = score_lookup.get(a2_name)
        s2 = s2 if s2 is not None else DEFAULT_ALLELE_SCORE
        activity_score = s1 + s2

    return a1_name, a2_name, a1_func, a2_func, activity_score


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def match_pgx(
    user_df: pl.DataFrame,
    session: AsyncSession,
    genome_build: str = "GRCh37",
    is_vcf: bool = False,
) -> list[PgxResult]:
    """Match user variants against pharmacogenomic definitions.

    Args:
        user_df: DataFrame with columns [rsid, chrom, position, allele1, allele2]
        session: Async database session
        genome_build: Genome build of the input data ("GRCh37" or "GRCh38")
        is_vcf: True for variant-only VCF input. Enables homozygous-reference
            imputation: PGx positions absent from the VCF are assumed ref/ref,
            matching the standard convention that variant-only VCFs omit
            homozygous reference sites.

    Returns:
        List of PgxResult, one per gene, sorted by gene name.
    """
    t0 = time.perf_counter()

    # Build user genotype lookup
    user_rsids = user_df["rsid"].to_list()
    if not user_rsids:
        return []

    user_lookup: dict[str, tuple[str, str]] = {}
    for row in user_df.select("rsid", "allele1", "allele2").iter_rows():
        user_lookup[row[0]] = (row[1], row[2])

    # Supplement user_lookup with position-resolved genotypes
    # for PGx variants where the VCF has "." rsids
    pgx_positions = _load_pgx_positions(genome_build)
    needed = {rsid: pos for rsid, pos in pgx_positions.items() if rsid not in user_lookup}

    if needed:
        lookup_df = pl.DataFrame(
            {
                "pgx_rsid": list(needed.keys()),
                "chrom": [v[0] for v in needed.values()],
                "position": [v[1] for v in needed.values()],
            },
            schema={"pgx_rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64},
        )
        matched = user_df.join(lookup_df, on=["chrom", "position"], how="inner")

        supplemented = 0
        for row in matched.select("pgx_rsid", "allele1", "allele2").iter_rows():
            user_lookup[row[0]] = (row[1], row[2])
            supplemented += 1

        if supplemented > 0:
            log.info(f"PGX: supplemented {supplemented} genotypes via position lookup ({genome_build})")

    # For variant-only VCFs: positions absent from the file are homozygous
    # reference. Impute ref/ref for PGx positions not found in user_lookup.
    if is_vcf and pgx_positions:
        ref_alleles = _load_pgx_ref_alleles()
        imputed = 0
        for rsid in pgx_positions:
            if rsid not in user_lookup and rsid in ref_alleles:
                ref = ref_alleles[rsid]
                user_lookup[rsid] = (ref, ref)
                imputed += 1
        if imputed > 0:
            log.info(f"PGX: imputed {imputed} homozygous-ref genotypes from VCF absence")

    # Load gene definitions
    gene_result = await session.execute(text(
        "SELECT gene, calling_method, default_allele, description FROM pgx_gene_definitions ORDER BY gene"
    ))
    gene_rows = gene_result.fetchall()
    if not gene_rows:
        log.warning("No PGX gene definitions found in database")
        return []

    # Load all star allele definitions
    allele_result = await session.execute(text(
        "SELECT gene, star_allele, rsid, variant_allele, function, activity_score, clinical_significance "
        "FROM pgx_star_allele_definitions"
    ))
    allele_rows = allele_result.fetchall()

    # Group allele defs by gene
    allele_defs_by_gene: dict[str, list[dict]] = defaultdict(list)
    for row in allele_rows:
        allele_defs_by_gene[row.gene].append({
            "star_allele": row.star_allele,
            "rsid": row.rsid,
            "variant_allele": row.variant_allele,
            "function": row.function,
            "activity_score": row.activity_score,
            "clinical_significance": row.clinical_significance,
        })

    # Load diplotype phenotype mappings (for simple method)
    pheno_result = await session.execute(text(
        "SELECT gene, function_pair, phenotype, description FROM pgx_diplotype_phenotypes"
    ))
    pheno_rows = pheno_result.fetchall()
    pheno_lookup: dict[tuple[str, str], tuple[str, str | None]] = {}
    for row in pheno_rows:
        pheno_lookup[(row.gene, row.function_pair)] = (row.phenotype, row.description)

    # Load drug annotations
    drug_cache = _load_drug_cache()

    results: list[PgxResult] = []

    for gene_row in gene_rows:
        gene = gene_row.gene
        if gene in PGX_SKIP_GENES:
            continue
        calling_method = gene_row.calling_method
        default_allele = gene_row.default_allele


        defs = allele_defs_by_gene.get(gene, [])
        if not defs:
            continue

        # Call star alleles
        detected, n_tested, n_total = call_star_alleles_for_gene(
            gene, calling_method, default_allele, defs, user_lookup
        )

        # Collect per-variant genotypes for this gene's panel
        gene_rsids: set[str] = set()
        for d in defs:
            gene_rsids.add(d["rsid"])
        variant_genos: dict[str, str] = {}
        for rsid in sorted(gene_rsids):
            if rsid in user_lookup:
                a1, a2 = user_lookup[rsid]
                variant_genos[rsid] = f"{a1}/{a2}"

        # For VCF: all positions are assessed (absence = homozygous reference).
        # Missing positions have already been imputed as ref/ref, so every
        # defining variant is effectively tested.
        if is_vcf:
            n_tested = n_total

        if n_tested == 0:
            if not is_vcf:
                continue  # No variants on chip for this gene
            # VCF: absence means reference. Binary/count/simple genes with
            # few defining variants can still report a reference result.
            if calling_method not in ("binary", "count", "simple"):
                continue

        # Assign diplotype
        a1, a2, a1_func, a2_func, act_score = assign_diplotype(
            gene, calling_method, default_allele, detected, defs
        )

        # Determine phenotype
        if calling_method == "activity_score" and act_score is not None:
            phenotype = _score_to_phenotype(gene, act_score)
        elif calling_method == "binary":
            if a1 == "positive":
                phenotype = "Positive (Carrier)"
            else:
                phenotype = "Negative (Non-carrier)"
        elif calling_method == "count":
            _, _, slow_count = detected[0]
            if slow_count == 0:
                phenotype = "Rapid Acetylator"
            elif slow_count == 1:
                phenotype = "Intermediate Acetylator"
            else:
                phenotype = "Slow Acetylator"
        else:
            # Simple: look up function pair
            pair = "/".join(sorted([a1_func, a2_func]))
            pheno_entry = pheno_lookup.get((gene, pair))
            if pheno_entry:
                phenotype = pheno_entry[0]
            else:
                # Fallback
                phenotype = f"{gene} — {pair.replace('_', ' ')}"

        # Format diplotype string
        if calling_method == "binary":
            diplotype = f"{gene.replace('_', '*')}: {phenotype}"
        elif calling_method == "count":
            diplotype = f"NAT2: {phenotype}"
        else:
            diplotype = f"{a1}/{a2}"

        confidence = _compute_confidence(n_tested, n_total)

        # Drug annotations
        # Map gene names (HLA-B_5701 → HLA-B, etc.)
        drug_gene = gene.split("_")[0] if "_" in gene else gene
        drugs = drug_cache.get(drug_gene, [])
        drugs_str = ", ".join(drugs[:10]) if drugs else None  # limit to top 10

        clinical_note = _generate_clinical_note(gene, diplotype, phenotype, calling_method)

        results.append(PgxResult(
            gene=gene,
            diplotype=diplotype,
            allele1=a1,
            allele2=a2,
            allele1_function=a1_func,
            allele2_function=a2_func,
            phenotype=phenotype,
            activity_score=act_score,
            n_variants_tested=n_tested,
            n_variants_total=n_total,
            calling_method=calling_method,
            confidence=confidence,
            drugs_affected=drugs_str,
            clinical_note=clinical_note,
            variant_genotypes=variant_genos if variant_genos else None,
        ))

    elapsed = time.perf_counter() - t0
    log.info(f"PGX matching: {len(results)} genes from {len(user_rsids)} variants in {elapsed:.2f}s")

    return results
