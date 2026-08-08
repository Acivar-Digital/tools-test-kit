import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getenv("KIT_INFRA_ROOT", ""))

from _infra_codebase import index_repository


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for index_repository")
    parser.add_argument("repo_name", help="Repository folder name")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate collection")
    parser.add_argument("--collection-name", help="Custom collection name")
    args = parser.parse_args()

    result = index_repository(
        repo_name=args.repo_name,
        reset=args.reset,
        collection_name=args.collection_name
    )
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
