#!/usr/bin/env bash
set -euo pipefail

echo "==> Running Ruff formatting check..."
ruff format --check .

echo "==> Running Ruff linter..."
ruff check .
