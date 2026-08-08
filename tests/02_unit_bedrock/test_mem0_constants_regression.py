"""Regression tests for src2.core.memory constants and the mem0_store import.

Guards against commit cfd763f2 (BaziRAG migration to TurboVec/SQLite) accidentally
removing QDRANT_MEMORY_COLLECTION, which mem0 still depends on for the user_memory
Qdrant collection. BaziRAG was migrated to TurboVec/SQLite, but mem0 was intentionally
kept on Qdrant (see migration commit message and CHANGELOG).
"""

import importlib


def test_qdrant_memory_collection_constant_importable():
    """The constant removed by the BaziRAG migration must be restored for mem0."""
    from src2.core.memory.constants import QDRANT_MEMORY_COLLECTION

    assert QDRANT_MEMORY_COLLECTION == "user_memory"


def test_mem0_store_module_imports_without_error():
    """start2.py preflight imports Mem0Store at module load; this was the crash site."""
    mod = importlib.import_module("src2.core.memory.mem0_store")

    assert hasattr(mod, "Mem0Store")
    assert hasattr(mod, "InHouseBGEM3Embedder")


def test_qdrant_rag_collection_correctly_removed():
    """The BaziRAG-only constant must stay removed; only mem0 collection restored."""
    import src2.core.memory.constants as consts

    assert not hasattr(consts, "QDRANT_RAG_COLLECTION")
    assert hasattr(consts, "QDRANT_MEMORY_COLLECTION")


def test_turbovec_sqlite_paths_remain_intact():
    """BaziRAG TurboVec/SQLite migration paths must survive the restoration."""
    from src2.core.memory.constants import (
        BAZI_SQLITE_PATH,
        TURBOVEC_INDEX_PATH,
        VECTOR_SIZE,
    )

    assert VECTOR_SIZE == 1024
    assert str(BAZI_SQLITE_PATH).endswith("bazi_metadata.db")
    assert str(TURBOVEC_INDEX_PATH).endswith("bazi_index.tv")
