"""
Unit tests for the Python 3.14+ fastembed/onnxruntime BM25 bypass in Mem0Store.
"""

import os
from unittest.mock import MagicMock, patch

from src.memory.mem0_store import Mem0Store


def test_mem0_store_python_314_bypass():
    # Create mock memory instance
    mock_memory = MagicMock()
    mock_vector_store = MagicMock()
    mock_vector_store._has_bm25_slot = True

    # Simulate a real _get_bm25_encoder method
    def original_get_encoder():
        return "should_be_none_on_3_14"

    mock_vector_store._get_bm25_encoder = original_get_encoder
    mock_memory.vector_store = mock_vector_store

    # Mock Memory.from_config to avoid connection errors and return mock memory
    with patch("src.memory.mem0_store.Memory.from_config", return_value=mock_memory):
        with patch.dict(os.environ, {"QDRANT_URL": "http://localhost:6333", "BGEM3_URL": "http://localhost:8000"}):
            # 1. Test when Python is >= 3.14
            with patch("sys.version_info", (3, 14, 0)):
                from mem0.vector_stores.qdrant import Qdrant
                orig_get = Qdrant._get_bm25_encoder
                orig_encode = Qdrant._encode_bm25
                try:
                    _ = Mem0Store()

                    # The slot should be disabled
                    assert mock_vector_store._has_bm25_slot is False
                    # The encoder should be mocked to return None
                    assert mock_vector_store._get_bm25_encoder() is None

                    # Check that Qdrant class methods were monkeypatched
                    q = Qdrant(collection_name="test", embedding_model_dims=1024, client=MagicMock())
                    assert q._get_bm25_encoder() is None
                    assert q._encode_bm25("test") is None
                finally:
                    Qdrant._get_bm25_encoder = orig_get
                    Qdrant._encode_bm25 = orig_encode

            # Reset
            mock_vector_store._has_bm25_slot = True

            def original_get_encoder_v2():
                return "should_remain_unchanged"

            mock_vector_store._get_bm25_encoder = original_get_encoder_v2

            # 2. Test when Python is < 3.14 (e.g. 3.12)
            with patch("sys.version_info", (3, 12, 0)):
                _ = Mem0Store()

                # Should remain untouched
                assert mock_vector_store._has_bm25_slot is True
                assert mock_vector_store._get_bm25_encoder() == "should_remain_unchanged"
