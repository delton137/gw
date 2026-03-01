"""Tests for the health check endpoint."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routes.health import router

_app = FastAPI()
_app.include_router(router)


def test_health_returns_ok():
    with TestClient(_app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
