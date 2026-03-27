"""PRS Scorer — computes polygenic risk scores from user genotype data.

Takes a user's parsed genotype DataFrame (from parser.py) and PRS weight data,
computes dosage of the effect allele, and produces a raw score + percentile.

Missing variants (not in user's file) are imputed as homozygous reference
(REF/REF). Reference distributions are computed from all variants in the PRS
using per-variant allele frequencies from 1000 Genomes Phase 3.
"""

from __future__ import annotations

import logging
from math import erf, sqrt
from dataclasses import dataclass

import polars as pl

log = logging.getLogger(__name__)

# Confidence interval and coverage constants
Z_95_CONFIDENCE = 1.96
HIGH_COVERAGE_THRESHOLD = 0.80
MEDIUM_COVERAGE_THRESHOLD = 0.50
# Assumed per-variant variance factor: 2 * p * (1-p) where p ≈ 0.25 (average MAF)
ASSUMED_MAF_VARIANCE_FACTOR = 0.375


# Threshold for score sanity check: flag scores beyond this many σ from reference mean
SCORE_SANITY_THRESHOLD_Z = 5.0


@dataclass
class PrsResultData:
    """Result of computing a single PRS for a user."""
    pgs_id: str
    raw_score: float
    percentile: float | None  # None when no valid reference distribution
    z_score: float | None  # None when no valid reference distribution
    ref_mean: float
    ref_std: float
    ancestry_group_used: str
    n_variants_matched: int
    n_variants_total: int
    percentile_lower: float | None = None
    percentile_upper: float | None = None
    coverage_quality: str | None = None  # high / medium / low
    n_variants_imputed: int = 0  # variants imputed as REF/REF


def _augment_user_df_with_positions(
    user_df: pl.DataFrame,
    weights_df: pl.DataFrame,
    genome_build: str,
) -> pl.DataFrame:
    """Assign weight rsids to user variants that don't match any weight rsid, by position.

    Handles two cases:
    1. VCF files where rsid='.' (e.g., many WGS VCFs without rsID annotation)
    2. VCFs where rsids differ from PGS Catalog rsids (e.g., different dbSNP version,
       rsid merges/splits). Without this, rsid-annotated WGS files (e.g., Nebula Genomics
       GRCh38) miss any PGS variant whose rsid doesn't exactly match the user's VCF
       annotation, even though the variant is present at the correct position.

    The weights_df must contain 'chrom' and position columns ('w_position' for GRCh37,
    'w_position_grch38' for GRCh38).
    """
    pos_col = "w_position_grch38" if genome_build == "GRCh38" else "w_position"
    if pos_col not in weights_df.columns or "chrom" not in weights_df.columns:
        return user_df

    # Find user variants not in the weight table (either "." or a different rsid)
    weight_rsid_set = set(weights_df["rsid"].to_list())
    needs_fix = ~user_df["rsid"].is_in(weight_rsid_set)
    if not needs_fix.any():
        return user_df

    # Build position → rsid from weights (one rsid per position, drop nulls)
    pos_lookup = (
        weights_df.select(
            pl.col("chrom").cast(pl.Utf8).alias("w_chrom"),
            pl.col(pos_col).cast(pl.Int64).alias("w_pos"),
            pl.col("rsid").alias("w_rsid"),
        )
        .drop_nulls(subset=["w_chrom", "w_pos"])
        .unique(subset=["w_chrom", "w_pos"])
    )

    if pos_lookup.height == 0:
        return user_df

    # Join user_df with position lookup
    augmented = user_df.join(
        pos_lookup,
        left_on=["chrom", "position"],
        right_on=["w_chrom", "w_pos"],
        how="left",
    )

    # Replace rsid where: (1) user rsid not in weight table, AND (2) position match found.
    # This preserves correct rsid matches and only fixes unmatched variants.
    weight_rsids_list = list(weight_rsid_set)
    augmented = augmented.with_columns(
        pl.when(
            ~pl.col("rsid").is_in(weight_rsids_list) & pl.col("w_rsid").is_not_null()
        )
        .then(pl.col("w_rsid"))
        .otherwise(pl.col("rsid"))
        .alias("rsid")
    ).drop("w_rsid")

    return augmented


def compute_dosage(
    user_df: pl.DataFrame,
    weights_df: pl.DataFrame,
) -> pl.DataFrame:
    """Join user variants with PRS weights and compute effect allele dosage.

    Args:
        user_df: DataFrame with columns [rsid, chrom, position, allele1, allele2]
        weights_df: DataFrame with columns [rsid, effect_allele, weight, ...]

    Returns:
        DataFrame with columns [rsid, effect_allele, weight, dosage, contribution]
        where dosage is 0, 1, or 2 copies of the effect allele
        and contribution = dosage * weight.
    """
    # Join on rsid
    joined = weights_df.join(user_df, on="rsid", how="inner")

    # Count copies of effect allele: 0, 1, or 2
    dosage = (
        (joined["allele1"] == joined["effect_allele"]).cast(pl.Int32)
        + (joined["allele2"] == joined["effect_allele"]).cast(pl.Int32)
    )

    result = joined.with_columns([
        dosage.alias("dosage"),
        (dosage.cast(pl.Float64) * joined["weight"]).alias("contribution"),
    ])

    return result


def compute_raw_score(
    user_df: pl.DataFrame,
    weights_df: pl.DataFrame,
) -> tuple[float, int, int]:
    """Compute the raw PRS as sum(dosage * weight).

    Returns:
        (raw_score, n_variants_matched, n_variants_total)
    """
    n_total = len(weights_df)
    scored = compute_dosage(user_df, weights_df)
    n_matched = len(scored)

    if n_matched == 0:
        return 0.0, 0, n_total

    raw_score = scored["contribution"].sum()
    return float(raw_score), n_matched, n_total


def score_to_percentile(
    raw_score: float,
    mean: float,
    std: float,
) -> float:
    """Convert a raw PRS to a percentile using z-score and normal CDF.

    Uses the error function for a closed-form normal CDF.
    Returns percentile in range [0, 100].
    """
    if std <= 0:
        return 50.0

    z = (raw_score - mean) / std
    # Normal CDF: Φ(z) = 0.5 * (1 + erf(z / sqrt(2)))
    percentile = 0.5 * (1.0 + erf(z / sqrt(2.0))) * 100.0
    return max(0.0, min(100.0, percentile))


def empirical_percentile(
    raw_score: float,
    sorted_scores: list[float],
) -> float:
    """Compute empirical percentile from a sorted reference score array.

    Returns the fraction of reference scores ≤ raw_score, as a percentage [0, 100].
    Uses bisect for O(log n) lookup.
    """
    from bisect import bisect_right

    n = len(sorted_scores)
    if n == 0:
        return 50.0

    rank = bisect_right(sorted_scores, raw_score)
    return max(0.0, min(100.0, rank / n * 100.0))


def compute_matched_ref_dist(
    user_df: pl.DataFrame,
    weights_df: pl.DataFrame,
    af_column: str,
) -> tuple[float, float, int]:
    """Compute reference distribution from the matched variants' allele frequencies.

    Uses the analytical formula under Hardy-Weinberg equilibrium:
      E[S] = Σ 2 * p_i * w_i   (for matched variants only)
      Var[S] = Σ 2 * p_i * (1-p_i) * w_i²
      std[S] = sqrt(Var[S])

    Args:
        user_df: User genotype DataFrame
        weights_df: Weights DataFrame with allele frequency columns
        af_column: Name of the allele frequency column (e.g., "eur_af")

    Returns:
        (mean, std, n_variants_with_af) for the matched subset
    """
    if af_column not in weights_df.columns:
        return 0.0, 1.0, 0

    # Join to get only matched variants
    joined = weights_df.join(user_df.select("rsid"), on="rsid", how="inner")

    # Filter to variants with AF data
    with_af = joined.filter(pl.col(af_column).is_not_null())

    if len(with_af) == 0:
        return 0.0, 1.0, 0

    p = with_af[af_column].clip(0.0, 1.0)
    w = with_af["weight"]

    # E[S] = Σ 2 * p_i * w_i
    mean = float((2.0 * p * w).sum())

    # Var[S] = Σ 2 * p_i * (1-p_i) * w_i²
    variance = float((2.0 * p * (1.0 - p) * w * w).sum())
    std = sqrt(variance) if variance > 0 else 0.0

    return mean, std, len(with_af)


# Map ancestry group codes to allele frequency column names
ANCESTRY_AF_COLUMNS = {
    "EUR": "eur_af",
    "AFR": "afr_af",
    "EAS": "eas_af",
    "SAS": "sas_af",
    "AMR": "amr_af",
}


def _estimate_confidence_interval(
    raw_score: float,
    ref_mean: float,
    ref_std: float,
    n_matched: int,
    n_total: int,
    weights_df: pl.DataFrame,
    af_col: str | None,
) -> tuple[float | None, float | None, str]:
    """Estimate percentile confidence interval from missing-variant uncertainty.

    Approach: compute the average per-variant variance contribution from matched
    variants (using AF data), then extrapolate the missing variance as
    n_missing * avg_var_per_variant. The 95% CI on the score is
    [score - 1.96*sqrt(var_missing), score + 1.96*sqrt(var_missing)],
    converted to percentile space.

    Returns:
        (percentile_lower, percentile_upper, coverage_quality)
    """
    n_missing = max(0, n_total - n_matched)

    # Coverage quality classification
    if n_total == 0:
        return None, None, "low"
    coverage = n_matched / n_total
    if coverage >= HIGH_COVERAGE_THRESHOLD:
        quality = "high"
    elif coverage >= MEDIUM_COVERAGE_THRESHOLD:
        quality = "medium"
    else:
        quality = "low"

    if n_missing == 0 or ref_std <= 0:
        # Perfect coverage — no uncertainty from missing variants
        return None, None, quality

    # Estimate average per-variant variance from matched variants
    if af_col and af_col in weights_df.columns:
        with_af = weights_df.filter(pl.col(af_col).is_not_null())
        if len(with_af) > 0:
            p = with_af[af_col].clip(0.0, 1.0)
            w = with_af["weight"]
            per_variant_vars = 2.0 * p * (1.0 - p) * w * w
            avg_var = float(per_variant_vars.mean())
        else:
            avg_var = _fallback_avg_var(weights_df)
    else:
        avg_var = _fallback_avg_var(weights_df)

    if avg_var <= 0:
        return None, None, quality

    var_missing = n_missing * avg_var
    std_missing = sqrt(var_missing)

    # 95% CI on the raw score
    score_lower = raw_score - Z_95_CONFIDENCE * std_missing
    score_upper = raw_score + Z_95_CONFIDENCE * std_missing

    pct_lower = score_to_percentile(score_lower, ref_mean, ref_std)
    pct_upper = score_to_percentile(score_upper, ref_mean, ref_std)

    return round(pct_lower, 1), round(pct_upper, 1), quality


def _fallback_avg_var(weights_df: pl.DataFrame) -> float:
    """Estimate avg per-variant variance when no AF data available.

    Assumes average MAF ≈ 0.25 (reasonable for common variants on chips).
    Var_i ≈ 2 * 0.25 * 0.75 * w_i² = 0.375 * w_i²
    """
    w2_mean = float((weights_df["weight"] * weights_df["weight"]).mean())
    return ASSUMED_MAF_VARIANCE_FACTOR * w2_mean


def compute_mixture_ref_dist(
    user_df: pl.DataFrame,
    weights_df: pl.DataFrame,
    ancestry_weights: dict[str, float],
) -> tuple[float, float]:
    """Compute a mixture reference distribution from ancestry proportions.

    For an admixed individual with ancestry weights w_k, the expected PRS
    distribution is a Gaussian mixture:

        mixture_mean = Σ w_k * μ_k
        mixture_var  = Σ w_k * (σ_k² + μ_k²) - mixture_mean²

    where μ_k and σ_k are the per-population reference mean and std computed
    from matched-variant allele frequencies under HWE.

    Args:
        user_df: User genotype DataFrame (for matched-variant filtering).
        weights_df: Weights DataFrame with per-population AF columns.
        ancestry_weights: Population proportions, e.g. {"EUR": 0.7, "AFR": 0.3, ...}.

    Returns:
        (mixture_mean, mixture_std) — the blended reference distribution parameters.
    """
    pop_stats: dict[str, tuple[float, float]] = {}  # {pop: (mean, std)}

    for pop, weight in ancestry_weights.items():
        if weight < 0.01:
            continue
        af_col = ANCESTRY_AF_COLUMNS.get(pop)
        if not af_col or af_col not in weights_df.columns:
            continue
        mean, std, n_af = compute_matched_ref_dist(user_df, weights_df, af_col)
        if n_af > 0 and std > 0:
            pop_stats[pop] = (mean, std)

    if not pop_stats:
        return 0.0, 0.0

    # Renormalize weights to only populations with valid stats
    active_weights = {p: ancestry_weights[p] for p in pop_stats}
    w_total = sum(active_weights.values())
    if w_total <= 0:
        return 0.0, 0.0
    normed = {p: w / w_total for p, w in active_weights.items()}

    # Mixture mean: Σ w_k * μ_k
    mix_mean = sum(normed[p] * pop_stats[p][0] for p in normed)

    # Mixture variance: Σ w_k * (σ_k² + μ_k²) - mixture_mean²
    mix_second_moment = sum(
        normed[p] * (pop_stats[p][1] ** 2 + pop_stats[p][0] ** 2) for p in normed
    )
    mix_var = mix_second_moment - mix_mean ** 2
    mix_std = sqrt(max(0.0, mix_var))

    return mix_mean, mix_std


def _impute_missing_as_ref(
    raw_score: float,
    user_df: pl.DataFrame,
    weights_df: pl.DataFrame,
) -> tuple[float, int]:
    """Impute missing variants as REF/REF and return the adjusted score and imputed count.

    Missing variants (not in user's file) are assumed to be homozygous reference:
      - effect_is_alt = True  → dosage = 0 → contribution = 0
      - effect_is_alt = False → dosage = 2 → contribution = 2 * weight

    The returned score includes both the matched raw_score and imputed missing
    variant contributions.

    Args:
        raw_score: Score from matched (present in VCF) variants
        user_df: User genotype DataFrame (for identifying matched rsids)
        weights_df: All weights including effect_is_alt column

    Returns:
        (Imputed full PRS score, number of variants imputed as REF/REF)
    """
    if "effect_is_alt" not in weights_df.columns:
        return raw_score, 0

    # Find unmatched variants (in weights but NOT in user's VCF)
    user_rsids = user_df.select("rsid")
    unmatched = weights_df.join(user_rsids, on="rsid", how="anti")

    # Warn if many unmatched variants have NULL effect_is_alt — these cannot
    # be imputed and will silently contribute 0 instead of their true value.
    if len(unmatched) > 0:
        n_null = int(unmatched["effect_is_alt"].null_count())
        if n_null > 0:
            log.warning(
                "VCF imputation: %d/%d unmatched variants have NULL effect_is_alt "
                "and cannot be imputed. Run load_1kg_frequencies.py to fix.",
                n_null, len(unmatched),
            )

    # For unmatched variants where effect_is_alt = False (effect allele = REF),
    # the genotype is REF/REF = 2 copies of effect allele → dosage = 2
    # For unmatched variants where effect_is_alt = True, they are implicitly matched as dosage=0
    # Thus, *all* unmatched variants represent implicitly validated reference genotypes
    # which means all unmatched variants are effectively "covered"
    # But for scoring, only the REF-effect ones add to the actual score value
    ref_effect = unmatched.filter(pl.col("effect_is_alt") == False)  # noqa: E712

    # Imputed variants: number of variants found in weights_df but not in user_df
    # In a full-genome VCF, all of these are implicitly matched as REF/REF.
    n_imputed = len(unmatched)

    if len(ref_effect) == 0:
        return raw_score, n_imputed

    # Add imputed contribution: sum of 2 * weight for REF-effect missing variants
    imputed_contribution = float((2.0 * ref_effect["weight"]).sum())
    return raw_score + imputed_contribution, n_imputed


def compute_prs(
    user_df: pl.DataFrame,
    pgs_id: str,
    weights_df: pl.DataFrame,
    ref_mean: float,
    ref_std: float,
    ancestry_group: str,
    ancestry_weights: dict[str, float] | None = None,
    is_vcf: bool = False,
    genome_build: str = "GRCh37",
    ref_sorted_scores: list[float] | None = None,
) -> PrsResultData:
    """Compute a single PRS for a user.

    Missing variants are imputed as homozygous reference (REF/REF) when the
    effect_is_alt column is available. The reference distribution is computed
    from ALL variants in the PRS (not just matched ones).

    If ancestry_weights is provided (from auto-detected ancestry), computes a
    mixture reference distribution blending all population-specific references
    by the user's ancestry proportions. Otherwise uses a single population.

    If ref_sorted_scores is provided (from empirical reference panel scoring),
    the percentile is computed empirically instead of using the normal CDF.

    Args:
        user_df: Parsed genotype DataFrame
        pgs_id: PGS Catalog ID
        weights_df: DataFrame with [rsid, effect_allele, weight] + optional AF/flag columns
        ref_mean: Reference population mean score (global, from DB)
        ref_std: Reference population standard deviation (global, from DB)
        ancestry_group: Which ancestry reference to use (e.g., "EUR")
        ancestry_weights: Optional population proportions for mixture normalization
        is_vcf: Deprecated, kept for backward compatibility (ignored)
        genome_build: Genome build for position-based matching ("GRCh37" or "GRCh38")
        ref_sorted_scores: Optional sorted array of reference panel scores for empirical percentile

    Returns:
        PrsResultData with score, percentile, and match stats.
    """
    # For VCFs with "." rsids, supplement user genotypes by position matching
    if genome_build and "chrom" in weights_df.columns:
        user_df = _augment_user_df_with_positions(user_df, weights_df, genome_build)

    raw_score, n_matched, n_total = compute_raw_score(user_df, weights_df)

    af_col = ANCESTRY_AF_COLUMNS.get(ancestry_group)

    # Track whether we obtained a valid reference distribution.
    has_valid_ref = ref_std > 0  # True if caller provided a real ref_dist from DB

    # ----- Impute missing variants as REF/REF -----
    n_imputed = 0
    if "effect_is_alt" in weights_df.columns:
        raw_score, n_imputed = _impute_missing_as_ref(raw_score, user_df, weights_df)
    elif n_matched < n_total:
        log.warning(
            "Imputation skipped for %s: effect_is_alt column missing. "
            "Score may be less accurate — run load_1kg_frequencies.py to populate flags.",
            pgs_id,
        )

    # ----- Compute reference distribution from ALL variants -----
    matched_ref_computed = False

    # Save the DB std (empirically computed from reference panel, captures LD).
    db_std = ref_std

    # Use all variants for reference distribution (imputation covers missing ones)
    all_rsids_df = weights_df.select("rsid")

    if ancestry_weights is not None:
        mix_mean, mix_std = compute_mixture_ref_dist(
            all_rsids_df, weights_df, ancestry_weights
        )
        if mix_std > 0:
            ref_mean = mix_mean
            ref_std = mix_std
            matched_ref_computed = True
    elif af_col and af_col in weights_df.columns:
        computed_mean, computed_std, n_with_af = compute_matched_ref_dist(
            all_rsids_df, weights_df, af_col
        )
        if n_with_af > 0 and computed_std > 0:
            ref_mean = computed_mean
            ref_std = computed_std
            matched_ref_computed = True

    # Prefer the DB std if it's larger (empirical std captures LD effects
    # that the analytical HWE formula underestimates).
    if db_std > ref_std:
        log.info(
            "Using empirical std=%.6f from DB (analytical=%.6f, ratio=%.2fx) for %s",
            db_std, ref_std, db_std / ref_std if ref_std > 0 else 0, pgs_id,
        )
        ref_std = db_std

    has_valid_ref = matched_ref_computed or has_valid_ref

    if has_valid_ref and ref_std > 0:
        z = (raw_score - ref_mean) / ref_std

        # Prefer empirical percentile when sorted reference scores are available
        if ref_sorted_scores and len(ref_sorted_scores) >= 50:
            percentile = empirical_percentile(raw_score, ref_sorted_scores)
        else:
            percentile = score_to_percentile(raw_score, ref_mean, ref_std)

        # Score sanity check: flag physically implausible scores
        if abs(z) > SCORE_SANITY_THRESHOLD_Z:
            log.warning(
                "SANITY CHECK: %s score %.6f is %.1fσ from reference mean %.6f "
                "(std=%.6f). This may indicate a scoring bug or stale scoring file.",
                pgs_id, raw_score, z, ref_mean, ref_std,
            )
    else:
        percentile = None
        z = None

    # Coverage quality based on variants actually found in user's file
    n_effective = n_matched + n_imputed
    pct_lower: float | None = None
    pct_upper: float | None = None
    quality = "low"
    if has_valid_ref:
        pct_lower, pct_upper, quality = _estimate_confidence_interval(
            raw_score, ref_mean, ref_std, n_effective, n_total, weights_df, af_col
        )
    else:
        if n_total > 0:
            coverage = n_effective / n_total
            quality = "high" if coverage >= 0.8 else "medium" if coverage >= 0.5 else "low"

    return PrsResultData(
        pgs_id=pgs_id,
        raw_score=raw_score,
        percentile=percentile,
        z_score=z,
        ref_mean=ref_mean,
        ref_std=ref_std,
        ancestry_group_used=ancestry_group,
        n_variants_matched=n_matched,
        n_variants_total=n_total,
        percentile_lower=pct_lower,
        percentile_upper=pct_upper,
        coverage_quality=quality,
        n_variants_imputed=n_imputed,
    )
