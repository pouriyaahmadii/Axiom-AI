"""Baseline tests verifying project configuration, security primitives, and API readiness."""

import pytest

from app.core.config import Settings
from app.core.logging import get_logger, setup_logging
from app.core.security import (
    SecurityValidationError,
    generate_secure_token,
    is_safe_url,
    validate_url_for_request,
    verify_hmac_signature,
)


def test_settings_defaults():
    """Verify default configuration has secure loopback and mock values."""
    settings = Settings()
    assert settings.API_HOST == "127.0.0.1"
    assert settings.LLM_PROVIDER == "mock"
    assert settings.SEARCH_PROVIDER == "mock"
    assert settings.MAX_PLAN_STEPS == 10
    assert settings.MAX_EXECUTION_SECONDS == 300
    assert settings.STEP_TIMEOUT_SECONDS == 60
    assert settings.BUDGET_USD_LIMIT == 1.00


def test_ssrf_rejects_disallowed_schemes():
    """Verify non-HTTP schemes are rejected by SSRF guard."""
    safe, reason = is_safe_url("file:///etc/passwd")
    assert not safe
    assert "scheme" in reason.lower()

    safe, reason = is_safe_url("ftp://example.com/test.txt")
    assert not safe
    assert "scheme" in reason.lower()


def test_ssrf_rejects_localhost_and_loopback():
    """Verify loopback addresses are blocked by default."""
    safe, reason = is_safe_url("http://localhost:8000/api")
    assert not safe
    assert "loopback" in reason.lower() or "localhost" in reason.lower()

    safe, reason = is_safe_url("http://127.0.0.1:8000/api")
    assert not safe
    assert "blocked" in reason.lower() or "private" in reason.lower()


def test_ssrf_rejects_cloud_metadata_ip():
    """Verify AWS/GCP/Azure link-local metadata IP (169.254.169.254) is blocked."""
    safe, reason = is_safe_url("http://169.254.169.254/latest/meta-data/")
    assert not safe
    assert "blocked" in reason.lower() or "private" in reason.lower()


def test_ssrf_rejects_private_subnets():
    """Verify RFC 1918 private subnets are blocked."""
    # 10.0.0.0/8
    safe, _ = is_safe_url("http://10.0.0.5/admin")
    assert not safe

    # 192.168.0.0/16
    safe, _ = is_safe_url("http://192.168.1.100/status")
    assert not safe

    # 172.16.0.0/12
    safe, _ = is_safe_url("http://172.16.0.1/dashboard")
    assert not safe


def test_validate_url_for_request_raises_security_exception():
    """Verify validate_url_for_request raises SecurityValidationError on unsafe URLs."""
    with pytest.raises(SecurityValidationError):
        validate_url_for_request("http://127.0.0.1/internal")


def test_secure_token_generation():
    """Verify random secure token generation."""
    token1 = generate_secure_token(32)
    token2 = generate_secure_token(32)
    assert len(token1) >= 32
    assert len(token2) >= 32
    assert token1 != token2


def test_hmac_signature_verification():
    """Verify constant-time HMAC signature generation and verification."""
    secret = "test-secret-key-42"
    payload = b'{"event":"test","status":"ok"}'

    # Compute signature
    import hashlib
    import hmac

    valid_sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

    assert verify_hmac_signature(payload, valid_sig, secret) is True
    assert verify_hmac_signature(payload, "invalid_sig", secret) is False
    assert verify_hmac_signature(payload, valid_sig, "wrong-secret") is False
    assert verify_hmac_signature(payload, valid_sig, "") is False


def test_structured_logging():
    """Verify structured logging setup initializes properly."""
    setup_logging(level="DEBUG", log_format="json")
    logger = get_logger("test_logger")
    assert logger is not None


@pytest.mark.asyncio
async def test_api_root_endpoint(async_client):
    """Verify GET / returns application status."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "AgentOps"
    assert "version" in data


@pytest.mark.asyncio
async def test_api_health_endpoint(async_client):
    """Verify GET /api/v1/health returns healthy status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["app_name"] == "AgentOps"
    assert data["llm_provider"] == "mock"
    assert data["search_provider"] == "mock"


@pytest.mark.asyncio
async def test_api_info_endpoint(async_client):
    """Verify GET /api/v1/info returns system constraints."""
    response = await async_client.get("/api/v1/info")
    assert response.status_code == 200
    data = response.json()
    assert "limits" in data
    assert data["limits"]["max_plan_steps"] == 10
    assert data["providers"]["llm"] == "mock"
