"""Tests for results endpoints — analysis status, PRS results, trait hits."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.results import router
from app.db import get_session
from app.auth import get_current_user_id
from tests.helpers import TEST_USER_ID, make_auth_override

TEST_ANALYSIS_ID = str(uuid.uuid4())

_app = FastAPI()
_app.include_router(router, prefix="/api/v1")

_app.dependency_overrides[get_current_user_id] = make_auth_override()


def _mock_analysis(status="done", analysis_id=None):
    """Create a mock Analysis ORM object."""
    analysis = MagicMock()
    analysis.id = uuid.UUID(analysis_id or TEST_ANALYSIS_ID)
    analysis.user_id = TEST_USER_ID
    analysis.status = status
    analysis.chip_type = "23andme_v5"
    analysis.variant_count = 640000
    analysis.error_message = None
    analysis.detected_ancestry = {"EUR": 0.85}
    analysis.ancestry_method = "computed"
    analysis.ancestry_confidence = 0.85
    analysis.selected_ancestry = "EUR"
    analysis.created_at = datetime(2025, 1, 15, tzinfo=timezone.utc)
    analysis.completed_at = datetime(2025, 1, 15, 0, 5, tzinfo=timezone.utc)
    return analysis


def _mock_trait_hit(rsid="rs429358", trait="Alzheimer's", risk_level="moderate"):
    """Create a mock UserSnpTraitHit ORM object."""
    hit = MagicMock()
    hit.id = uuid.uuid4()
    hit.rsid = rsid
    hit.user_genotype = "CT"
    hit.trait = trait
    hit.effect_description = "Increased risk"
    hit.risk_level = risk_level
    hit.evidence_level = "high"
    return hit


@pytest.fixture(autouse=True)
def _reset_overrides():
    yield
    _app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


class TestGetAnalysisStatus:
    def test_returns_status(self, client):
        """Returns analysis status for valid ID."""
        analysis = _mock_analysis(status="done")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = analysis
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/analysis/{TEST_ANALYSIS_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert data["chip_type"] == "23andme_v5"
        assert data["variant_count"] == 640000

    def test_pending_status(self, client):
        """Pending analysis returns status and no error."""
        analysis = _mock_analysis(status="pending")
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = analysis
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/analysis/{TEST_ANALYSIS_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "pending"
        assert data["error_message"] is None

    def test_not_found(self, client):
        """Unknown analysis ID returns 404."""
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/analysis/{uuid.uuid4()}")
        assert response.status_code == 404

    def test_failed_includes_error(self, client):
        """Failed analysis includes error_message."""
        analysis = _mock_analysis(status="failed")
        analysis.error_message = "Parse error"
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = analysis
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/analysis/{TEST_ANALYSIS_ID}")
        assert response.status_code == 200
        assert response.json()["error_message"] == "Parse error"

    def test_selected_ancestry_included(self, client):
        """Analysis status includes selected_ancestry."""
        analysis = _mock_analysis(status="done")
        analysis.selected_ancestry = "AFR"
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = analysis
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/analysis/{TEST_ANALYSIS_ID}")
        assert response.status_code == 200
        assert response.json()["selected_ancestry"] == "AFR"

    def test_done_status_with_error_shows_prs_failure(self, client):
        """Done status with error_message shows the PRS failure error."""
        analysis = _mock_analysis(status="done")
        analysis.error_message = "PRS scoring failed: connection lost"
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = analysis
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/analysis/{TEST_ANALYSIS_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["error_message"] == "PRS scoring failed: connection lost"


class TestGetPrsResults:
    def test_returns_prs_list(self, client):
        """Returns PRS results from most recent analysis."""
        analysis = _mock_analysis()

        # Mock for select(Analysis) — finds most recent done
        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        # Mock for the fetch_prs_results text query — returns a PRS row
        prs_row = MagicMock()
        prs_row.pgs_id = "PGS000001"
        prs_row.trait_name = "CAD"
        prs_row.raw_score = 5.2
        prs_row.percentile = 72.3
        prs_row.z_score = 0.59
        prs_row.ref_mean = 4.8
        prs_row.ref_std = 1.1
        prs_row.ancestry_group_used = "EUR"
        prs_row.n_variants_matched = 65
        prs_row.n_variants_total = 77
        prs_row.reported_auc = None
        prs_row.percentile_lower = 60.0
        prs_row.percentile_upper = 82.0
        prs_row.coverage_quality = "high"
        prs_row.computed_at = datetime(2025, 1, 15, tzinfo=timezone.utc)
        prs_row.trait_type = None
        prs_row.prevalence = None

        prs_result = MagicMock()
        prs_result.__iter__ = MagicMock(return_value=iter([prs_row]))

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[analysis_result, prs_result])

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/prs/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == TEST_ANALYSIS_ID
        assert len(data["results"]) == 1
        assert data["results"][0]["pgs_id"] == "PGS000001"
        assert data["results"][0]["percentile"] == 72.3

    def test_no_analysis_returns_404(self, client):
        """No completed analysis → 404."""
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/prs/{TEST_USER_ID}")
        assert response.status_code == 404

    def test_prs_status_ready_when_complete(self, client):
        """PRS status is 'ready' when analysis is complete."""
        analysis = _mock_analysis(status="complete")

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        prs_result = MagicMock()
        prs_result.__iter__ = MagicMock(return_value=iter([]))

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[analysis_result, prs_result])

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/prs/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["prs_status"] == "ready"
        assert data["selected_ancestry"] == "EUR"

    def test_prs_status_computing_when_done(self, client):
        """PRS status is 'computing' when analysis is done (fast results ready, PRS still running)."""
        analysis = _mock_analysis(status="done")

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        prs_result = MagicMock()
        prs_result.__iter__ = MagicMock(return_value=iter([]))

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[analysis_result, prs_result])

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/prs/{TEST_USER_ID}")
        assert response.status_code == 200
        assert response.json()["prs_status"] == "computing"

    def test_prs_status_failed_when_done_with_error(self, client):
        """PRS status is 'failed' when analysis is done with an error message."""
        analysis = _mock_analysis(status="done")
        analysis.error_message = "PRS scoring failed: connection lost"

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        prs_result = MagicMock()
        prs_result.__iter__ = MagicMock(return_value=iter([]))

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[analysis_result, prs_result])

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/prs/{TEST_USER_ID}")
        assert response.status_code == 200
        assert response.json()["prs_status"] == "failed"

    def test_wrong_user_returns_403(self, client):
        """Accessing another user's results → 403."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/results/prs/user_someone_else")
        assert response.status_code == 403


class TestGetTraitHits:
    def test_returns_hits(self, client):
        """Returns trait hits for user."""
        analysis = _mock_analysis()
        hit = _mock_trait_hit()

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        hits_result = MagicMock()
        hits_result.all.return_value = [(hit, "APOE", "C", "Higher Alzheimer's risk")]

        kb_total_result = MagicMock()
        kb_total_result.scalar.return_value = 116

        unique_matched_result = MagicMock()
        unique_matched_result.scalar.return_value = 1

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[analysis_result, hits_result, kb_total_result, unique_matched_result]
        )

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/traits/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert len(data["hits"]) == 1
        assert data["hits"][0]["rsid"] == "rs429358"
        assert data["hits"][0]["gene"] == "APOE"
        assert data["hits"][0]["risk_level"] == "moderate"

    def test_no_analysis_returns_404(self, client):
        """No completed analysis → 404."""
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/traits/{TEST_USER_ID}")
        assert response.status_code == 404

    def test_wrong_user_returns_403(self, client):
        """Accessing another user's traits → 403."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/results/traits/user_someone_else")
        assert response.status_code == 403

    def test_empty_hits(self, client):
        """Analysis exists but no trait hits → empty list."""
        analysis = _mock_analysis()
        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        hits_result = MagicMock()
        hits_result.all.return_value = []

        kb_total_result = MagicMock()
        kb_total_result.scalar.return_value = 116

        unique_matched_result = MagicMock()
        unique_matched_result.scalar.return_value = 0

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[analysis_result, hits_result, kb_total_result, unique_matched_result]
        )

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/traits/{TEST_USER_ID}")
        assert response.status_code == 200
        assert response.json()["hits"] == []


class TestGetClinvarHits:
    def test_returns_hits(self, client):
        """Returns ClinVar hits for user."""
        analysis = _mock_analysis()

        analysis_result = MagicMock()
        analysis_result.scalar_one_or_none.return_value = analysis

        # Mock count query result
        count_row = MagicMock()
        count_row.clinvar_significance = "pathogenic"
        count_row.cnt = 5
        count_result = MagicMock()
        count_result.__iter__ = MagicMock(return_value=iter([count_row]))

        # Mock paginated hits query result
        hit_row = MagicMock()
        hit_row.rsid = "rs1234"
        hit_row.user_genotype = "AG"
        hit_row.gene = "BRCA1"
        hit_row.clinvar_significance = "pathogenic"
        hit_row.clinvar_conditions = "Breast cancer"
        hit_row.clinvar_review_stars = 3
        hit_row.clinvar_allele_id = 12345
        hit_row.functional_class = "missense_variant"
        hit_row.chrom = "17"
        hit_row.position = 43000000
        hit_row.ref_allele = "A"
        hit_row.alt_allele = "G"
        hits_result = MagicMock()
        hits_result.all.return_value = [hit_row]

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[analysis_result, count_result, hits_result])

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/clinvar/{TEST_USER_ID}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert data["counts"]["pathogenic"] == 5
        assert len(data["hits"]) == 1
        assert data["hits"][0]["rsid"] == "rs1234"
        assert data["hits"][0]["clinvar_significance"] == "pathogenic"
        assert data["hits"][0]["ref_allele"] == "A"
        assert data["hits"][0]["alt_allele"] == "G"

    def test_no_analysis_returns_404(self, client):
        """No completed analysis → 404."""
        session = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get(f"/api/v1/results/clinvar/{TEST_USER_ID}")
        assert response.status_code == 404

    def test_wrong_user_returns_403(self, client):
        """Accessing another user's ClinVar results → 403."""
        session = AsyncMock()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.get("/api/v1/results/clinvar/user_someone_else")
        assert response.status_code == 403
