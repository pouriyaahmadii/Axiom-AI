"""Authentication dependencies and service credential validation."""

import hmac

from fastapi import Request

from app.core.config import get_settings
from app.core.exceptions import AuthenticationError

settings = get_settings()


async def verify_api_key(request: Request) -> str:
    """Validate API key from request headers or bearer token.

    Accepts:
    1. Header `X-API-Key: <key>`
    2. Header `Authorization: Bearer <key>`
    """
    # 1. Check X-API-Key
    api_key = request.headers.get("X-API-Key")

    # 2. Check Authorization header
    if not api_key:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            api_key = auth_header[7:].strip()

    expected_key = settings.API_KEY

    # Check key if provided
    if api_key:
        if hmac.compare_digest(api_key, expected_key) or hmac.compare_digest(
            api_key, settings.SECRET_KEY
        ):
            return api_key
        raise AuthenticationError("Invalid service API key.")

    # In production, credentials are strictly mandatory
    if settings.ENVIRONMENT == "production":
        raise AuthenticationError("API key required in production.")

    # In local development / test mode, allow loopback callers if no key specified
    client_host = request.client.host if request.client else "unknown"
    if client_host in ("127.0.0.1", "localhost", "testclient"):
        return "local-dev-loopback"

    raise AuthenticationError("Authentication required.")
