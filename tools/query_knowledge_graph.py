import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.getenv("KIT_INFRA_ROOT", ""))

from _infra_codebase import query_knowledge_graph


def main():
    parser = argparse.ArgumentParser(description="CLI wrapper for query_knowledge_graph")
    parser.add_argument("query", help="Natural language query")
    parser.add_argument("--max-entities", type=int, default=10, help="Max entities to return (default 10)")
    args = parser.parse_args()

    result = query_knowledge_graph(args.query, max_entities=args.max_entities)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
