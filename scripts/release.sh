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

echo "=== Protocol version ==="
python -c "
import re
content = open('src/veltix/internal/compatibility.py').read()
match = re.search(r'PROTOCOL_VERSION: tuple\[int, int\] = \((\d+), (\d+)\)', content)
if not match:
    print('❌ PROTOCOL_VERSION not found or malformed in src/veltix/internal/compatibility.py')
    exit(1)
major, minor = int(match.group(1)), int(match.group(2))
print(f'✅ PROTOCOL_VERSION = {major}.{minor}')
"

echo "=== Tests ==="
python -m pytest tests/ --tb=short

echo ""
echo "✅ All checks passed — ready to release."
