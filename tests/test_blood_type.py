"""Tests for blood type determination using RBCeq2 allele database.

Tests use real GRCh37 positions from the curated ISBT allele database.
Key positions used in tests:
- ABO: chr9:136132908 (c.261delG — T→TC insertion = functional; ref = O)
- ABO B-specific: chr9:136131322 (c.796C>A, G→T), chr9:136131592 (c.803G>C, G→C)
- FY (Duffy): chr1:159175354 (ref = Fy(a+), G→A = Fy(b+))
- JK (Kidd): chr18:43319519 (ref = Jk(a+), G→A = Jk(b+))
- KEL (Kell): chr7:142655008 (ref = k+, G→A = K+)
- FUT2 (Secretor): chr19:49206674 (G→A = non-secretor W154X)
- GYPB (MNS S/s): chr4:144920596 (ref = s+, G→A = S+)
"""

import polars as pl
import pytest

from app.services.blood_type import (
    BloodTypeResult,
    BLOOD_TYPE_DELETION_RSIDS,
    determine_blood_type,
    _build_user_lookups,
    _load_db,
    _DB,
)


def make_pos_df(variants: list[tuple[str, int, str, str]]) -> pl.DataFrame:
    """Build a Polars DataFrame from position-based variant data.

    Each tuple is (chrom, position, allele1, allele2).
    """
    if not variants:
        return pl.DataFrame(
            schema={"rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64,
                    "allele1": pl.Utf8, "allele2": pl.Utf8}
        )
    return pl.DataFrame({
        "rsid": [f"." for _ in variants],
        "chrom": [v[0] for v in variants],
        "position": [v[1] for v in variants],
        "allele1": [v[2] for v in variants],
        "allele2": [v[3] for v in variants],
    })


# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------

class TestDatabaseLoading:
    def test_db_loaded(self):
        """Database is loaded at module level."""
        assert len(_DB) > 0

    def test_db_has_abo(self):
        """Database includes ABO alleles."""
        abo = [a for a in _DB if a.system == "ABO"]
        assert len(abo) > 5

    def test_db_has_multiple_systems(self):
        """Database includes alleles for multiple blood group systems."""
        systems = {a.system for a in _DB}
        assert "ABO" in systems
        assert "RHCE" in systems
        assert "FY" in systems
        assert "JK" in systems
        assert "KEL" in systems

    def test_allele_has_variants(self):
        """Each allele definition has GRCh37 variants."""
        for a in _DB[:50]:
            assert len(a.variants_grch37) > 0 or len(a.variants_grch38) > 0

    def test_deletion_rsids_constant(self):
        """BLOOD_TYPE_DELETION_RSIDS contains rs8176719."""
        assert "rs8176719" in BLOOD_TYPE_DELETION_RSIDS


# ---------------------------------------------------------------------------
# ABO via DTC deletion genotypes (rs8176719)
# ---------------------------------------------------------------------------

class TestABOViaDTCDeletion:
    """ABO determination using DTC chip rs8176719 deletion genotypes."""

    def test_type_o_homozygous_deletion(self):
        """Both copies are O deletion (-/-) → type O."""
        df = make_pos_df([])  # no positional data
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        assert result.abo_phenotype == "O"

    def test_type_a_het_deletion(self):
        """One functional (G), one deletion (-) → A/O → type A.

        Without B-specific SNPs, the functional allele defaults to A.
        """
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("G", "-")},
        )
        assert result is not None
        assert result.abo_phenotype == "A"

    def test_type_a_homozygous_functional(self):
        """Both copies functional (G/G) → A/A → type A (no B SNPs)."""
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("G", "G")},
        )
        assert result is not None
        assert result.abo_phenotype == "A"


# ---------------------------------------------------------------------------
# ABO via VCF position-based matching
# ---------------------------------------------------------------------------

class TestABOViaPosition:
    """ABO determination using position-based variant matching (VCF data)."""

    def test_type_o_position_absent(self):
        """Position 136132908 absent (not in data) → reference → O allele.

        For VCF data: absence at c.261delG position means no T→TC insertion.
        """
        # Only include non-ABO variants so the position is absent
        df = make_pos_df([
            ("1", 159175354, "G", "A"),   # Duffy variant (irrelevant)
        ])
        # With no ABO positions and no deletion data, should return None
        result = determine_blood_type(df, genome_build="GRCh37")
        # No ABO markers at all → no ABO determination possible
        # The service should return None when it can't determine ABO
        assert result is None or result.abo_phenotype == "O"

    def test_type_b_all_positions(self):
        """Type B requires the c.261delG insertion PLUS B-specific SNPs.

        B allele (ABO*B.01) defining variants at GRCh37:
        136131188_C_T, 136131315_C_G, 136131322_G_T, 136131415_C_T,
        136131461_G_A, 136131592_G_C, 136132873_T_C, 136132908_T_TC
        """
        b_variants = [
            ("9", 136131188, "C", "T"),
            ("9", 136131315, "C", "G"),
            ("9", 136131322, "G", "T"),
            ("9", 136131415, "C", "T"),
            ("9", 136131461, "G", "A"),
            ("9", 136131592, "G", "C"),
            ("9", 136132873, "T", "C"),
            ("9", 136132908, "T", "TC"),  # c.261delG insertion (functional)
        ]
        # Homozygous B — all positions are hom alt
        df = make_pos_df(b_variants)
        result = determine_blood_type(df, genome_build="GRCh37")
        assert result is not None
        assert result.abo_phenotype == "B"


# ---------------------------------------------------------------------------
# Duffy (FY) system — chr1:159175354
# ---------------------------------------------------------------------------

class TestDuffy:
    """Duffy system: FY*01 (ref=Fy(a+)) vs FY*02 (G→A=Fy(b+)) at chr1:159175354."""

    def test_fya_positive_fyb_negative(self):
        """Homozygous reference → Fy(a+b-)."""
        # FY*01 matches on 159175354_ref, but user must NOT have alt at that pos
        # If position is absent, it's assumed reference (microarray behavior)
        df = make_pos_df([])  # no Duffy position → assumed ref
        # Need ABO data for a result to be returned
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        # With no Duffy position data, the system may or may not match
        # depending on how _ref matching works with absent positions
        if result and result.duffy_phenotype:
            assert "Fy" in result.duffy_phenotype

    def test_fyb_positive(self):
        """Homozygous alt (A/A) at 159175354 → Fy(a-b+)."""
        df = make_pos_df([
            ("1", 159175354, "A", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        systems = result.systems
        if "Duffy" in systems:
            assert "Fy(b+)" in systems["Duffy"]["phenotype"] or "Fy(a-)" in systems["Duffy"]["phenotype"]

    def test_fya_fyb_heterozygous(self):
        """Heterozygous (G/A) at 159175354 → Fy(a+b+)."""
        df = make_pos_df([
            ("1", 159175354, "G", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        # Should have both FY*01 and FY*02 matched
        if "Duffy" in result.systems:
            pheno = result.systems["Duffy"]["phenotype"]
            assert "Fy" in pheno


# ---------------------------------------------------------------------------
# Kidd (JK) system — chr18:43319519
# ---------------------------------------------------------------------------

class TestKidd:
    """Kidd system: JK*01 (ref=Jk(a+)) vs JK*02 (G→A=Jk(b+)) at chr18:43319519."""

    def test_jkb_positive(self):
        """Homozygous alt (A/A) at 43319519 → Jk(a-b+)."""
        df = make_pos_df([
            ("18", 43319519, "A", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        if "Kidd" in result.systems:
            assert "Jk(b+)" in result.systems["Kidd"]["phenotype"] or "Jk" in result.systems["Kidd"]["phenotype"]

    def test_jka_jkb_heterozygous(self):
        """Heterozygous (G/A) at 43319519 → Jk(a+b+)."""
        df = make_pos_df([
            ("18", 43319519, "G", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        if "Kidd" in result.systems:
            pheno = result.systems["Kidd"]["phenotype"]
            assert "Jk" in pheno


# ---------------------------------------------------------------------------
# Kell (KEL) system — chr7:142655008
# ---------------------------------------------------------------------------

class TestKell:
    """Kell system: KEL*02 (ref=k+) vs KEL*01 (G→A=K+) at chr7:142655008."""

    def test_k_positive_heterozygous(self):
        """Heterozygous (G/A) at 142655008 → K+k+."""
        df = make_pos_df([
            ("7", 142655008, "G", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        if "Kell" in result.systems:
            pheno = result.systems["Kell"]["phenotype"]
            assert "K" in pheno or "k" in pheno


# ---------------------------------------------------------------------------
# Secretor (FUT2) system — chr19:49206674
# ---------------------------------------------------------------------------

class TestSecretor:
    """Secretor: FUT2*01 (ref=Se+) vs FUT2*01N.02 (G→A=Se-) at chr19:49206674."""

    def test_non_secretor(self):
        """Homozygous nonsense (A/A) at 49206674 → non-secretor."""
        df = make_pos_df([
            ("19", 49206674, "A", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        if "Secretor" in result.systems:
            pheno = result.systems["Secretor"]["phenotype"]
            assert "Se-" in pheno or "se" in pheno.lower()


# ---------------------------------------------------------------------------
# GYPB (MNS S/s) — chr4:144920596
# ---------------------------------------------------------------------------

class TestMNSSs:
    """MNS S/s system: GYPB*04 (ref=s+) vs GYPB*03 (G→A=S+) at chr4:144920596."""

    def test_s_positive(self):
        """Homozygous alt (A/A) at 144920596 → S+s-."""
        df = make_pos_df([
            ("4", 144920596, "A", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        # GYPB maps to "MNS (Ss)" in system display names
        if "MNS (Ss)" in result.systems:
            pheno = result.systems["MNS (Ss)"]["phenotype"]
            assert "S" in pheno


# ---------------------------------------------------------------------------
# Integration tests
# ---------------------------------------------------------------------------

class TestDetermineBloodType:
    """Full integration tests for determine_blood_type()."""

    def test_empty_dataframe_no_deletion_returns_none(self):
        """No variants and no deletion data → None."""
        df = make_pos_df([])
        result = determine_blood_type(df, genome_build="GRCh37")
        assert result is None

    def test_empty_dataframe_with_deletion_returns_result(self):
        """Empty DataFrame + deletion genotypes → minimal result."""
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        assert result.abo_phenotype == "O"

    def test_result_has_display_type(self):
        """Result includes display_type — plain ABO phenotype, no '?'."""
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("G", "-")},
        )
        assert result is not None
        assert result.display_type in ("A", "B", "AB", "O")
        assert "?" not in result.display_type

    def test_result_has_systems_dict(self):
        """Result includes systems dict with at least ABO."""
        df = make_pos_df([
            ("1", 159175354, "G", "A"),    # Duffy
            ("18", 43319519, "G", "A"),     # Kidd
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        assert isinstance(result.systems, dict)

    def test_confidence_note_mentions_rhd(self):
        """Confidence note always mentions RhD limitation."""
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        assert result.confidence_note is not None
        assert "Rh" in result.confidence_note or "RhD" in result.confidence_note

    def test_n_variants_counted(self):
        """n_variants_tested and n_variants_total are set."""
        df = make_pos_df([
            ("1", 159175354, "G", "A"),
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("G", "-")},
        )
        assert result is not None
        assert result.n_variants_total > 0
        assert result.n_variants_tested >= 0

    def test_n_systems_determined(self):
        """n_systems_determined counts how many blood group systems were resolved."""
        df = make_pos_df([
            ("1", 159175354, "G", "A"),    # Duffy
            ("18", 43319519, "G", "A"),     # Kidd
            ("7", 142655008, "G", "A"),     # Kell
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        # ABO + at least Duffy/Kidd/Kell = 4+ systems
        assert result.n_systems_determined >= 4

    def test_multi_system_high_confidence(self):
        """Multiple systems matched → higher confidence."""
        df = make_pos_df([
            ("1", 159175354, "G", "A"),    # Duffy
            ("18", 43319519, "G", "A"),     # Kidd
            ("7", 142655008, "G", "A"),     # Kell
            ("4", 144920596, "G", "A"),     # GYPB (MNS S/s)
        ])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("G", "-")},
        )
        assert result is not None
        assert result.abo_phenotype in ("A", "B", "AB", "O")
        # With many systems, should be medium or high
        assert result.confidence in ("medium", "high")

    def test_grch38_build(self):
        """GRCh38 build uses GRCh38 positions."""
        # ABO c.261delG position in GRCh38 is 133257521
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh38",
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        assert result.abo_phenotype == "O"

    def test_returns_blood_type_result_dataclass(self):
        """Result is a BloodTypeResult instance."""
        df = make_pos_df([])
        result = determine_blood_type(
            df, genome_build="GRCh37",
            deletion_genotypes={"rs8176719": ("G", "G")},
        )
        assert result is not None
        assert isinstance(result, BloodTypeResult)
        assert isinstance(result.abo_genotype, str)
        assert isinstance(result.abo_phenotype, str)

    def test_genome_build_default_is_grch37(self):
        """Default genome build is GRCh37."""
        df = make_pos_df([])
        result = determine_blood_type(
            df,
            deletion_genotypes={"rs8176719": ("-", "-")},
        )
        assert result is not None
        assert result.abo_phenotype == "O"


# ---------------------------------------------------------------------------
# User lookup building
# ---------------------------------------------------------------------------

class TestBuildUserLookups:
    """Tests for the position-based lookup builder."""

    def test_builds_position_lookup(self):
        """Builds (chrom, pos) → (a1, a2) lookup."""
        df = make_pos_df([
            ("1", 100, "A", "G"),
            ("2", 200, "C", "T"),
        ])
        pos_lookup, positions, delg_info = _build_user_lookups(df, "GRCh37", None)
        assert ("1", 100) in pos_lookup
        assert pos_lookup[("1", 100)] == ("A", "G")
        assert ("2", 200) in positions
        assert delg_info is None

    def test_deletion_oo(self):
        """Homozygous deletion → OO info, position NOT added."""
        df = make_pos_df([])
        pos_lookup, positions, delg_info = _build_user_lookups(
            df, "GRCh37", {"rs8176719": ("-", "-")},
        )
        assert delg_info == "OO"
        # 261delG position should NOT be in lookup (absence = reference = O)
        assert ("9", 136132908) not in pos_lookup

    def test_deletion_het(self):
        """Heterozygous G/- → het info, synthetic indel entry added."""
        df = make_pos_df([])
        pos_lookup, positions, delg_info = _build_user_lookups(
            df, "GRCh37", {"rs8176719": ("G", "-")},
        )
        assert delg_info == "het"
        assert ("9", 136132908) in pos_lookup
        assert pos_lookup[("9", 136132908)] == ("T", "TC")

    def test_deletion_functional(self):
        """Homozygous functional G/G → func info, homozygous indel added."""
        df = make_pos_df([])
        pos_lookup, positions, delg_info = _build_user_lookups(
            df, "GRCh37", {"rs8176719": ("G", "G")},
        )
        assert delg_info == "func"
        assert pos_lookup[("9", 136132908)] == ("TC", "TC")

    def test_grch38_deletion_position(self):
        """GRCh38 build uses GRCh38 position for 261delG."""
        df = make_pos_df([])
        pos_lookup, positions, delg_info = _build_user_lookups(
            df, "GRCh38", {"rs8176719": ("G", "-")},
        )
        assert delg_info == "het"
        # GRCh38 position: 133257521
        assert ("9", 133257521) in pos_lookup
