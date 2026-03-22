"""Integration tests for match_traits() — the async DB-querying function."""

import uuid

import polars as pl
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.trait_matcher import match_traits, TraitHit, BATCH_SIZE


def _user_df(variants: list[tuple[str, str, int, str, str]]) -> pl.DataFrame:
    """Build a minimal user DataFrame from (rsid, chrom, position, allele1, allele2) tuples."""
    if not variants:
        return pl.DataFrame(
            schema={"rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64,
                    "allele1": pl.Utf8, "allele2": pl.Utf8}
        )
    return pl.DataFrame(
        {
            "rsid": [v[0] for v in variants],
            "chrom": [v[1] for v in variants],
            "position": [v[2] for v in variants],
            "allele1": [v[3] for v in variants],
            "allele2": [v[4] for v in variants],
        }
    )


def _make_assoc_row(rsid, trait, risk_allele, evidence="high", odds_ratio=None):
    """Create a mock DB row for snp_trait_associations."""
    return (
        str(uuid.uuid4()),  # id
        rsid,
        trait,
        risk_allele,
        f"Effect of {trait}",  # effect_description
        evidence,
        odds_ratio,
    )


def _mock_session(assoc_rows: list[tuple]) -> AsyncMock:
    """Create a mock session whose execute() returns the given association rows."""
    session = AsyncMock()
    result = MagicMock()
    result.__iter__ = MagicMock(return_value=iter(assoc_rows))
    session.execute = AsyncMock(return_value=result)
    return session


class TestMatchTraitsEmptyInput:
    @pytest.mark.asyncio
    async def test_empty_dataframe_returns_empty(self):
        """Empty user DataFrame → no hits."""
        df = _user_df([])
        session = _mock_session([])
        hits = await match_traits(df, session)
        assert hits == []
        session.execute.assert_not_called()


class TestMatchTraitsWithResults:
    @pytest.mark.asyncio
    async def test_single_hit_increased(self):
        """Homozygous risk allele → 'increased'."""
        df = _user_df([("rs429358", "19", 45411941, "C", "C")])
        row = _make_assoc_row("rs429358", "Alzheimer's", "C")
        session = _mock_session([row])

        hits = await match_traits(df, session)

        assert len(hits) == 1
        assert hits[0].rsid == "rs429358"
        assert hits[0].risk_level == "increased"
        assert hits[0].user_genotype == "CC"
        assert hits[0].trait == "Alzheimer's"

    @pytest.mark.asyncio
    async def test_single_hit_moderate(self):
        """Heterozygous risk allele → 'moderate'."""
        df = _user_df([("rs429358", "19", 45411941, "T", "C")])
        row = _make_assoc_row("rs429358", "Alzheimer's", "C")
        session = _mock_session([row])

        hits = await match_traits(df, session)

        assert len(hits) == 1
        assert hits[0].risk_level == "moderate"
        assert hits[0].user_genotype == "TC"

    @pytest.mark.asyncio
    async def test_single_hit_typical(self):
        """No risk allele copies → 'typical'."""
        df = _user_df([("rs429358", "19", 45411941, "T", "T")])
        row = _make_assoc_row("rs429358", "Alzheimer's", "C")
        session = _mock_session([row])

        hits = await match_traits(df, session)

        assert len(hits) == 1
        assert hits[0].risk_level == "typical"

    @pytest.mark.asyncio
    async def test_no_matching_associations(self):
        """User has variants but none match associations in DB."""
        df = _user_df([("rs12345", "1", 100, "A", "G")])
        session = _mock_session([])  # DB returns nothing

        hits = await match_traits(df, session)
        assert hits == []

    @pytest.mark.asyncio
    async def test_multiple_traits_same_rsid(self):
        """One rsid can have multiple trait associations."""
        df = _user_df([("rs429358", "19", 45411941, "C", "C")])
        rows = [
            _make_assoc_row("rs429358", "Alzheimer's", "C"),
            _make_assoc_row("rs429358", "Heart Disease", "C"),
        ]
        session = _mock_session(rows)

        hits = await match_traits(df, session)

        assert len(hits) == 2
        traits = {h.trait for h in hits}
        assert traits == {"Alzheimer's", "Heart Disease"}

    @pytest.mark.asyncio
    async def test_multiple_variants(self):
        """Multiple user variants, each with their own association."""
        df = _user_df([
            ("rs429358", "19", 45411941, "C", "T"),
            ("rs7412", "19", 45412079, "C", "C"),
        ])
        rows = [
            _make_assoc_row("rs429358", "Alzheimer's", "C"),
            _make_assoc_row("rs7412", "Cholesterol", "C"),
        ]
        session = _mock_session(rows)

        hits = await match_traits(df, session)

        assert len(hits) == 2


class TestMatchTraitsSorting:
    @pytest.mark.asyncio
    async def test_results_sorted_by_risk(self):
        """Hits are sorted: increased → moderate → typical."""
        df = _user_df([
            ("rs1", "1", 100, "A", "A"),  # typical (risk=G)
            ("rs2", "2", 200, "G", "G"),  # increased (risk=G)
            ("rs3", "3", 300, "A", "G"),  # moderate (risk=G)
        ])
        rows = [
            _make_assoc_row("rs1", "Trait1", "G"),
            _make_assoc_row("rs2", "Trait2", "G"),
            _make_assoc_row("rs3", "Trait3", "G"),
        ]
        session = _mock_session(rows)

        hits = await match_traits(df, session)

        assert [h.risk_level for h in hits] == ["increased", "moderate", "typical"]


class TestMatchTraitsVcfImputation:
    """Tests for VCF REF/REF imputation of missing positions."""

    def _mock_session_two_queries(self, matched_rows, imputed_rows):
        """Mock session that returns different results for matched vs imputed queries."""
        session = AsyncMock()
        result1 = MagicMock()
        result1.__iter__ = MagicMock(return_value=iter(matched_rows))
        result2 = MagicMock()
        result2.__iter__ = MagicMock(return_value=iter(imputed_rows))
        session.execute = AsyncMock(side_effect=[result1, result2])
        return session

    @pytest.mark.asyncio
    async def test_vcf_imputes_missing_as_typical(self):
        """Missing VCF position → imputed as REF/REF → typical risk (risk_allele != REF)."""
        # User has rs429358 but NOT rs7412 (absent from variant-only VCF)
        df = _user_df([("rs429358", "19", 45411941, "C", "C")])
        matched_row = _make_assoc_row("rs429358", "Alzheimer's", "C")
        # Imputed row: risk_allele=T, ref_allele=C → 0 copies of T → typical
        imputed_row = (
            str(uuid.uuid4()), "rs7412", "Cholesterol", "T",
            "Cholesterol effect", "high", None, "C",  # odds_ratio, ref_allele
        )
        session = self._mock_session_two_queries([matched_row], [imputed_row])

        hits = await match_traits(df, session, is_vcf=True)

        assert len(hits) == 2
        # Matched hit
        matched = [h for h in hits if h.rsid == "rs429358"]
        assert len(matched) == 1
        assert matched[0].risk_level == "increased"
        # Imputed hit
        imputed = [h for h in hits if h.rsid == "rs7412"]
        assert len(imputed) == 1
        assert imputed[0].risk_level == "typical"
        assert imputed[0].user_genotype == "CC"

    @pytest.mark.asyncio
    async def test_vcf_imputes_risk_allele_is_ref(self):
        """Safety-critical: risk_allele = REF, user is HOM_REF → increased risk."""
        df = _user_df([("rs429358", "19", 45411941, "C", "C")])
        matched_row = _make_assoc_row("rs429358", "Alzheimer's", "C")
        # Imputed: risk_allele=G = ref_allele → 2 copies → increased
        imputed_row = (
            str(uuid.uuid4()), "rs999", "Heart Disease", "G",
            "Effect", "high", None, "G",  # odds_ratio, ref_allele = risk_allele
        )
        session = self._mock_session_two_queries([matched_row], [imputed_row])

        hits = await match_traits(df, session, is_vcf=True)

        imputed = [h for h in hits if h.rsid == "rs999"]
        assert len(imputed) == 1
        assert imputed[0].risk_level == "increased"
        assert imputed[0].user_genotype == "GG"

    @pytest.mark.asyncio
    async def test_no_imputation_when_not_vcf(self):
        """is_vcf=False → no imputation query, only matched variants."""
        df = _user_df([("rs429358", "19", 45411941, "C", "C")])
        matched_row = _make_assoc_row("rs429358", "Alzheimer's", "C")
        session = _mock_session([matched_row])

        hits = await match_traits(df, session, is_vcf=False)

        assert len(hits) == 1
        # Only one query (matched), not two
        session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_vcf_imputation_skips_null_ref_allele(self):
        """Associations with NULL ref_allele in snps table are skipped."""
        df = _user_df([("rs1", "1", 100, "A", "G")])
        matched_row = _make_assoc_row("rs1", "Trait1", "A")
        # ref_allele is None → should be skipped
        imputed_row = (
            str(uuid.uuid4()), "rs2", "Trait2", "C",
            "Effect", "high", None, None,  # odds_ratio, no ref_allele
        )
        session = self._mock_session_two_queries([matched_row], [imputed_row])

        hits = await match_traits(df, session, is_vcf=True)

        assert len(hits) == 1  # only the matched hit
        assert hits[0].rsid == "rs1"

    @pytest.mark.asyncio
    async def test_vcf_empty_user_df_still_imputes(self):
        """Even with empty user DataFrame, VCF imputation queries all associations."""
        df = _user_df([])
        # No matched query needed (empty rsids), but imputation query returns results
        imputed_row = (
            str(uuid.uuid4()), "rs7412", "Cholesterol", "T",
            "Effect", "medium", None, "C",  # odds_ratio, ref_allele
        )
        session = AsyncMock()
        result = MagicMock()
        result.__iter__ = MagicMock(return_value=iter([imputed_row]))
        session.execute = AsyncMock(return_value=result)

        hits = await match_traits(df, session, is_vcf=True)

        assert len(hits) == 1
        assert hits[0].rsid == "rs7412"
        assert hits[0].risk_level == "typical"


class TestMatchTraitsBatching:
    @pytest.mark.asyncio
    async def test_batches_large_variant_lists(self):
        """Verify that large variant lists are batched into multiple queries."""
        n = BATCH_SIZE + 100  # trigger 2 batches
        variants = [(f"rs{i}", "1", i, "A", "G") for i in range(n)]
        df = _user_df(variants)

        session = AsyncMock()
        empty_result = MagicMock()
        empty_result.__iter__ = MagicMock(return_value=iter([]))
        session.execute = AsyncMock(return_value=empty_result)

        await match_traits(df, session)

        # Should have been called twice (2 batches)
        assert session.execute.call_count == 2
