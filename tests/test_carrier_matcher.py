"""Tests for carrier status screening service.

Tests cover panel loading, allele counting, and classification logic
across all status categories: not_detected, carrier, likely_affected,
and potential_compound_het.
"""

import polars as pl
import pytest

from app.services.carrier_matcher import (
    CarrierGeneResult,
    CarrierVariantResult,
    _complement,
    _count_allele,
    _load_panel,
    _resolve_alleles,
    determine_carrier_status,
)


def make_df(variants: list[tuple[str, str, str, str]], positions: list[int] | None = None) -> pl.DataFrame:
    """Build a Polars DataFrame from (rsid, chrom, allele1, allele2) tuples.

    Optional positions list overrides the default position of 0.
    """
    if not variants:
        return pl.DataFrame(
            schema={
                "rsid": pl.Utf8,
                "chrom": pl.Utf8,
                "position": pl.Int64,
                "allele1": pl.Utf8,
                "allele2": pl.Utf8,
            }
        )
    return pl.DataFrame(
        {
            "rsid": [v[0] for v in variants],
            "chrom": [v[1] for v in variants],
            "position": positions if positions else [0 for _ in variants],
            "allele1": [v[2] for v in variants],
            "allele2": [v[3] for v in variants],
        }
    )


# ---------------------------------------------------------------------------
# Panel loading
# ---------------------------------------------------------------------------


class TestPanelLoading:
    def test_panel_loads(self):
        panel = _load_panel()
        assert "genes" in panel
        assert len(panel["genes"]) > 0

    def test_panel_has_expected_genes(self):
        panel = _load_panel()
        gene_names = {g["gene"] for g in panel["genes"]}
        assert "HFE" in gene_names
        assert "GJB2" in gene_names
        assert "HBB" in gene_names

    def test_panel_genes_have_variants(self):
        panel = _load_panel()
        for gene in panel["genes"]:
            assert len(gene["variants"]) > 0, f"{gene['gene']} has no variants"
            for v in gene["variants"]:
                assert "rsid" in v
                assert "pathogenic_allele" in v

    def test_panel_has_conditions_not_screenable(self):
        panel = _load_panel()
        assert "conditions_not_screenable" in panel
        assert len(panel["conditions_not_screenable"]) >= 2


# ---------------------------------------------------------------------------
# Allele counting
# ---------------------------------------------------------------------------


class TestCountAllele:
    def test_simple_het(self):
        assert _count_allele("AG", "A") == 1

    def test_simple_hom(self):
        assert _count_allele("AA", "A") == 2

    def test_no_match(self):
        assert _count_allele("GG", "A") == 0

    def test_missing_genotype(self):
        assert _count_allele("--", "A") == 0
        assert _count_allele("00", "A") == 0
        assert _count_allele("NC", "A") == 0
        assert _count_allele("", "A") == 0

    def test_none_genotype(self):
        assert _count_allele(None, "A") == 0


# ---------------------------------------------------------------------------
# Carrier status determination — HFE (well-represented on arrays)
# ---------------------------------------------------------------------------


class TestHFECarrier:
    """HFE: C282Y (rs1800562, pathogenic allele = A) and H63D (rs1799945, pathogenic allele = G)."""

    def test_no_hfe_variants(self):
        """User has reference alleles for both HFE variants → not_detected."""
        df = make_df([
            ("rs1800562", "6", "G", "G"),  # C282Y ref/ref
            ("rs1799945", "6", "C", "C"),  # H63D ref/ref
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "not_detected"
        assert hfe.total_pathogenic_alleles == 0
        assert len(hfe.variants_detected) == 0

    def test_c282y_carrier(self):
        """Heterozygous C282Y → carrier."""
        df = make_df([
            ("rs1800562", "6", "G", "A"),  # C282Y het
            ("rs1799945", "6", "C", "C"),  # H63D ref/ref
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"
        assert hfe.total_pathogenic_alleles == 1
        assert len(hfe.variants_detected) == 1
        assert hfe.variants_detected[0].rsid == "rs1800562"
        assert hfe.variants_detected[0].pathogenic_allele_count == 1

    def test_c282y_homozygous(self):
        """Homozygous C282Y → likely_affected."""
        df = make_df([
            ("rs1800562", "6", "A", "A"),  # C282Y hom
            ("rs1799945", "6", "C", "C"),  # H63D ref/ref
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "likely_affected"
        assert hfe.total_pathogenic_alleles == 2

    def test_compound_het_c282y_h63d(self):
        """Het C282Y + Het H63D → potential_compound_het."""
        df = make_df([
            ("rs1800562", "6", "G", "A"),  # C282Y het
            ("rs1799945", "6", "C", "G"),  # H63D het
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "potential_compound_het"
        assert hfe.total_pathogenic_alleles == 2
        assert len(hfe.variants_detected) == 2

    def test_h63d_carrier(self):
        """Heterozygous H63D only → carrier."""
        df = make_df([
            ("rs1800562", "6", "G", "G"),  # C282Y ref/ref
            ("rs1799945", "6", "C", "G"),  # H63D het
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"
        assert hfe.total_pathogenic_alleles == 1


# ---------------------------------------------------------------------------
# Carrier status — HBB (sickle cell)
# ---------------------------------------------------------------------------


class TestHBBCarrier:
    """HBB: HbS (rs334, pathogenic = A), HbC (rs33930165, pathogenic = T)."""

    def test_sickle_trait_carrier(self):
        """One copy of HbS → carrier (sickle cell trait)."""
        df = make_df([
            ("rs334", "11", "T", "A"),       # HbS het
            ("rs33930165", "11", "C", "C"),   # HbC ref/ref
        ])
        results = determine_carrier_status(df)
        hbb = next(r for r in results if r.gene == "HBB")
        assert hbb.status == "carrier"
        assert "carrier" in hbb.clinical_note.lower()

    def test_sickle_cell_disease(self):
        """Homozygous HbS → likely_affected."""
        df = make_df([
            ("rs334", "11", "A", "A"),        # HbS hom
            ("rs33930165", "11", "C", "C"),    # HbC ref/ref
        ])
        results = determine_carrier_status(df)
        hbb = next(r for r in results if r.gene == "HBB")
        assert hbb.status == "likely_affected"

    def test_hbsc_compound_het(self):
        """Het HbS + Het HbC → potential_compound_het (HbSC disease)."""
        df = make_df([
            ("rs334", "11", "T", "A"),        # HbS het
            ("rs33930165", "11", "C", "T"),    # HbC het
        ])
        results = determine_carrier_status(df)
        hbb = next(r for r in results if r.gene == "HBB")
        assert hbb.status == "potential_compound_het"
        assert "compound" in hbb.clinical_note.lower()


# ---------------------------------------------------------------------------
# Empty / missing data
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_dataframe(self):
        """Empty DataFrame → all genes should be not_detected."""
        df = make_df([])
        results = determine_carrier_status(df)
        assert len(results) > 0
        for r in results:
            assert r.status == "not_detected"

    def test_no_matching_rsids(self):
        """DataFrame with rsids not in panel → all genes not_detected."""
        df = make_df([
            ("rs999999999", "1", "A", "G"),
        ])
        results = determine_carrier_status(df)
        for r in results:
            assert r.status == "not_detected"

    def test_missing_alleles_ignored(self):
        """No-call genotypes should not count as pathogenic."""
        df = make_df([
            ("rs1800562", "6", "-", "-"),
            ("rs1799945", "6", "0", "0"),
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "not_detected"

    def test_all_genes_have_required_fields(self):
        """All gene results have required fields populated."""
        df = make_df([])
        results = determine_carrier_status(df)
        for r in results:
            assert r.gene
            assert r.condition
            assert r.inheritance
            assert r.severity
            assert r.status in ("not_detected", "carrier", "likely_affected", "potential_compound_het")
            assert r.total_variants_screened > 0


# ---------------------------------------------------------------------------
# to_dict() serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_to_dict_carrier(self):
        """CarrierGeneResult.to_dict() produces expected keys."""
        df = make_df([
            ("rs1800562", "6", "G", "A"),
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        d = hfe.to_dict()
        assert d["gene"] == "HFE"
        assert d["status"] == "carrier"
        assert isinstance(d["variants_detected"], list)
        assert len(d["variants_detected"]) == 1
        assert d["variants_detected"][0]["rsid"] == "rs1800562"
        assert "carrier_frequencies" in d
        assert "clinical_note" in d
        assert "key_pmids" in d

    def test_to_dict_not_detected(self):
        df = make_df([
            ("rs1800562", "6", "G", "G"),
            ("rs1799945", "6", "C", "C"),
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        d = hfe.to_dict()
        assert d["status"] == "not_detected"
        assert d["variants_detected"] == []


# ---------------------------------------------------------------------------
# Clinical note content
# ---------------------------------------------------------------------------


class TestClinicalNotes:
    def test_carrier_note_mentions_25_percent(self):
        """Carrier clinical note should mention 25% reproductive risk."""
        df = make_df([("rs1800562", "6", "G", "A")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert "25%" in hfe.clinical_note

    def test_not_detected_note_mentions_limitations(self):
        """Not-detected note should reference limitations."""
        df = make_df([("rs1800562", "6", "G", "G"), ("rs1799945", "6", "C", "C")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert "limitation" in hfe.clinical_note.lower()

    def test_compound_het_note_mentions_phase(self):
        """Compound het note should mention phase ambiguity."""
        df = make_df([
            ("rs1800562", "6", "G", "A"),
            ("rs1799945", "6", "C", "G"),
        ])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert "phase" in hfe.clinical_note.lower()

    def test_likely_affected_note_mentions_counseling(self):
        """Likely affected note should recommend genetic counseling."""
        df = make_df([("rs1800562", "6", "A", "A")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert "counseling" in hfe.clinical_note.lower()


# ---------------------------------------------------------------------------
# Strand validation (_resolve_alleles)
# ---------------------------------------------------------------------------


class TestResolveAlleles:
    """Tests for the _resolve_alleles strand correction function."""

    def test_correct_strand_passes_through(self):
        """Alleles matching expected ref/pathogenic pass through unchanged."""
        result = _resolve_alleles("G", "A", ref_allele="G", pathogenic_allele="A")
        assert result == ("G", "A")

    def test_correct_strand_hom_ref(self):
        result = _resolve_alleles("G", "G", ref_allele="G", pathogenic_allele="A")
        assert result == ("G", "G")

    def test_opposite_strand_flipped(self):
        """Alleles on opposite strand (complement) get flipped."""
        # User has C/T (complement of G/A) → should flip to G/A
        result = _resolve_alleles("C", "T", ref_allele="G", pathogenic_allele="A")
        assert result == ("G", "A")

    def test_opposite_strand_hom_ref_flipped(self):
        """Homozygous ref on opposite strand gets flipped correctly."""
        # User has C/C (complement of G/G) → flip to G/G
        result = _resolve_alleles("C", "C", ref_allele="G", pathogenic_allele="A")
        assert result == ("G", "G")

    def test_strand_ambiguous_at_passes_through(self):
        """A/T SNP: expected={A,T} == complement. User A/T matches first check → passes through.

        For strand-ambiguous SNPs, user alleles always match the expected set directly,
        so the ambiguity branch is unreachable. Genotype interpretation is still correct.
        """
        result = _resolve_alleles("A", "T", ref_allele="A", pathogenic_allele="T")
        assert result == ("A", "T")

    def test_strand_ambiguous_cg_passes_through(self):
        """C/G SNP: same logic as A/T — always matches first check."""
        result = _resolve_alleles("C", "G", ref_allele="C", pathogenic_allele="G")
        assert result == ("C", "G")

    def test_non_ambiguous_at_variant(self):
        """A/T variant where pathogenic != complement(ref) is NOT ambiguous.

        e.g., ref=A, pathogenic=C. Complement of expected is {T,G}.
        If user has T/G, they're on the opposite strand and should be flipped.
        """
        result = _resolve_alleles("T", "G", ref_allele="A", pathogenic_allele="C")
        assert result == ("A", "C")

    def test_complement_match_flipped(self):
        """User alleles match complement of expected → flipped to correct strand.

        ref=G, path=T. Complement: {C, A}. User has A/C → matches complement → flip to T/G.
        """
        result = _resolve_alleles("A", "C", ref_allele="G", pathogenic_allele="T")
        assert result == ("T", "G")

    def test_triallelic_returns_none(self):
        """Alleles not matching either strand → None."""
        # ref=G, path=A. Expected={G,A}, complement={C,T}. User has G/T → not subset of either.
        result = _resolve_alleles("G", "T", ref_allele="G", pathogenic_allele="A")
        assert result is None

    def test_no_call_returns_none(self):
        """No-call genotypes return None."""
        assert _resolve_alleles("-", "-", "G", "A") is None
        assert _resolve_alleles("0", "0", "G", "A") is None
        assert _resolve_alleles("", "", "G", "A") is None

    def test_indel_skips_strand_check(self):
        """Multi-base alleles (indels) skip strand validation."""
        result = _resolve_alleles("ATCT", "A", ref_allele="ATCT", pathogenic_allele="A")
        assert result == ("ATCT", "A")


# ---------------------------------------------------------------------------
# Complement function
# ---------------------------------------------------------------------------


class TestComplement:
    def test_single_base(self):
        assert _complement("A") == "T"
        assert _complement("T") == "A"
        assert _complement("C") == "G"
        assert _complement("G") == "C"

    def test_multi_base(self):
        assert _complement("ATCG") == "TAGC"


# ---------------------------------------------------------------------------
# Position-based matching (VCFs with "." rsids)
# ---------------------------------------------------------------------------


class TestPositionBasedMatching:
    """Test carrier matching using chrom+position when rsids are "."."""

    def test_vcf_position_match_hfe_carrier(self):
        """VCF with '.' rsids matches HFE C282Y by position → carrier."""
        # HFE C282Y: chrom 6, position 26093141 (GRCh37), ref=G, pathogenic=A
        df = make_df(
            [
                (".", "6", "G", "A"),  # C282Y het at correct position
                (".", "6", "C", "C"),  # H63D ref/ref at correct position
            ],
            positions=[26093141, 26091179],
        )
        results = determine_carrier_status(df, genome_build="GRCh37")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"
        assert hfe.total_pathogenic_alleles == 1
        assert len(hfe.variants_detected) == 1
        assert hfe.variants_detected[0].rsid == "rs1800562"

    def test_vcf_position_match_hfe_homozygous(self):
        """VCF position match for homozygous C282Y → likely_affected."""
        df = make_df(
            [(".", "6", "A", "A")],
            positions=[26093141],
        )
        results = determine_carrier_status(df, genome_build="GRCh37")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "likely_affected"
        assert hfe.total_pathogenic_alleles == 2

    def test_vcf_position_no_match_wrong_position(self):
        """VCF variant at wrong position should not match."""
        df = make_df(
            [(".", "6", "G", "A")],
            positions=[99999999],
        )
        results = determine_carrier_status(df, genome_build="GRCh37")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "not_detected"

    def test_vcf_position_compound_het(self):
        """VCF position match for compound het HFE (C282Y + H63D)."""
        df = make_df(
            [
                (".", "6", "G", "A"),  # C282Y het
                (".", "6", "C", "G"),  # H63D het
            ],
            positions=[26093141, 26091179],
        )
        results = determine_carrier_status(df, genome_build="GRCh37")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "potential_compound_het"
        assert hfe.total_pathogenic_alleles == 2

    def test_rsid_preferred_over_position(self):
        """When both rsid and position are available, rsid match takes priority."""
        # Provide correct rsid with het genotype
        df = make_df(
            [("rs1800562", "6", "G", "A")],
            positions=[26093141],
        )
        results = determine_carrier_status(df, genome_build="GRCh37")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"

    def test_chrom_prefix_stripped(self):
        """Chrom with 'chr' prefix should still match."""
        df = make_df(
            [(".", "chr6", "G", "A")],
            positions=[26093141],
        )
        results = determine_carrier_status(df, genome_build="GRCh37")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"


# ---------------------------------------------------------------------------
# GRCh38 position matching
# ---------------------------------------------------------------------------


class TestGRCh38Matching:
    """Test matching when input is GRCh38."""

    def test_grch38_position_match(self):
        """GRCh38 VCF matches using position_grch38 field."""
        # HFE C282Y GRCh38 position: 26092913
        df = make_df(
            [(".", "6", "G", "A")],
            positions=[26092913],
        )
        results = determine_carrier_status(df, genome_build="GRCh38")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"

    def test_grch38_does_not_match_grch37_position(self):
        """GRCh38 mode should NOT match against GRCh37 positions."""
        # Using GRCh37 position (26093141) with GRCh38 mode → no match
        df = make_df(
            [(".", "6", "G", "A")],
            positions=[26093141],
        )
        results = determine_carrier_status(df, genome_build="GRCh38")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "not_detected"

    def test_grch38_rsid_still_works(self):
        """rsid-based matching works regardless of genome build."""
        df = make_df([("rs1800562", "6", "G", "A")])
        results = determine_carrier_status(df, genome_build="GRCh38")
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"


# ---------------------------------------------------------------------------
# Strand correction in full pipeline
# ---------------------------------------------------------------------------


class TestStrandCorrectionIntegration:
    """Test strand correction within determine_carrier_status.

    For non-ambiguous SNPs (e.g., G/A, C/T), the matcher can detect when
    user alleles are on the opposite strand and flip them. For A/T and C/G
    SNPs, the expected and complement sets are identical, so user alleles
    always match the first check — strand correction is not needed (or
    possible) but genotype interpretation is still correct.
    """

    def test_opposite_strand_genotype_corrected(self):
        """HFE C282Y: ref=G, path=A. User reports C/T (complement strand) → flipped to G/A → carrier."""
        df = make_df([("rs1800562", "6", "C", "T")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "carrier"
        assert hfe.total_pathogenic_alleles == 1

    def test_opposite_strand_hom_ref_not_called(self):
        """HFE C282Y: ref=G, path=A. User has C/C (complement of G/G) → flipped to G/G → not_detected."""
        df = make_df([("rs1800562", "6", "C", "C")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "not_detected"

    def test_opposite_strand_hom_pathogenic_corrected(self):
        """HFE C282Y: ref=G, path=A. User has T/T (complement of A/A) → flipped to A/A → likely_affected."""
        df = make_df([("rs1800562", "6", "T", "T")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        assert hfe.status == "likely_affected"
        assert hfe.total_pathogenic_alleles == 2

    def test_at_snp_het_accepted_as_carrier(self):
        """rs17580 (SERPINA1 Pi*S): ref=T, path=A. A/T SNP, user T/A → carrier.

        For A/T SNPs, expected={T,A} matches any T/A genotype on the first check,
        so the ambiguity branch is never reached. Genotype interpretation is correct.
        """
        df = make_df([("rs17580", "14", "T", "A")])
        results = determine_carrier_status(df)
        serpina1 = next(r for r in results if r.gene == "SERPINA1")
        assert serpina1.status == "carrier"
        assert serpina1.total_pathogenic_alleles == 1

    def test_corrected_panel_prevents_old_false_positive(self):
        """rs17580 (SERPINA1 Pi*S): ref=T, path=A. User T/T → homozygous ref → not_detected.

        Previously the panel had ref=A/path=T (wrong strand), so 23andMe reporting
        "TT" was falsely called as 2 copies of pathogenic allele T → likely_affected.
        With corrected alleles, "TT" is correctly 2 copies of ref T → not_detected.
        """
        df = make_df([("rs17580", "14", "T", "T")])
        results = determine_carrier_status(df)
        serpina1 = next(r for r in results if r.gene == "SERPINA1")
        assert serpina1.status == "not_detected"

    def test_triallelic_skipped(self):
        """Alleles not matching expected ref/pathogenic on either strand → skipped."""
        # HFE C282Y: ref=G, path=A. User has A/C → not in {G,A} or {C,T}
        df = make_df([("rs1800562", "6", "A", "C")])
        results = determine_carrier_status(df)
        hfe = next(r for r in results if r.gene == "HFE")
        # The one variant is skipped due to allele mismatch
        assert hfe.total_pathogenic_alleles == 0
