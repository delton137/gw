"""Tests for gene endpoints (public, unauthenticated)."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.gene import router
from app.db import get_session

_app = FastAPI()
_app.include_router(router, prefix="/api/v1")


def _mock_gene(symbol="BRCA1", name="BRCA1 DNA repair associated", pathogenic=15):
    gene = MagicMock()
    gene.symbol = symbol
    gene.name = name
    gene.summary = "Encodes a tumor suppressor."
    gene.ncbi_gene_id = 672
    gene.omim_number = 113705
    gene.clinvar_total_variants = 100
    gene.clinvar_pathogenic_count = pathogenic
    gene.clinvar_uncertain_count = 30
    gene.clinvar_conflicting_count = 5
    gene.clinvar_total_submissions = 500
    return gene


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    _app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


class TestGetFeaturedGenes:
    def test_returns_genes(self, client):
        """Featured genes endpoint returns a list."""
        gene = _mock_gene()
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [gene]
        result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/gene/featured")
        assert response.status_code == 200
        data = response.json()
        assert len(data["genes"]) == 1
        assert data["genes"][0]["symbol"] == "BRCA1"

    def test_empty_results(self, client):
        """No featured genes → empty list."""
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = []
        result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/gene/featured")
        assert response.status_code == 200
        assert response.json()["genes"] == []


class TestSearchGenes:
    def test_search_returns_results(self, client):
        """Partial match returns matching gene."""
        gene = _mock_gene()
        session = AsyncMock()
        result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [gene]
        result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/gene/search?q=BRCA")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["genes"][0]["symbol"] == "BRCA1"

    def test_search_requires_query(self, client):
        """Missing q parameter returns 422."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/gene/search")
        assert response.status_code == 422


class TestGetGene:
    def test_gene_not_found(self, client):
        """Unknown gene returns 404."""
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/gene/NONEXISTENT")
        assert response.status_code == 404

    def test_gene_detail_returns_structure(self, client):
        """Known gene returns full detail with SNPs and traits."""
        gene = _mock_gene()

        # Mock session with multiple queries
        gene_result = MagicMock()
        gene_result.scalar_one_or_none.return_value = gene

        # SNPs query
        snps_result = MagicMock()
        snps_scalars = MagicMock()
        snps_scalars.all.return_value = []
        snps_result.scalars.return_value = snps_scalars

        # Count query
        count_result = MagicMock()
        count_result.scalar.return_value = 0

        # PGx query
        pgx_result = MagicMock()
        pgx_result.scalar_one_or_none.return_value = None

        # Traits query
        traits_result = MagicMock()
        traits_result.__iter__ = MagicMock(return_value=iter([]))

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[gene_result, snps_result, count_result, pgx_result, traits_result]
        )

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/gene/BRCA1")
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "BRCA1"
        assert data["name"] == "BRCA1 DNA repair associated"
        assert data["is_pharmacogene"] is False
        assert "clinvar_stats" in data
        assert "snps" in data

    def test_gene_symbol_too_long(self, client):
        """Gene symbol > 50 chars returns 400."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/gene/{'A' * 51}")
        assert response.status_code == 400
