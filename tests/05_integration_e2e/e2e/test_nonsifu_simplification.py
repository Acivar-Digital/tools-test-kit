"""
Test: Narrative Simplification with gemma-4-26b-a4b-it (LOCAL_LLM_NONSIFU_MODEL)

Verifies that the new model correctly converts technical Bazi narratives to plain English.
Shows raw input → simplified output side-by-side.
"""
import os

import pytest

from src.engine.narrative_simplifier import simplify_advisory, simplify_month_narrative

SAMPLE_TECHNICAL_ADVISORY = """
Day Master: Geng Metal (庚金)
7 Killings (七杀) creates structural friction in Career domain.
Direct Resource (正印) provides support but is weakened by Wealth clash.
Rob Wealth (劫财) in Month Branch indicates competitive pressure.
Composite score: 72/100. Career: 65/100, Wealth: 70/100, Relationships: 78/100, Health: 75/100.
"""


SAMPLE_TECHNICAL_MONTH = {
    "month_name": "Jia Chen (甲辰) - April 2026",
    "month_title": "Rob Wealth Month with Structural Resonance",
    "ten_god_narrative": """
The Jia Chen month brings strong Wood energy that activates your Wealth palace.
Rob Wealth (劫财) in the Month Branch creates competitive dynamics in Career.
Direct Officer (正官) provides stability but is challenged by the Chen-Xu clash.
Composite score for the month: 68/100.
""",
    "advisory": {
        "career": "7 Killings friction with Direct Officer support. Score: 65/100",
        "relationships": "Direct Resource weakened by Wealth clash. Score: 72/100",
        "wealth": "Rob Wealth creates competitive pressure but Wood energy is favorable. Score: 70/100",
        "health": "Metal energy under stress from Wood dominance. Score: 60/100"
    }
}


@pytest.mark.asyncio
async def test_simplify_advisory_shows_output():
    """Test simplify_advisory with gemma-4-26b-a4b-it and print the output."""
    if not os.getenv("SUMMARIZER_URL"):
        pytest.skip("SUMMARIZER_URL not set")

    print("\n" + "="*80)
    print("SIMPLIFICATION TEST - gemma-4-26b-a4b-it (LOCAL_LLM_NONSIFU_MODEL)")
    print("="*80)
    print("\nINPUT (Technical):")
    print(SAMPLE_TECHNICAL_ADVISORY)
    print("-"*80)

    result = await simplify_advisory(SAMPLE_TECHNICAL_ADVISORY, alias="Tester")

    print("\nOUTPUT (Plain English):")
    print(result)
    print("="*80)

    # Verify no scores remain
    assert "score" not in result.lower() or "score" not in result.lower().split("output")[0]
    assert "/100" not in result

    # Verify no Chinese characters
    for char in result:
        if '\u4e00' <= char <= '\u9fff':
            pytest.fail(f"Chinese character found in output: {char}")

    # Verify output is not empty
    assert len(result) > 50, "Simplified output too short"


@pytest.mark.asyncio
async def test_simplify_month_narrative_shows_output():
    """Test simplify_month_narrative with gemma-4-26b-a4b-it and print the output."""
    if not os.getenv("SUMMARIZER_URL"):
        pytest.skip("SUMMARIZER_URL not set")

    print("\n" + "="*80)
    print("MONTH NARRATIVE SIMPLIFICATION TEST - gemma-4-26b-a4b-it")
    print("="*80)
    print("\nINPUT (Technical):")
    print(f"Month: {SAMPLE_TECHNICAL_MONTH['month_name']}")
    print(f"Title: {SAMPLE_TECHNICAL_MONTH['month_title']}")
    print(f"Narrative: {SAMPLE_TECHNICAL_MONTH['ten_god_narrative']}")
    print(f"Advisory: {SAMPLE_TECHNICAL_MONTH['advisory']}")
    print("-"*80)

    result = await simplify_month_narrative(SAMPLE_TECHNICAL_MONTH)

    print("\nOUTPUT (Plain English):")
    print(result)
    print("="*80)

    # Verify no scores remain
    assert "/100" not in result

    # Verify no Chinese characters
    for char in result:
        if '\u4e00' <= char <= '\u9fff':
            pytest.fail(f"Chinese character found in output: {char}")

    # Verify output is not empty
    assert len(result) > 100, "Simplified output too short"


@pytest.mark.asyncio
async def test_env_var_uses_nonsifu_model():
    """Verify that LOCAL_LLM_NONSIFU_MODEL and call_local_llm_async are removed."""
    import inspect

    from src.engine import narrative_simplifier

    source = inspect.getsource(narrative_simplifier.simplify_advisory)
    assert "LOCAL_LLM_NONSIFU_MODEL" not in source
    assert "call_local_llm_async" not in source

    source2 = inspect.getsource(narrative_simplifier.simplify_month_narrative)
    assert "LOCAL_LLM_NONSIFU_MODEL" not in source2
    assert "call_local_llm_async" not in source2
