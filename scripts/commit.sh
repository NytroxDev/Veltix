#!/usr/bin/env bash
set -euo pipefail

echo "=== ruff check ==="
ruff check .

echo "=== ruff format ==="
ruff format . --check

echo "=== mypy ==="
mypy veltix/

echo "=== Compatibility table ==="
python -c "
import re
content = open('veltix/version.py').read()
ver = re.search(r'__version__\s*=\s*[\"\'](.*?)[\"\']', content).group(1)
parts = [int(x) for x in ver.split('.')[:3]]

compat = open('veltix/internal/compatibility.py').read()
entry = f'Version({parts[0]}, {parts[1]}, {parts[2]})'
if entry not in compat:
    print(f'❌ Version {ver} not found in COMPATIBILITY table!')
    print(f'   Add this to veltix/internal/compatibility.py:')
    print(f'   {entry}: [{entry}],')
    exit(1)
print(f'✅ Version {ver} is registered in COMPATIBILITY table')
"

echo "=== Tests ==="
python -m pytest tests/ --tb=short

echo ""
echo "✅ All checks passed — ready to commit."
