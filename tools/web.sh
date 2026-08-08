#!/bin/bash
# Resolve the project root directory (two levels up from kit-tools/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Run the Python script with PYTHONPATH set to the project root
PYTHONPATH="$PROJECT_ROOT" uv run python "$SCRIPT_DIR/web.py" "$@"
