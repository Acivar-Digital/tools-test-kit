"""Tests for Mem0-on-Qdrant consolidation — baziForecaster memory module.

Annot: baziforecaster-only — run from target repo: cd $TARGET_REPO && uv run pytest TEST/unit/test_mem0_consolidation.py -v
"""



# ── Test 1: VECTOR_SIZE is 1024 ───────────────────────────────────────

def test_vector_size_is_1024():
    """Verify the hardcoded constant matches BGEM3 output."""
    from src.memory.constants import VECTOR_SIZE
    assert VECTOR_SIZE == 1024, f"Expected 1024, got {VECTOR_SIZE}"


def test_collection_names():
    """Verify collection name constants exist and are distinct."""
    from src.memory.constants import (
        QDRANT_MEMORY_COLLECTION,
        QDRANT_RAG_COLLECTION,
    )
    assert QDRANT_RAG_COLLECTION == "bazi_knowledge"
    assert QDRANT_MEMORY_COLLECTION == "user_memory"
    assert QDRANT_RAG_COLLECTION != QDRANT_MEMORY_COLLECTION


# ── Test 2: InHouseBGEM3Embedder structure ────────────────────────────

def test_mem0_store_imports_cleanly():
    """Module must import without errors."""
    # Just verify the module loads
    import src.memory.mem0_store  # noqa: F401


def test_mem0_config_no_chroma_references():
    """Verify no ChromaDB references in the source file."""
    import inspect

    import src.memory.mem0_store as mod

    source = inspect.getsource(mod)
    assert "chroma" not in source.lower(), \
        f"ChromaDB reference found in mem0_store.py source:\n{source}"


# ── Test 3: InHouseBGEM3Embedder is proper EmbeddingBase ──────────────────────

def test_inhouse_embedder_is_embeddingbase():
    """The class defined inside Mem0Store must be an EmbeddingBase subclass."""
    import inspect

    import src.memory.mem0_store as mod

    # The class is defined inside Mem0Store.__init__() so we can't import it
    # directly. But we can verify the module uses EmbeddingBase.
    source = inspect.getsource(mod)
    assert "EmbeddingBase" in source, "InHouseBGEM3Embedder must inherit from EmbeddingBase"
    assert "class InHouseBGEM3Embedder(EmbeddingBase)" in source, \
        "InHouseBGEM3Embedder must explicitly subclass EmbeddingBase"


# ── Test 4: InHouseBGEM3Embedder.embed accepts task_type ──────────────────────

def test_inhouse_embedder_accepts_task_type():
    """InHouseBGEM3Embedder.embed must accept task_type param (mem0 passes 'search').

    mem0's _search_vector_store calls embed(query, 'search') with 2 positional
    args. If task_type is missing, this raises TypeError.
    """
    import inspect

    from src2.core.memory.mem0_store import InHouseBGEM3Embedder

    sig = inspect.signature(InHouseBGEM3Embedder.embed)
    params = list(sig.parameters.keys())
    assert "task_type" in params, \
        f"InHouseBGEM3Embedder.embed missing 'task_type' param. Params: {params}"
