#!/usr/bin/env python3
"""Validates all n8n workflow JSON files for structural integrity, syntax, and zero credential leakage."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
N8N_DIR = ROOT_DIR / "workflows" / "n8n"

# Sensitive token patterns that must never appear in committed n8n workflow files
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9]{32,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36,}", re.IGNORECASE),
    re.compile(r"tvly-[a-zA-Z0-9]{32,}", re.IGNORECASE),
    re.compile(r"Bearer\s+ey[a-zA-Z0-9\._\-]{20,}", re.IGNORECASE),
]


def validate_workflow_file(file_path: Path) -> list[str]:
    """Validate a single n8n workflow JSON file. Returns list of error messages."""
    errors: list[str] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as exc:
        return [f"Could not read file: {exc}"]

    # 1. Secret pattern scanning
    for pattern in SECRET_PATTERNS:
        match = pattern.search(content)
        if match:
            errors.append(
                f"Potential hardcoded secret detected matching {pattern.pattern}: '{match.group(0)[:8]}...'"
            )

    # 2. JSON syntax parsing
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        return [f"Invalid JSON syntax at line {exc.lineno}, col {exc.colno}: {exc.msg}"]

    if not isinstance(data, dict):
        return ["Workflow root must be a JSON object."]

    # 3. Top-level n8n schema checks
    if "nodes" not in data:
        errors.append("Missing required top-level key: 'nodes'")
    elif not isinstance(data["nodes"], list):
        errors.append("'nodes' must be a list")
    elif len(data["nodes"]) == 0:
        errors.append("'nodes' list must not be empty")

    if "connections" not in data:
        errors.append("Missing required top-level key: 'connections'")
    elif not isinstance(data["connections"], dict):
        errors.append("'connections' must be a JSON object")

    # 4. Node integrity
    nodes = data.get("nodes", [])
    if isinstance(nodes, list):
        node_names = set()
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(f"Node at index {idx} is not an object")
                continue
            name = node.get("name")
            if not name:
                errors.append(f"Node at index {idx} is missing 'name'")
            elif name in node_names:
                errors.append(f"Duplicate node name '{name}' at index {idx}")
            else:
                node_names.add(name)

            if "type" not in node:
                errors.append(f"Node '{name or idx}' is missing 'type'")

    return errors


def main() -> int:
    if not N8N_DIR.exists():
        print(f"Error: Directory {N8N_DIR} does not exist", file=sys.stderr)
        return 1

    json_files = sorted(list(N8N_DIR.glob("*.json")) + list(N8N_DIR.glob("**/*.json")))
    # Deduplicate in case glob overlap
    seen = set()
    unique_files: list[Path] = []
    for f in json_files:
        if f.resolve() not in seen:
            seen.add(f.resolve())
            unique_files.append(f)

    if not unique_files:
        print(f"No JSON workflow files found in {N8N_DIR}")
        return 0

    print(f"Validating {len(unique_files)} n8n workflow file(s)...")
    total_errors = 0

    for file_path in unique_files:
        rel_path = file_path.relative_to(ROOT_DIR)
        errors = validate_workflow_file(file_path)
        if errors:
            print(f"FAIL: {rel_path}")
            for err in errors:
                print(f"      - {err}")
            total_errors += len(errors)
        else:
            print(f"PASS: {rel_path}")

    if total_errors > 0:
        print(f"\nValidation failed with {total_errors} error(s).", file=sys.stderr)
        return 1

    print("\nAll n8n workflow files are valid and contain no credential leakage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
