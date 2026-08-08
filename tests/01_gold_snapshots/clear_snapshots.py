#!/usr/bin/env python3
"""
Utility script to clear cached/expected bot responses and timestamps
inside the snapshot JSON files under the TEST/GOLD/ directory [baziforecaster-only: not in kit download]
"""

import json
from pathlib import Path

GOLD_DIR = Path(__file__).parent.resolve()

def clear_snapshot(snap_file: Path):
    print(f"Clearing {snap_file.relative_to(GOLD_DIR.parent)}")
    with open(snap_file) as f:
        data = json.load(f)

    # Reset/clear values
    if "actual_bot_response" in data:
        data["actual_bot_response"] = ""
    if "actual_bot_responses" in data:
        data["actual_bot_responses"] = {}
    if "expected_bot_response" in data:
        data["expected_bot_response"] = ""
    if "expected_bot_responses" in data:
        data["expected_bot_responses"] = {}
    if "last_updated" in data:
        data["last_updated"] = ""

    with open(snap_file, "w") as f:
        json.dump(data, f, indent=2)

def main():
    for snap_file in sorted(GOLD_DIR.glob("**/snapshot*.json")):
        clear_snapshot(snap_file)

if __name__ == "__main__":
    main()
