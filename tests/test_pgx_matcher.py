"""Tests for pharmacogenomics star allele / diplotype inference."""

import polars as pl
import pytest

import app.services.pgx_matcher as pgx_mod
from app.services.pgx_matcher import (
    PgxResult,
    _compute_confidence,
    _load_pgx_positions,
    _load_pgx_ref_alleles,
    _score_to_phenotype,
    assign_diplotype,
    call_star_alleles_for_gene,
)


# ---------------------------------------------------------------------------
# Helper to build a user DataFrame
# ---------------------------------------------------------------------------

def make_user_df(genotypes: dict[str, tuple[str, str]]) -> dict[str, tuple[str, str]]:
    """Build a user_lookup dict from rsid -> (allele1, allele2) mapping."""
    return genotypes


# ---------------------------------------------------------------------------
# Activity score threshold tests
# ---------------------------------------------------------------------------

class TestScoreToPhenotype:
    def test_cyp2d6_poor_metabolizer(self):
        assert _score_to_phenotype("CYP2D6", 0) == "Poor Metabolizer"

    def test_cyp2d6_intermediate_metabolizer(self):
        assert _score_to_phenotype("CYP2D6", 0.5) == "Intermediate Metabolizer"
        assert _score_to_phenotype("CYP2D6", 0.25) == "Intermediate Metabolizer"

    def test_cyp2d6_normal_metabolizer(self):
        assert _score_to_phenotype("CYP2D6", 1.0) == "Normal Metabolizer"
        assert _score_to_phenotype("CYP2D6", 2.0) == "Normal Metabolizer"

    def test_cyp2d6_ultrarapid_metabolizer(self):
        assert _score_to_phenotype("CYP2D6", 3.0) == "Ultra-rapid Metabolizer"

    def test_cyp2c19_poor(self):
        assert _score_to_phenotype("CYP2C19", 0) == "Poor Metabolizer"

    def test_cyp2c19_likely_poor(self):
        assert _score_to_phenotype("CYP2C19", 0.5) == "Likely Poor Metabolizer"

    def test_cyp2c19_intermediate(self):
        assert _score_to_phenotype("CYP2C19", 1.0) == "Intermediate Metabolizer"

    def test_cyp2c19_likely_intermediate(self):
        assert _score_to_phenotype("CYP2C19", 1.5) == "Likely Intermediate Metabolizer"

    def test_cyp2c19_normal(self):
        assert _score_to_phenotype("CYP2C19", 2.0) == "Normal Metabolizer"

    def test_cyp2c19_rapid(self):
        assert _score_to_phenotype("CYP2C19", 2.5) == "Rapid Metabolizer"

    def test_cyp2c19_ultrarapid(self):
        assert _score_to_phenotype("CYP2C19", 3.0) == "Ultrarapid Metabolizer"

    def test_dpyd_poor(self):
        assert _score_to_phenotype("DPYD", 0) == "Poor Metabolizer"
        assert _score_to_phenotype("DPYD", 0.5) == "Poor Metabolizer"

    def test_dpyd_intermediate(self):
        assert _score_to_phenotype("DPYD", 1.0) == "Intermediate Metabolizer"
        assert _score_to_phenotype("DPYD", 1.5) == "Intermediate Metabolizer"

    def test_dpyd_normal(self):
        assert _score_to_phenotype("DPYD", 2.0) == "Normal Metabolizer"

    def test_unknown_gene_uses_default_thresholds(self):
        # Unknown genes fall back to default metabolizer thresholds
        # Score 1.0 is in the IM range (0.001–1.25) for the defaults
        assert _score_to_phenotype("UNKNOWN_GENE", 1.0) == "Intermediate Metabolizer"
        # Score 1.5 is in the NM range (1.25–2.001)
        assert _score_to_phenotype("UNKNOWN_GENE", 1.5) == "Normal Metabolizer"


# ---------------------------------------------------------------------------
# Confidence scoring tests
# ---------------------------------------------------------------------------

class TestConfidence:
    def test_high_confidence(self):
        assert _compute_confidence(8, 10) == "high"
        assert _compute_confidence(10, 10) == "high"

    def test_medium_confidence(self):
        assert _compute_confidence(5, 10) == "medium"
        assert _compute_confidence(7, 10) == "medium"

    def test_low_confidence(self):
        assert _compute_confidence(2, 10) == "low"
        assert _compute_confidence(0, 10) == "low"

    def test_zero_total(self):
        assert _compute_confidence(0, 0) == "low"


# ---------------------------------------------------------------------------
# Star allele calling tests
# ---------------------------------------------------------------------------

class TestCallStarAlleles:
    """Test star allele calling for different gene types."""

    def test_single_snp_homozygous_variant(self):
        """CYP2D6 *4/*4 — homozygous loss-of-function."""
        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
        ]
        user = {"rs3892097": ("A", "A")}

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2D6", "activity_score", "*1", defs, user
        )
        assert len(detected) == 1
        assert detected[0] == ("*4", "no_function", 2)
        assert n_tested == 1
        assert n_total == 1

    def test_single_snp_heterozygous(self):
        """CYP2D6 *1/*4 — heterozygous."""
        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
        ]
        user = {"rs3892097": ("G", "A")}

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2D6", "activity_score", "*1", defs, user
        )
        assert len(detected) == 1
        assert detected[0] == ("*4", "no_function", 1)

    def test_single_snp_wild_type(self):
        """CYP2D6 *1/*1 — no variant alleles."""
        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
        ]
        user = {"rs3892097": ("G", "G")}

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2D6", "activity_score", "*1", defs, user
        )
        assert len(detected) == 0
        assert n_tested == 1

    def test_multiple_alleles_detected(self):
        """CYP2C19 *2/*17 — two different alleles."""
        defs = [
            {"star_allele": "*2", "rsid": "rs4244285", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
            {"star_allele": "*17", "rsid": "rs12248560", "variant_allele": "T",
             "function": "increased_function", "activity_score": 2.0},
        ]
        user = {
            "rs4244285": ("G", "A"),
            "rs12248560": ("C", "T"),
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2C19", "activity_score", "*1", defs, user
        )
        assert len(detected) == 2
        alleles = {d[0] for d in detected}
        assert "*2" in alleles
        assert "*17" in alleles

    def test_variant_not_on_chip(self):
        """SNP not in user data — not tested, not called."""
        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
        ]
        user = {}  # empty — variant not on chip

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2D6", "activity_score", "*1", defs, user
        )
        assert len(detected) == 0
        assert n_tested == 0
        assert n_total == 1

    def test_multi_snp_allele_both_present(self):
        """TPMT *3A — requires both rs1800460 AND rs1142345."""
        defs = [
            {"star_allele": "*3A", "rsid": "rs1800460", "variant_allele": "G",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*3A", "rsid": "rs1142345", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
        ]
        user = {
            "rs1800460": ("A", "G"),
            "rs1142345": ("T", "C"),
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "TPMT", "simple", "*1", defs, user
        )
        assert len(detected) == 1
        assert detected[0][0] == "*3A"
        assert detected[0][2] == 1  # min copies across both SNPs

    def test_multi_snp_allele_one_missing(self):
        """TPMT *3A — only one of two SNPs present → not called."""
        defs = [
            {"star_allele": "*3A", "rsid": "rs1800460", "variant_allele": "G",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*3A", "rsid": "rs1142345", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
        ]
        user = {
            "rs1800460": ("A", "G"),
            "rs1142345": ("T", "T"),  # wild-type
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "TPMT", "simple", "*1", defs, user
        )
        assert len(detected) == 0

    def test_binary_hla_positive(self):
        """HLA-B*57:01 — tag SNP present."""
        defs = [
            {"star_allele": "positive", "rsid": "rs2395029", "variant_allele": "G",
             "function": "risk", "activity_score": None},
        ]
        user = {"rs2395029": ("T", "G")}

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "HLA-B_5701", "binary", "negative", defs, user
        )
        assert len(detected) == 1
        assert detected[0][0] == "positive"

    def test_binary_hla_negative(self):
        """HLA-B*57:01 — tag SNP absent."""
        defs = [
            {"star_allele": "positive", "rsid": "rs2395029", "variant_allele": "G",
             "function": "risk", "activity_score": None},
        ]
        user = {"rs2395029": ("T", "T")}

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "HLA-B_5701", "binary", "negative", defs, user
        )
        assert detected[0][0] == "negative"

    def test_nat2_slow_acetylator(self):
        """NAT2 — 2+ slow-allele variants → Slow Acetylator."""
        defs = [
            {"star_allele": "*5", "rsid": "rs1801280", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*6", "rsid": "rs1799930", "variant_allele": "A",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*12", "rsid": "rs1208", "variant_allele": "G",
             "function": "normal_function", "activity_score": None},
        ]
        user = {
            "rs1801280": ("T", "C"),  # 1 slow
            "rs1799930": ("G", "A"),  # 1 slow
            "rs1208": ("A", "G"),     # rapid tag — should not count
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "NAT2", "count", "*4", defs, user
        )
        assert detected[0][2] == 2  # 2 slow alleles
        assert n_tested == 3

    def test_nat2_intermediate_acetylator(self):
        """NAT2 *4/*5B — one slow allele + rapid *11 tag → Intermediate.

        *5B carries rs1801280 (I114T, slow) and rs1799929 (481C>T, L161L,
        synonymous *11 rapid tag) on the same chromosome.  rs1799929 has
        normal_function (*11 = rapid acetylator) and is skipped by the
        slow count.  Only rs1801280 counts → 1 slow → Intermediate.
        """
        defs = [
            {"star_allele": "*5", "rsid": "rs1801280", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*11", "rsid": "rs1799929", "variant_allele": "T",
             "function": "normal_function", "activity_score": None},
            {"star_allele": "*12", "rsid": "rs1208", "variant_allele": "G",
             "function": "normal_function", "activity_score": None},
        ]
        user = {
            "rs1801280": ("T", "C"),  # het — 1 copy of *5 slow variant
            "rs1799929": ("C", "T"),  # het — *11 rapid tag, skipped
            "rs1208": ("G", "A"),     # rapid tag — skipped
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "NAT2", "count", "*4", defs, user
        )
        # Only *5 (rs1801280) counts as slow; *11 is normal_function
        assert detected[0][2] == 1
        assert n_tested == 3

    def test_nat2_single_slow_allele_multi_snp(self):
        """NAT2 — one slow allele defined by two SNPs, both het → still 1.

        When a single star-allele is defined by multiple SNPs (e.g. if *5
        had two defining variants), heterozygous at both should count as
        only 1 slow chromosome, not 2.
        """
        defs = [
            {"star_allele": "*5", "rsid": "rs1801280", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*5", "rsid": "rs_fake_5b", "variant_allele": "A",
             "function": "no_function", "activity_score": None},
        ]
        user = {
            "rs1801280": ("T", "C"),  # het
            "rs_fake_5b": ("G", "A"),  # het
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "NAT2", "count", "*4", defs, user
        )
        # Both SNPs belong to *5 → per-allele max = 1, total = 1
        assert detected[0][2] == 1

    def test_nat2_homozygous_slow(self):
        """NAT2 *5/*5 — homozygous slow → 2."""
        defs = [
            {"star_allele": "*5", "rsid": "rs1801280", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*6", "rsid": "rs1799930", "variant_allele": "A",
             "function": "no_function", "activity_score": None},
        ]
        user = {
            "rs1801280": ("C", "C"),  # hom slow
            "rs1799930": ("G", "G"),  # ref
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "NAT2", "count", "*4", defs, user
        )
        assert detected[0][2] == 2

    def test_nat2_rapid_acetylator(self):
        """NAT2 — 0 slow variants → Rapid."""
        defs = [
            {"star_allele": "*5", "rsid": "rs1801280", "variant_allele": "C",
             "function": "no_function", "activity_score": None},
            {"star_allele": "*6", "rsid": "rs1799930", "variant_allele": "A",
             "function": "no_function", "activity_score": None},
        ]
        user = {
            "rs1801280": ("T", "T"),
            "rs1799930": ("G", "G"),
        }

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "NAT2", "count", "*4", defs, user
        )
        assert detected[0][2] == 0


# ---------------------------------------------------------------------------
# Diplotype assignment tests
# ---------------------------------------------------------------------------

class TestAssignDiplotype:
    def test_homozygous_variant(self):
        """CYP2D6 *4/*4 from 2 copies of *4."""
        detected = [("*4", "no_function", 2)]
        defs = [{"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
                 "function": "no_function", "activity_score": 0}]

        a1, a2, f1, f2, score = assign_diplotype("CYP2D6", "activity_score", "*1", detected, defs)
        assert a1 == "*4"
        assert a2 == "*4"
        assert f1 == "no_function"
        assert score == 0.0

    def test_heterozygous_variant(self):
        """CYP2D6 *1/*4 from 1 copy of *4."""
        detected = [("*4", "no_function", 1)]
        defs = [{"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
                 "function": "no_function", "activity_score": 0}]

        a1, a2, f1, f2, score = assign_diplotype("CYP2D6", "activity_score", "*1", detected, defs)
        assert {a1, a2} == {"*1", "*4"}
        assert score == 1.0  # *1 (1.0) + *4 (0)

    def test_wild_type(self):
        """CYP2D6 *1/*1 — no variants detected."""
        detected = []
        defs = []

        a1, a2, f1, f2, score = assign_diplotype("CYP2D6", "activity_score", "*1", detected, defs)
        assert a1 == "*1"
        assert a2 == "*1"
        assert score == 2.0

    def test_two_different_alleles(self):
        """CYP2C19 *2/*17 — compound heterozygote."""
        detected = [
            ("*2", "no_function", 1),
            ("*17", "increased_function", 1),
        ]
        defs = [
            {"star_allele": "*2", "rsid": "rs4244285", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
            {"star_allele": "*17", "rsid": "rs12248560", "variant_allele": "T",
             "function": "increased_function", "activity_score": 2.0},
        ]

        a1, a2, f1, f2, score = assign_diplotype("CYP2C19", "activity_score", "*1", detected, defs)
        assert {a1, a2} == {"*2", "*17"}
        assert score == 2.0  # *2 (0) + *17 (2.0)

    def test_binary_positive(self):
        detected = [("positive", "risk", 1)]
        a1, a2, f1, f2, score = assign_diplotype("HLA-B_5701", "binary", "negative", detected, [])
        assert a1 == "positive"
        assert a2 == "negative"

    def test_binary_negative(self):
        detected = [("negative", "normal_function", 0)]
        a1, a2, f1, f2, score = assign_diplotype("HLA-B_5701", "binary", "negative", detected, [])
        assert a1 == "negative"
        assert a2 == "negative"

    def test_count_slow(self):
        detected = [("count", "count", 3)]
        a1, a2, f1, f2, score = assign_diplotype("NAT2", "count", "*4", detected, [])
        assert a1 == "slow"
        assert a2 == "slow"

    def test_count_rapid(self):
        detected = [("count", "count", 0)]
        a1, a2, f1, f2, score = assign_diplotype("NAT2", "count", "*4", detected, [])
        assert a1 == "rapid"
        assert a2 == "rapid"


# ---------------------------------------------------------------------------
# Integration-style test with full gene calling
# ---------------------------------------------------------------------------

class TestFullGeneCalling:
    """End-to-end star allele calling → diplotype → phenotype."""

    def test_cyp2d6_poor_metabolizer_full(self):
        """CYP2D6 *4/*4 → activity score 0 → PM."""
        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
            {"star_allele": "*10", "rsid": "rs1065852", "variant_allele": "T",
             "function": "decreased_function", "activity_score": 0.25},
        ]
        user = {"rs3892097": ("A", "A"), "rs1065852": ("C", "C")}

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2D6", "activity_score", "*1", defs, user
        )
        a1, a2, f1, f2, score = assign_diplotype("CYP2D6", "activity_score", "*1", detected, defs)

        assert a1 == "*4" and a2 == "*4"
        assert score == 0.0
        assert _score_to_phenotype("CYP2D6", score) == "Poor Metabolizer"

    def test_cyp2d6_intermediate_metabolizer(self):
        """CYP2D6 *1/*10 → activity score 1.25 → NM (score >= 1.0)."""
        defs = [
            {"star_allele": "*10", "rsid": "rs1065852", "variant_allele": "T",
             "function": "decreased_function", "activity_score": 0.25},
        ]
        user = {"rs1065852": ("C", "T")}

        detected, _, _ = call_star_alleles_for_gene("CYP2D6", "activity_score", "*1", defs, user)
        a1, a2, f1, f2, score = assign_diplotype("CYP2D6", "activity_score", "*1", detected, defs)

        assert score == 1.25  # *1 (1.0) + *10 (0.25)
        assert _score_to_phenotype("CYP2D6", score) == "Normal Metabolizer"

    def test_cyp2d6_im_with_null_and_decreased(self):
        """CYP2D6 *4/*41 → activity score 0.5 → IM."""
        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
            {"star_allele": "*41", "rsid": "rs28371725", "variant_allele": "A",
             "function": "decreased_function", "activity_score": 0.5},
        ]
        user = {"rs3892097": ("G", "A"), "rs28371725": ("G", "A")}

        detected, _, _ = call_star_alleles_for_gene("CYP2D6", "activity_score", "*1", defs, user)
        a1, a2, f1, f2, score = assign_diplotype("CYP2D6", "activity_score", "*1", detected, defs)

        assert {a1, a2} == {"*4", "*41"}
        assert score == 0.5  # *4 (0) + *41 (0.5)
        assert _score_to_phenotype("CYP2D6", score) == "Intermediate Metabolizer"

    def test_dpyd_life_threatening(self):
        """DPYD *2A homozygous → score 0 → PM (LIFE-THREATENING with 5-FU)."""
        defs = [
            {"star_allele": "*2A", "rsid": "rs3918290", "variant_allele": "T",
             "function": "no_function", "activity_score": 0},
        ]
        user = {"rs3918290": ("T", "T")}

        detected, _, _ = call_star_alleles_for_gene("DPYD", "activity_score", "*1", defs, user)
        _, _, _, _, score = assign_diplotype("DPYD", "activity_score", "*1", detected, defs)

        assert score == 0.0
        assert _score_to_phenotype("DPYD", score) == "Poor Metabolizer"


# ---------------------------------------------------------------------------
# Position-based PGx supplement tests
# ---------------------------------------------------------------------------

class TestPgxPositionLookup:
    """Test the position-based genotype supplement for VCF data."""

    def test_load_pgx_positions(self):
        """Stargazer alleles should load a non-empty rsid→(chrom, pos) mapping."""
        positions = _load_pgx_positions()
        # stargazer_alleles.json should have ~1333 variants
        assert len(positions) > 100
        # Check that values are tuples of (str, int)
        for rsid, (chrom, pos) in list(positions.items())[:5]:
            assert isinstance(rsid, str)
            assert rsid.startswith("rs")
            assert isinstance(chrom, str)
            assert isinstance(pos, int)

    def test_position_supplements_user_lookup(self):
        """Simulate how match_pgx supplements user_lookup by position for GRCh38 VCFs."""
        # Load real PGx positions
        pgx_positions = _load_pgx_positions()
        if not pgx_positions:
            pytest.skip("stargazer_alleles.json not found")

        # Pick a real PGx variant
        sample_rsid = next(iter(pgx_positions))
        sample_chrom, sample_pos = pgx_positions[sample_rsid]

        # Build a user_df where the variant is at the right position but has "." rsid
        user_df = pl.DataFrame(
            [{"rsid": ".", "chrom": sample_chrom, "position": sample_pos,
              "allele1": "A", "allele2": "G"}],
            schema={"rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64,
                    "allele1": pl.Utf8, "allele2": pl.Utf8},
        )

        # Build user_lookup (empty — no rsid matches)
        user_lookup: dict[str, tuple[str, str]] = {}

        # Simulate the position-based supplement from match_pgx
        needed = {rsid: pos for rsid, pos in pgx_positions.items() if rsid not in user_lookup}
        lookup_df = pl.DataFrame(
            {
                "pgx_rsid": list(needed.keys()),
                "chrom": [v[0] for v in needed.values()],
                "position": [v[1] for v in needed.values()],
            },
            schema={"pgx_rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64},
        )
        matched = user_df.join(lookup_df, on=["chrom", "position"], how="inner")

        for row in matched.select("pgx_rsid", "allele1", "allele2").iter_rows():
            user_lookup[row[0]] = (row[1], row[2])

        # The sample variant should now be in user_lookup
        assert sample_rsid in user_lookup
        assert user_lookup[sample_rsid] == ("A", "G")

    def test_star_allele_calling_with_position_supplement(self):
        """Position-supplemented genotypes should enable star allele calling."""
        # CYP2D6 *4 is defined by rs3892097 variant allele "A"
        pgx_positions = _load_pgx_positions()
        if "rs3892097" not in pgx_positions:
            pytest.skip("rs3892097 not in stargazer positions")

        # Simulate a user_lookup built via position supplement
        user_lookup = {"rs3892097": ("G", "A")}  # heterozygous

        defs = [
            {"star_allele": "*4", "rsid": "rs3892097", "variant_allele": "A",
             "function": "no_function", "activity_score": 0},
        ]

        detected, n_tested, n_total = call_star_alleles_for_gene(
            "CYP2D6", "activity_score", "*1", defs, user_lookup
        )

        # Should detect *4 with 1 copy
        assert len(detected) == 1
        assert detected[0][0] == "*4"
        assert detected[0][2] == 1  # 1 copy

    def test_load_pgx_positions_grch37(self):
        """GRCh37 positions should differ from GRCh38 for most variants."""
        # Clear cache so both builds load fresh
        pgx_mod._PGX_POS_CACHE.clear()

        pos37 = _load_pgx_positions("GRCh37")
        pos38 = _load_pgx_positions("GRCh38")
        assert len(pos37) > 100
        assert len(pos38) > 100
        # GRCh37 and GRCh38 coordinates differ for most loci
        differ_count = 0
        for rsid in pos37:
            if rsid in pos38 and pos37[rsid] != pos38[rsid]:
                differ_count += 1
        assert differ_count > 50, f"Only {differ_count} variants differ between builds"

        # Spot-check CYP2D6 rs3892097 (well-known, verified positions)
        if "rs3892097" in pos37 and "rs3892097" in pos38:
            assert pos37["rs3892097"][1] == 42524947  # GRCh37
            assert pos38["rs3892097"][1] == 42128945  # GRCh38

    def test_load_pgx_ref_alleles(self):
        """Ref allele mapping should cover all positioned variants."""
        pgx_mod._PGX_REF_CACHE = None
        ref_map = _load_pgx_ref_alleles()
        positions = _load_pgx_positions()
        assert len(ref_map) > 100
        # Every positioned variant should have a ref allele
        for rsid in positions:
            assert rsid in ref_map, f"{rsid} in positions but missing ref allele"
            assert isinstance(ref_map[rsid], str)
            assert len(ref_map[rsid]) >= 1

    def test_vcf_ref_imputation(self):
        """VCF mode should impute ref/ref for absent PGx positions."""
        pgx_mod._PGX_REF_CACHE = None
        ref_alleles = _load_pgx_ref_alleles()
        pgx_positions = _load_pgx_positions()
        if not pgx_positions or not ref_alleles:
            pytest.skip("stargazer data not available")

        # Simulate empty user_lookup (VCF with no PGx variants present)
        user_lookup: dict[str, tuple[str, str]] = {}

        # Replicate the ref/ref imputation from match_pgx lines 511-520
        imputed = 0
        for rsid in pgx_positions:
            if rsid not in user_lookup and rsid in ref_alleles:
                ref = ref_alleles[rsid]
                user_lookup[rsid] = (ref, ref)
                imputed += 1

        assert imputed > 100
        # Spot-check: rs3892097 should be imputed as ref/ref
        if "rs3892097" in user_lookup:
            a1, a2 = user_lookup["rs3892097"]
            assert a1 == a2  # homozygous reference

    def test_position_supplements_user_lookup_grch37(self):
        """Position-based supplement should work with GRCh37 coordinates."""
        pgx_mod._PGX_POS_CACHE.clear()
        pgx_positions = _load_pgx_positions("GRCh37")
        if not pgx_positions:
            pytest.skip("stargazer_alleles.json not found")

        sample_rsid = next(iter(pgx_positions))
        sample_chrom, sample_pos = pgx_positions[sample_rsid]

        user_df = pl.DataFrame(
            [{"rsid": ".", "chrom": sample_chrom, "position": sample_pos,
              "allele1": "C", "allele2": "T"}],
            schema={"rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64,
                    "allele1": pl.Utf8, "allele2": pl.Utf8},
        )

        user_lookup: dict[str, tuple[str, str]] = {}
        needed = {rsid: pos for rsid, pos in pgx_positions.items() if rsid not in user_lookup}
        lookup_df = pl.DataFrame(
            {"pgx_rsid": list(needed.keys()),
             "chrom": [v[0] for v in needed.values()],
             "position": [v[1] for v in needed.values()]},
            schema={"pgx_rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64},
        )
        matched = user_df.join(lookup_df, on=["chrom", "position"], how="inner")
        for row in matched.select("pgx_rsid", "allele1", "allele2").iter_rows():
            user_lookup[row[0]] = (row[1], row[2])

        assert sample_rsid in user_lookup
        assert user_lookup[sample_rsid] == ("C", "T")


# ---------------------------------------------------------------------------
# VCF binary gene ref/ref inference
# ---------------------------------------------------------------------------

class TestVcfBinaryGeneInference:
    """Binary/count/simple genes with 0 tested variants should still produce
    results when processing VCF data, since absence = reference genotype."""

    def test_binary_gene_negative_when_no_variants(self):
        """A binary gene with no user variants → Negative (Non-carrier)."""
        from app.services.pgx_matcher import _call_binary

        # Empty user_lookup: VCF had no reads at this position
        user_lookup: dict[str, tuple[str, str]] = {}
        defs_by_allele = {
            "*1": [{"rsid": "rs2395029", "variant_allele": "G",
                     "function": "risk", "activity_score": None}],
        }

        detected, n_tested, n_total = _call_binary(defs_by_allele, user_lookup, 0, 1)

        assert detected == [("negative", "normal_function", 0)]
        assert n_tested == 0

    def test_binary_diplotype_assignment_negative(self):
        """assign_diplotype for a binary gene with no detected alleles."""
        detected: list[tuple[str, str, int]] = [("negative", "normal_function", 0)]
        defs = [{"star_allele": "*1", "rsid": "rs2395029", "variant_allele": "G",
                 "function": "risk", "activity_score": None}]

        a1, a2, a1_func, a2_func, act_score = assign_diplotype(
            "HLA-B_5701", "binary", "negative", detected, defs
        )

        assert a1 == "negative"
        assert a1_func == "normal_function"
        assert act_score is None  # binary genes don't use activity scores

    def test_simple_gene_defaults_to_reference_when_empty(self):
        """A simple gene with no detected variants → default allele (ref/ref)."""
        detected: list[tuple[str, str, int]] = []
        defs = [{"star_allele": "Val", "rsid": "rs4680", "variant_allele": "A",
                 "function": "decreased_function", "activity_score": None}]

        a1, a2, a1_func, a2_func, act_score = assign_diplotype(
            "COMT", "simple", "Val", detected, defs
        )

        # Both alleles should be the default (reference)
        assert a1 == "Val"
        assert a2 == "Val"
        assert a1_func == "normal_function"
        assert a2_func == "normal_function"

    def test_vcf_binary_gene_n_tested_equals_n_total(self):
        """For VCF input, binary genes should report n_tested = n_total.

        In WGS VCFs, absence of a position means homozygous reference,
        so all positions are effectively assessed. The n_tested override
        happens in match_pgx after call_star_alleles_for_gene returns.
        """
        from app.services.pgx_matcher import _call_binary

        user_lookup: dict[str, tuple[str, str]] = {}
        defs_by_allele = {
            "*1": [
                {"rsid": "rs1061235", "variant_allele": "A",
                 "function": "risk", "activity_score": None},
                {"rsid": "rs2571375", "variant_allele": "A",
                 "function": "risk", "activity_score": None},
            ],
        }

        detected, n_tested, n_total = _call_binary(defs_by_allele, user_lookup, 0, 2)

        # _call_binary itself returns n_tested=0 (raw count from caller)
        assert detected == [("negative", "normal_function", 0)]
        assert n_tested == 0
        assert n_total == 2

        # Simulate the VCF override that match_pgx applies
        is_vcf = True
        calling_method = "binary"
        if is_vcf and calling_method in ("binary", "count", "simple"):
            n_tested = n_total

        assert n_tested == 2
        assert _compute_confidence(n_tested, n_total) == "high"
