#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo "=== CC Nested Scan (src2/) ==="
echo ""
find "$PROJECT_ROOT/src2" -name "*.py" -print0 | xargs -0 uv run python "$SCRIPT_DIR/find_cc_nested.py" --min-cc 6

echo ""
echo "=== Ruff Check Summary (src2/) ==="
echo ""
cd "$PROJECT_ROOT"
uv run ruff check src2/ 2>&1 | tail -5

echo ""
echo "=== CC>=6 Functions Detail ==="
echo ""
uv run python -c "
from radon.complexity import cc_visit
from pathlib import Path

results = []
for fpath in Path('src2').rglob('*.py'):
    try:
        source = fpath.read_text(encoding='utf-8', errors='ignore')
        blocks = cc_visit(source)
        for b in blocks:
            if b.complexity >= 6:
                results.append((b.complexity, str(fpath), b.name, b.lineno))
    except:
        pass

results.sort(reverse=True)
for cc, fpath, name, lineno in results:
    print(f'  CC {cc:3d}  {name:<40s}  {fpath}:{lineno}')
print(f'\nTotal CC>=6 functions: {len(results)}')
" 2>&1
