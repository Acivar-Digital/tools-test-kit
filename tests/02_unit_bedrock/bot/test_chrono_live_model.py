import os

import pytest

from src.engine.openrouter import call_local_llm_async


@pytest.mark.asyncio
@pytest.mark.skip(reason="Live LLM E2E integration test requires live Antigravity Manager at port 8045")
async def test_live_gemini_35_low_integration():
    """
    Verifies that call_local_llm_async successfully routes to the local
    gemini-3.5-flash-low endpoint (port 8045) using sk-antigravity authentication.
    """
    # 1. Verify environment config is correct
    chrono_model = os.getenv("CHRONO_MODEL")
    chrono_url = os.getenv("CHRONO_URL")

    assert chrono_model == "gemini-3.5-flash-low", "CHRONO_MODEL must be configured to gemini-3.5-flash-low"
    assert "8045" in chrono_url, "CHRONO_URL must reference port 8045"
    assert "sk-antigravity" in chrono_url, "CHRONO_URL must contain sk-antigravity token"

    # 2. Call local LLM function directly (simulating real Chronomancer routing)
    prompt = "Format this exact phrase: 'Verification complete. Model is active.'"
    response = await call_local_llm_async(
        prompt=prompt,
        system_prompt="You are a helpful assistant.",
        model=chrono_model,
        endpoint=chrono_url,
        temperature=0.1
    )

    assert response is not None, "Response must not be None"
    assert len(response) > 0, "Response must have length"
    print("\n--- Live Model Response ---")
    print(response)
    print("---------------------------")
