import asyncio
import sys

from bazirag import search_bazi


async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print('  uv run python query_cli.py "natural language query"')
        print("  uv run python query_cli.py <keyword1> <keyword2> <keyword3>")
        sys.exit(1)

    args = sys.argv[1:]
    if len(args) == 3:
        # Keywords mode — join into a single query for the LLM-powered translator
        query_str = " ".join(args)
    else:
        # Query mode
        query_str = " ".join(args)

    res = await search_bazi(query_str)
    for i, r in enumerate(res, 1):
        print(f"### {i}. Source: `{r['source']}` (Score: {r['score']})")
        print("```text")
        print(r["text"].strip())
        print("```\n")


if __name__ == "__main__":
    asyncio.run(main())