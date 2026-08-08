"""Test mem0 Memory initialization and add flow."""
from unittest.mock import patch


class MockEmbedder:
    """Mocks the embedder since our config uses a dummy API key."""

    def embed(self, text, mode="search"):
        """Accept (text, mode) signature expected by mem0 >= 0.1.25."""
        return [0.0] * 1024


def _make_mock_memory():
    """Build a Memory instance with mocked embedder."""
    from mem0 import Memory

    config = {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": "test_collection",
                "path": "scratch/test_qdrant",
                "embedding_model_dims": 1024,
            },
        },
        "version": "v1.1",
        "enable_graph": False,
        "llm": {
            "provider": "openai",
            "config": {"model": "gpt-4o", "api_key": "none"},
        },
        "embedder": {
            "provider": "openai",
            "config": {"model": "gpt-4o", "api_key": "none"},
        },
    }
    m = Memory.from_config(config)
    m.embedding_model = MockEmbedder()
    return m


@patch("mem0.vector_stores.qdrant.Qdrant._get_bm25_encoder", return_value=None)
@patch("mem0.vector_stores.qdrant.Qdrant._encode_bm25", return_value=None)
def test_memory_init_and_add(mock_encode, mock_get):
    """Memory initializes and can add a message."""
    m = _make_mock_memory()
    m.add("test text", user_id="test_user")
    # No exception means success


@patch("mem0.vector_stores.qdrant.Qdrant._get_bm25_encoder", return_value=None)
@patch("mem0.vector_stores.qdrant.Qdrant._encode_bm25", return_value=None)
def test_memory_init_with_multiple_adds(mock_encode, mock_get):
    """Memory handles multiple add calls."""
    m = _make_mock_memory()
    m.add("first message", user_id="user_a")
    m.add("second message", user_id="user_a")
    m.add("third message", user_id="user_b")

