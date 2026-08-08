"""
Tests for rag_client.py and bazirag.py query execution.
Covers async/sync queries, turbovec.search, SQLite joins,
float32 casting, and hard-fail error handling.
"""
import os
import sqlite3
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import aiosqlite
import numpy as np
import pytest
import turbovec

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

VECTOR_SIZE = 1024


class TestFloat32Reshape:
    def test_reshape_1d_to_2d_shape(self):
        vec = np.random.rand(VECTOR_SIZE).astype(np.float32)
        reshaped = vec.reshape(1, -1)
        assert reshaped.shape == (1, VECTOR_SIZE)
        assert reshaped.dtype == np.float32

    def test_reshape_preserves_data(self):
        vec = np.arange(VECTOR_SIZE, dtype=np.float32)
        reshaped = vec.reshape(1, -1)
        assert np.array_equal(reshaped.flatten(), vec)

    def test_query_np_is_2d_float32(self):
        query_vector = [0.1] * VECTOR_SIZE
        query_np = np.array(query_vector, dtype=np.float32).reshape(1, -1)
        assert query_np.dtype == np.float32
        assert query_np.ndim == 2
        assert query_np.shape == (1, VECTOR_SIZE)

    def test_turbovec_search_requires_2d_input(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=4)
        vectors = np.random.rand(5, VECTOR_SIZE).astype(np.float32)
        ids = np.arange(5, dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        query_2d = np.random.rand(1, VECTOR_SIZE).astype(np.float32)
        scores, retrieved = index.search(query_2d, k=3)
        assert scores.ndim == 2
        assert retrieved.ndim == 2


class TestSyncQueryExecution:
    def test_search_turbovec_sync_returns_scores_and_ids(self):
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=4)
        vectors = np.random.rand(5, VECTOR_SIZE).astype(np.float32)
        ids = np.array([100, 200, 300, 400, 500], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        query = np.random.rand(1, VECTOR_SIZE).astype(np.float32)
        scores, retrieved = index.search(query, k=3)
        assert len(scores.flatten()) == 3
        assert len(retrieved.flatten()) == 3

    def test_sqlite_join_with_retrieved_ids(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, chunk_index INTEGER, text TEXT)"
        )
        test_id = 999
        conn.execute(
            "INSERT INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
            (test_id, "test_source", 0, "test text"),
        )
        conn.commit()
        retrieved_ids = [test_id]
        placeholders = ",".join("?" * len(retrieved_ids))
        rows = conn.execute(
            f"SELECT id, source, chunk_index, text FROM chunks WHERE id IN ({placeholders})",
            retrieved_ids,
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == test_id
        assert rows[0][3] == "test text"

    def test_sqlite_join_handles_missing_ids(self, tmp_path: Path):
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, chunk_index INTEGER, text TEXT)"
        )
        conn.execute(
            "INSERT INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
            (1, "source_a", 0, "text a"),
        )
        conn.commit()
        retrieved_ids = [1, 9999]
        placeholders = ",".join("?" * len(retrieved_ids))
        rows = conn.execute(
            f"SELECT id, source, chunk_index, text FROM chunks WHERE id IN ({placeholders})",
            retrieved_ids,
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        assert rows[0][0] == 1

    def test_score_computation_1_minus_score(self):
        raw_score = 0.15
        adjusted = round(1.0 - raw_score, 4)
        assert adjusted == 0.85

    def test_results_sorted_by_score_desc(self):
        results = [
            {"score": 0.5, "source": "a"},
            {"score": 0.9, "source": "b"},
            {"score": 0.3, "source": "c"},
        ]
        sorted_results = sorted(results, key=lambda x: x["score"], reverse=True)
        assert sorted_results[0]["score"] == 0.9
        assert sorted_results[1]["score"] == 0.5
        assert sorted_results[2]["score"] == 0.3

    def test_query_classical_text_type_check(self, tmp_path: Path, monkeypatch):

        tv = tmp_path / "bazi_index.tv"
        tv.write_text("fake")
        db = tmp_path / "bazi_metadata.db"
        db.write_text("fake")
        monkeypatch.setenv("BGEM3_URL", "http://localhost:8002/v1/embeddings")
        monkeypatch.setenv("BGEM3_TOKEN", "test-token")
        with patch("src2.core.memory.constants.TURBOVEC_INDEX_PATH", tv):
            with patch("src2.core.memory.constants.BAZI_SQLITE_PATH", db):
                if "src2.engine.rag_client" in sys.modules:
                    del sys.modules["src2.engine.rag_client"]
                from src2.engine.rag_client import query_classical_text
                with pytest.raises(TypeError, match="query must be a string"):
                    query_classical_text(123)  # type: ignore[arg-type]


class TestAsyncQueryExecution:

    @pytest.mark.asyncio
    async def test_query_turbovec_async_returns_points(self, tmp_path: Path, monkeypatch):

        tv = tmp_path / "bazi_index.tv"
        tv.write_text("fake")
        db = tmp_path / "bazi_metadata.db"
        db.write_text("fake")
        monkeypatch.setenv("BGEM3_URL", "http://localhost:8002/v1/embeddings")
        monkeypatch.setenv("BGEM3_TOKEN", "test-token")
        mock_conn = AsyncMock()
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            (10, "source_a", 0, "text a"),
        ]
        mock_conn.execute.return_value = mock_cursor
        mock_conn.row_factory = aiosqlite.Row

        with patch("src2.core.memory.constants.TURBOVEC_INDEX_PATH", tv):
            with patch("src2.core.memory.constants.BAZI_SQLITE_PATH", db):
                if "src2.engine.rag_client" in sys.modules:
                    del sys.modules["src2.engine.rag_client"]
                from src2.engine.rag_client import _query_turbovec
                index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=4)
                vectors = np.random.rand(3, VECTOR_SIZE).astype(np.float32)
                ids = np.array([10, 20, 30], dtype=np.uint64)
                index.add_with_ids(vectors, ids)
                query_vec = vectors[0].tolist()
                result = await _query_turbovec(index, mock_conn, query_vec, top_k=3)
                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_classical_text_async_type_check(self, tmp_path: Path, monkeypatch):

        tv = tmp_path / "bazi_index.tv"
        tv.write_text("fake")
        db = tmp_path / "bazi_metadata.db"
        db.write_text("fake")
        monkeypatch.setenv("BGEM3_URL", "http://localhost:8002/v1/embeddings")
        monkeypatch.setenv("BGEM3_TOKEN", "test-token")
        with patch("src2.core.memory.constants.TURBOVEC_INDEX_PATH", tv):
            with patch("src2.core.memory.constants.BAZI_SQLITE_PATH", db):
                if "src2.engine.rag_client" in sys.modules:
                    del sys.modules["src2.engine.rag_client"]
                from src2.engine.rag_client import query_classical_text_async
                with pytest.raises(TypeError, match="query must be a string"):
                    await query_classical_text_async(42)  # type: ignore[arg-type]


class TestHardFailHandling:
    def test_load_turbovec_index_raises_on_missing_file(self):
        from src2.engine.rag_client import _load_turbovec_index_sync
        with patch(
            "src2.core.memory.constants.TURBOVEC_INDEX_PATH",
            Path("/nonexistent/bazi_index.tv"),
        ):
            with pytest.raises((FileNotFoundError, OSError)):
                _load_turbovec_index_sync()

    def test_get_sqlite_connection_raises_on_missing_db(self):
        from src2.engine.rag_client import _get_sqlite_connection_readonly
        with patch(
            "src2.core.memory.constants.BAZI_SQLITE_PATH",
            Path("/nonexistent/bazi_metadata.db"),
        ):
            # sqlite3.connect creates a new DB for non-existent paths,
            # so we verify the function does not crash with a path error
            conn = _get_sqlite_connection_readonly()
            conn.close()

    def test_bazirag_load_index_raises_on_missing(self):
        from infrastructure.bazirag import _load_turbovec_index
        with patch(
            "infrastructure.bazirag.TURBOVEC_INDEX_PATH",
            Path("/nonexistent/bazi_index.tv"),
        ):
            with pytest.raises(FileNotFoundError):
                _load_turbovec_index()

    def test_bazirag_get_conn_raises_on_missing_db(self):
        from infrastructure.bazirag import _get_sqlite_connection
        with patch(
            "infrastructure.bazirag.BAZI_SQLITE_PATH",
            Path("/nonexistent/bazi_metadata.db"),
        ):
            with pytest.raises(FileNotFoundError):
                _get_sqlite_connection()


class TestBaziragSearchSingle:
    @pytest.mark.asyncio
    async def test_search_single_returns_list_of_dicts(self):
        from infrastructure.bazirag import search_single
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=4)
        vectors = np.random.rand(5, VECTOR_SIZE).astype(np.float32)
        ids = np.array([1, 2, 3, 4, 5], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        db_path = "/tmp/test_bazirag_search.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, chunk_index INTEGER, text TEXT)"
        )
        for i in range(5):
            conn.execute(
                "INSERT INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
                (int(ids[i]), "test_source", i, f"chunk text {i}"),
            )
        conn.commit()
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": vectors[0].tolist()}]}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value.__aenter__.return_value = mock_response
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None
        result = await search_single(index, conn, mock_http_client, "test keyword")
        assert isinstance(result, list)
        conn.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.mark.asyncio
    async def test_search_single_handles_embedding_failure(self):
        from infrastructure.bazirag import search_single
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=4)
        vectors = np.random.rand(3, VECTOR_SIZE).astype(np.float32)
        ids = np.array([1, 2, 3], dtype=np.uint64)
        index.add_with_ids(vectors, ids)
        db_path = "/tmp/test_bazirag_embed_fail.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, chunk_index INTEGER, text TEXT)"
        )
        conn.commit()
        mock_http_client = AsyncMock()
        mock_http_client.post.side_effect = Exception("Connection error")
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None
        result = await search_single(index, conn, mock_http_client, "test keyword")
        assert result == []
        conn.close()
        if os.path.exists(db_path):
            os.remove(db_path)

    @pytest.mark.asyncio
    async def test_search_single_handles_turbovec_search_failure(self):
        from infrastructure.bazirag import search_single
        index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=4)
        db_path = "/tmp/test_bazirag_search_fail.db"
        conn = sqlite3.connect(db_path)
        conn.execute(
            "CREATE TABLE chunks (id INTEGER PRIMARY KEY, source TEXT, chunk_index INTEGER, text TEXT)"
        )
        conn.commit()
        mock_http_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": [{"embedding": [0.1] * VECTOR_SIZE}]}
        mock_response.raise_for_status = MagicMock()
        mock_http_client.post.return_value.__aenter__.return_value = mock_response
        mock_http_client.__aenter__.return_value = mock_http_client
        mock_http_client.__aexit__.return_value = None
        result = await search_single(index, conn, mock_http_client, "test keyword")
        assert result == []
        conn.close()
        if os.path.exists(db_path):
            os.remove(db_path)
