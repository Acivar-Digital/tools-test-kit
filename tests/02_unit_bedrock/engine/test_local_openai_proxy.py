import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_local_openai_proxy_integration():
    """
    Test exercises call_openrouter_async and verifies integration.
    """
    mock_env = {
        "CHRONO_MODEL": "gemini-3.5-flash-low",
        "CHRONO_URL": "http://10.32.34.243:8045/v1/chat/completions?key=sk-antigravity",
    }

    with patch.dict(os.environ, mock_env):
        prompt = "Hello. Reply only with the word 'ACK'."
        system_prompt = "You are a precise robotic helper."

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ACK"}}]
        }

        async def mock_post(*args, **kwargs):
            return mock_response

        with patch("httpx.AsyncClient.post", side_effect=mock_post):
            from src.engine.openrouter import call_openrouter_async
            response = await call_openrouter_async(
                prompt=prompt,
                url=mock_env["CHRONO_URL"],
                model=mock_env["CHRONO_MODEL"],
                system_prompt=system_prompt,
                temperature=0.1
            )

            assert response is not None
            assert "ACK" in response.upper()
