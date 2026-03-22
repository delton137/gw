"""Tests for newsletter subscribe endpoint."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.newsletter import router, _subscribe_attempts
from app.db import get_session

_app = FastAPI()
_app.include_router(router, prefix="/api/v1")


@pytest.fixture(autouse=True)
def _reset():
    """Reset rate limiter and dependency overrides between tests."""
    _subscribe_attempts.clear()
    yield
    _app.dependency_overrides.pop(get_session, None)
    _subscribe_attempts.clear()


@pytest.fixture
def client():
    with TestClient(_app) as c:
        yield c


def _mock_session_subscribe(existing=False):
    """Mock session for subscribe endpoint."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = 1 if existing else None
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    return session


class TestSubscribe:
    def test_valid_email(self, client):
        """Valid email returns OK."""
        session = _mock_session_subscribe()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/newsletter/subscribe",
            json={"email": "test@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_invalid_email(self, client):
        """Invalid email returns 422."""
        session = _mock_session_subscribe()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/newsletter/subscribe",
            json={"email": "not-an-email"},
        )
        assert response.status_code == 422

    def test_duplicate_email_returns_ok(self, client):
        """Already-subscribed email returns OK (no info leakage)."""
        session = _mock_session_subscribe(existing=True)

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        response = client.post(
            "/api/v1/newsletter/subscribe",
            json={"email": "existing@example.com"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_rate_limit(self, client):
        """6th attempt from same IP returns 429."""
        session = _mock_session_subscribe()

        async def override():
            return session

        _app.dependency_overrides[get_session] = override

        for i in range(5):
            resp = client.post(
                "/api/v1/newsletter/subscribe",
                json={"email": f"user{i}@example.com"},
            )
            assert resp.status_code == 200

        response = client.post(
            "/api/v1/newsletter/subscribe",
            json={"email": "user5@example.com"},
        )
        assert response.status_code == 429
