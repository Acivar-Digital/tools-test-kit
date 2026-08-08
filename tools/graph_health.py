import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getenv("KIT_INFRA_ROOT", ""))

from _infra_codebase import graph_health


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for graph_health")
    parser.parse_args()

    result = graph_health()
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
