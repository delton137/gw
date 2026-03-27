"""Tests for the PRS scorer — hand-computed dosage × weight examples."""

import polars as pl
import pytest

from app.services.scorer import (
    PrsResultData,
    _augment_user_df_with_positions,
    _impute_missing_as_ref,
    compute_dosage,
    compute_mixture_ref_dist,
    compute_prs,
    compute_raw_score,
    score_to_percentile,
    _estimate_confidence_interval,
    _fallback_avg_var,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_user_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={
            "rsid": pl.Utf8,
            "chrom": pl.Utf8,
            "position": pl.Int64,
            "allele1": pl.Utf8,
            "allele2": pl.Utf8,
        },
    )


def make_weights_df(rows: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        rows,
        schema={"rsid": pl.Utf8, "effect_allele": pl.Utf8, "weight": pl.Float64},
    )


USER_VARIANTS = make_user_df([
    {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
    {"rsid": "rs2", "chrom": "1", "position": 200, "allele1": "C", "allele2": "C"},
    {"rsid": "rs3", "chrom": "2", "position": 300, "allele1": "T", "allele2": "A"},
    {"rsid": "rs4", "chrom": "3", "position": 400, "allele1": "G", "allele2": "G"},
])

WEIGHTS = make_weights_df([
    {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},   # user has 1 copy → 0.5
    {"rsid": "rs2", "effect_allele": "C", "weight": 0.3},   # user has 2 copies → 0.6
    {"rsid": "rs3", "effect_allele": "G", "weight": 0.2},   # user has 0 copies → 0.0
    {"rsid": "rs5", "effect_allele": "T", "weight": 1.0},   # not in user data → no match
])


# ---------------------------------------------------------------------------
# Dosage computation
# ---------------------------------------------------------------------------

class TestComputeDosage:
    def test_correct_dosages(self):
        result = compute_dosage(USER_VARIANTS, WEIGHTS)
        # Should have 3 matched variants (rs1, rs2, rs3 — rs5 not in user data)
        assert len(result) == 3

        rows = result.sort("rsid").to_dicts()

        # rs1: allele1=A, allele2=G, effect=A → dosage=1
        assert rows[0]["rsid"] == "rs1"
        assert rows[0]["dosage"] == 1

        # rs2: allele1=C, allele2=C, effect=C → dosage=2
        assert rows[1]["rsid"] == "rs2"
        assert rows[1]["dosage"] == 2

        # rs3: allele1=T, allele2=A, effect=G → dosage=0
        assert rows[2]["rsid"] == "rs3"
        assert rows[2]["dosage"] == 0

    def test_contributions(self):
        result = compute_dosage(USER_VARIANTS, WEIGHTS).sort("rsid")
        rows = result.to_dicts()

        assert rows[0]["contribution"] == pytest.approx(0.5)   # 1 × 0.5
        assert rows[1]["contribution"] == pytest.approx(0.6)   # 2 × 0.3
        assert rows[2]["contribution"] == pytest.approx(0.0)   # 0 × 0.2

    def test_homozygous_effect(self):
        """User homozygous for effect allele → dosage 2."""
        user = make_user_df([
            {"rsid": "rs10", "chrom": "1", "position": 100, "allele1": "T", "allele2": "T"},
        ])
        weights = make_weights_df([
            {"rsid": "rs10", "effect_allele": "T", "weight": 1.5},
        ])
        result = compute_dosage(user, weights)
        assert result["dosage"][0] == 2
        assert result["contribution"][0] == pytest.approx(3.0)

    def test_no_overlap(self):
        """No matching rsids → empty result."""
        user = make_user_df([
            {"rsid": "rs99", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
        ])
        result = compute_dosage(user, weights)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Raw score computation
# ---------------------------------------------------------------------------

class TestComputeRawScore:
    def test_hand_computed_score(self):
        """Raw score = 1*0.5 + 2*0.3 + 0*0.2 = 1.1"""
        score, n_matched, n_total = compute_raw_score(USER_VARIANTS, WEIGHTS)
        assert score == pytest.approx(1.1)
        assert n_matched == 3
        assert n_total == 4  # 4 weights, 3 matched

    def test_no_matches(self):
        user = make_user_df([
            {"rsid": "rs99", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        score, n_matched, n_total = compute_raw_score(user, WEIGHTS)
        assert score == 0.0
        assert n_matched == 0
        assert n_total == 4

    def test_negative_weights(self):
        """Negative weights should work correctly (protective variants)."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "A"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": -0.3},
        ])
        score, _, _ = compute_raw_score(user, weights)
        assert score == pytest.approx(-0.6)  # dosage 2 × -0.3

    def test_single_variant(self):
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "C", "allele2": "T"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "T", "weight": 2.0},
        ])
        score, n_matched, n_total = compute_raw_score(user, weights)
        assert score == pytest.approx(2.0)  # dosage 1 × 2.0
        assert n_matched == 1
        assert n_total == 1


# ---------------------------------------------------------------------------
# Percentile computation
# ---------------------------------------------------------------------------

class TestScoreToPercentile:
    def test_mean_score_is_50th(self):
        assert score_to_percentile(0.0, 0.0, 1.0) == pytest.approx(50.0)

    def test_one_sd_above(self):
        """1 SD above mean ≈ 84.13th percentile."""
        pct = score_to_percentile(1.0, 0.0, 1.0)
        assert pct == pytest.approx(84.13, abs=0.1)

    def test_one_sd_below(self):
        """1 SD below mean ≈ 15.87th percentile."""
        pct = score_to_percentile(-1.0, 0.0, 1.0)
        assert pct == pytest.approx(15.87, abs=0.1)

    def test_two_sd_above(self):
        """2 SD above ≈ 97.72th percentile."""
        pct = score_to_percentile(2.0, 0.0, 1.0)
        assert pct == pytest.approx(97.72, abs=0.1)

    def test_extreme_high(self):
        """Very extreme score should cap at ~100."""
        pct = score_to_percentile(10.0, 0.0, 1.0)
        assert pct >= 99.99

    def test_extreme_low(self):
        pct = score_to_percentile(-10.0, 0.0, 1.0)
        assert pct <= 0.01

    def test_zero_std_returns_50(self):
        assert score_to_percentile(5.0, 0.0, 0.0) == 50.0

    def test_nonzero_mean(self):
        """Score equal to mean should give 50th percentile regardless of mean value."""
        assert score_to_percentile(3.5, 3.5, 1.0) == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# Full PRS computation
# ---------------------------------------------------------------------------

class TestComputePrs:
    def test_full_computation(self):
        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS000001",
            weights_df=WEIGHTS,
            ref_mean=1.0,
            ref_std=0.5,
            ancestry_group="EUR",
        )
        assert isinstance(result, PrsResultData)
        assert result.pgs_id == "PGS000001"
        assert result.raw_score == pytest.approx(1.1)
        assert result.n_variants_matched == 3
        assert result.n_variants_total == 4
        assert result.ancestry_group_used == "EUR"
        # Score 1.1, mean 1.0, std 0.5 → z=0.2 → ~57.9th percentile
        assert result.percentile == pytest.approx(57.93, abs=0.5)
        assert result.z_score == pytest.approx(0.2)
        assert result.ref_mean == pytest.approx(1.0)
        assert result.ref_std == pytest.approx(0.5)

    def test_at_mean(self):
        """If raw score equals the reference mean, percentile should be ~50."""
        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS_TEST",
            weights_df=WEIGHTS,
            ref_mean=1.1,  # exactly the expected raw score
            ref_std=1.0,
            ancestry_group="EUR",
        )
        assert result.percentile == pytest.approx(50.0, abs=0.1)
        assert result.z_score == pytest.approx(0.0, abs=0.01)

    def test_z_score_zero_std(self):
        """Zero std means no valid ref_dist — should return None for z/percentile."""
        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS_TEST",
            weights_df=WEIGHTS,
            ref_mean=1.0,
            ref_std=0.0,
            ancestry_group="EUR",
        )
        assert result.z_score is None
        assert result.percentile is None

    def test_confidence_interval_fields(self):
        """PRS with missing variants should have CI fields populated."""
        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS000001",
            weights_df=WEIGHTS,
            ref_mean=1.0,
            ref_std=0.5,
            ancestry_group="EUR",
        )
        # 3 matched out of 4 total → 75% coverage → medium quality
        assert result.coverage_quality == "medium"
        # Should have CI bounds since there's 1 missing variant
        assert result.percentile_lower is not None
        assert result.percentile_upper is not None
        assert result.percentile_lower < result.percentile
        assert result.percentile_upper > result.percentile

    def test_perfect_coverage_no_ci(self):
        """When all variants match, no CI uncertainty from missing variants."""
        # Weights with only variants that exist in user data
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs2", "effect_allele": "C", "weight": 0.3},
        ])
        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS_TEST",
            weights_df=weights,
            ref_mean=0.5,
            ref_std=0.3,
            ancestry_group="EUR",
        )
        assert result.coverage_quality == "high"
        assert result.percentile_lower is None
        assert result.percentile_upper is None


# ---------------------------------------------------------------------------
# Confidence interval estimation
# ---------------------------------------------------------------------------

class TestConfidenceInterval:
    def test_perfect_coverage(self):
        """No missing variants → no CI bounds, just quality."""
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
        ])
        lower, upper, quality = _estimate_confidence_interval(
            raw_score=0.5, ref_mean=0.0, ref_std=1.0,
            n_matched=1, n_total=1, weights_df=weights, af_col=None,
        )
        assert lower is None
        assert upper is None
        assert quality == "high"

    def test_low_coverage(self):
        """< 50% coverage → low quality."""
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs2", "effect_allele": "C", "weight": 0.3},
            {"rsid": "rs3", "effect_allele": "G", "weight": 0.2},
        ])
        lower, upper, quality = _estimate_confidence_interval(
            raw_score=0.5, ref_mean=0.0, ref_std=1.0,
            n_matched=1, n_total=3, weights_df=weights, af_col=None,
        )
        assert quality == "low"
        assert lower is not None
        assert upper is not None
        assert lower < upper

    def test_ci_widens_with_more_missing(self):
        """More missing variants → wider CI."""
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
        ])
        _, _, q1 = _estimate_confidence_interval(
            raw_score=0.5, ref_mean=0.0, ref_std=1.0,
            n_matched=9, n_total=10, weights_df=weights, af_col=None,
        )
        l1, u1, _ = _estimate_confidence_interval(
            raw_score=0.5, ref_mean=0.0, ref_std=1.0,
            n_matched=9, n_total=10, weights_df=weights, af_col=None,
        )
        l2, u2, _ = _estimate_confidence_interval(
            raw_score=0.5, ref_mean=0.0, ref_std=1.0,
            n_matched=5, n_total=10, weights_df=weights, af_col=None,
        )
        # More missing → wider CI
        assert (u2 - l2) > (u1 - l1)

    def test_fallback_avg_var(self):
        """Fallback uses MAF≈0.25 assumption."""
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 1.0},
            {"rsid": "rs2", "effect_allele": "C", "weight": 2.0},
        ])
        avg = _fallback_avg_var(weights)
        # 0.375 * mean(1² + 2²) = 0.375 * 2.5 = 0.9375
        assert avg == pytest.approx(0.375 * 2.5)


# ---------------------------------------------------------------------------
# Mixture ancestry-weighted normalization
# ---------------------------------------------------------------------------

def make_weights_with_af(rows: list[dict]) -> pl.DataFrame:
    """Create weights DataFrame with per-population AF columns."""
    schema = {
        "rsid": pl.Utf8, "effect_allele": pl.Utf8, "weight": pl.Float64,
        "eur_af": pl.Float64, "afr_af": pl.Float64,
        "eas_af": pl.Float64, "sas_af": pl.Float64, "amr_af": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema)


# Shared fixture: weights with divergent population AFs
MIXTURE_WEIGHTS = make_weights_with_af([
    {"rsid": "rs1", "effect_allele": "A", "weight": 0.5,
     "eur_af": 0.3, "afr_af": 0.7, "eas_af": 0.1, "sas_af": 0.2, "amr_af": 0.4},
    {"rsid": "rs2", "effect_allele": "C", "weight": 0.3,
     "eur_af": 0.5, "afr_af": 0.2, "eas_af": 0.8, "sas_af": 0.6, "amr_af": 0.3},
    {"rsid": "rs3", "effect_allele": "G", "weight": 0.2,
     "eur_af": 0.4, "afr_af": 0.6, "eas_af": 0.3, "sas_af": 0.5, "amr_af": 0.5},
])


class TestMixtureRefDist:
    def test_pure_population_matches_single(self):
        """100% EUR weights should match single-pop EUR ref dist."""
        from app.services.scorer import compute_matched_ref_dist

        mix_mean, mix_std = compute_mixture_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS,
            {"EUR": 1.0, "AFR": 0.0, "EAS": 0.0, "SAS": 0.0, "AMR": 0.0},
        )
        single_mean, single_std, _ = compute_matched_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS, "eur_af",
        )
        assert mix_mean == pytest.approx(single_mean, abs=0.001)
        assert mix_std == pytest.approx(single_std, abs=0.001)

    def test_mixture_mean_is_weighted_average(self):
        """50/50 EUR/AFR mixture mean should be average of EUR and AFR means."""
        from app.services.scorer import compute_matched_ref_dist

        eur_mean, _, _ = compute_matched_ref_dist(USER_VARIANTS, MIXTURE_WEIGHTS, "eur_af")
        afr_mean, _, _ = compute_matched_ref_dist(USER_VARIANTS, MIXTURE_WEIGHTS, "afr_af")

        mix_mean, _ = compute_mixture_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS,
            {"EUR": 0.5, "AFR": 0.5, "EAS": 0.0, "SAS": 0.0, "AMR": 0.0},
        )
        expected_mean = 0.5 * eur_mean + 0.5 * afr_mean
        assert mix_mean == pytest.approx(expected_mean, abs=0.001)

    def test_mixture_std_wider_than_components(self):
        """Mixture of divergent populations should have wider std than either alone."""
        from app.services.scorer import compute_matched_ref_dist

        _, eur_std, _ = compute_matched_ref_dist(USER_VARIANTS, MIXTURE_WEIGHTS, "eur_af")
        _, afr_std, _ = compute_matched_ref_dist(USER_VARIANTS, MIXTURE_WEIGHTS, "afr_af")

        _, mix_std = compute_mixture_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS,
            {"EUR": 0.5, "AFR": 0.5, "EAS": 0.0, "SAS": 0.0, "AMR": 0.0},
        )
        # Mixture variance >= weighted average of component variances
        # (due to between-population variance term)
        min_component_std = min(eur_std, afr_std)
        assert mix_std >= min_component_std * 0.99  # Allow tiny float tolerance

    def test_no_af_columns_returns_zero(self):
        """Weights without AF columns → mixture returns (0, 0)."""
        weights_no_af = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
        ])
        mean, std = compute_mixture_ref_dist(
            USER_VARIANTS, weights_no_af,
            {"EUR": 0.5, "AFR": 0.5},
        )
        assert mean == 0.0
        assert std == 0.0

    def test_skips_negligible_populations(self):
        """Populations with < 1% weight are skipped."""
        from app.services.scorer import compute_matched_ref_dist

        # 99% EUR, 1% AFR should be essentially the same as pure EUR
        mix_mean, mix_std = compute_mixture_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS,
            {"EUR": 0.995, "AFR": 0.005, "EAS": 0.0, "SAS": 0.0, "AMR": 0.0},
        )
        eur_mean, eur_std, _ = compute_matched_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS, "eur_af",
        )
        # AFR at 0.5% is below 1% threshold → only EUR used
        assert mix_mean == pytest.approx(eur_mean, abs=0.001)
        assert mix_std == pytest.approx(eur_std, abs=0.001)


class TestComputePrsMixture:
    def test_ancestry_weights_used(self):
        """compute_prs with ancestry_weights should use mixture normalization."""
        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS_MIX",
            weights_df=MIXTURE_WEIGHTS,
            ref_mean=0.0,
            ref_std=1.0,
            ancestry_group="EUR",
            ancestry_weights={"EUR": 0.6, "AFR": 0.4, "EAS": 0.0, "SAS": 0.0, "AMR": 0.0},
        )
        # Should have used mixture ref dist, not the fallback 0.0/1.0
        assert result.ref_mean != 0.0 or result.ref_std != 1.0

    def test_no_weights_uses_single_pop(self):
        """compute_prs without ancestry_weights should use single-pop ref_mean,
        but prefer the larger DB std over analytical std (captures LD effects)."""
        from app.services.scorer import compute_matched_ref_dist

        result = compute_prs(
            user_df=USER_VARIANTS,
            pgs_id="PGS_SINGLE",
            weights_df=MIXTURE_WEIGHTS,
            ref_mean=0.0,
            ref_std=1.0,
            ancestry_group="EUR",
            ancestry_weights=None,
        )
        eur_mean, eur_std, _ = compute_matched_ref_dist(
            USER_VARIANTS, MIXTURE_WEIGHTS, "eur_af",
        )
        assert result.ref_mean == pytest.approx(eur_mean, abs=0.001)
        # DB std (1.0) is larger than analytical std (~0.41), so DB std is used
        assert result.ref_std == pytest.approx(1.0, abs=0.001)

    def test_mixture_changes_percentile(self):
        """Mixture normalization should produce different percentile than single-pop."""
        result_single = compute_prs(
            user_df=USER_VARIANTS, pgs_id="PGS_TEST",
            weights_df=MIXTURE_WEIGHTS, ref_mean=0.0, ref_std=1.0,
            ancestry_group="EUR", ancestry_weights=None,
        )
        result_mixture = compute_prs(
            user_df=USER_VARIANTS, pgs_id="PGS_TEST",
            weights_df=MIXTURE_WEIGHTS, ref_mean=0.0, ref_std=1.0,
            ancestry_group="EUR",
            ancestry_weights={"EUR": 0.5, "AFR": 0.5, "EAS": 0.0, "SAS": 0.0, "AMR": 0.0},
        )
        # Same raw score, different ref dist → different percentile
        assert result_single.raw_score == result_mixture.raw_score
        assert result_single.percentile != pytest.approx(result_mixture.percentile, abs=0.1)


# ---------------------------------------------------------------------------
# VCF imputation
# ---------------------------------------------------------------------------

def make_weights_with_flags(rows: list[dict]) -> pl.DataFrame:
    """Create weights DataFrame with effect_is_alt flag."""
    schema = {
        "rsid": pl.Utf8, "effect_allele": pl.Utf8, "weight": pl.Float64,
        "effect_is_alt": pl.Boolean,
        "eur_af": pl.Float64, "afr_af": pl.Float64,
        "eas_af": pl.Float64, "sas_af": pl.Float64, "amr_af": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema)


class TestRefImputation:
    def test_impute_missing_ref_effect(self):
        """Missing variant with effect_is_alt=False → dosage=2, contribution=2*weight."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_flags([
            # rs1: user has it, effect=A=ALT → normal scoring
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5, "effect_is_alt": True,
             "eur_af": 0.3, "afr_af": 0.3, "eas_af": 0.3, "sas_af": 0.3, "amr_af": 0.3},
            # rs9: user does NOT have it, effect=REF → impute dosage=2
            {"rsid": "rs9", "effect_allele": "C", "weight": 0.4, "effect_is_alt": False,
             "eur_af": 0.7, "afr_af": 0.7, "eas_af": 0.7, "sas_af": 0.7, "amr_af": 0.7},
        ])
        raw_score = 0.5  # from rs1: dosage=1 × weight=0.5
        imputed_score, n_imputed = _impute_missing_as_ref(raw_score, user, weights)
        # Imputed = 0.5 + 2*0.4 = 1.3
        assert imputed_score == pytest.approx(1.3)
        assert n_imputed == 1

    def test_impute_missing_alt_effect(self):
        """Missing variant with effect_is_alt=True → dosage=0, no contribution."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_flags([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5, "effect_is_alt": True,
             "eur_af": 0.3, "afr_af": 0.3, "eas_af": 0.3, "sas_af": 0.3, "amr_af": 0.3},
            # rs9: user does NOT have it, effect=ALT → impute dosage=0
            {"rsid": "rs9", "effect_allele": "T", "weight": 0.4, "effect_is_alt": True,
             "eur_af": 0.3, "afr_af": 0.3, "eas_af": 0.3, "sas_af": 0.3, "amr_af": 0.3},
        ])
        raw_score = 0.5
        imputed_score, n_imputed = _impute_missing_as_ref(raw_score, user, weights)
        # No addition for ALT-effect missing variants (dosage=0)
        assert imputed_score == pytest.approx(0.5)
        assert n_imputed == 1

    def test_impute_no_flag_column(self):
        """Without effect_is_alt column, imputation returns raw_score unchanged."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs9", "effect_allele": "T", "weight": 0.4},
        ])
        imputed_score, n_imputed = _impute_missing_as_ref(0.5, user, weights)
        assert imputed_score == pytest.approx(0.5)
        assert n_imputed == 0

    def test_imputation_in_compute_prs(self):
        """compute_prs should impute missing variants and use global ref_dist."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_flags([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5, "effect_is_alt": True,
             "eur_af": 0.3, "afr_af": 0.3, "eas_af": 0.3, "sas_af": 0.3, "amr_af": 0.3},
            # Missing variant with REF as effect allele
            {"rsid": "rs9", "effect_allele": "C", "weight": 0.4, "effect_is_alt": False,
             "eur_af": 0.7, "afr_af": 0.7, "eas_af": 0.7, "sas_af": 0.7, "amr_af": 0.7},
        ])
        # Global ref_dist (from all variants)
        # E[S] = 2*0.3*0.5 + 2*0.7*0.4 = 0.3 + 0.56 = 0.86
        global_mean = 0.86
        # Var[S] = 2*0.3*0.7*0.25 + 2*0.7*0.3*0.16 = 0.105 + 0.0672 = 0.1722
        # std = sqrt(0.1722) = 0.4149698784
        global_std = 0.4149698784249286

        result = compute_prs(
            user_df=user, pgs_id="PGS_VCF", weights_df=weights,
            ref_mean=0.86, ref_std=0.3,  # Pass in incorrect ones to prove it overrides
            ancestry_group="EUR",
        )
        # Imputed raw score: 0.5 (rs1: dosage=1 × 0.5) + 0.8 (rs9: dosage=2 × 0.4) = 1.3
        assert result.raw_score == pytest.approx(1.3)
        # n_matched = 1 (only rs1 found in file), n_imputed = 1 (rs9)
        assert result.n_variants_matched == 1
        assert result.n_variants_imputed == 1
        # Should recompute global ref_dist from ALL variants
        assert result.ref_mean == pytest.approx(global_mean)
        assert result.ref_std == pytest.approx(global_std)
        # Percentile should be computable
        assert result.percentile is not None

    def test_is_vcf_flag_ignored(self):
        """is_vcf flag is deprecated — both modes produce identical results."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_flags([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5, "effect_is_alt": True,
             "eur_af": 0.3, "afr_af": 0.3, "eas_af": 0.3, "sas_af": 0.3, "amr_af": 0.3},
            {"rsid": "rs9", "effect_allele": "C", "weight": 0.4, "effect_is_alt": False,
             "eur_af": 0.7, "afr_af": 0.7, "eas_af": 0.7, "sas_af": 0.7, "amr_af": 0.7},
        ])
        result_vcf = compute_prs(
            user_df=user, pgs_id="PGS_TEST", weights_df=weights,
            ref_mean=0.86, ref_std=0.3,
            ancestry_group="EUR", is_vcf=True,
        )
        result_array = compute_prs(
            user_df=user, pgs_id="PGS_TEST", weights_df=weights,
            ref_mean=0.86, ref_std=0.3,
            ancestry_group="EUR", is_vcf=False,
        )
        assert result_vcf.raw_score == result_array.raw_score
        assert result_vcf.percentile == result_array.percentile

    def test_impute_null_flags_warns(self):
        """Unmatched variants with NULL effect_is_alt should log a warning."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        # Create weights where effect_is_alt is present but NULL for the missing variant
        weights = pl.DataFrame(
            {
                "rsid": ["rs1", "rs9"],
                "effect_allele": ["A", "T"],
                "weight": [0.5, 0.4],
                "effect_is_alt": [True, None],
                "eur_af": [0.3, 0.3],
                "afr_af": [0.3, 0.3],
                "eas_af": [0.3, 0.3],
                "sas_af": [0.3, 0.3],
                "amr_af": [0.3, 0.3],
            },
            schema={
                "rsid": pl.Utf8, "effect_allele": pl.Utf8, "weight": pl.Float64,
                "effect_is_alt": pl.Boolean,
                "eur_af": pl.Float64, "afr_af": pl.Float64, "eas_af": pl.Float64,
                "sas_af": pl.Float64, "amr_af": pl.Float64,
            },
        )
        # NULL effect_is_alt → variant is NOT imputed, score stays at raw_score
        imputed_score, n_imputed = _impute_missing_as_ref(0.5, user, weights)
        assert imputed_score == pytest.approx(0.5)  # no imputation for NULL flag
        assert n_imputed == 1  # variant is counted as unmatched

    def test_missing_flag_column_warns(self, caplog):
        """compute_prs without effect_is_alt column should warn when variants are missing."""
        import logging
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs9", "effect_allele": "T", "weight": 0.4},
        ])
        with caplog.at_level(logging.WARNING, logger="app.services.scorer"):
            result = compute_prs(
                user_df=user, pgs_id="PGS_TEST", weights_df=weights,
                ref_mean=0.5, ref_std=0.3,
                ancestry_group="EUR",
            )
        assert "Imputation skipped" in caplog.text
        assert "effect_is_alt column missing" in caplog.text


# ---------------------------------------------------------------------------
# Position-based PRS matching (VCF with "." rsids)
# ---------------------------------------------------------------------------

def make_weights_with_positions(rows: list[dict]) -> pl.DataFrame:
    """Create weights DataFrame with position columns for position-based matching."""
    schema = {
        "rsid": pl.Utf8, "chrom": pl.Utf8,
        "w_position": pl.Int64, "w_position_grch38": pl.Int64,
        "effect_allele": pl.Utf8, "weight": pl.Float64,
    }
    return pl.DataFrame(rows, schema=schema)


class TestAugmentUserDfWithPositions:
    def test_dot_rsids_get_replaced(self):
        """User variants with rsid='.' should get rsids from weights by position."""
        user = make_user_df([
            {"rsid": ".", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
            {"rsid": "rs2", "chrom": "1", "position": 200, "allele1": "C", "allele2": "C"},
            {"rsid": ".", "chrom": "2", "position": 300, "allele1": "T", "allele2": "A"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs3", "chrom": "2", "w_position": 300, "w_position_grch38": 350,
             "effect_allele": "T", "weight": 0.2},
        ])

        result = _augment_user_df_with_positions(user, weights, "GRCh37")
        rsids = result.sort("position")["rsid"].to_list()
        assert rsids == ["rs1", "rs2", "rs3"]

    def test_grch38_uses_correct_position_column(self):
        """GRCh38 build should match on w_position_grch38."""
        user = make_user_df([
            {"rsid": ".", "chrom": "1", "position": 150, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
        ])

        # GRCh38: should match on position 150 (w_position_grch38)
        result = _augment_user_df_with_positions(user, weights, "GRCh38")
        assert result["rsid"][0] == "rs1"

        # GRCh37: should NOT match (w_position=100, user position=150)
        result37 = _augment_user_df_with_positions(user, weights, "GRCh37")
        assert result37["rsid"][0] == "."

    def test_mismatched_rsid_replaced_by_position(self):
        """User rsids not in the weight table should be replaced by position match.

        This is the core fix for rsid-annotated WGS VCFs (e.g. Nebula GRCh38) where
        the user's dbSNP rsids differ from PGS Catalog rsids at the same position.
        """
        user = make_user_df([
            {"rsid": "rs99", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
        ])

        result = _augment_user_df_with_positions(user, weights, "GRCh37")
        # rs99 is not in the weight table; rs1 is at the same position → replace
        assert result["rsid"][0] == "rs1"

    def test_correct_rsid_not_replaced(self):
        """User rsids that already match a weight rsid should not be touched."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
        ])

        result = _augment_user_df_with_positions(user, weights, "GRCh37")
        assert result["rsid"][0] == "rs1"

    def test_no_dot_rsids_returns_unchanged(self):
        """If no '.' rsids exist, return user_df unchanged."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
        ])

        result = _augment_user_df_with_positions(user, weights, "GRCh37")
        assert result.equals(user)

    def test_no_position_columns_returns_unchanged(self):
        """Weights without position columns should return user_df unchanged."""
        user = make_user_df([
            {"rsid": ".", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
        ])

        result = _augment_user_df_with_positions(user, weights, "GRCh37")
        assert result["rsid"][0] == "."


class TestPositionBasedPrs:
    def test_position_matched_variants_scored(self):
        """Variants with '.' rsids should be scored when position matches weights."""
        user = make_user_df([
            {"rsid": ".", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
            {"rsid": ".", "chrom": "2", "position": 300, "allele1": "T", "allele2": "T"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs3", "chrom": "2", "w_position": 300, "w_position_grch38": 350,
             "effect_allele": "T", "weight": 0.3},
        ])

        result = compute_prs(
            user_df=user,
            pgs_id="PGS_POS",
            weights_df=weights,
            ref_mean=0.0,
            ref_std=1.0,
            ancestry_group="EUR",
            genome_build="GRCh37",
        )
        # rs1: dosage=1 (A/G, effect=A) → 0.5
        # rs3: dosage=2 (T/T, effect=T) → 0.6
        assert result.raw_score == pytest.approx(1.1)
        assert result.n_variants_matched == 2
        assert result.n_variants_total == 2

    def test_position_matching_without_genome_build(self):
        """Without position columns, '.' rsid variants are not matched."""
        user = make_user_df([
            {"rsid": ".", "chrom": "1", "position": 100, "allele1": "A", "allele2": "G"},
        ])
        weights = make_weights_df([
            {"rsid": "rs1", "effect_allele": "A", "weight": 0.5},
        ])

        result = compute_prs(
            user_df=user,
            pgs_id="PGS_NOPOS",
            weights_df=weights,
            ref_mean=0.0,
            ref_std=1.0,
            ancestry_group="EUR",
        )
        assert result.n_variants_matched == 0
        assert result.raw_score == 0.0

    def test_mixed_rsid_and_position_matching(self):
        """Both rsid-matched and position-matched variants should be scored."""
        user = make_user_df([
            {"rsid": "rs1", "chrom": "1", "position": 100, "allele1": "A", "allele2": "A"},
            {"rsid": ".", "chrom": "2", "position": 300, "allele1": "C", "allele2": "C"},
        ])
        weights = make_weights_with_positions([
            {"rsid": "rs1", "chrom": "1", "w_position": 100, "w_position_grch38": 150,
             "effect_allele": "A", "weight": 0.5},
            {"rsid": "rs3", "chrom": "2", "w_position": 300, "w_position_grch38": 350,
             "effect_allele": "C", "weight": 0.3},
        ])

        result = compute_prs(
            user_df=user,
            pgs_id="PGS_MIX",
            weights_df=weights,
            ref_mean=0.0,
            ref_std=1.0,
            ancestry_group="EUR",
            genome_build="GRCh37",
        )
        # rs1: dosage=2 (A/A) → 1.0
        # rs3 (by position): dosage=2 (C/C) → 0.6
        assert result.raw_score == pytest.approx(1.6)
        assert result.n_variants_matched == 2
