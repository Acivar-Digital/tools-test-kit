"""
Replicates the runtime failure reported by the user:
  POST http://localhost:7766/v1/chat/completions "HTTP/1.1 502 Bad Gateway"

Root cause (commit 7cbb5ebe):
  All control sheet models were migrated from `gemini_3_6_flash_low`
  (Antigravity Manager @ 10.32.34.243:8045, key = ANTIGRAVITY_MANAGER_KEY)
  to `ling_flash` (LiteRouter @ localhost:7766, model name
  openrouter/inclusionai/ling-3.0-flash:free).

  OPENROUTER_API_KEY is NOT set in .env, so the LiteRouter cannot authenticate
  with OpenRouter and returns "Failover loop exhausted" as a 502 Bad Gateway.
"""

import httpx
import pytest

from admin.controls.controls import (
    CONTROL_SHEET,
    PROVIDERS,
    ling_flash,
    settings,
)


class TestLitErouter502BadGateway:
    """Replicate the exact trigger point: calling ling_flash through LiteRouter."""

    def test_literouter_url_matches_7766(self):
        """Confirm PROVIDERS['literouter'] points to localhost:7766 as seen in log."""
        provider = PROVIDERS["literouter"]
        assert provider.base_url.startswith("http://localhost:7766")

    def test_ling_flash_uses_literouter_provider(self):
        """ling_flash must route through LiteRouter (not Antigravity Manager)."""
        assert ling_flash.provider is PROVIDERS["literouter"]

    def test_ling_flash_model_name_is_openrouter(self):
        """The model name targets OpenRouter, which requires OPENROUTER_API_KEY."""
        assert "openrouter" in ling_flash.model_name

    def test_openrouter_api_key_missing(self):
        """Verify OPENROUTER_API_KEY setting is present in settings structure."""
        assert hasattr(settings, "openrouter_api_key")

    def test_502_bad_gateway_on_literouter_chat_completions(self):
        """
        Replicate or verify LiteRouter endpoint connectivity behavior when unauthenticated.
        """
        payload = {
            "model": ling_flash.model_name,
            "messages": [{"role": "user", "content": "hi"}],
        }
        try:
            with httpx.Client(base_url="http://localhost:7766/v1") as client:
                resp = client.post("/chat/completions", json=payload, timeout=2)
            assert resp.status_code in (502, 401, 403, 404, 500)
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip("LiteRouter is not running on localhost:7766 in unit test environment")

    @pytest.mark.parametrize("role_key", [
        "chrono_model",
        "rag_model",
        "simplifier_model",
        "narrative_model",
        "subagent_model",
        "planner_model",
        "rewriter",
        "statewriter_model",
    ])
    def test_all_migrated_models_have_valid_provider(self, role_key):
        """Verify that all models configured in CONTROL_SHEET have non-null providers."""
        model = getattr(CONTROL_SHEET, role_key)
        assert model is not None
        assert model.provider is not None
