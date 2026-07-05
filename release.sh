#!/usr/bin/env bash
set -euo pipefail

echo "=== ruff check ==="
ruff check .

echo "=== ruff format ==="
ruff format . --check

echo "=== mypy ==="
mypy veltix/

echo "=== Version consistency ==="
VERSION_PY=$(python -c "import re; content = open('veltix/version.py').read(); print(re.search(r'__version__\s*=\s*[\"\'](.*?)[\"\']', content).group(1))")
VERSION_TOML=$(python -c "import re; content = open('pyproject.toml').read(); print(re.search(r'^version\s*=\s*[\"\'](.*?)[\"\']', content, re.MULTILINE).group(1))")

if [ "$VERSION_PY" != "$VERSION_TOML" ]; then
    echo ""
    echo "❌ Version mismatch!"
    echo "   version.py    → $VERSION_PY"
    echo "   pyproject.toml → $VERSION_TOML"
    exit 1
fi
echo "✅ Versions match: $VERSION_PY"

echo "=== Tests ==="
python -m pytest tests/ -v --tb=short

echo "=== Build check ==="
python -m build --check 2>/dev/null || python -m pip install build && python -m build --check

echo ""
echo "✅ All checks passed — ready to release."
