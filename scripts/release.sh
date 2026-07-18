#!/usr/bin/env bash
set -euo pipefail

echo "=== ruff check ==="
ruff check .

echo "=== ruff format ==="
ruff format . --check

echo "=== mypy ==="
mypy src/veltix/

echo "=== Version check ==="
VERSION=$(python -c "import re; content = open('pyproject.toml').read(); print(re.search(r'^version\s*=\s*[\"\'](.*?)[\"\']', content, re.MULTILINE).group(1))")
echo "Version: $VERSION"
if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+'; then
    echo "❌ Invalid version: $VERSION"
    exit 1
fi
echo "✅ Version valid: $VERSION"

echo "=== Compatibility table ==="
python -c "
import re
content = open('pyproject.toml').read()
ver = re.search(r'^version\s*=\s*[\"\'](.*?)[\"\']', content, re.MULTILINE).group(1)
parts = [int(re.sub(r'[^0-9].*', '', p)) for p in ver.split('.')[:3]]

compat = open('src/veltix/internal/compatibility.py').read()
entry = f'Version({parts[0]}, {parts[1]}, {parts[2]})'
if entry not in compat:
    print(f'❌ Version {ver} not found in COMPATIBILITY table!')
    print(f'   Add this to src/veltix/internal/compatibility.py:')
    print(f'   {entry}: [{entry}],')
    exit(1)
print(f'✅ Version {ver} is registered in COMPATIBILITY table')
"

echo "=== Tests ==="
python -m pytest tests/ --tb=short

echo ""
echo "✅ All checks passed — ready to release."
