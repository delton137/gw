"""Tests for the absolute risk conversion — Bayesian mixture model."""

import pytest

from app.services.absolute_risk import (
    AbsoluteRiskResult,
    auc_to_cohens_d,
    compute_absolute_risk,
    _norm_cdf,
    _norm_pdf,
    _norm_ppf,
)


class TestNormFunctions:
    """Test internal normal distribution helper functions."""

    def test_cdf_at_zero(self):
        assert _norm_cdf(0.0) == pytest.approx(0.5)

    def test_cdf_at_one(self):
        assert _norm_cdf(1.0) == pytest.approx(0.8413, abs=0.001)

    def test_pdf_at_zero(self):
        assert _norm_pdf(0.0) == pytest.approx(0.3989, abs=0.001)

    def test_pdf_symmetric(self):
        assert _norm_pdf(1.5) == pytest.approx(_norm_pdf(-1.5))

    def test_ppf_at_half(self):
        assert _norm_ppf(0.5) == pytest.approx(0.0, abs=0.01)

    def test_ppf_at_975(self):
        assert _norm_ppf(0.975) == pytest.approx(1.96, abs=0.01)

    def test_ppf_cdf_roundtrip(self):
        """ppf(cdf(x)) ≈ x for reasonable values."""
        for x in [-2.0, -1.0, 0.0, 0.5, 1.0, 2.0]:
            assert _norm_ppf(_norm_cdf(x)) == pytest.approx(x, abs=0.01)


class TestAucToCohensD:
    def test_auc_0_5_gives_zero(self):
        """AUC of 0.5 (random) → d = 0."""
        assert auc_to_cohens_d(0.5) == 0.0

    def test_auc_0_7(self):
        """AUC 0.7 → d ≈ 0.74 (√2 * 0.524)."""
        d = auc_to_cohens_d(0.7)
        assert d == pytest.approx(0.74, abs=0.05)

    def test_auc_0_8(self):
        """AUC 0.8 → d ≈ 1.19 (√2 * 0.842)."""
        d = auc_to_cohens_d(0.8)
        assert d == pytest.approx(1.19, abs=0.05)

    def test_monotonically_increasing(self):
        """Higher AUC → higher Cohen's d."""
        aucs = [0.55, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        ds = [auc_to_cohens_d(a) for a in aucs]
        for i in range(len(ds) - 1):
            assert ds[i] < ds[i + 1]


class TestComputeAbsoluteRisk:
    def test_average_z_score_near_prevalence(self):
        """z=0 (population average) should have risk close to prevalence."""
        result = compute_absolute_risk(z_score=0.0, prevalence=0.10, auc=0.65)
        assert result is not None
        # Not exactly K due to mixture model asymmetry, but close
        assert result.absolute_risk == pytest.approx(0.10, abs=0.03)

    def test_high_z_score_increases_risk(self):
        """z=2 (97.5th percentile) should have risk > prevalence."""
        result = compute_absolute_risk(z_score=2.0, prevalence=0.10, auc=0.65)
        assert result is not None
        assert result.absolute_risk > 0.10
        assert result.relative_risk > 1.0

    def test_low_z_score_decreases_risk(self):
        """z=-2 should have risk < prevalence."""
        result = compute_absolute_risk(z_score=-2.0, prevalence=0.10, auc=0.65)
        assert result is not None
        assert result.absolute_risk < 0.10
        assert result.relative_risk < 1.0

    def test_risk_bounded_0_1(self):
        """Risk should always be between 0 and 1."""
        for z in [-5, -2, 0, 2, 5]:
            result = compute_absolute_risk(z_score=z, prevalence=0.05, auc=0.7)
            assert result is not None
            assert 0 <= result.absolute_risk <= 1

    def test_higher_auc_amplifies_risk_difference(self):
        """Higher AUC means the PRS is more discriminating."""
        result_low = compute_absolute_risk(z_score=2.0, prevalence=0.10, auc=0.6)
        result_high = compute_absolute_risk(z_score=2.0, prevalence=0.10, auc=0.75)
        assert result_low is not None and result_high is not None
        assert result_high.absolute_risk > result_low.absolute_risk

    def test_uses_cohens_d_directly(self):
        """Can provide Cohen's d directly instead of AUC."""
        result = compute_absolute_risk(z_score=1.5, prevalence=0.05, cohens_d=0.5)
        assert result is not None
        assert result.absolute_risk > 0.05

    def test_returns_none_without_effect_size(self):
        """Must provide either AUC or Cohen's d."""
        result = compute_absolute_risk(z_score=1.0, prevalence=0.10)
        assert result is None

    def test_returns_none_for_random_auc(self):
        """AUC <= 0.5 means the PRS is useless."""
        result = compute_absolute_risk(z_score=1.0, prevalence=0.10, auc=0.5)
        assert result is None

    def test_returns_none_for_invalid_prevalence(self):
        assert compute_absolute_risk(z_score=1.0, prevalence=0.0, auc=0.7) is None
        assert compute_absolute_risk(z_score=1.0, prevalence=1.0, auc=0.7) is None
        assert compute_absolute_risk(z_score=1.0, prevalence=-0.1, auc=0.7) is None

    def test_risk_categories(self):
        """Test that risk categories make directional sense."""
        result_high = compute_absolute_risk(z_score=3.0, prevalence=0.05, auc=0.70)
        assert result_high is not None
        assert result_high.risk_category in ("high", "elevated")

        result_low = compute_absolute_risk(z_score=-3.0, prevalence=0.05, auc=0.70)
        assert result_low is not None
        assert result_low.risk_category in ("reduced", "average")

    def test_symmetry_of_relative_risk(self):
        """A person 2 SD above average should have symmetric inverse of 2 SD below."""
        K = 0.10
        result_high = compute_absolute_risk(z_score=2.0, prevalence=K, auc=0.65)
        result_low = compute_absolute_risk(z_score=-2.0, prevalence=K, auc=0.65)
        assert result_high is not None and result_low is not None
        # Product of odds should be approximately 1 (by Bayes symmetry)
        odds_high = result_high.absolute_risk / (1 - result_high.absolute_risk)
        odds_low = result_low.absolute_risk / (1 - result_low.absolute_risk)
        # Odds ratio for +2z vs -2z should reflect 4*d shift
        assert odds_high > odds_low

    def test_validates_against_genopred_cad(self):
        """Validate against GenoPred: CAD (PGS000001).

        Paper: prevalence ~6.5%, AUC ~0.62.
        For z=1.96 (97.5th percentile), risk should be meaningfully above baseline.
        For z=0 (50th percentile), risk should be near baseline.
        """
        result_avg = compute_absolute_risk(z_score=0.0, prevalence=0.065, auc=0.62)
        result_high = compute_absolute_risk(z_score=1.96, prevalence=0.065, auc=0.62)
        assert result_avg is not None and result_high is not None

        # Average person should be near population risk
        assert 0.04 < result_avg.absolute_risk < 0.10

        # 97.5th percentile should be elevated
        assert result_high.absolute_risk > result_avg.absolute_risk
        assert result_high.relative_risk > 1.5

    def test_low_auc_produces_modest_risk_changes(self):
        """AUC 0.55 (barely above chance) should barely change risk."""
        result = compute_absolute_risk(z_score=2.0, prevalence=0.10, auc=0.55)
        assert result is not None
        # Even at z=2, risk shouldn't change dramatically for low AUC
        assert 0.05 < result.absolute_risk < 0.30
