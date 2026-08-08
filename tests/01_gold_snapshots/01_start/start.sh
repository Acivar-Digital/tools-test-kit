#!/usr/bin/env bash
set -euo pipefail

# Run the 01_start GOLD E2E test against the live tmux infra (bazi-infra, :8445).
# Must be run with the server already up (see [baziforecaster-only: TEST/GOLD/00_infra/start.sh not in kit download]).
cd "$(dirname "$0")/../../.."

# [baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.]
uv run python -c 'import sys; sys.path.insert(0,"."); import TEST.GOLD.run as R; R.SERVER_URL="http://127.0.0.1:8445"; R.HEALTH_ENDPOINT=R.SERVER_URL+"/health"; import json; print(json.dumps(R.run_test_folder("01_start"), indent=2, default=str))'
