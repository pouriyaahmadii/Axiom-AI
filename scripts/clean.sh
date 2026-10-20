#!/usr/bin/env bash
set -euo pipefail

echo "==> Cleaning Python bytecode and test caches..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.py[cod]" -delete 2>/dev/null || true
rm -rf .pytest_cache .ruff_cache .coverage htmlcov 2>/dev/null || true
echo "==> Done."
