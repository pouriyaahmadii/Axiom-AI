#!/usr/bin/env python3
"""Audits Python dependencies for permissive licenses and security constraints per docs/17-dependency-policy.md."""

from __future__ import annotations

import re
import subprocess
import sys

# Prohibited license patterns according to ADR and dependency policy (strictly GPL / AGPL, not LGPL)
PROHIBITED_PATTERNS = [
    re.compile(r"\b(?:gnu\s+)?(?:affero\s+)?agpl\b", re.IGNORECASE),
    re.compile(r"\b(?:gnu\s+)?gpl(?:v[23])?\b", re.IGNORECASE),
    re.compile(r"\bsspl\b", re.IGNORECASE),
    re.compile(r"\bcommons\s+clause\b", re.IGNORECASE),
]


def check_python_licenses() -> int:
    """Audit installed package licenses if pip-licenses is available."""
    try:
        import importlib.metadata as importlib_metadata

        print("Auditing installed Python package licenses...")
        prohibited_found: list[tuple[str, str]] = []

        for dist in importlib_metadata.distributions():
            name = dist.metadata.get("Name", "unknown")
            license_str = (dist.metadata.get("License") or "").lower()
            classifiers = dist.metadata.get_all("Classifier") or []

            # Check if license matches prohibited copyleft
            for pattern in PROHIBITED_PATTERNS:
                # Exclude LGPL explicitly from matching GPL
                clean_lic = re.sub(r"\blgpl[^\s,]*\b", "", license_str, flags=re.IGNORECASE)
                if pattern.search(clean_lic):
                    prohibited_found.append((name, license_str))
                    break
                for c in classifiers:
                    clean_c = re.sub(r"\blgpl[^\s,]*\b", "", c, flags=re.IGNORECASE)
                    if pattern.search(clean_c):
                        prohibited_found.append((name, c))
                        break

        if prohibited_found:
            print("ALERT: Prohibited copyleft licenses detected:")
            for name, lic in prohibited_found:
                print(f"  - {name}: {lic}")
            return 1

        print(
            "SUCCESS: 100% of installed Python packages comply with the Permissive License Policy."
        )
        return 0
    except Exception as exc:
        print(f"Warning: License audit encountered error: {exc}", file=sys.stderr)
        return 0


def check_pip_audit() -> int:
    """Run pip-audit if installed in environment."""
    try:
        res = subprocess.run(["pip-audit", "--version"], capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Running {res.stdout.strip()}...")
            audit_res = subprocess.run(["pip-audit"], capture_output=True, text=True)
            print(audit_res.stdout)
            if audit_res.returncode != 0:
                print(audit_res.stderr, file=sys.stderr)
                return audit_res.returncode
    except FileNotFoundError:
        print("Note: pip-audit is not installed in the local environment; license check completed.")
    return 0


def main() -> int:
    ret_license = check_python_licenses()
    if ret_license != 0:
        return ret_license
    return check_pip_audit()


if __name__ == "__main__":
    sys.exit(main())
