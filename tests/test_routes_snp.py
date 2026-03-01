"""Tests for SNP endpoints (public, unauthenticated)."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.snp import router
from app.db import get_session

_app = FastAPI()
_app.include_router(router, prefix="/api/v1")


def _mock_snp(rsid="rs429358", chrom="19", position=45411941, gene="APOE"):
    """Create a mock Snp ORM object."""
    snp = MagicMock()
    snp.rsid = rsid
    snp.chrom = chrom
    snp.position = position
    snp.ref_allele = "T"
    snp.alt_allele = "C"
    snp.gene = gene
    snp.functional_class = "missense"
    snp.maf_global = 0.15
    return snp


def _mock_association(rsid="rs429358", trait="Alzheimer's Disease"):
    """Create a mock SnpTraitAssociation ORM object."""
    assoc = MagicMock()
    assoc.id = uuid.uuid4()
    assoc.rsid = rsid
    assoc.trait = trait
    assoc.risk_allele = "C"
    assoc.odds_ratio = 3.2
    assoc.beta = None
    assoc.p_value = 1e-15
    assoc.effect_description = "Increased risk"
    assoc.evidence_level = "high"
    assoc.source_pmid = "12345678"
    assoc.source_title = "Study title"
    assoc.trait_prevalence = 0.10
    return assoc


def _mock_prs_row(pgs_id="PGS000001", trait_name="CAD"):
    """Create a mock row for PRS weight query."""
    row = MagicMock()
    row.pgs_id = pgs_id
    row.trait_name = trait_name
    row.effect_allele = "C"
    row.weight = 0.05
    return row


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    _app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


class TestGetSnp:
    def test_known_snp_returns_data(self, client):
        """Lookup a known SNP returns full data."""
        snp = _mock_snp()
        assoc = _mock_association()
        prs_row = _mock_prs_row()

        session = AsyncMock()

        # First call: select(Snp) → returns snp
        snp_result = MagicMock()
        snp_result.scalar_one_or_none.return_value = snp

        # Second call: select(Gene) → returns gene info
        gene_result = MagicMock()
        gene_result.scalar_one_or_none.return_value = None  # no gene record

        # Third call: select(SnpTraitAssociation) → returns associations
        assoc_result = MagicMock()
        assoc_scalars = MagicMock()
        assoc_scalars.all.return_value = [assoc]
        assoc_result.scalars.return_value = assoc_scalars

        # Fourth call: text(PRS query) → returns PRS rows
        prs_result = MagicMock()
        prs_result.__iter__ = MagicMock(return_value=iter([prs_row]))

        session.execute = AsyncMock(side_effect=[snp_result, gene_result, assoc_result, prs_result])

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/rs429358")
        assert response.status_code == 200
        data = response.json()
        assert data["rsid"] == "rs429358"
        assert data["in_database"] is True
        assert data["gene"] == "APOE"
        assert len(data["trait_associations"]) == 1
        assert data["trait_associations"][0]["trait"] == "Alzheimer's Disease"
        assert len(data["prs_scores"]) == 1

    def test_unknown_snp_returns_minimal(self, client):
        """Lookup an unknown SNP returns minimal response."""
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/rs999999999")
        assert response.status_code == 200
        data = response.json()
        assert data["rsid"] == "rs999999999"
        assert data["in_database"] is False
        assert data["trait_associations"] == []
        assert data["prs_scores"] == []

    def test_invalid_rsid_format(self, client):
        """Invalid rsid format returns 400."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/invalid")
        assert response.status_code == 400
        assert "Invalid rsid" in response.json()["detail"]

    def test_rsid_too_long(self, client):
        """rsid longer than 20 chars returns 400."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/rs12345678901234567890")
        assert response.status_code == 400


class TestSearchSnps:
    def test_search_requires_filter(self, client):
        """Search with no filters returns 400."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/")
        assert response.status_code == 400
        assert "Provide at least one filter" in response.json()["detail"]

    def test_search_by_gene(self, client):
        """Search by gene returns matching SNPs."""
        snp = _mock_snp()
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [snp]
        result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/?gene=APOE")
        assert response.status_code == 200
        data = response.json()
        assert len(data["snps"]) == 1
        assert data["snps"][0]["gene"] == "APOE"

    def test_search_by_chrom(self, client):
        """Search by chromosome returns matching SNPs."""
        snp = _mock_snp()
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [snp]
        result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/?chrom=19")
        assert response.status_code == 200
        data = response.json()
        assert len(data["snps"]) == 1

    def test_search_empty_results(self, client):
        """Search returning no results."""
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/snp/?gene=NONEXISTENT")
        assert response.status_code == 200
        assert response.json()["snps"] == []
