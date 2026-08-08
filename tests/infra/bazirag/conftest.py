"""
Shared fixtures for BaziRAG (turbovec + SQLite) test suite.
"""
import hashlib
import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
import turbovec

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

sys.path.insert(0, str(PROJECT_ROOT))

VECTOR_SIZE = 1024
BIT_WIDTH = 4


@pytest.fixture
def sample_chunk_texts() -> list[str]:
    return [
        "戊土生于寅月，财星透干，贵人相助。",
        "庚金坐酉，刃旺身强，宜攻不宜守。",
        "丙火在午位，禄马同乡，名利双收。",
        "甲木生亥月，水木相生，事业渐入佳境。",
        "壬水漫金，财星受损，需防破耗。",
    ]


@pytest.fixture
def mock_bgem3_embeddings(sample_chunk_texts: list[str]) -> list[list[float]]:
    rng = np.random.RandomState(42)
    vectors = []
    for _ in sample_chunk_texts:
        vec = rng.rand(VECTOR_SIZE).astype(np.float32)
        vec = vec / np.linalg.norm(vec)
        vectors.append(vec.tolist())
    return vectors


@pytest.fixture
def mock_embedding_fn():
    def _embed(texts: list[str]) -> list[list[float]]:
        rng = np.random.RandomState(42)
        result = []
        for _ in texts:
            vec = rng.rand(VECTOR_SIZE).astype(np.float32)
            vec = vec / np.linalg.norm(vec)
            result.append(vec.tolist())
        return result
    return _embed


@pytest.fixture
def temp_sqlite_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "bazi_metadata.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE chunks ("
        "id INTEGER PRIMARY KEY,"
        "source TEXT,"
        "chunk_index INTEGER,"
        "text TEXT"
        ")"
    )
    source = "yuan_hai_zi_ping"
    for i, text in enumerate(
        ["渊海子平 第一章", "渊海子平 第二章", "滴天髓阐微", "穷通宝鉴卷一"]
    ):
        raw = f"{source}:{i}"
        chunk_id = abs(
            int(hashlib.sha256(raw.encode()).hexdigest(), 16)
        ) % (2**63)
        conn.execute(
            "INSERT INTO chunks (id, source, chunk_index, text) VALUES (?, ?, ?, ?)",
            (chunk_id, source, i, text),
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def temp_turbovec_index(tmp_path: Path, mock_embedding_fn) -> tuple[Path, turbovec.IdMapIndex]:
    index_path = tmp_path / "bazi_index.tv"
    index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
    source = "yuan_hai_zi_ping"
    texts = [
        "戊土生于寅月，财星透干，贵人相助。",
        "庚金坐酉，刃旺身强，宜攻不宜守。",
        "丙火在午位，禄马同乡，名利双收。",
    ]
    vectors = mock_embedding_fn(texts)
    ids = np.array(
        [
            abs(int(hashlib.sha256(f"{source}:{i}".encode()).hexdigest(), 16))
            % (2**63)
            for i in range(len(texts))
        ],
        dtype=np.uint64,
    )
    vecs = np.array(vectors, dtype=np.float32)
    index.add_with_ids(vecs, ids)
    index.write(str(index_path))
    return index_path, index


@pytest.fixture
def mock_turbovec_index(tmp_path: Path, mock_embedding_fn) -> turbovec.IdMapIndex:
    index = turbovec.IdMapIndex(dim=VECTOR_SIZE, bit_width=BIT_WIDTH)
    source = "yuan_hai_zi_ping"
    texts = [
        "戊土生于寅月，财星透干，贵人相助。",
        "庚金坐酉，刃旺身强，宜攻不宜守。",
        "丙火在午位，禄马同乡，名利双收。",
    ]
    vectors = mock_embedding_fn(texts)
    ids = np.array(
        [
            abs(int(hashlib.sha256(f"{source}:{i}".encode()).hexdigest(), 16))
            % (2**63)
            for i in range(len(texts))
        ],
        dtype=np.uint64,
    )
    vecs = np.array(vectors, dtype=np.float32)
    index.add_with_ids(vecs, ids)
    return index


@pytest.fixture
def sha256_uint64_id() -> int:
    raw = "yuan_hai_zi_ping:0"
    return abs(int(hashlib.sha256(raw.encode()).hexdigest(), 16)) % (2**63)


@pytest.fixture
def sample_sqlite_rows() -> list[dict]:
    return [
        {"id": 1, "source": "yuan_hai_zi_ping", "chunk_index": 0, "text": "渊海子平 第一章"},
        {"id": 2, "source": "yuan_hai_zi_ping", "chunk_index": 1, "text": "渊海子平 第二章"},
        {"id": 3, "source": "di_tian_sui", "chunk_index": 0, "text": "滴天髓阐微"},
    ]


@pytest.fixture
def mock_qdrant_client():
    mock = MagicMock()
    mock.search.return_value = ([0.9, 0.8, 0.7], [[1, 2, 3]])
    return mock
