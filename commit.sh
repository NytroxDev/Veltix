#!/usr/bin/env bash
set -euo pipefail

echo "=== ruff check ==="
ruff check .

echo "=== ruff format ==="
ruff format . --check

echo "=== mypy ==="
mypy veltix/

echo ""
echo "✅ All checks passed — ready to commit."
