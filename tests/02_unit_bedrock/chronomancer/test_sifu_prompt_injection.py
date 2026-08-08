import os
import sys

sys.path.append(os.getcwd())

from src.bot.chronomancer_handler import _build_advisory_prompt
from src.config.sifu_translation import SIFU_INTERPRETATION_GUIDE


def test_sifu_guide_is_unconditionally_injected():
    """Verify that SIFU_INTERPRETATION_GUIDE is unconditionally present in the constructed prompt."""
    scored_data = [
        {
            "date": "2026-06-02",
            "user_score": {
                "stem": "Bing",
                "branch": "Wu",
                "activities": {
                    "investment": {"verdict": "favorable", "reason": "strong pillars"}
                },
                "events": []
            },
            "compatibility": {"total_score": 85, "level": "High", "breakdown": "harmonious"}
        }
    ]

    prompt = _build_advisory_prompt(
        user_query="How is my day looking?",
        scored_data=scored_data,
        memory_context="Some episodic memory",
        rag_context="Some classical grounding",
        chat_history=[],
        profile_context="Strong Wu Earth DM",
        current_context=None,
        monthly_context=None,
        stakeholder_context=None,
        intent="general",
        reviewer_flags=""
    )

    assert SIFU_INTERPRETATION_GUIDE in prompt, "SIFU_INTERPRETATION_GUIDE must be unconditionally injected into the prompt"
    print("✅ Unit Test Passed: Sifu Interpretation Guide is present in the prompt!")


def test_raw_score_is_unmasked_in_prompt():
    """Verify that raw mathematical scores are unmasked in the constructed prompt acts block."""
    scored_data = [
        {
            "date": "2026-06-02",
            "user_score": {
                "stem": "Bing",
                "branch": "Wu",
                "activities": {
                    "travel": {"score": 15, "verdict": "Peak", "reason": "Traveling horse active"},
                    "love": {"score": -8, "verdict": "Caution", "reason": "Branch clash"}
                },
                "events": []
            },
            "compatibility": {"total_score": 85, "level": "High", "breakdown": "harmonious"}
        }
    ]

    prompt = _build_advisory_prompt(
        user_query="How is my day looking?",
        scored_data=scored_data,
        memory_context="Some episodic memory",
        rag_context="Some classical grounding",
        chat_history=[],
        profile_context="Strong Wu Earth DM",
        current_context=None,
        monthly_context=None,
        stakeholder_context=None,
        intent="general",
        reviewer_flags=""
    )

    assert "[Score: 15/20]" in prompt, "Raw score of +15 must be unmasked in the prompt"
    assert "[Score: -8/20]" in prompt, "Raw score of -8 must be unmasked in the prompt"
    print("✅ Unit Test Passed: Raw activity scores are unmasked in the prompt!")


if __name__ == "__main__":
    test_sifu_guide_is_unconditionally_injected()
    test_raw_score_is_unmasked_in_prompt()
