#!/usr/bin/env python3
import asyncio
import json
import os
import sqlite3
import sys
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from qdrant_client import AsyncQdrantClient

from control import ControlSheet  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INFRA_ROOT = Path(os.getenv("KIT_INFRA_ROOT", str(PROJECT_ROOT.parent)))
GRAPH_JSON = INFRA_ROOT / "infra" / "graph" / "code_knowledge_graph.json"
DIRECTIVES_DB = INFRA_ROOT / ".ctx" / "agents_graph.db"

KIT_QDRANT_URL = os.getenv("KIT_QDRANT_URL", "http://localhost:6333")
KIT_EMBEDDING_URL = os.getenv("KIT_EMBEDDING_URL", "http://localhost:8002")
KIT_EMBEDDING_TOKEN = os.getenv("KIT_EMBEDDING_TOKEN", "")
COLLECTION_NAME = os.getenv("KIT_COLLECTION_NAME", "codebase_index")

class StructuredCodeQuery(BaseModel):
    semantic_concepts: list[str] = Field(
        description="Key conceptual terms or themes to search semantically (e.g. 'session handling', 'timezone correction')."
    )
    literal_symbols: list[str] = Field(
        default_factory=list,
        description="Exact variable, class, function, or method names detected (e.g. 'UserProfile', 'db')."
    )
    target_directory: str | None = Field(
        None,
        description="If the query targets a specific directory, extract it (e.g., 'src/bot', 'src/engine')."
    )
    file_extensions: list[str] = Field(
        default_factory=lambda: ["*.py"],
        description="List of target file extensions (e.g., '*.py', '*.md', '*.json')."
    )

# Initialize Pydantic AI Agent (sandboxed: ControlSheet.codebase_model)
model = ControlSheet.codebase_model
agent = Agent(
    model,
    output_type=StructuredCodeQuery,
    system_prompt="Parse this codebase search query into structured fields.",
)

async def get_embedding(text: str, async_client: httpx.AsyncClient) -> list[float]:
    is_openai = "v1/embeddings" in KIT_EMBEDDING_URL
    payload = {"input": text} if is_openai else [text]
    headers = {"Authorization": f"Bearer {KIT_EMBEDDING_TOKEN}"} if KIT_EMBEDDING_TOKEN else {}

    resp = await async_client.post(KIT_EMBEDDING_URL, json=payload, headers=headers, timeout=30.0)
    resp.raise_for_status()
    data = resp.json()

    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list) and len(data["data"]) > 0:
            return data["data"][0]["embedding"]
        else:
            return data["embeddings"][0]
    else:
        return data[0]

def _resolve_secure_path(relative_path: str) -> Path:
    try:
        root = PROJECT_ROOT.resolve()
        if relative_path.startswith(f"{root.name}/"):
            relative_path = relative_path[len(f"{root.name}/") :]
        elif relative_path == root.name:
            relative_path = ""
        target = (root / relative_path).resolve()
        if not target.is_relative_to(root):
            raise ValueError(f"Path escape detected: {relative_path}")
        return target
    except Exception as e:
        raise ValueError(f"Invalid path: {relative_path} ({str(e)})")

def _get_scope_expanded_snippet(rel_path: str, match_text: str) -> str:
    import ast
    try:
        path = _resolve_secure_path(rel_path)
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return match_text[:300] + "..."

    try:
        tree = ast.parse(content)

        match_line = -1
        lines = content.splitlines()
        for i, line in enumerate(lines):
            if match_text in line:
                match_line = i + 1
                break

        if match_line == -1:
            return match_text[:300] + "..."

        parent_header = ""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.lineno <= match_line <= (node.end_lineno or node.lineno):
                    header_line = lines[node.lineno - 1].strip()
                    parent_header = f"[{header_line}] "
                    break

        snippet = lines[max(0, match_line - 3) : match_line + 5]
        return parent_header + "\n".join(snippet)
    except Exception as e:
        raise e

async def query_knowledge_graph(query: str, query_vec: list[float], max_entities: int = 10) -> dict[str, Any]:
    if not GRAPH_JSON.exists():
        return {"success": False, "message": "Knowledge graph not found.", "data": {}}

    try:
        graph = json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        return {"success": False, "message": f"Failed to load graph: {e}", "data": {}}

    entities = graph.get("entities", [])
    if not entities:
        return {"success": True, "message": "Graph has no entities.", "data": {"entities": [], "relationships": []}}

    import numpy as np
    q_vec = np.array(query_vec)
    q_norm = np.linalg.norm(q_vec)

    matched_entities = []
    if q_norm >= 1e-10:
        all_scores = []
        for i, ent in enumerate(entities):
            if "embedding" in ent:
                e_vec = np.array(ent["embedding"])
                e_norm = np.linalg.norm(e_vec)
                if e_norm >= 1e-10:
                    score = float(np.dot(q_vec, e_vec) / (q_norm * e_norm))
                    if not np.isnan(score):
                        all_scores.append((i, score))

        all_scores.sort(key=lambda x: x[1], reverse=True)
        top_indices = [idx for idx, _ in all_scores[:max_entities]]
        matched_entities = [entities[idx] for idx in top_indices]


    matched_names = {e["name"].lower() for e in matched_entities}
    related_rels = []
    for rel in graph.get("relationships", []):
        src_low = rel["source"].lower()
        tgt_low = rel["target"].lower()
        if src_low in matched_names or tgt_low in matched_names:
            related_rels.append(rel)

    return {
        "success": True,
        "data": {
            "entities": matched_entities,
            "relationships": related_rels[: max_entities * 5],
        },
    }

async def inject_directives(query_vec: list[float], top_k: int = 2, threshold: float = 0.6) -> list[dict]:
    if not DIRECTIVES_DB.exists():
        return []

    import numpy as np
    q_vec = np.array(query_vec)
    q_norm = np.linalg.norm(q_vec)
    if q_norm < 1e-10:
        return []

    conn = sqlite3.connect(str(DIRECTIVES_DB))
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT id, section_title, content, embedding_json FROM directives").fetchall()
    conn.close()

    results = []
    for row in rows:
        emb_json = row["embedding_json"]
        if not emb_json:
            continue
        try:
            emb = np.array(json.loads(emb_json))
            e_norm = np.linalg.norm(emb)
            if e_norm < 1e-10:
                continue
            score = float(np.dot(q_vec, emb) / (q_norm * e_norm))
            if score >= threshold:
                results.append({
                    "section_title": row["section_title"],
                    "content": row["content"][:500],
                    "score": round(score, 4),
                })
        except Exception as e:
            raise e

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

async def mcp_search(query: str, limit: int = 10):
    try:
        async with httpx.AsyncClient() as async_client:
            result = await agent.run(f"Parse this codebase search query: {query}")
            structured_query = result.output

            search_str = " ".join(structured_query.semantic_concepts) if structured_query.semantic_concepts else query

            query_vector = await get_embedding(search_str, async_client)

            qdrant = AsyncQdrantClient(url=KIT_QDRANT_URL)

            try:
                raw_limit = limit * 3
                results = await qdrant.query_points(
                    collection_name=COLLECTION_NAME, query=query_vector, limit=raw_limit, with_payload=True
                )
                points = results.points
            finally:
                await qdrant.close()

            matches = []
            for res in points:
                if not res.payload:
                    continue
                rel_path = res.payload.get("file_path", "unknown")
                raw_content = res.payload.get("content", "")

                if structured_query.target_directory:
                    target_dir = structured_query.target_directory.strip("/")
                    if target_dir not in rel_path:
                        continue

                if structured_query.file_extensions:
                    norm_exts = [e.replace("*", "").strip() for e in structured_query.file_extensions]
                    norm_exts = [e for e in norm_exts if e]
                    if norm_exts:
                        if not any(rel_path.endswith(ext) for ext in norm_exts):
                            continue

                snippet = _get_scope_expanded_snippet(rel_path, raw_content)

                score = res.score
                if structured_query.literal_symbols:
                    for sym in structured_query.literal_symbols:
                        if sym in snippet or sym in raw_content:
                            score = min(1.0, score + 0.15)

                matches.append({
                    "file_path": rel_path,
                    "score": round(score, 4),
                    "snippet": snippet,
                    "source": "vector"
                })

            matches.sort(key=lambda x: x["score"], reverse=True)
            matches = matches[:limit]

            graph_resp = await query_knowledge_graph(query, query_vector, max_entities=limit)
            directives = await inject_directives(query_vector, top_k=2, threshold=0.6)

            # Print Markdown Report
            print(f"# Search Report for: '{query}'\n")

            print(f"## Top Vector Matches ({len(matches)})\n")
            for i, match in enumerate(matches, 1):
                print(f"### {i}. `{match['file_path']}` (Score: {match['score']})")
                print("```python")
                print(match['snippet'])
                print("```\n")

            if graph_resp.get("success") and graph_resp["data"].get("entities"):
                print("## Key Knowledge Graph Context\n")
                print("### Entities")
                for ent in graph_resp["data"]["entities"][:5]:  # Limit to top 5
                    print(f"- **{ent['name']}**: {ent.get('description', '')}")

                rels = graph_resp["data"].get("relationships", [])
                if rels:
                    print("\n### Relationships")
                    for rel in rels[:5]:  # Limit to top 5
                        print(f"- {rel['source']} --[{rel.get('rel_type', 'related')}]--> {rel['target']}")
                print()

            if directives:
                print("## Auto-Injected Directives\n")
                for d in directives:
                    print(f"### {d['section_title']} (Score: {d['score']})")
                    print(f"{d['content']}...\n")
    except Exception as e:
        print(f"Error during search: {e}", file=sys.stderr)
        raise

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python search.py <query>")
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    asyncio.run(mcp_search(query))
