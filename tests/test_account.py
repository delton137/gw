"""Tests for account endpoints — report download and data deletion."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.account import router
from app.db import get_session
from app.auth import get_current_user_id
from tests.helpers import TEST_USER_ID, make_auth_override

_app = FastAPI()
_app.include_router(router, prefix="/api/v1")

_app.dependency_overrides[get_current_user_id] = make_auth_override()


def _mock_session_no_analysis():
    """Mock session that returns no analysis for any query."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    return session


def _mock_session_for_delete(analyses=1):
    """Mock session for delete endpoint — single CASCADE delete on analyses."""
    session = AsyncMock()
    analysis_result = MagicMock(rowcount=analyses)
    session.execute = AsyncMock(return_value=analysis_result)
    session.commit = AsyncMock()
    return session


@pytest.fixture(autouse=True)
def _set_mock_session():
    """Default: mock session returns no analysis. Tests can override."""
    session = _mock_session_no_analysis()

    async def override():
        return session

    _app.dependency_overrides[get_session] = override
    yield session
    _app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


class TestDeleteEndpoint:
    def test_delete_returns_counts(self, client):
        session = _mock_session_for_delete(analyses=2)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.delete("/api/v1/account/data")
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "All your data has been permanently deleted."
        assert data["deleted"]["analyses"] == 2

    def test_delete_zero_rows(self, client):
        """Delete with no existing data returns zero counts."""
        session = _mock_session_for_delete(analyses=0)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.delete("/api/v1/account/data")
        assert response.status_code == 200
        data = response.json()
        assert data["deleted"]["analyses"] == 0


class TestDownloadEndpoint:
    def test_no_analysis_returns_404(self, client):
        """Returns 404 when no completed analysis exists."""
        response = client.get("/api/v1/report/download")
        assert response.status_code == 404
        assert "No completed analysis" in response.json()["detail"]
