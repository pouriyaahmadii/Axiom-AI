#!/usr/bin/env bash
set -euo pipefail

echo "==> Running pytest suite for services/backend..."
pytest services/backend/tests "$@"
