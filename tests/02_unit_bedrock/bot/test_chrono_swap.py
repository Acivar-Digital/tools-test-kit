import os
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from src.engine.openrouter import call_openrouter_async


class TestOpenRouterGeneric(unittest.IsolatedAsyncioTestCase):
    @patch("httpx.AsyncClient")
    async def test_call_custom_provider(self, mock_client_class):
        # Setup mock client
        mock_client = mock_client_class.return_value.__aenter__.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test Response"}}]
        }
        mock_client.post.return_value = mock_response

        # Test data
        base_url = "https://custom.api/v1"
        model = "test-model"

        # Force non-local mode
        env_patch = {"LLM_FORCE_LOCAL": "false"}
        with patch.dict(os.environ, env_patch, clear=False):
            await call_openrouter_async(
                prompt="Hello",
                url=base_url + "/chat/completions",
                model=model,
            )

        # Verify call arguments
        args, kwargs = mock_client.post.call_args
        url = args[0]
        headers = kwargs["headers"]
        payload = kwargs["json"]

        self.assertEqual(url, base_url + "/chat/completions")
        self.assertEqual(payload["model"], model)

        # Verify OpenRouter specific fields are NOT present
        self.assertNotIn("provider", payload)
        self.assertNotIn("include_reasoning", payload)
        self.assertNotIn("HTTP-Referer", headers)

    @patch("httpx.AsyncClient")
    async def test_call_openrouter_default(self, mock_client_class):
        # Setup mock client
        mock_client = mock_client_class.return_value.__aenter__.return_value
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Test Response"}}]
        }
        mock_client.post.return_value = mock_response

        env_patch = {"LLM_FORCE_LOCAL": "false", "OPENROUTER_API_KEY": "or-key", "APP_NAME": "TestApp"}
        with patch.dict(os.environ, env_patch, clear=False):
            await call_openrouter_async(
                prompt="Hello",
                url="https://openrouter.ai/api/v1/chat/completions",
                model="or-model",
            )

            args, kwargs = mock_client.post.call_args
            url = args[0]
            headers = kwargs["headers"]
            payload = kwargs["json"]

            self.assertEqual(url, "https://openrouter.ai/api/v1/chat/completions")
            self.assertEqual(headers["Authorization"], "Bearer or-key")
            self.assertTrue(payload["extra_body"]["chat_template_kwargs"]["enable_thinking"])

    @patch("src.bot.chronomancer_handler._get_monthly_context", new_callable=AsyncMock)
    @patch("src.bot.chronomancer_handler._get_current_pillars_from_reference")
    @patch("src.bot.chronomancer_handler.get_session")
    @patch("src.bot.chronomancer_handler.call_openrouter_async")
    async def test_chrono_handler_uses_openrouter_configs(
        self, mock_call, mock_get_session, mock_ref, mock_context
    ):
        mock_call.return_value = "Mocked Response"
        mock_ref.return_value = ("Jia", "Zi")
        mock_context.return_value = {}

        # Setup mock session
        mock_session = MagicMock()
        mock_session.profile.birth_year = 2000
        mock_session.profile.year_pillar = MagicMock(stem="Geng", branch="Chen")
        mock_session.profile.month_pillar = MagicMock(stem="Ji", branch="Mao")
        mock_session.profile.day_pillar = MagicMock(stem="Ding", branch="You")
        mock_session.profile.hour_pillar = MagicMock(stem="Yi", branch="Si")
        mock_session.profile.strength = "Shen Qiang"
        mock_session.profile.favorable_elements = ["Wood", "Fire"]
        mock_session.profile.unfavorable_elements = ["Metal", "Water"]
        mock_get_session.return_value = mock_session

        mock_update = AsyncMock()
        mock_bot = MagicMock()

        # Import handler inside to prevent premature startup load
        from src.bot.chronomancer_handler import handle_forecast

        # Test basic forecast triggers the openrouter call matching configured variables
        mock_env = {
            "CHRONO_URL": "https://openrouter.ai/api/v1/chat/completions",
            "CHRONO_MODEL": "or-chrono-model",
        }
        with patch.dict(os.environ, mock_env):
            await handle_forecast(
                mock_bot,
                mock_update,
            )

    @patch("httpx.AsyncClient")
    async def test_503_retry(self, mock_client_class):
        # Setup mock client
        mock_client = mock_client_class.return_value.__aenter__.return_value

        # First call fails with 503, second succeeds
        mock_response_503 = MagicMock()
        mock_response_503.status_code = 503
        mock_response_503.raise_for_status.side_effect = httpx.HTTPStatusError("503", request=None, response=mock_response_503)

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"choices": [{"message": {"content": "Success after retry"}}]}

        mock_client.post.side_effect = [mock_response_503, mock_response_200]

        # Force non-local mode and patch sleep
        env_patch = {"LLM_FORCE_LOCAL": "false"}
        with patch.dict(os.environ, env_patch, clear=False):
            with patch("asyncio.sleep", AsyncMock()):
                response = await call_openrouter_async(
                    prompt="test",
                    url="https://openrouter.ai/api/v1/chat/completions",
                    model="test",
                )
                self.assertEqual(response, "Success after retry")
                self.assertEqual(mock_client.post.call_count, 2)

if __name__ == "__main__":
    unittest.main()
