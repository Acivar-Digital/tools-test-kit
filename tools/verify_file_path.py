import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getenv("KIT_INFRA_ROOT", ""))

from _infra_codebase import verify_file_path


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for verify_file_path")
    parser.add_argument("path", help="Path to verify")
    args = parser.parse_args()

    result = verify_file_path(args.path)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
