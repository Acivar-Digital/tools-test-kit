"""
RAG Pipeline: Clean rebuild of bazi_classical collection using TurboVec + SQLite.

Drops the existing index and database, then rebuilds from clean texts.

Usage:
    uv run python infrastructure/rag/run_rag_pipeline.py

Stages:
    1. Backup existing index and database
    2. Initialize TurboVec IdMapIndex and SQLite database
    3. Clean and ingest replacement texts
    4. Verify results
"""
import hashlib
import os
import shutil
import sqlite3
import sys
import time

import numpy as np
import requests
import turbovec

# ── Config ──────────────────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAG_DIR = os.path.join(PROJECT_ROOT, "infrastructure", "rag")

TURBOVEC_INDEX_PATH = os.path.join(RAG_DIR, "bazi_index.tv")
BAZI_SQLITE_PATH = os.path.join(RAG_DIR, "bazi_metadata.db")
BACKUP_DIR = os.path.join(RAG_DIR, "pipeline_backup")

EMBED_URL = "http://localhost:8002/v1/embeddings"

VECTOR_SIZE = 1024
BIT_WIDTH = 4
CHUNK_SIZE = 400
CHUNK_OVERLAP = 50
BATCH_SIZE = 15

SOURCES = {
    "yuan_hai_zi_ping":     {"file": "yuan_hai_zi_ping.txt",     "label": "渊海子平"},
    "zi_ping_zhen_quan":    {"file": "zi_ping_zhen_quan.txt",    "label": "子平真诠"},
    "qiong_tong_bao_jian":  {"file": "qiong_tong_bao_jian.txt",  "label": "穷通宝鉴"},
    "san_ming_zhi_mi_fu":   {"file": "san_ming_zhi_mi_fu.txt",   "label": "三命指迷赋"},
    "san_ming_tong_hui":    {"file": "san_ming_tong_hui.txt",    "label": "三命通会"},
    "shen_feng_tong_kao":   {"file": "shen_feng_tong_kao.txt",   "label": "神峰通考"},
    "qian_li_ming_gao":     {"file": "qian_li_ming_gao.txt",     "label": "千里命稿"},
    "di_tian_sui":          {"file": "di_tian_sui.txt",          "label": "滴天髓"},
    "ming_li_tan_yuan":     {"file": "ming_li_tan_yuan.txt",     "label": "命理探源"},
}


def log(msg: str):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")


def backup():
    for path in (TURBOVEC_INDEX_PATH, BAZI_SQLITE_PATH):
        if os.path.exists(path):
            backup_path = path + ".pipeline_backup"
            if os.path.exists(backup_path):
                log(f"Removing existing backup at {backup_path}")
                if os.path.isdir(backup_path):
                    shutil.rmtree(backup_path)
                else:
                    os.remove(backup_path)
            log(f"Backing up {path} -> {backup_path}")
            shutil.copy2(path, backup_path)
            log("Backup complete")


def rollback():
    for path in (TURBOVEC_INDEX_PATH, BAZI_SQLITE_PATH):
        backup_path = path + ".pipeline_backup"
        if not os.path.exists(backup_path):
            log(f"ERROR: No backup found for {path}, cannot rollback")
            continue
        log(f"Rolling back {path}...")
        if os.path.exists(path):
            os.remove(path)
        shutil.copy2(backup_path, path)
        log(f"Rollback complete for {path}")


def init_sqlite(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "id INTEGER PRIMARY KEY,"
        "source TEXT,"
        "chunk_index INTEGER,"
        "text TEXT"
        ")"
    )
    conn.commit()
    return conn


def init_turbovec(index_path: str) -> turbovec.IdMapIndex:
    if os.path.exists(index_path):
        os.remove(index_path)
    index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
    return index


def _chunk_id_to_uint64(source_name: str, idx: int) -> int:
    raw = f"{source_name}:{idx}"
    return abs(int(hashlib.sha256(raw.encode()).hexdigest(), 16)) % (2**63)


def clean_text(raw_text: str, source_name: str) -> str:
    import re
    text = re.sub(r'<!--.*?-->', '', raw_text, flags=re.DOTALL)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()

    if source_name == "yuan_hai_zi_ping":
        text = re.sub(r'【[^】]*】', '', text)
        text = re.sub(r'★', '', text)
        text = re.sub(r'[。！？]', r'\g<0>\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
    elif source_name == "zi_ping_zhen_quan":
        lines = text.split('\n')
        text = '\n'.join(lines[3:])
        text = re.sub(r'\.{4,}.*?\d+', '', text)
        text = re.sub(r'-\d+/\d+-', '', text)
    elif source_name == "qiong_tong_bao_jian":
        text = re.sub(r'=+\s*', '', text)
        text = re.sub(r'\[edit\]', '', text)
    elif source_name == "san_ming_zhi_mi_fu":
        text = text.replace('【', ' ').replace('】', ' ')
        text = re.sub(r'\s+', ' ', text)

    return text.strip()


def chunk_text(text: str, source_name: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[dict]:
    # Sanitize lone surrogates to prevent UnicodeEncodeError during JSON
    # serialization in the embedding ingestion pipeline (embed → requests.post json=).
    text = text.encode("utf-8", "replace").decode("utf-8")
    chunks = []
    start = 0
    idx = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            last_period = text.rfind('。', start, end)
            last_newline = text.rfind('\n', start, end)
            break_point = max(last_period, last_newline)
            if break_point > start + chunk_size // 2:
                end = break_point + 1

        chunk_text_val = text[start:end].strip()
        if chunk_text_val and len(chunk_text_val) > 10:
            chunk_id = _chunk_id_to_uint64(source_name, idx)
            chunks.append({
                "id": chunk_id,
                "source": source_name,
                "chunk_index": idx,
                "text": chunk_text_val,
            })
            idx += 1

        if end >= len(text):
            break

        start = end - overlap if end - overlap > start else end

    return chunks


def embed(texts: list[str]) -> list[list[float]]:
    texts = [t for t in texts if t.strip()]
    if not texts:
        return []
    r = requests.post(EMBED_URL, json={"input": texts}, timeout=60)
    if r.status_code != 200:
        log(f"  Embedding error {r.status_code}: {r.text[:200]}")
        log(f"  First text repr: {repr(texts[0][:100])}")
    r.raise_for_status()
    return [item["embedding"] for item in r.json()["data"]]


def ingest_text(conn: sqlite3.Connection, index: turbovec.IdMapIndex,
                source_name: str, raw_text: str):
    log(f"  Cleaning and chunking {source_name}...")
    cleaned = clean_text(raw_text, source_name)
    chunks = chunk_text(cleaned, source_name)
    log(f"  Created {len(chunks)} chunks from {len(cleaned)} chars")

    batch_size = BATCH_SIZE
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        batch_texts = [c["text"] for c in batch]
        try:
            vectors = embed(batch_texts)
        except Exception as e:
            log(f"  Embedding failed at batch {i}: {e}")
            raise

        ids = np.array([c["id"] for c in batch], dtype=np.uint64)
        vecs = np.array(vectors, dtype=np.float32)
        index.add_with_ids(vecs, ids)

        for c in batch:
            conn.execute(
                "INSERT OR REPLACE INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
                (c["id"], c["source"], c["chunk_index"], c["text"]),
            )

        if (i // batch_size) % 5 == 0:
            log(f"  Ingested {min(i + batch_size, len(chunks))}/{len(chunks)} chunks")

    conn.commit()
    log(f"  Finished ingesting {source_name}: {len(chunks)} chunks")


def verify(conn: sqlite3.Connection, index: turbovec.IdMapIndex):
    log("\n=== Verification ===")
    cursor = conn.execute("SELECT source, COUNT(*) FROM chunks GROUP BY source ORDER BY source")
    sources = cursor.fetchall()
    total = sum(count for _, count in sources)
    log(f"Total chunks: {total}")
    for s, n in sources:
        log(f"  {n:>5} — {s}")

    for source_name, info in SOURCES.items():
        cursor = conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE source = ?", (source_name,)
        )
        count = cursor.fetchone()[0]
        label = info["label"]
        if count > 0:
            log(f"  {label} ({source_name}): {count} chunks")
        else:
            log(f"  WARNING: {label} ({source_name}) has 0 chunks!")

    log(f"  TurboVec index vectors: {index.ntotal() if hasattr(index, 'ntotal') else 'N/A'}")
    return total


def main():
    log("=== RAG Pipeline: TurboVec + SQLite Rebuild ===")

    try:
        r = requests.get("http://localhost:8002/health", timeout=5)
        r.raise_for_status()
        log("TEI embedding server OK (BAAI/bge-m3)")
    except Exception as e:
        log(f"ERROR: TEI embedding server not reachable: {e}")
        log("Run: text-embeddings-router ...")
        sys.exit(1)

    backup()

    try:
        if os.path.exists(BAZI_SQLITE_PATH):
            os.remove(BAZI_SQLITE_PATH)
        if os.path.exists(TURBOVEC_INDEX_PATH):
            os.remove(TURBOVEC_INDEX_PATH)

        conn = init_sqlite(BAZI_SQLITE_PATH)
        index = init_turbovec(TURBOVEC_INDEX_PATH)

        log("\nIngesting all texts...")
        for source_name, info in SOURCES.items():
            file_path = os.path.join(RAG_DIR, info["file"])
            if not os.path.exists(file_path):
                log(f"  WARNING: {file_path} not found, skipping {source_name}")
                continue
            with open(file_path, encoding="utf-8") as f:
                raw = f.read()
            ingest_text(conn, index, source_name, raw)

        index.write(TURBOVEC_INDEX_PATH)
        log(f"TurboVec index persisted to {TURBOVEC_INDEX_PATH}")

        count_after = verify(conn, index)
        log(f"\n=== Pipeline Complete: {count_after} chunks ===")

        conn.close()

    except Exception as e:
        log(f"ERROR: Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        log("Rolling back to backup...")
        rollback()
        sys.exit(1)


if __name__ == "__main__":
    main()
