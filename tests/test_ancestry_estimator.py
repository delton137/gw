"""Tests for the Aeon MLE-based ancestry estimator."""

import json
import polars as pl
import numpy as np
import pytest
from unittest.mock import patch

from app.services.ancestry_estimator import (
    AncestryResult,
    estimate_ancestry,
    _mle_ancestry,
    _genotype_to_dosage,
    MIN_MARKERS,
    SUPERPOPULATIONS,
)


# ---------------------------------------------------------------------------
# Test data helpers
# ---------------------------------------------------------------------------

# Simplified 5-population reference for testing (real panel has 26)
TEST_POPS = ["POP_A", "POP_B", "POP_C", "POP_D", "POP_E"]
TEST_POP_MAP = {
    "POP_A": "AFR",
    "POP_B": "EUR",
    "POP_C": "EAS",
    "POP_D": "SAS",
    "POP_E": "AMR",
}


def make_test_reference(n_markers: int = 2000) -> pl.DataFrame:
    """Create a synthetic reference with known population-distinguishing allele frequencies.

    POP_A has high AF (0.8) while others have low (0.1) for first n/5 markers, etc.
    This makes populations clearly separable.
    """
    rng = np.random.default_rng(42)
    rsids = [f"rs{100000 + i}" for i in range(n_markers)]
    chroms = [str((i % 22) + 1) for i in range(n_markers)]
    positions = [1000000 + i * 100 for i in range(n_markers)]

    block_size = n_markers // 5
    af_data = {}
    for pi, pop in enumerate(TEST_POPS):
        freqs = np.full(n_markers, 0.15)
        start = pi * block_size
        end = start + block_size
        freqs[start:end] = rng.uniform(0.7, 0.95, min(block_size, n_markers - start))
        af_data[pop] = freqs.astype(np.float32)

    df = pl.DataFrame({
        "rsid": rsids,
        "var_id": [f"chr{c}_{p}_A_G" for c, p in zip(chroms, positions)],
        "chrom": chroms,
        "position": positions,
        "ref": ["A"] * n_markers,
        "alt": ["G"] * n_markers,
        **{pop: af_data[pop] for pop in TEST_POPS},
    })
    return df


def make_user_df_for_pop(ref_df: pl.DataFrame, target_pop: str, n_markers: int | None = None) -> pl.DataFrame:
    """Generate user genotypes that simulate an individual from target_pop.

    Uses the reference allele frequencies to probabilistically assign genotypes.
    """
    rng = np.random.default_rng(123)
    ref = ref_df if n_markers is None else ref_df.head(n_markers)

    af = ref[target_pop].to_numpy()
    # Simulate diploid genotype from allele frequency
    allele1 = np.where(rng.random(len(af)) < af, "G", "A")
    allele2 = np.where(rng.random(len(af)) < af, "G", "A")

    return pl.DataFrame({
        "rsid": ref["rsid"].to_list(),
        "chrom": ref["chrom"].to_list(),
        "position": ref["position"].to_list(),
        "allele1": allele1.tolist(),
        "allele2": allele2.tolist(),
    })


def make_user_df_simple(rsids: list[str], n: int | None = None) -> pl.DataFrame:
    """Create a simple user DataFrame with given rsids."""
    if n is not None:
        rsids = rsids[:n]
    return pl.DataFrame({
        "rsid": rsids,
        "chrom": ["1"] * len(rsids),
        "position": list(range(1000000, 1000000 + len(rsids))),
        "allele1": ["A"] * len(rsids),
        "allele2": ["G"] * len(rsids),
    })


@pytest.fixture
def mock_ancestry_env(tmp_path):
    """Set up mock reference data for testing."""
    import app.services.ancestry_estimator as _mod

    # Clear lazy singleton cache
    _mod._CACHED_REF = None
    _mod._CACHED_POP_MAP = None
    _mod._CACHED_POP_ORDER = None

    # Create reference parquet
    ref_df = make_test_reference(2000)
    ref_path = tmp_path / "aeon_reference.parquet"
    ref_df.write_parquet(ref_path)

    # Create pop map
    pop_map_path = tmp_path / "pop_to_superpop.json"
    pop_map_path.write_text(json.dumps(TEST_POP_MAP))

    with patch.object(_mod, "_REFERENCE_PATH", ref_path), \
         patch.object(_mod, "_POP_MAP_PATH", pop_map_path), \
         patch.object(_mod, "MIN_MARKERS", 50):  # Lower threshold for testing

        yield {"ref_df": ref_df}

    # Clean up cache
    _mod._CACHED_REF = None
    _mod._CACHED_POP_MAP = None
    _mod._CACHED_POP_ORDER = None


# ---------------------------------------------------------------------------
# Unit tests for core MLE algorithm
# ---------------------------------------------------------------------------

class TestMleAlgorithm:
    """Test the scipy MLE estimator directly."""

    def test_pure_population(self):
        """Individual from a single population should get ~100% for that pop."""
        rng = np.random.default_rng(42)
        n_loci = 5000
        n_pops = 3

        # Create allele frequencies that distinguish 3 populations
        af = np.zeros((n_loci, n_pops), dtype=np.float64)
        block = n_loci // n_pops
        for i in range(n_pops):
            af[i * block:(i + 1) * block, i] = rng.uniform(0.7, 0.95, block)
            for j in range(n_pops):
                if j != i:
                    af[i * block:(i + 1) * block, j] = rng.uniform(0.05, 0.2, block)

        # Simulate individual from pop 0
        true_af = af[:, 0]
        dosages = (rng.random(n_loci) < true_af).astype(int) + (rng.random(n_loci) < true_af).astype(int)

        result, nll = _mle_ancestry(dosages, af)

        assert result[0] > 0.7  # Should be clearly highest
        assert np.sum(result) == pytest.approx(1.0, abs=0.01)
        assert all(r >= 0 for r in result)

    def test_admixed_individual(self):
        """50/50 admixed individual should get ~50% for each contributing pop."""
        rng = np.random.default_rng(99)
        n_loci = 10000
        n_pops = 3

        af = rng.uniform(0.1, 0.9, (n_loci, n_pops)).astype(np.float64)
        # Make populations distinguishable
        for i in range(n_pops):
            block = n_loci // n_pops
            af[i * block:(i + 1) * block, i] = rng.uniform(0.7, 0.95, block)

        # 50/50 mix of pop 0 and pop 1
        mixed_af = 0.5 * af[:, 0] + 0.5 * af[:, 1]
        dosages = (rng.random(n_loci) < mixed_af).astype(int) + (rng.random(n_loci) < mixed_af).astype(int)

        result, nll = _mle_ancestry(dosages, af)

        # Both contributing populations should have significant fractions
        assert result[0] > 0.2
        assert result[1] > 0.2
        # Non-contributing pop should be small
        assert result[2] < 0.3
        assert np.sum(result) == pytest.approx(1.0, abs=0.01)

    def test_proportions_sum_to_one(self):
        """MLE result should always sum to 1.0."""
        rng = np.random.default_rng(0)
        n_loci = 1000
        af = rng.uniform(0.05, 0.95, (n_loci, 5)).astype(np.float64)
        dosages = rng.choice([0, 1, 2], size=n_loci)

        result, _ = _mle_ancestry(dosages, af)

        assert np.sum(result) == pytest.approx(1.0, abs=0.01)
        assert all(r >= -0.01 for r in result)  # Allow tiny numerical error


# ---------------------------------------------------------------------------
# Unit tests for dosage computation
# ---------------------------------------------------------------------------

class TestDosageConversion:
    def test_hom_ref(self):
        assert _genotype_to_dosage("A", "A", "A", "G") == 0

    def test_het(self):
        assert _genotype_to_dosage("A", "G", "A", "G") == 1

    def test_hom_alt(self):
        assert _genotype_to_dosage("G", "G", "A", "G") == 2

    def test_het_reversed(self):
        assert _genotype_to_dosage("G", "A", "A", "G") == 1

    def test_unknown_allele_treated_as_ref(self):
        assert _genotype_to_dosage("T", "A", "A", "G") == 0

    def test_both_unknown(self):
        assert _genotype_to_dosage("T", "C", "A", "G") == 0


# ---------------------------------------------------------------------------
# Integration tests with mock reference
# ---------------------------------------------------------------------------

def test_estimate_ancestry_success(mock_ancestry_env):
    """Genotypes simulated from POP_A → should detect AFR superpopulation."""
    ref_df = mock_ancestry_env["ref_df"]
    user_df = make_user_df_for_pop(ref_df, "POP_A")

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is not None
    assert isinstance(result, AncestryResult)
    assert "AFR" in result.superpopulations
    assert result.superpopulations["AFR"] > 0.3  # Should be dominant
    assert result.n_markers_used > 1000
    assert sum(result.superpopulations.values()) == pytest.approx(1.0, abs=0.02)


def test_estimate_ancestry_returns_all_fields(mock_ancestry_env):
    """Result should contain all expected fields."""
    ref_df = mock_ancestry_env["ref_df"]
    user_df = make_user_df_for_pop(ref_df, "POP_B")

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is not None
    # Check all fields exist
    assert result.populations is not None
    assert result.superpopulations is not None
    assert result.best_pop in SUPERPOPULATIONS
    assert 0 <= result.confidence <= 1
    assert result.n_markers_used > 0
    assert result.n_markers_total > 0
    assert isinstance(result.is_admixed, bool)
    assert result.coverage_quality in ("high", "medium", "low")


def test_estimate_ancestry_too_few_markers(mock_ancestry_env):
    """Fewer than MIN_MARKERS matched → returns None."""
    user_df = make_user_df_simple(["rs_fake_1", "rs_fake_2", "rs_fake_3"])

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is None


def test_estimate_ancestry_no_overlap(mock_ancestry_env):
    """No matching rsids → returns None."""
    user_df = pl.DataFrame({
        "rsid": ["rs999999"],
        "chrom": ["1"],
        "position": [100],
        "allele1": ["A"],
        "allele2": ["G"],
    })

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is None


def test_estimate_ancestry_proportions_sum_to_one(mock_ancestry_env):
    """Population proportions should sum to ~1.0."""
    ref_df = mock_ancestry_env["ref_df"]
    user_df = make_user_df_for_pop(ref_df, "POP_C")

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is not None
    pop_total = sum(result.populations.values())
    super_total = sum(result.superpopulations.values())
    assert pop_total == pytest.approx(1.0, abs=0.02)
    assert super_total == pytest.approx(1.0, abs=0.02)


def test_estimate_ancestry_build_independence(mock_ancestry_env):
    """Matching by rsid should work regardless of position values."""
    ref_df = mock_ancestry_env["ref_df"]

    # Create user data with correct rsids but completely different positions
    user_df = pl.DataFrame({
        "rsid": ref_df["rsid"].to_list()[:1500],
        "chrom": ref_df["chrom"].to_list()[:1500],
        "position": [9000000 + i for i in range(1500)],
        "allele1": ["A"] * 1500,
        "allele2": ["G"] * 1500,
    })

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is not None
    assert result.n_markers_used == 1500


def test_estimate_ancestry_exception_returns_none(mock_ancestry_env):
    """Internal exception → returns None gracefully."""
    ref_df = mock_ancestry_env["ref_df"]
    user_df = make_user_df_for_pop(ref_df, "POP_A")

    with patch("app.services.ancestry_estimator._mle_ancestry", side_effect=RuntimeError("boom")):
        result = estimate_ancestry(user_df, is_vcf=False)

    assert result is None


def test_estimate_ancestry_coverage_quality(mock_ancestry_env):
    """Coverage quality should reflect fraction of markers matched."""
    ref_df = mock_ancestry_env["ref_df"]

    # Use all markers → high coverage
    user_df = make_user_df_for_pop(ref_df, "POP_A")
    result = estimate_ancestry(user_df, is_vcf=False)
    assert result is not None
    assert result.coverage_quality == "high"


def test_estimate_ancestry_backward_compat(mock_ancestry_env):
    """Result.proportions should be available for backward compat."""
    ref_df = mock_ancestry_env["ref_df"]
    user_df = make_user_df_for_pop(ref_df, "POP_B")

    result = estimate_ancestry(user_df, is_vcf=False)

    assert result is not None
    # proportions field should work (same as populations)
    assert result.proportions == result.populations
    # best_pop should be a superpopulation (for PRS compat)
    assert result.best_pop in SUPERPOPULATIONS
