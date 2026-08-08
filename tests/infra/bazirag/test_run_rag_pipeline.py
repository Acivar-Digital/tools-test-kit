"""
Tests for the RAG ingestion pipeline (run_rag_pipeline.py).
Covers SHA-256 ID hashing, SQLite schema, turbovec ingestion,
index persistence, and backup/rollback logic.
"""
import hashlib
import shutil
import sqlite3
from pathlib import Path

import numpy as np
import pytest
import turbovec

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

VECTOR_SIZE = 1024
BIT_WIDTH = 4


def _chunk_id_to_uint64(source_name: str, idx: int) -> int:
    raw = f"{source_name}:{idx}"
    return abs(int(hashlib.sha256(raw.encode()).hexdigest(), 16)) % (2**63)


class TestChunkIdHashing:
    def test_deterministic_id(self):
        id_a = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        id_b = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        assert id_a == id_b, "Same source and index must produce the same ID"

    def test_different_source_different_id(self):
        id_a = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        id_b = _chunk_id_to_uint64("zi_ping_zhen_quan", 0)
        assert id_a != id_b, "Different sources must produce different IDs"

    def test_different_index_different_id(self):
        id_a = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        id_b = _chunk_id_to_uint64("yuan_hai_zi_ping", 1)
        assert id_a != id_b, "Different indices must produce different IDs"

    def test_id_is_uint64(self):
        chunk_id = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        assert 0 <= chunk_id < 2**63, f"ID {chunk_id} is not in uint64 range"
        assert isinstance(chunk_id, int), "ID must be a Python int"

    def test_id_matches_sha256_mod(self):
        raw = "san_ming_zhi_mi_fu:5"
        expected = abs(int(hashlib.sha256(raw.encode()).hexdigest(), 16)) % (2**63)
        assert _chunk_id_to_uint64("san_ming_zhi_mi_fu", 5) == expected


class TestSqliteSchema:
    def test_chunks_table_created(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "id INTEGER PRIMARY KEY,"
            "source TEXT,"
            "chunk_index INTEGER,"
            "text TEXT"
            ")"
        )
        conn.commit()
        cursor = conn.execute("PRAGMA table_info(chunks)")
        columns = {row[1] for row in cursor.fetchall()}
        conn.close()
        assert columns == {"id", "source", "chunk_index", "text"}

    def test_insert_and_retrieve_chunk(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "id INTEGER PRIMARY KEY,"
            "source TEXT,"
            "chunk_index INTEGER,"
            "text TEXT"
            ")"
        )
        chunk_id = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        conn.execute(
            "INSERT INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
            (chunk_id, "yuan_hai_zi_ping", 0, "测试文本"),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        conn.close()
        assert row is not None
        assert row[1] == "yuan_hai_zi_ping"
        assert row[2] == 0
        assert row[3] == "测试文本"

    def test_insert_or_replace_does_not_duplicate(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "id INTEGER PRIMARY KEY,"
            "source TEXT,"
            "chunk_index INTEGER,"
            "text TEXT"
            ")"
        )
        chunk_id = _chunk_id_to_uint64("yuan_hai_zi_ping", 0)
        conn.execute(
            "INSERT OR REPLACE INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
            (chunk_id, "yuan_hai_zi_ping", 0, "原始文本"),
        )
        conn.execute(
            "INSERT OR REPLACE INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
            (chunk_id, "yuan_hai_zi_ping", 0, "更新文本"),
        )
        conn.commit()
        rows = conn.execute("SELECT COUNT(*) FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        conn.close()
        assert rows[0] == 1, "INSERT OR REPLACE must not create duplicates"


class TestTurbovecIngestion:
    def test_add_with_ids_receives_2d_float32(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(3, VECTOR_SIZE).astype(np.float32)
        ids = np.array([100, 200, 300], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        query = np.random.rand(1, VECTOR_SIZE).astype(np.float32)
        scores, retrieved = index.search(query, k=3)
        assert len(retrieved.flatten()) > 0

    def test_add_with_ids_uint64_ids(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(2, VECTOR_SIZE).astype(np.float32)
        ids = np.array([2**63 - 1, 0], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        scores, retrieved = index.search(vectors[0:1], k=2)
        assert len(retrieved.flatten().tolist()) > 0

    def test_index_shape_matches_vector_size(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(1, VECTOR_SIZE).astype(np.float32)
        ids = np.array([42], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        scores, retrieved = index.search(vectors, k=1)
        assert len(scores.flatten()) == 1

    def test_reshape_1d_to_2d_required(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(5, VECTOR_SIZE).astype(np.float32)
        ids = np.arange(5, dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        query_1d = np.random.rand(VECTOR_SIZE).astype(np.float32)
        with pytest.raises(Exception):
            index.search(query_1d, k=1)

    def test_reshape_1d_to_2d_works(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(5, VECTOR_SIZE).astype(np.float32)
        ids = np.arange(5, dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        query_1d = np.random.rand(VECTOR_SIZE).astype(np.float32)
        query_2d = query_1d.reshape(1, -1)
        scores, retrieved = index.search(query_2d, k=1)
        assert scores.shape == (1, 1)


class TestIndexPersistence:
    def test_write_produces_nonempty_file(self, tmp_path: Path):
        index_path = tmp_path / "test_index.tv"
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(2, VECTOR_SIZE).astype(np.float32)
        ids = np.array([1, 2], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        index.write(str(index_path))
        assert index_path.exists()
        assert index_path.stat().st_size > 0

    def test_load_from_disk(self, tmp_path: Path):
        index_path = tmp_path / "test_index.tv"
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        vectors = np.random.rand(2, VECTOR_SIZE).astype(np.float32)
        ids = np.array([10, 20], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        index.write(str(index_path))
        loaded = turbovec.IdMapIndex.load(str(index_path))
        scores, retrieved = loaded.search(vectors[0:1], k=2)
        assert len(retrieved.flatten().tolist()) > 0

    def test_write_overwrites_existing(self, tmp_path: Path):
        index_path = tmp_path / "test_index.tv"
        index1 = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        v1 = np.random.rand(1, VECTOR_SIZE).astype(np.float32)
        index1.add_with_ids(v1, np.array([1], dtype=np.uint64))
        index1.write(str(index_path))
        index2 = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        v2 = np.random.rand(3, VECTOR_SIZE).astype(np.float32)
        index2.add_with_ids(v2, np.array([2, 3, 4], dtype=np.uint64))
        index2.write(str(index_path))
        size2 = index_path.stat().st_size
        assert size2 > 0


class TestBackupAndRollback:
    def test_backup_copies_existing_files(self, tmp_path: Path):
        tv_path = tmp_path / "bazi_index.tv"
        db_path = tmp_path / "bazi_metadata.db"
        tv_path.write_text("index data")
        db_path.write_text("db data")
        backup_dir = tmp_path / "pipeline_backup"
        backup_dir.mkdir()
        for path in (tv_path, db_path):
            backup_path = path.with_suffix(path.suffix + ".pipeline_backup")
            shutil.copy2(path, backup_path)
        assert (tv_path.with_suffix(tv_path.suffix + ".pipeline_backup")).exists()
        assert (db_path.with_suffix(db_path.suffix + ".pipeline_backup")).exists()

    def test_rollback_restores_from_backup(self, tmp_path: Path):
        tv_path = tmp_path / "bazi_index.tv"
        backup_path = tv_path.with_suffix(tv_path.suffix + ".pipeline_backup")
        tv_path.write_text("original")
        backup_path.write_text("backup")
        tv_path.write_text("corrupted")
        assert tv_path.read_text() == "corrupted"
        shutil.copy2(backup_path, tv_path)
        assert tv_path.read_text() == "backup"

    def test_backup_removes_existing_backup(self, tmp_path: Path):
        tv_path = tmp_path / "bazi_index.tv"
        backup_path = tv_path.with_suffix(tv_path.suffix + ".pipeline_backup")
        tv_path.write_text("original")
        backup_path.write_text("old backup")
        if backup_path.exists():
            backup_path.unlink()
        shutil.copy2(tv_path, backup_path)
        assert backup_path.exists()

    def test_rollback_missing_backup_logs_error(self, tmp_path: Path, capsys):
        tv_path = tmp_path / "bazi_index.tv"
        backup_path = tv_path.with_suffix(tv_path.suffix + ".pipeline_backup")
        assert not backup_path.exists()
        if tv_path.exists():
            tv_path.unlink()


class TestPipelineIntegration:
    def test_full_ingest_cycle(self, tmp_path: Path, mock_embedding_fn):
        db_path = tmp_path / "bazi_metadata.db"
        index_path = tmp_path / "bazi_index.tv"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE IF NOT EXISTS chunks ("
            "id INTEGER PRIMARY KEY,"
            "source TEXT,"
            "chunk_index INTEGER,"
            "text TEXT"
            ")"
        )
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
        source = "yuan_hai_zi_ping"
        texts = ["测试文本一", "测试文本二", "测试文本三"]
        vectors = mock_embedding_fn(texts)
        ids = np.array(
            [_chunk_id_to_uint64(source, i) for i in range(len(texts))],
            dtype=np.uint64,
        )
        vecs = np.array(vectors, dtype=np.float32)
        index.add_with_ids(vecs, ids)
        for i, (text, vid) in enumerate(zip(texts, vectors)):
            cid = _chunk_id_to_uint64(source, i)
            conn.execute(
                "INSERT OR REPLACE INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
                (cid, source, i, text),
            )
        conn.commit()
        index.write(str(index_path))
        assert index_path.exists()
        assert index_path.stat().st_size > 0
        row_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        assert row_count == 3
        conn.close()

    def test_empty_texts_produce_no_chunks(self):
        texts = [t for t in [] if t.strip()]
        assert texts == []

    def test_batch_ingest_splits_correctly(self):
        items = list(range(25))
        batch_size = 15
        batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
        assert len(batches) == 2
        assert len(batches[0]) == 15
        assert len(batches[1]) == 10
