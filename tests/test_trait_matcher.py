"""Tests for the trait matcher — risk classification logic."""

import pytest

from app.services.trait_matcher import classify_risk


class TestClassifyRisk:
    def test_homozygous_risk(self):
        """Two copies of risk allele → increased (no OR)."""
        assert classify_risk("A", "A", "A") == "increased"

    def test_heterozygous_risk(self):
        """One copy of risk allele → moderate (no OR)."""
        assert classify_risk("A", "G", "A") == "moderate"
        assert classify_risk("G", "A", "A") == "moderate"

    def test_no_risk(self):
        """Zero copies of risk allele → typical."""
        assert classify_risk("G", "C", "A") == "typical"

    def test_homozygous_non_risk(self):
        assert classify_risk("T", "T", "C") == "typical"

    def test_both_alleles_different_from_risk(self):
        assert classify_risk("A", "G", "T") == "typical"

    def test_single_copy_allele2(self):
        """Risk allele only in allele2 position."""
        assert classify_risk("C", "T", "T") == "moderate"

    def test_case_sensitivity(self):
        """Allele comparison is case-sensitive (alleles should always be uppercase)."""
        assert classify_risk("a", "A", "A") == "moderate"
        assert classify_risk("A", "A", "a") == "typical"


class TestClassifyRiskWithOddsRatio:
    """Effect-size-aware classification when odds_ratio is provided."""

    def test_high_or_homozygous_increased(self):
        """OR >= 2.0 with 2 copies → increased."""
        assert classify_risk("A", "A", "A", odds_ratio=2.5) == "increased"
        assert classify_risk("A", "A", "A", odds_ratio=11.0) == "increased"

    def test_high_or_heterozygous_moderate(self):
        """OR >= 1.5 with 1 copy → moderate."""
        assert classify_risk("A", "G", "A", odds_ratio=1.8) == "moderate"
        assert classify_risk("A", "G", "A", odds_ratio=5.0) == "moderate"

    def test_moderate_or_homozygous_moderate(self):
        """OR 1.2–2.0 with 2 copies → moderate."""
        assert classify_risk("A", "A", "A", odds_ratio=1.3) == "moderate"
        assert classify_risk("A", "A", "A", odds_ratio=1.9) == "moderate"

    def test_low_or_always_typical(self):
        """OR < 1.2 → typical regardless of copies."""
        assert classify_risk("A", "A", "A", odds_ratio=1.05) == "typical"
        assert classify_risk("A", "G", "A", odds_ratio=1.1) == "typical"
        assert classify_risk("A", "A", "A", odds_ratio=1.0) == "typical"

    def test_zero_copies_always_typical(self):
        """No risk allele → typical even with high OR."""
        assert classify_risk("G", "C", "A", odds_ratio=11.0) == "typical"

    def test_none_or_falls_back(self):
        """None odds_ratio uses allele-count fallback."""
        assert classify_risk("A", "A", "A", odds_ratio=None) == "increased"
        assert classify_risk("A", "G", "A", odds_ratio=None) == "moderate"

    def test_boundary_or_2_0(self):
        """OR exactly 2.0 with 2 copies → increased."""
        assert classify_risk("A", "A", "A", odds_ratio=2.0) == "increased"

    def test_boundary_or_1_5_het(self):
        """OR exactly 1.5 with 1 copy → moderate."""
        assert classify_risk("A", "G", "A", odds_ratio=1.5) == "moderate"

    def test_boundary_or_1_2_hom(self):
        """OR exactly 1.2 with 2 copies → moderate."""
        assert classify_risk("A", "A", "A", odds_ratio=1.2) == "moderate"

    def test_moderate_or_heterozygous_below_1_5(self):
        """OR 1.2–1.5 with 1 copy → fallback to allele-count (moderate)."""
        assert classify_risk("A", "G", "A", odds_ratio=1.3) == "moderate"
