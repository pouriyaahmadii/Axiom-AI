"""Integration tests for health probes, authentication boundaries, and OpenAPI docs."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_async_session

settings = get_settings()


@pytest.mark.integration
async def test_liveness_probe(async_client: AsyncClient):
    """Verify GET /health/live returns 200 without dependency checks."""
    response = await async_client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


@pytest.mark.integration
async def test_readiness_probe_healthy(async_client: AsyncClient):
    """Verify GET /health/ready returns 200 and connected status when database is reachable."""
    response = await async_client.get("/health/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert "app_name" in data


@pytest.mark.integration
async def test_readiness_probe_dependency_unavailable(app):
    """Verify GET /health/ready returns 503 when the database dependency fails."""

    class FailingSession:
        async def execute(self, *_args, **_kwargs):  # type: ignore[no-untyped-def]
            raise RuntimeError("Database connection failure simulation")

    async def _failing_session():
        yield FailingSession()

    app.dependency_overrides[get_async_session] = _failing_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health/ready")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["database"] == "unavailable"


@pytest.mark.integration
async def test_auth_invalid_api_key(app):
    """Verify that requests with an invalid API key receive 401 Unauthorized."""
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "completely-invalid-key-attempt"}
    async with AsyncClient(
        transport=transport, base_url="http://testserver", headers=headers
    ) as client:
        response = await client.post(
            "/api/v1/runs",
            json={"objective": "Unauthorized attempt objective", "domain": "security"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.integration
async def test_auth_valid_api_key(app):
    """Verify that requests with the valid internal service key are accepted."""
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": settings.API_KEY}
    async with AsyncClient(
        transport=transport, base_url="http://testserver", headers=headers
    ) as client:
        response = await client.post(
            "/api/v1/runs",
            json={"objective": "Authorized valid run objective", "domain": "testing"},
        )
        assert response.status_code == 202


@pytest.mark.integration
async def test_openapi_documentation_coverage(async_client: AsyncClient):
    """Verify that OpenAPI documentation reflects all implemented endpoints."""
    response = await async_client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    paths = spec["paths"]

    # Verify all expected endpoints exist in OpenAPI
    expected_paths = [
        "/api/v1/runs",
        "/api/v1/runs/{run_id}",
        "/api/v1/runs/{run_id}/steps",
        "/api/v1/runs/{run_id}/events",
        "/api/v1/runs/{run_id}/cancel",
        "/api/v1/runs/{run_id}/report",
        "/api/v1/approvals/{approval_id}/approve",
        "/api/v1/approvals/{approval_id}/reject",
        "/health/live",
        "/health/ready",
    ]

    for expected in expected_paths:
        assert expected in paths, f"OpenAPI specification is missing endpoint: {expected}"
