#!/usr/bin/env python3
"""Local secret scanning scanner detecting accidental credential leakage in repository files."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

# Directories to ignore
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    ".next",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
    "coverage",
    "dist",
    "build",
}

# Files to ignore
IGNORE_FILES = {
    ".env.example",
    "compose.override.yaml.example",
    "package-lock.json",
}

# Known test and mock placeholder secrets that are explicitly allowed in test fixtures
ALLOWED_PLACEHOLDERS = {
    "agentops-dev-internal-key",
    "dev-secret-key-change-in-production-at-least-32-chars-long",
    "postgres_dev_pass",
    "agentops_pass",
    "n8n_pass",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "n8n_local_webhook_secret_for_hmac_verification",
    "test-secret-key-at-least-32-chars-long",
    "test-secret-key-42",
}

SECRET_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "Private Key Header",
        re.compile(r"-----BEGIN\s+(?:RSA|OPENSSH|DSA|EC|PGP)?\s*PRIVATE KEY-----"),
    ),
    ("AWS Access Key ID", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub Personal Access Token", re.compile(r"\bghp_[a-zA-Z0-9]{36}\b")),
    ("GitHub OAuth Access Token", re.compile(r"\bgho_[a-zA-Z0-9]{36}\b")),
    ("OpenAI API Key", re.compile(r"\bsk-(?:live|proj|test)?[a-zA-Z0-9]{32,}\b")),
    ("Tavily API Key", re.compile(r"\btvly-[a-zA-Z0-9]{32,}\b")),
    ("Slack API Token", re.compile(r"\bxox[baprs]-[0-9a-zA-Z]{10,48}\b")),
    (
        "Generic Password Assignment",
        re.compile(
            r"""(?:password|passwd|pwd|secret)\s*[:=]\s*["']([^"'\s]{10,})["']""", re.IGNORECASE
        ),
    ),
]


def should_ignore(path: Path) -> bool:
    for part in path.parts:
        if part in IGNORE_DIRS:
            return True
    if path.name in IGNORE_FILES:
        return True
    return path.suffix.lower() in {".pyc", ".png", ".jpg", ".jpeg", ".ico", ".svg", ".lock", ".db"}


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return [f"Unable to read file: {exc}"]

    lines = content.splitlines()
    for line_num, line in enumerate(lines, start=1):
        # Skip lines containing approved dev placeholders
        if any(placeholder in line for placeholder in ALLOWED_PLACEHOLDERS):
            continue

        for rule_name, pattern in SECRET_RULES:
            match = pattern.search(line)
            if match:
                # If generic password matched, check if it's a dummy value
                val = match.group(0)
                if any(p in val for p in ALLOWED_PLACEHOLDERS):
                    continue
                findings.append(f"Line {line_num} [{rule_name}]: {line[:80].strip()}")

    return findings


def main() -> int:
    print(f"Scanning repository for potential secrets starting from {ROOT_DIR}...")
    files_to_scan: list[Path] = []

    for root, dirs, files in os.walk(ROOT_DIR):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            p = Path(root) / f
            if not should_ignore(p):
                files_to_scan.append(p)

    total_findings = 0
    scanned_count = len(files_to_scan)

    for p in files_to_scan:
        rel_path = p.relative_to(ROOT_DIR)
        issues = scan_file(p)
        if issues:
            print(f"\nALERT: Secret found in {rel_path}:")
            for issue in issues:
                print(f"  {issue}")
            total_findings += len(issues)

    print(f"\nScanned {scanned_count} files.")
    if total_findings > 0:
        print(f"FAILED: Found {total_findings} potential secret(s) in repository.", file=sys.stderr)
        return 1

    print("SUCCESS: Zero hardcoded secrets detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
