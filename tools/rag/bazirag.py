#!/usr/bin/env python3
import asyncio
import os
import sqlite3
import sys
from pathlib import Path

import httpx
import numpy as np
import turbovec
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent

# Load environment
load_dotenv()

# ── TurboVec + SQLite paths (configurable via env, defaults to local ./data) ───────
RAG_DIR = Path(os.getenv("RAG_DATA_DIR", str(Path(__file__).resolve().parent / "data")))
TURBOVEC_INDEX_PATH = Path(os.getenv("TURBOVEC_INDEX_PATH", RAG_DIR / "bazi_index.tv"))
BAZI_SQLITE_PATH = Path(os.getenv("BAZI_SQLITE_PATH", RAG_DIR / "bazi_metadata.db"))

BGEM3_URL = os.getenv("BGEM3_URL", "http://localhost:8002/v1/embeddings")
BGEM3_TOKEN = os.getenv("BGEM3_TOKEN", "")

# ── Pydantic AI Schema & Agent ────────────────────────────────────
class StructuredBaziQuery(BaseModel):
    classical_terms: list[str] = Field(
        min_length=3,
        max_length=3,
        description=(
            "Exactly 3 distinct technical Simplified Chinese search terms representing: "
            "1. The Day Master or Stem/Branch in Chinese (e.g. 庚金, 戊土). "
            "2. The metaphysical/structure focus in Chinese (e.g. 食神, 偏印, 官杀). "
            "3. The domain query in Chinese (e.g. 财运, 寿夭, 贵贱)."
        )
    )

RAG_MODEL = os.getenv("RAG_MODEL", "google/gemini-2.0-flash")

agent = Agent(
    RAG_MODEL,
    output_type=StructuredBaziQuery,
    system_prompt=(
        "You are an expert in Zi Ping Bazi metaphysics. "
        "Translate natural language queries into exactly 3 highly-precise classical "
        "Simplified Chinese search terms matching classical texts (like Di Tian Sui or San Ming Tong Hui)."
    ),
)


def _load_turbovec_index() -> turbovec.IdMapIndex:
    if not TURBOVEC_INDEX_PATH.exists():
        raise FileNotFoundError(
            f"TurboVec index not found at {TURBOVEC_INDEX_PATH}. "
            "Run the ingestion pipeline first: uv run python infrastructure/rag/run_rag_pipeline.py"
        )
    return turbovec.IdMapIndex.load(str(TURBOVEC_INDEX_PATH))


def _get_sqlite_connection():
    if not BAZI_SQLITE_PATH.exists():
        raise FileNotFoundError(
            f"SQLite metadata database not found at {BAZI_SQLITE_PATH}. "
            "Run the ingestion pipeline first."
        )
    conn = sqlite3.connect(str(BAZI_SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    return conn


async def get_embedding(text: str, client: httpx.AsyncClient) -> list[float]:
    is_openai = "v1/embeddings" in BGEM3_URL
    payload = {"input": text} if is_openai else [text]
    headers = {"Authorization": f"Bearer {BGEM3_TOKEN}"} if BGEM3_TOKEN else {}

    r = await client.post(BGEM3_URL, json=payload, headers=headers, timeout=30.0)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        elif "embeddings" in data:
            return data["embeddings"][0]
        else:
            raise ValueError(f"Unexpected response structure: {data}")
    else:
        return data[0]


async def search_single(
    index: turbovec.IdMapIndex,
    conn: sqlite3.Connection,
    http_client: httpx.AsyncClient,
    keyword: str,
) -> list[dict]:
    try:
        query_vector = await get_embedding(keyword, http_client)
    except Exception as e:
        print(f"⚠️ Embedding failed for '{keyword}': {e}", file=sys.stderr)
        return []

    try:
        query_np = np.array(query_vector, dtype=np.float32).reshape(1, -1)
        scores, ids = index.search(query_np, k=30)
    except Exception as e:
        print(f"⚠️ TurboVec search failed for '{keyword}': {e}", file=sys.stderr)
        return []

    retrieved_ids = ids.flatten().tolist()
    score_list = scores.flatten().tolist()

    placeholders = ",".join("?" * len(retrieved_ids))
    rows = conn.execute(
        f"SELECT id, source, chunk_index, text FROM chunks WHERE id IN ({placeholders})",
        retrieved_ids,
    ).fetchall()

    id_to_row = {row["id"]: row for row in rows}

    candidates = []
    for tid, score in zip(retrieved_ids, score_list):
        row = id_to_row.get(tid)
        if row is None:
            continue
        candidates.append({
            "score": round(1.0 - score, 4),
            "source": row["source"],
            "chunk_index": row["chunk_index"],
            "text": row["text"],
        })

    candidates.sort(key=lambda x: x["score"], reverse=True)
    return candidates[:5]


async def search_bazi(query: str, limit: int = 15) -> list[dict]:
    index = _load_turbovec_index()
    conn = _get_sqlite_connection()

    async with httpx.AsyncClient() as http_client:
        result = await agent.run(query)
        keywords = result.output.classical_terms
        print(f"🔍 Translated terms: {keywords}", file=sys.stderr)

        tasks = [search_single(index, conn, http_client, kw) for kw in keywords]
        all_results = await asyncio.gather(*tasks)

    conn.close()

    seen = set()
    merged = []
    for sub_res in all_results:
        for item in sub_res:
            key = (item["source"], item["chunk_index"])
            if key not in seen:
                seen.add(key)
                merged.append(item)

    merged.sort(key=lambda x: x["score"], reverse=True)
    return merged[:limit]


async def main():
    if len(sys.argv) < 2:
        print("Usage: uv run bazirag.py \"<natural language query>\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    results = await search_bazi(query)

    print(f"# BaziRAG Report for: '{query}'\n")
    for i, res in enumerate(results, 1):
        print(f"### {i}. Source: `{res['source']}` (Score: {res['score']})")
        print("```text")
        print(res["text"].strip())
        print("```\n")


if __name__ == "__main__":
    asyncio.run(main())
