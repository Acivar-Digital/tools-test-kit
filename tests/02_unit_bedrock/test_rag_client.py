import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src2.engine.rag_client import query_classical_text, query_classical_text_async


class MockRow(dict):
    def __getitem__(self, item):
        if isinstance(item, int):
            keys = list(self.keys())
            return self[keys[item]]
        return super().__getitem__(item)


@patch("src2.engine.rag_client.turbovec.IdMapIndex.load")
@patch("src2.engine.rag_client.sqlite3.connect")
@patch("src2.engine.rag_client.httpx.Client")
def test_query_classical_text_json_serialization(mock_client, mock_sqlite, mock_turbovec):
    mock_post_response = MagicMock()
    mock_post_response.text = '{"data": [{"embedding": [0.1, 0.2]}]}'
    mock_post_response.raise_for_status = MagicMock()

    mock_client_instance = MagicMock()
    mock_client_instance.post.return_value = mock_post_response
    mock_client.return_value.__enter__.return_value = mock_client_instance

    mock_idx = MagicMock()
    mock_idx.search.return_value = (np.array([[0.9]]), np.array([[1]]))
    mock_turbovec.return_value = mock_idx

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = [
        MockRow({"id": 1, "source": "Classical Text", "chunk_index": 0, "text": "Sample text"})
    ]
    mock_sqlite.return_value = mock_conn

    with patch("src2.engine.rag_client.BGEM3_URL", "http://test/v1/embeddings"), \
         patch("src2.engine.rag_client.BGEM3_TOKEN", "token"):

        query_classical_text("test query")

        mock_client_instance.post.assert_called_once()
        _, kwargs = mock_client_instance.post.call_args
        assert "json" in kwargs
        assert isinstance(kwargs["json"], dict)


@pytest.mark.asyncio
@patch("src2.engine.rag_client.turbovec.IdMapIndex.load")
@patch("src2.engine.rag_client.aiosqlite.connect")
@patch("src2.engine.rag_client.httpx.AsyncClient")
async def test_query_classical_text_async_json_serialization(mock_client, mock_sqlite, mock_turbovec):
    mock_post_response = MagicMock()
    mock_post_response.text = '{"data": [{"embedding": [0.1, 0.2]}]}'
    mock_post_response.raise_for_status = MagicMock()

    mock_client_instance = AsyncMock()
    mock_client_instance.post.return_value = mock_post_response
    mock_client.return_value.__aenter__.return_value = mock_client_instance

    mock_idx = MagicMock()
    mock_idx.search.return_value = (np.array([[0.9]]), np.array([[1]]))
    mock_turbovec.return_value = mock_idx

    mock_conn = AsyncMock()
    mock_cursor = AsyncMock()
    mock_cursor.fetchall.return_value = [
        (1, "Classical Text", 0, "Sample text")
    ]
    mock_conn.execute.return_value = mock_cursor
    mock_sqlite.side_effect = AsyncMock(return_value=mock_conn)

    with patch("src2.engine.rag_client.BGEM3_URL", "http://test/v1/embeddings"), \
         patch("src2.engine.rag_client.BGEM3_TOKEN", "token"):

        await query_classical_text_async("test query async")

        mock_client_instance.post.assert_called_once()
        _, kwargs = mock_client_instance.post.call_args
        assert "json" in kwargs
        assert isinstance(kwargs["json"], dict)
