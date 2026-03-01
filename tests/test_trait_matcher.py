"""Tests for the trait matcher — risk classification logic."""

import pytest

from app.services.trait_matcher import classify_risk


class TestClassifyRisk:
    def test_homozygous_risk(self):
        """Two copies of risk allele → increased."""
        assert classify_risk("A", "A", "A") == "increased"

    def test_heterozygous_risk(self):
        """One copy of risk allele → moderate."""
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
