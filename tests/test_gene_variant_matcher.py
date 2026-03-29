"""Tests for gene_variant_matcher — interval tree gene mapping."""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.gene_variant_matcher import (
    GeneVariantHit,
    GeneCoverageEntry,
    GeneMatchResult,
    _is_hom_ref,
    match_gene_variants,
    _load_gene_intervals,
)


# ── Unit tests for _is_hom_ref ──────────────────────────────────────────

class TestIsHomRef:
    def test_hom_ref_match(self):
        assert _is_hom_ref("A", "A", "A") is True

    def test_het_not_hom_ref(self):
        assert _is_hom_ref("A", "G", "A") is False

    def test_hom_alt_not_hom_ref(self):
        assert _is_hom_ref("G", "G", "A") is False

    def test_complement_match(self):
        assert _is_hom_ref("T", "T", "A") is True

    def test_complement_het(self):
        assert _is_hom_ref("T", "C", "A") is False

    def test_no_ref_allele(self):
        assert _is_hom_ref("A", "A", None) is False

    def test_empty_ref(self):
        assert _is_hom_ref("A", "A", "") is False


# ── Tests using real NCLS trees with mocked DB ─────────────────────────

def _make_user_df(variants: list[dict]) -> pl.DataFrame:
    return pl.DataFrame(
        variants,
        schema={
            "rsid": pl.Utf8,
            "chrom": pl.Utf8,
            "position": pl.Int64,
            "allele1": pl.Utf8,
            "allele2": pl.Utf8,
        },
    )


def _mock_gene_rows(genes: list[tuple[str, str, int, int]]):
    """Create a mock result for gene coordinate queries."""
    mock = MagicMock()
    mock.all.return_value = genes
    return mock


def _mock_ref_alleles(ref_map: dict[str, str]):
    """Create a mock result for ref_allele batch queries."""
    mock = MagicMock()
    mock.__iter__ = MagicMock(return_value=iter(list(ref_map.items())))
    return mock


class TestMatchGeneVariants:
    async def test_empty_dataframe(self):
        session = AsyncMock()
        df = _make_user_df([])
        result = await match_gene_variants(df, session, "GRCh38")
        assert result.hits == []
        assert result.coverage == []

    async def test_no_gene_coordinates(self):
        session = AsyncMock()
        session.execute.return_value = _mock_gene_rows([])

        df = _make_user_df([
            {"rsid": "rs123", "chrom": "1", "position": 100000, "allele1": "A", "allele2": "G"},
        ])
        result = await match_gene_variants(df, session, "GRCh38")
        assert result.hits == []
        assert result.coverage == []

    async def test_basic_matching(self):
        """Variant in gene region produces a hit."""
        session = AsyncMock()
        # Gene coordinate query returns BRCA1
        gene_mock = _mock_gene_rows([("BRCA1", "17", 43044295, 43170245)])
        # Ref allele query
        ref_mock = _mock_ref_alleles({"rs80357906": "A"})

        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": "rs80357906", "chrom": "17", "position": 43100000, "allele1": "A", "allele2": "G"},
            {"rsid": "rs999", "chrom": "17", "position": 10000000, "allele1": "C", "allele2": "T"},
            {"rsid": "rs888", "chrom": "1", "position": 43100000, "allele1": "G", "allele2": "G"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        # rs80357906 is in BRCA1, het (A/G with ref A) — hit
        # rs999 is outside BRCA1 — no gene match (but on chr17)
        # rs888 is on chr1 — no gene there
        brca_hits = [h for h in result.hits if h.gene == "BRCA1"]
        assert len(brca_hits) == 1
        assert brca_hits[0].rsid == "rs80357906"
        assert brca_hits[0].user_genotype == "AG"

        # rs999 is outside BRCA1 region so no coverage for it under BRCA1
        # But it might match if it falls in another gene — here it doesn't
        brca_cov = [c for c in result.coverage if c.gene == "BRCA1"]
        assert len(brca_cov) == 1
        assert brca_cov[0].non_reference_count == 1

    async def test_hom_ref_skipped_from_hits(self):
        """Hom-ref increments coverage count but doesn't create a hit."""
        session = AsyncMock()
        gene_mock = _mock_gene_rows([("TESTGENE", "1", 1000, 2000)])
        ref_mock = _mock_ref_alleles({"rs100": "A", "rs101": "A"})
        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": "rs100", "chrom": "1", "position": 1500, "allele1": "A", "allele2": "A"},
            {"rsid": "rs101", "chrom": "1", "position": 1600, "allele1": "A", "allele2": "G"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        assert len(result.hits) == 1
        assert result.hits[0].rsid == "rs101"
        assert result.hits[0].user_genotype == "AG"

        assert len(result.coverage) == 1
        assert result.coverage[0].gene == "TESTGENE"
        assert result.coverage[0].total_variants_tested == 2
        assert result.coverage[0].non_reference_count == 1

    async def test_chr_prefix_handling(self):
        """Variants with 'chr' prefix match genes stored without prefix."""
        session = AsyncMock()
        gene_mock = _mock_gene_rows([("TESTGENE", "1", 1000, 2000)])
        ref_mock = _mock_ref_alleles({})
        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": "rs100", "chrom": "chr1", "position": 1500, "allele1": "C", "allele2": "T"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        assert len(result.hits) == 1
        assert result.hits[0].chrom == "1"

    async def test_novel_variant_no_rsid(self):
        """WGS variants with '.' rsid get rsid=None in hit."""
        session = AsyncMock()
        gene_mock = _mock_gene_rows([("TESTGENE", "1", 1000, 2000)])
        ref_mock = _mock_ref_alleles({})
        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": ".", "chrom": "1", "position": 1500, "allele1": "G", "allele2": "T"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        assert len(result.hits) == 1
        assert result.hits[0].rsid is None
        assert result.hits[0].user_genotype == "GT"

    async def test_overlapping_genes(self):
        """A variant at a position covered by two genes should match both."""
        session = AsyncMock()
        gene_mock = _mock_gene_rows([
            ("GENE_A", "1", 1000, 3000),
            ("GENE_B", "1", 2000, 4000),
        ])
        ref_mock = _mock_ref_alleles({})
        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": "rs200", "chrom": "1", "position": 2500, "allele1": "A", "allele2": "C"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        gene_names = {h.gene for h in result.hits}
        assert gene_names == {"GENE_A", "GENE_B"}
        assert len(result.coverage) == 2

    async def test_no_ref_allele_assumes_nonref(self):
        """When ref_allele is unknown, variant is treated as non-reference."""
        session = AsyncMock()
        gene_mock = _mock_gene_rows([("TESTGENE", "1", 1000, 2000)])
        ref_mock = _mock_ref_alleles({})  # No ref alleles known
        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": "rs100", "chrom": "1", "position": 1500, "allele1": "A", "allele2": "A"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        # Without ref allele info, A/A is assumed non-ref
        assert len(result.hits) == 1

    async def test_multiple_chromosomes(self):
        """Variants across different chromosomes are matched correctly."""
        session = AsyncMock()
        gene_mock = _mock_gene_rows([
            ("BRCA1", "17", 43044295, 43170245),
            ("APOE", "19", 44905796, 44909393),
        ])
        ref_mock = _mock_ref_alleles({})
        session.execute.side_effect = [gene_mock, ref_mock]

        df = _make_user_df([
            {"rsid": "rs1", "chrom": "17", "position": 43100000, "allele1": "A", "allele2": "G"},
            {"rsid": "rs2", "chrom": "19", "position": 44907000, "allele1": "C", "allele2": "T"},
            {"rsid": "rs3", "chrom": "5", "position": 100000, "allele1": "G", "allele2": "A"},
        ])

        result = await match_gene_variants(df, session, "GRCh38")

        gene_names = {h.gene for h in result.hits}
        assert gene_names == {"BRCA1", "APOE"}
        assert len(result.coverage) == 2
