"""Sensitive data redactor and payload size boundary for logs and traces."""

from __future__ import annotations

import re
from typing import Any

# Field names that must be redacted (case-insensitive substring and exact matches)
SENSITIVE_KEY_NAMES: frozenset[str] = frozenset(
    {
        "api_key",
        "apikey",
        "secret",
        "secret_key",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "cookie",
        "set-cookie",
        "private_key",
        "credentials",
        "bearer",
        "webhook_secret",
        "client_secret",
        "proxy_auth",
        "x-api-key",
    }
)

# Regex patterns for sensitive tokens and headers inside arbitrary strings
BEARER_TOKEN_REGEX = re.compile(r"(Bearer\s+)[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE)
OPENAI_KEY_REGEX = re.compile(r"sk-[A-Za-z0-9]{20,}", re.IGNORECASE)
SENSITIVE_URL_PARAM_REGEX = re.compile(
    r"([?&](?:api_key|token|secret|password|key)=)[^&#\s]+", re.IGNORECASE
)

REDACTED_MASK = "[REDACTED]"
DEFAULT_MAX_STRING_LENGTH = 1024
DEFAULT_MAX_PAYLOAD_DEPTH = 8


def is_sensitive_key(key: str) -> bool:
    """Check if a dictionary or header key matches sensitive naming patterns."""
    normalized = key.lower().replace("-", "_")
    if normalized in SENSITIVE_KEY_NAMES:
        return True
    return any(
        sensitive in normalized
        for sensitive in ("api_key", "secret", "password", "token", "auth", "cookie")
    )


def sanitize_string(value: str, max_length: int = DEFAULT_MAX_STRING_LENGTH) -> str:
    """Scrub sensitive patterns from a string and bound its length."""
    if not value:
        return value

    # Scrub known pattern formats
    scrubbed = BEARER_TOKEN_REGEX.sub(r"\1[REDACTED]", value)
    scrubbed = OPENAI_KEY_REGEX.sub("[REDACTED]", scrubbed)
    scrubbed = SENSITIVE_URL_PARAM_REGEX.sub(r"\1[REDACTED]", scrubbed)

    # Bound maximum length
    if len(scrubbed) > max_length:
        excess = len(scrubbed) - max_length
        return f"{scrubbed[:max_length]}... [truncated {excess} chars]"
    return scrubbed


def redact_data(
    data: Any,
    max_string_len: int = DEFAULT_MAX_STRING_LENGTH,
    current_depth: int = 0,
    max_depth: int = DEFAULT_MAX_PAYLOAD_DEPTH,
) -> Any:
    """Recursively scrub sensitive keys and bound payload sizes across collections."""
    if current_depth > max_depth:
        return "... [max payload depth reached]"

    if isinstance(data, dict):
        sanitized_dict: dict[str, Any] = {}
        for key, val in data.items():
            key_str = str(key)
            if is_sensitive_key(key_str):
                if isinstance(val, dict):
                    sanitized_dict[key_str] = redact_data(
                        val,
                        max_string_len=max_string_len,
                        current_depth=current_depth + 1,
                        max_depth=max_depth,
                    )
                else:
                    sanitized_dict[key_str] = REDACTED_MASK
            else:
                sanitized_dict[key_str] = redact_data(
                    val,
                    max_string_len=max_string_len,
                    current_depth=current_depth + 1,
                    max_depth=max_depth,
                )
        return sanitized_dict

    if isinstance(data, (list, tuple, set)):
        sanitized_list = [
            redact_data(
                item,
                max_string_len=max_string_len,
                current_depth=current_depth + 1,
                max_depth=max_depth,
            )
            for item in data
        ]
        return type(data)(sanitized_list) if not isinstance(data, set) else set(sanitized_list)

    if isinstance(data, str):
        return sanitize_string(data, max_length=max_string_len)

    return data


def redact_log_event(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Structlog processor ensuring no secrets or unbounded values escape into logs."""
    return redact_data(event_dict)
