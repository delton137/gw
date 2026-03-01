"""Tests for GWAS-hit PRS scoring service."""

from math import exp, log

import polars as pl
import pytest

from app.services.scorer import compute_dosage, compute_raw_score, score_to_percentile
from app.services.gwas_scorer import _get_af, empirical_percentile


# ---------------------------------------------------------------------------
# Helper: build user genotype DataFrame
# ---------------------------------------------------------------------------

def make_user_df(genotypes: list[tuple[str, str, str]]) -> pl.DataFrame:
    """Build a user DataFrame from list of (rsid, allele1, allele2)."""
    return pl.DataFrame(
        {
            "rsid": [g[0] for g in genotypes],
            "chrom": ["1"] * len(genotypes),
            "position": list(range(100, 100 + len(genotypes))),
            "allele1": [g[1] for g in genotypes],
            "allele2": [g[2] for g in genotypes],
        }
    )


def make_weights_df(weights: list[tuple[str, str, float]]) -> pl.DataFrame:
    """Build a weights DataFrame from list of (rsid, effect_allele, weight)."""
    return pl.DataFrame(
        {
            "rsid": [w[0] for w in weights],
            "effect_allele": [w[1] for w in weights],
            "weight": [w[2] for w in weights],
        }
    )


class FakeAssoc:
    """Minimal stand-in for GwasAssociation ORM object."""
    def __init__(self, rsid, risk_allele, beta, risk_allele_frequency=None,
                 eur_af=None, afr_af=None, eas_af=None, sas_af=None, amr_af=None):
        self.rsid = rsid
        self.risk_allele = risk_allele
        self.beta = beta
        self.risk_allele_frequency = risk_allele_frequency
        self.eur_af = eur_af
        self.afr_af = afr_af
        self.eas_af = eas_af
        self.sas_af = sas_af
        self.amr_af = amr_af


# ---------------------------------------------------------------------------
# Tests: compute_dosage (reused from scorer.py)
# ---------------------------------------------------------------------------

class TestComputeDosage:
    def test_homozygous_effect(self):
        user_df = make_user_df([("rs1", "A", "A")])
        weights_df = make_weights_df([("rs1", "A", 0.5)])
        result = compute_dosage(user_df, weights_df)
        assert len(result) == 1
        assert result["dosage"][0] == 2
        assert result["contribution"][0] == pytest.approx(1.0)

    def test_heterozygous(self):
        user_df = make_user_df([("rs1", "A", "G")])
        weights_df = make_weights_df([("rs1", "A", 0.5)])
        result = compute_dosage(user_df, weights_df)
        assert result["dosage"][0] == 1
        assert result["contribution"][0] == pytest.approx(0.5)

    def test_no_effect_allele(self):
        user_df = make_user_df([("rs1", "G", "G")])
        weights_df = make_weights_df([("rs1", "A", 0.5)])
        result = compute_dosage(user_df, weights_df)
        assert result["dosage"][0] == 0
        assert result["contribution"][0] == pytest.approx(0.0)

    def test_no_match(self):
        user_df = make_user_df([("rs1", "A", "G")])
        weights_df = make_weights_df([("rs99", "A", 0.5)])
        result = compute_dosage(user_df, weights_df)
        assert len(result) == 0


# ---------------------------------------------------------------------------
# Tests: compute_raw_score (unnormalized, from scorer.py)
# ---------------------------------------------------------------------------

class TestComputeRawScore:
    def test_basic_score(self):
        user_df = make_user_df([
            ("rs1", "A", "G"),  # 1 copy of A
            ("rs2", "T", "T"),  # 2 copies of T
            ("rs3", "C", "G"),  # 0 copies of A
        ])
        weights_df = make_weights_df([
            ("rs1", "A", 0.3),
            ("rs2", "T", 0.2),
            ("rs3", "A", 0.1),
        ])
        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        # 1*0.3 + 2*0.2 + 0*0.1 = 0.7
        assert raw == pytest.approx(0.7)
        assert n_matched == 3
        assert n_total == 3

    def test_partial_match(self):
        user_df = make_user_df([("rs1", "A", "G")])
        weights_df = make_weights_df([
            ("rs1", "A", 0.5),
            ("rs2", "T", 0.3),
        ])
        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        assert raw == pytest.approx(0.5)
        assert n_matched == 1
        assert n_total == 2

    def test_zero_match(self):
        user_df = make_user_df([("rs1", "A", "G")])
        weights_df = make_weights_df([("rs99", "T", 0.3)])
        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        assert raw == 0.0
        assert n_matched == 0
        assert n_total == 1

    def test_negative_weights(self):
        """OR < 1 → log(OR) < 0 → negative beta → protective allele."""
        user_df = make_user_df([("rs1", "A", "A")])
        weights_df = make_weights_df([("rs1", "A", -0.2)])
        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        assert raw == pytest.approx(-0.4)
        assert n_matched == 1


# ---------------------------------------------------------------------------
# Tests: score_to_percentile
# ---------------------------------------------------------------------------

class TestScoreToPercentile:
    def test_mean_is_50th(self):
        assert score_to_percentile(0.0, 0.0, 1.0) == pytest.approx(50.0)

    def test_above_mean(self):
        pct = score_to_percentile(1.0, 0.0, 1.0)
        assert pct > 50.0
        assert pct == pytest.approx(84.13, abs=0.1)

    def test_below_mean(self):
        pct = score_to_percentile(-1.0, 0.0, 1.0)
        assert pct < 50.0
        assert pct == pytest.approx(15.87, abs=0.1)

    def test_zero_std_returns_50(self):
        assert score_to_percentile(10.0, 0.0, 0.0) == 50.0

    def test_extreme_high(self):
        pct = score_to_percentile(5.0, 0.0, 1.0)
        assert pct > 99.0

    def test_extreme_low(self):
        pct = score_to_percentile(-5.0, 0.0, 1.0)
        assert pct < 1.0


# ---------------------------------------------------------------------------
# Tests: OR → beta conversion (used in ingest script)
# ---------------------------------------------------------------------------

class TestOrToBeta:
    def test_or_1_gives_zero_beta(self):
        assert log(1.0) == pytest.approx(0.0)

    def test_or_greater_than_1(self):
        beta = log(1.5)
        assert beta > 0
        assert beta == pytest.approx(0.4055, abs=0.001)

    def test_or_less_than_1(self):
        beta = log(0.8)
        assert beta < 0


# ---------------------------------------------------------------------------
# Tests: _get_af helper
# ---------------------------------------------------------------------------

class TestGetAf:
    def test_uses_population_af(self):
        a = FakeAssoc("rs1", "A", 0.3, risk_allele_frequency=0.25, eur_af=0.30)
        assert _get_af(a, "EUR") == 0.30

    def test_no_raf_fallback(self):
        """Does NOT fall back to risk_allele_frequency — matches PRSKB mafVal=0 behavior."""
        a = FakeAssoc("rs1", "A", 0.3, risk_allele_frequency=0.25, eur_af=None)
        assert _get_af(a, "EUR") is None

    def test_returns_none_when_no_af(self):
        a = FakeAssoc("rs1", "A", 0.3, risk_allele_frequency=None, eur_af=None)
        assert _get_af(a, "EUR") is None

    def test_rejects_zero_af(self):
        a = FakeAssoc("rs1", "A", 0.3, eur_af=0.0)
        assert _get_af(a, "EUR") is None

    def test_rejects_af_of_one(self):
        a = FakeAssoc("rs1", "A", 0.3, eur_af=1.0)
        assert _get_af(a, "EUR") is None

    def test_afr_ancestry(self):
        a = FakeAssoc("rs1", "A", 0.3, risk_allele_frequency=0.25, afr_af=0.40)
        assert _get_af(a, "AFR") == 0.40

    def test_unknown_ancestry_returns_none(self):
        a = FakeAssoc("rs1", "A", 0.3, eur_af=0.30)
        assert _get_af(a, "UNKNOWN") is None


# ---------------------------------------------------------------------------
# Tests: empirical_percentile (PRSKB getPercentile reimplementation)
# ---------------------------------------------------------------------------

class TestEmpiricalPercentile:
    @pytest.fixture
    def pct_dict(self):
        """Simple linear percentile table: p0=0.0, p50=0.5, p100=1.0."""
        return {f"p{i}": i / 100.0 for i in range(101)}

    def test_at_median(self, pct_dict):
        pct = empirical_percentile(0.50, pct_dict)
        assert pct == 50.0

    def test_below_minimum(self, pct_dict):
        pct = empirical_percentile(-1.0, pct_dict)
        assert pct == 0.0

    def test_above_maximum(self, pct_dict):
        pct = empirical_percentile(2.0, pct_dict)
        assert pct == 100.0

    def test_between_percentiles(self, pct_dict):
        # Score 0.25 is >= p25=0.25 but < p26=0.26 → percentile = 25
        pct = empirical_percentile(0.25, pct_dict)
        assert pct == 25.0

    def test_tied_percentiles(self):
        """When multiple percentiles have the same value, return midpoint."""
        pct_dict = {f"p{i}": 0.0 for i in range(101)}
        # p0-p50 = 0.0, p51-p100 = 1.0
        for i in range(51, 101):
            pct_dict[f"p{i}"] = 1.0
        # Score 0.0 should be in range p0-p50 → midpoint = 25
        pct = empirical_percentile(0.0, pct_dict)
        assert pct == 25.0

    def test_exact_p75(self, pct_dict):
        pct = empirical_percentile(0.75, pct_dict)
        assert pct == 75.0

    def test_or_type_score(self):
        """OR-type study percentiles are in exp() space (values around 1.0)."""
        # Simulates a typical OR-type percentile table
        pct_dict = {f"p{i}": exp(0.001 * i) for i in range(101)}
        # p50 = exp(0.05) ≈ 1.0513
        score = exp(0.05)  # user at population median
        pct = empirical_percentile(score, pct_dict)
        assert pct == 50.0


# ---------------------------------------------------------------------------
# Tests: PRSKB-style scoring (MAF imputation + normalization)
# ---------------------------------------------------------------------------

class TestPrskbScoring:
    """Test the full PRSKB scoring formula:
    score = (matched_contribution + imputed_contribution) / (2 × N_total)
    """

    def test_all_matched_normalized(self):
        """When all variants are matched, score = Σ(dosage × beta) / (2 × N)."""
        user_df = make_user_df([
            ("rs1", "A", "G"),  # dosage=1, contribution=0.3
            ("rs2", "T", "T"),  # dosage=2, contribution=0.4
        ])
        weights_df = make_weights_df([
            ("rs1", "A", 0.3),
            ("rs2", "T", 0.2),
        ])
        scored = compute_dosage(user_df, weights_df)
        matched_contribution = float(scored["contribution"].sum())
        N = 2
        score = matched_contribution / (2 * N)
        # (0.3 + 0.4) / 4 = 0.175
        assert score == pytest.approx(0.175)

    def test_with_imputation(self):
        """Unmatched variant is imputed with 2 × MAF × beta."""
        # User only has rs1, missing rs2
        user_df = make_user_df([("rs1", "A", "G")])  # dosage=1
        weights_df = make_weights_df([
            ("rs1", "A", 0.3),
            ("rs2", "T", 0.2),
        ])
        scored = compute_dosage(user_df, weights_df)
        matched_rsids = set(scored["rsid"].to_list())
        matched_contribution = float(scored["contribution"].sum())  # 1 × 0.3 = 0.3

        # Impute rs2: MAF=0.4, beta=0.2 → 2 × 0.4 × 0.2 = 0.16
        assocs = [
            FakeAssoc("rs1", "A", 0.3, eur_af=0.2),
            FakeAssoc("rs2", "T", 0.2, eur_af=0.4),
        ]
        imputed_contribution = 0.0
        for a in assocs:
            if a.rsid not in matched_rsids:
                af = _get_af(a, "EUR")
                if af is not None:
                    imputed_contribution += 2 * af * a.beta

        assert imputed_contribution == pytest.approx(0.16)  # 2 × 0.4 × 0.2

        N = 2
        score = (matched_contribution + imputed_contribution) / (2 * N)
        # (0.3 + 0.16) / 4 = 0.115
        assert score == pytest.approx(0.115)

    def test_imputation_no_af_contributes_zero(self):
        """Variant without AF data contributes 0 (matching PRSKB mafVal default)."""
        assocs = [
            FakeAssoc("rs1", "A", 0.3, eur_af=None, risk_allele_frequency=None),
        ]
        imputed = 0.0
        for a in assocs:
            af = _get_af(a, "EUR")
            if af is not None:
                imputed += 2 * af * a.beta
        assert imputed == 0.0

    def test_or_type_exp_transform(self):
        """OR-type studies apply exp() after normalization (PRSKB line 318-319)."""
        user_df = make_user_df([
            ("rs1", "A", "G"),  # dosage=1
            ("rs2", "T", "T"),  # dosage=2
        ])
        weights_df = make_weights_df([
            ("rs1", "A", log(1.3)),   # beta = ln(OR=1.3)
            ("rs2", "T", log(1.1)),   # beta = ln(OR=1.1)
        ])
        scored = compute_dosage(user_df, weights_df)
        matched_contribution = float(scored["contribution"].sum())
        N = 2
        # In log space
        log_score = matched_contribution / (2 * N)
        # Apply exp for OR-type
        or_score = exp(log_score)
        assert or_score > 1.0  # OR > 1 means above baseline

    def test_beta_zero_filtered(self):
        """Associations with beta=0 should be filtered out before scoring."""
        assocs = [
            FakeAssoc("rs1", "A", 0.3, eur_af=0.2),
            FakeAssoc("rs2", "T", 0.0, eur_af=0.4),  # zero effect
            FakeAssoc("rs3", "C", 0.1, eur_af=0.3),
        ]
        # After filtering
        filtered = [a for a in assocs if a.beta != 0]
        assert len(filtered) == 2
        assert all(a.beta != 0 for a in filtered)


# ---------------------------------------------------------------------------
# Tests: end-to-end scoring scenario
# ---------------------------------------------------------------------------

class TestEndToEndScoring:
    def test_cad_like_score(self):
        """Simulate a small CAD-like GWAS score with known genotypes."""
        # 5 SNPs from a hypothetical CAD study
        weights = [
            ("rs1333049", "C", 0.22),   # 9p21 locus
            ("rs2241880", "T", -0.10),   # ATG16L1 (protective)
            ("rs6725887", "C", 0.17),    # WDR12
            ("rs964184",  "G", 0.13),    # ZPR1
            ("rs1746048", "C", 0.11),    # CXCL12
        ]
        # User has mixed genotypes
        genotypes = [
            ("rs1333049", "C", "G"),     # 1 risk allele
            ("rs2241880", "T", "T"),     # 2 copies of protective
            ("rs6725887", "G", "G"),     # 0 risk alleles
            ("rs964184",  "A", "G"),     # 1 risk allele
            ("rs1746048", "C", "C"),     # 2 risk alleles
        ]

        user_df = make_user_df(genotypes)
        weights_df = make_weights_df(weights)

        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        # 1*0.22 + 2*(-0.10) + 0*0.17 + 1*0.13 + 2*0.11 = 0.22 - 0.20 + 0.13 + 0.22 = 0.37
        assert raw == pytest.approx(0.37)
        assert n_matched == 5
        assert n_total == 5

        # Normalized score (PRSKB style): 0.37 / (2 × 5) = 0.037
        score = raw / (2 * n_total)
        assert score == pytest.approx(0.037)

    def test_partial_coverage_with_imputation(self):
        """User matches 2/4 variants; 2 are imputed with MAF."""
        genotypes = [
            ("rs1", "A", "A"),  # dosage=2, contribution=2*0.3=0.6
            ("rs2", "T", "G"),  # dosage=1, contribution=1*0.2=0.2
        ]
        assocs = [
            FakeAssoc("rs1", "A", 0.3, eur_af=0.2),
            FakeAssoc("rs2", "T", 0.2, eur_af=0.4),
            FakeAssoc("rs3", "C", 0.1, eur_af=0.3),  # missing → impute
            FakeAssoc("rs4", "G", 0.5, eur_af=0.1),  # missing → impute
        ]

        user_df = make_user_df(genotypes)
        weights_df = make_weights_df([(a.rsid, a.risk_allele, a.beta) for a in assocs])
        scored = compute_dosage(user_df, weights_df)
        matched_rsids = set(scored["rsid"].to_list())
        matched_contribution = float(scored["contribution"].sum())
        # rs1: 2×0.3=0.6, rs2: 1×0.2=0.2 → total=0.8
        assert matched_contribution == pytest.approx(0.8)

        # Impute rs3 and rs4
        imputed = sum(2 * _get_af(a, "EUR") * a.beta
                       for a in assocs if a.rsid not in matched_rsids)
        # rs3: 2×0.3×0.1=0.06, rs4: 2×0.1×0.5=0.10 → total=0.16
        assert imputed == pytest.approx(0.16)

        N = 4
        score = (matched_contribution + imputed) / (2 * N)
        # (0.8 + 0.16) / 8 = 0.12
        assert score == pytest.approx(0.12)

    def test_all_ref_ref(self):
        """User has no risk alleles → raw score = 0 for positive-beta SNPs."""
        weights = [
            ("rs1", "A", 0.3),
            ("rs2", "T", 0.2),
        ]
        genotypes = [
            ("rs1", "G", "G"),  # no A
            ("rs2", "C", "C"),  # no T
        ]
        user_df = make_user_df(genotypes)
        weights_df = make_weights_df(weights)
        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        assert raw == pytest.approx(0.0)
        assert n_matched == 2

    def test_all_homozygous_risk(self):
        """User is homozygous for all risk alleles → maximum score."""
        weights = [
            ("rs1", "A", 0.3),
            ("rs2", "T", 0.2),
        ]
        genotypes = [
            ("rs1", "A", "A"),
            ("rs2", "T", "T"),
        ]
        user_df = make_user_df(genotypes)
        weights_df = make_weights_df(weights)
        raw, n_matched, n_total = compute_raw_score(user_df, weights_df)
        # 2*0.3 + 2*0.2 = 1.0
        assert raw == pytest.approx(1.0)
