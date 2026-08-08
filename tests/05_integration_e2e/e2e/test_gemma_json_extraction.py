"""
Set — Gemma JSON Bracket Extraction Tests
==========================================
Three layers testing the conductor parser and Gemma model outputs:

  Layer A — _parse_conductor_response()   → pure Python, no mocks
  Layer B — Parser resilience / negatives  → pure Python, malformed inputs
  Layer C — Live LLM calls                 → real OpenRouter/Local LLM (CI-safe skip)

Layer C requires OPENROUTER_API_KEY in .env.
Skipped automatically if the key is absent (CI-safe).

Pass criteria
-------------
- Layer A/B: assertions on return values only, no exceptions.
- Layer C: Gemma-4-31b-it extracts fields from natural text;
           Gemma-4-31b-it produces simplified output with no scores or jargon.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from src.bot.conductor import _parse_conductor_response  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw(reply: str, extracted: dict, all_collected: bool) -> str:
    """Build a standard REPLY/JSON conductor response string."""
    return (
        f"REPLY: {reply}\n"
        "---\n"
        f"JSON:\n{json.dumps({'extracted': extracted, 'all_collected': all_collected, 'next_prompt': None})}"
    )


# ---------------------------------------------------------------------------
# Layer A — _parse_conductor_response  (pure, valid shapes)
# ---------------------------------------------------------------------------


class TestParseValidReplies:
    """_parse_conductor_response handles all valid conductor output shapes."""

    def test_parse_valid_replies_json_brackets(self):
        """Standard REPLY/JSON format with valid JSON."""
        raw = _make_raw("Thanks! What is your birth date?", {"alias": "TEST", "gender": "Male"}, False)
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert reply == "Thanks! What is your birth date?"
        assert extracted["alias"] == "TEST"
        assert extracted["gender"] == "Male"
        assert all_collected is False

    def test_parse_multi_field_single_turn(self):
        """User dumps alias + gender + DOB + location in one message."""
        raw = _make_raw(
            "Great, got it!",
            {"alias": "TEST", "gender": "Male", "dob": "1977-04-28 11:51", "location": "Singapore"},
            False,
        )
        _, extracted, _ = _parse_conductor_response(raw)
        assert extracted["alias"] == "TEST"
        assert extracted["gender"] == "Male"
        assert extracted["dob"] == "1977-04-28 11:51"
        assert extracted["location"] == "Singapore"

    def test_parse_all_collected_true(self):
        """all_collected=true triggers handoff to engine."""
        raw = _make_raw(
            "Thank you, computing your chart now...",
            {"dob": "1977-04-28 11:51", "location": "Singapore"},
            True,
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert all_collected is True
        assert extracted["dob"] == "1977-04-28 11:51"
        assert extracted["location"] == "Singapore"

    def test_parse_bare_json_no_labels(self):
        """LLM outputs only JSON, no REPLY/JSON labels."""
        raw = '{"extracted": {"gender": "M"}, "all_collected": false, "next_prompt": "DOB?"}'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted.get("gender") == "M"
        assert all_collected is False

    def test_parse_json_with_nested_brackets(self):
        """JSON containing string values with { or } characters."""
        extracted = {"note": "User said {something} in braces", "alias": "Test"}
        raw = _make_raw("Got it!", extracted, False)
        _, parsed, _ = _parse_conductor_response(raw)
        assert parsed["alias"] == "Test"
        assert "{something}" in parsed["note"]

    def test_parse_dob_with_time_preserved(self):
        """DOB field preserves HH:MM format exactly."""
        raw = _make_raw("Got it.", {"dob": "1977-04-28 11:51"}, False)
        _, extracted, _ = _parse_conductor_response(raw)
        assert extracted["dob"] == "1977-04-28 11:51"

    def test_parse_json_key_format_no_separator(self):
        """Conductor output with JSON: label but no --- separator."""
        raw = (
            "REPLY: Please enter your date of birth.\n"
            'JSON: {"extracted": {"alias": "FY"}, "all_collected": false, "next_prompt": "DOB?"}'
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert "date of birth" in reply.lower()
        assert extracted.get("alias") == "FY"
        assert all_collected is False


# ---------------------------------------------------------------------------
# Layer B — Parser resilience / negative scenarios
# ---------------------------------------------------------------------------


class TestParseNegativeScenarios:
    """Parser must handle malformed, edge-case, and adversarial LLM output."""

    def test_parse_malformed_json_returns_safe_defaults(self):
        """Broken JSON like {bad json returns (str, {}, False)."""
        raw = "REPLY: Something went sideways\n---\nJSON: {bad json here"
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted == {}
        assert all_collected is False

    def test_parse_empty_json_block(self):
        """Empty {} returns safe defaults."""
        raw = "REPLY: Hi\n---\nJSON: {}"
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted == {}
        assert all_collected is False

    def test_parse_json_with_missing_extracted_key(self):
        """JSON without 'extracted' key doesn't crash."""
        raw = 'REPLY: Hi\n---\nJSON: {"all_collected": true, "next_prompt": null}'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted == {}
        assert all_collected is True

    def test_parse_json_with_wrong_types(self):
        """'extracted' is a list instead of dict — must not crash."""
        raw = 'REPLY: Hi\n---\nJSON: {"extracted": ["alias", "gender"], "all_collected": false}'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert isinstance(extracted, list)  # parser passes it through; _apply_extracted guards
        assert all_collected is False

    def test_parse_no_json_at_all(self):
        """Pure conversational text, no JSON anywhere."""
        raw = "Hey there! I'd love to help you with your Bazi chart. What's your name?"
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted == {}
        assert all_collected is False

    def test_parse_partial_json_truncated(self):
        """JSON cut off mid-value — must not crash."""
        raw = 'REPLY: Got it\n---\nJSON: {"extracted": {"alias": "Fra'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted == {}
        assert all_collected is False

    def test_parse_escaped_unicode_artifacts(self):
        r"""JSON with \n, \u escape sequences."""
        raw = (
            'REPLY: Hello\nWorld\n'
            '---\n'
            'JSON: {"extracted": {"alias": "Fran\u00e7ois"}, "all_collected": false}'
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted.get("alias") == "Fran\u00e7ois"
        assert all_collected is False

    def test_parse_json_inside_markdown_code_block(self):
        """LLM wraps JSON in ```json ... ```."""
        raw = (
            "REPLY: Here's your data.\n"
            "---\n"
            "```\n"
            "json\n"
            '{"extracted": {"alias": "CodeBlock"}, "all_collected": false}\n'
            "```\n"
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        # Parser should still find the JSON inside the code block
        assert extracted.get("alias") == "CodeBlock"
        assert all_collected is False

    def test_parse_multiple_json_blocks(self):
        """LLM outputs JSON twice; parser returns safe defaults (resilient fallback)."""
        raw = (
            'REPLY: Here is the data\n'
            '---\n'
            'JSON:\n'
            '{"extracted": {"alias": "First"}, "all_collected": false}\n'
            '\n'
            '{"extracted": {"alias": "Second"}, "all_collected": true}'
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        # Parser cannot disambiguate multiple JSON blocks — returns safe defaults
        assert extracted == {}
        assert all_collected is False

    def test_parse_json_with_null_extracted(self):
        """'extracted' is null — must not crash."""
        raw = 'REPLY: Hi\n---\nJSON: {"extracted": null, "all_collected": false}'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted is None or extracted == {}
        assert all_collected is False

    def test_parse_json_with_boolean_extracted(self):
        """'extracted' is a boolean — must not crash."""
        raw = 'REPLY: Hi\n---\nJSON: {"extracted": true, "all_collected": false}'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted is True
        assert all_collected is False


# ---------------------------------------------------------------------------
# Layer C — Live LLM tests (CI-safe skip)
# ---------------------------------------------------------------------------

# Intake tests require a local LLM proxy (INTAKE_URL)
LIVE_INTAKE = pytest.mark.skipif(
    not os.getenv("INTAKE_URL"),
    reason="INTAKE_URL not set — skipping live intake tests",
)

# Simplification tests require SUMMARIZER_URL (local LLM proxy)
LIVE_SIMPLIFY = pytest.mark.skipif(
    not os.getenv("SUMMARIZER_URL"),
    reason="SUMMARIZER_URL not set — skipping live simplification tests",
)


@LIVE_INTAKE
class TestGemmaIntakeExtraction:
    """
    Real LLM calls using gemma-4-31b-it via MCPMart local proxy.
    Tests that the model produces parseable REPLY/JSON output and
    correctly extracts fields from natural language input.
    """

    @pytest.mark.asyncio
    async def test_gemma_intake_extracts_alias_gender_from_natural_text(self):
        """'I'm Tester, male' → extracted alias + gender."""
        from src.engine.openrouter import call_openrouter_async_with_history

        system_prompt = """Collect the Bazi chart parameters from the user.

RESPONSE FORMAT:
REPLY: <your conversational reply to the user>
---
JSON:
{
  "extracted": { <field_name>: <value>, ... },
  "next_prompt": "<what you will ask next, or null if all fields collected>",
  "all_collected": true/false
}

RULES:
- Keep messages short.
- Extract alias and gender from the user's message.
"""
        messages = [{"role": "user", "content": "Hi, I'm Tester, male."}]

        raw = await call_openrouter_async_with_history(
            messages=messages,
            system_prompt=system_prompt,
            model="gemma-4-31b-it",
            preset="intake",
        )

        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert len(reply) > 0, "Expected a conversational reply"
        assert isinstance(extracted, dict)
        # At least one of alias or gender should be extracted
        has_alias = "alias" in extracted and extracted["alias"]
        has_gender = "gender" in extracted and extracted["gender"]
        assert has_alias or has_gender, (
            f"Expected alias or gender extracted. Got: {extracted}. Raw: {raw[:300]}"
        )

    @pytest.mark.asyncio
    async def test_gemma_intake_extracts_dob_from_various_formats(self):
        """'born April 28 1977 at 11:51am' → dob field."""
        from src.engine.openrouter import call_openrouter_async_with_history

        system_prompt = """Collect the Bazi chart parameters from the user.

RESPONSE FORMAT:
REPLY: <your conversational reply to the user>
---
JSON:
{
  "extracted": { <field_name>: <value>, ... },
  "next_prompt": "<what you will ask next, or null if all fields collected>",
  "all_collected": true/false
}

RULES:
- Extract DOB in YYYY-MM-DD HH:MM format.
- If time is given as am/pm, convert to 24-hour format.
"""
        messages = [{"role": "user", "content": "I was born on January 1, 1990 at 11:51am."}]

        raw = await call_openrouter_async_with_history(
            messages=messages,
            system_prompt=system_prompt,
            model="gemma-4-31b-it",
            preset="intake",
        )

        _, extracted, _ = _parse_conductor_response(raw)
        assert isinstance(extracted, dict)
        dob = extracted.get("dob", "")
        assert "1977" in dob, f"Year 1977 missing from dob: {dob!r}"
        assert "04" in dob or "4" in dob, f"Month 04 missing from dob: {dob!r}"
        assert "28" in dob, f"Day 28 missing from dob: {dob!r}"

    @pytest.mark.asyncio
    async def test_gemma_intake_handles_chinese_characters(self):
        """'男' → gender M, '新加坡' → location."""
        from src.engine.openrouter import call_openrouter_async_with_history

        system_prompt = """Collect the Bazi chart parameters from the user.

RESPONSE FORMAT:
REPLY: <your conversational reply to the user>
---
JSON:
{
  "extracted": { <field_name>: <value>, ... },
  "next_prompt": "<what you will ask next, or null if all fields collected>",
  "all_collected": true/false
}

RULES:
- Accept Chinese characters for gender and location.
- Map 男/男性 to gender M, 女/女性 to gender F.
- Map Chinese place names to the location field.
"""
        messages = [{"role": "user", "content": "男，出生地：新加坡"}]

        raw = await call_openrouter_async_with_history(
            messages=messages,
            system_prompt=system_prompt,
            model="gemma-4-31b-it",
            preset="intake",
        )

        _, extracted, _ = _parse_conductor_response(raw)
        assert isinstance(extracted, dict)
        gender = extracted.get("gender", "")
        location = extracted.get("location", "")
        assert gender.upper() in ("M", "MALE", "男"), f"Gender not extracted from 男: {gender!r}"
        assert "新加坡" in location or "singapore" in location.lower(), (
            f"Location not extracted from 新加坡: {location!r}"
        )

    @pytest.mark.asyncio
    async def test_gemma_intake_power_user_dumps_all_fields(self):
        """All 4 auto fields in one message."""
        from src.engine.openrouter import call_openrouter_async_with_history

        system_prompt = """Collect the Bazi chart parameters from the user.

RESPONSE FORMAT:
REPLY: <your conversational reply to the user>
---
JSON:
{
  "extracted": { <field_name>: <value>, ... },
  "next_prompt": "<what you will ask next, or null if all fields collected>",
  "all_collected": true/false
}

RULES:
- Extract ALL fields the user provides in one message.
- Auto mode fields: alias, gender, dob (YYYY-MM-DD HH:MM), location.
"""
        messages = [{
            "role": "user",
            "content": "My name is Test Profile, alias TEST, male. Born 01 January 1990 at 11:51am in Singapore.",
        }]

        raw = await call_openrouter_async_with_history(
            messages=messages,
            system_prompt=system_prompt,
            model="gemma-4-31b-it",
            preset="intake",
        )

        _, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(extracted, dict)
        assert extracted.get("alias"), f"Alias not extracted. Got: {extracted}"
        assert extracted.get("gender"), f"Gender not extracted. Got: {extracted}"
        dob = extracted.get("dob", "")
        assert "1977" in dob, f"Year missing from dob: {dob!r}"
        loc = extracted.get("location", "")
        assert "singapore" in loc.lower() or "新加坡" in loc, f"Location not extracted: {loc!r}"
        assert all_collected is True, (
            f"Expected all_collected=true when all 4 fields provided. Got: {all_collected}"
        )


@LIVE_SIMPLIFY
class TestGemmaSimplification:
    """
    Real LLM calls using gemma-4-31b-it via local LLM proxy.
    Tests that the simplification model produces clean output
    with no scores or technical jargon.
    """

    @pytest.mark.asyncio
    async def test_gemma_simplification_produces_no_scores(self):
        """Sifu mode output contains no numeric scores."""
        from src.engine.narrative_simplifier import simplify_month_narrative

        month_data = {
            "month_name": "Jia Chen (Wood Dragon) - May 2026",
            "month_title": "Seven Killings Month",
            "ten_god_narrative": "This month brings strong Seven Killings (Qi Sha) energy. "
            "Your Day Master faces pressure with a composite_score of 72/100. "
            "The clash creates a 65/100 friction index in career domains.",
            "advisory": {
                "career": "Seven Killings brings competitive pressure. Score: 70/100. "
                "Direct Officer support at 55/100.",
                "relationships": "Relationship harmony at 80/100. Rob Wealth creates tension at 40/100.",
                "wealth": "Direct Wealth score: 60/100. Indirect Wealth at 45/100.",
                "health": "Health index: 75/100. Watch for Metal-related issues.",
            },
        }

        result = await simplify_month_narrative(month_data)

        assert isinstance(result, str)
        assert len(result) > 0, "Simplification returned empty string"
        assert "Simplification failed" not in result, f"Simplification failed: {result}"

        # Check for score patterns: N/100, score: N, index: N, N%
        score_patterns = ["/100", "score:", "score :", "index:", "_score", "composite"]
        for pattern in score_patterns:
            assert pattern.lower() not in result.lower(), (
                f"Found score pattern '{pattern}' in simplified output: {result[:200]}"
            )

    @pytest.mark.asyncio
    async def test_gemma_simplification_produces_no_jargon(self):
        """Sifu mode output contains no technical Bazi terms."""
        from src.engine.narrative_simplifier import simplify_month_narrative

        month_data = {
            "month_name": "Yi Si (Fire Snake) - June 2026",
            "month_title": "Direct Resource Month",
            "ten_god_narrative": "Direct Resource (Zheng Yin) supports your Day Master. "
            "The Yi Wood stem combines with your Geng Metal Day Master. "
            "Si Hai clash activates the travel horse. Yang Ren in the hour branch "
            "creates hidden tension.",
            "advisory": {
                "career": "Direct Resource brings learning opportunities. "
                "Xing between Si and Hai creates movement. "
                "Pian Cai in the month stem indicates side income.",
                "relationships": "Zheng Guan supports official relationships. "
                "Shi Shen creates expression and creativity in social settings.",
                "wealth": "Zheng Cai and Pian Cai both present. "
                "Jie Cai warns against partnerships.",
                "health": "Fire-Water clash affects kidneys. "
                "Wood supports liver health.",
            },
        }

        result = await simplify_month_narrative(month_data)

        assert isinstance(result, str)
        assert len(result) > 0, "Simplification returned empty string"
        assert "Simplification failed" not in result, f"Simplification failed: {result}"

        # Check for technical jargon that should be removed
        jargon_terms = [
            "qi sha", "seven killings", "zheng yin", "direct resource",
            "pian cai", "indirect wealth", "zheng cai", "direct wealth",
            "jie cai", "rob wealth", "shi shen", "eating god",
            "shang guan", "hurting officer", "zheng guan", "direct officer",
            "pian guan", "indirect officer", "yang ren", "goat blade",
            "xing", "chong", "hai", "day master", "stem", "branch",
            "travel horse", "canopy star", "composite_score",
            "friction index", "十神", "七杀", "正印", "偏财",
            "破",  # Chinese character for "po" (break/destruction)
        ]
        import re
        for term in jargon_terms:
            if any('\u4e00' <= c <= '\u9fff' for c in term):
                found = term.lower() in result.lower()
            else:
                found = re.search(r'\b' + re.escape(term.lower()) + r'\b', result.lower()) is not None
            assert not found, (
                f"Found jargon term '{term}' in simplified output: {result[:200]}"
            )

    @pytest.mark.asyncio
    async def test_gemma_simplification_maintains_domain_structure(self):
        """Simplified output should still reference the 4 domains (Career, Relationships, Wealth, Health)."""
        from src.engine.narrative_simplifier import simplify_month_narrative

        month_data = {
            "month_name": "Bing Wu (Fire Horse) - July 2026",
            "month_title": "Hurting Officer Month",
            "ten_god_narrative": "Strong Hurting Officer (Shang Guan) energy. "
            "Bing Fire clashes with your Xin Metal Day Master. "
            "Wu Horse creates self-penalty with another Wu in the chart.",
            "advisory": {
                "career": "Hurting Officer brings innovation but also rebellion. "
                "Good for creative projects, bad for hierarchy.",
                "relationships": "Shang Guan hurts relationships for women. "
                "Be careful with words and tone.",
                "wealth": "Output generates wealth. Good for sales and performance.",
                "health": "Fire excess affects heart and eyes. Stay hydrated.",
            },
        }

        result = await simplify_month_narrative(month_data)

        assert isinstance(result, str)
        assert len(result) > 0

        # At least some domain references should be present
        domain_keywords = ["career", "relationship", "wealth", "health", "work", "love", "money", "wellbeing", "body"]
        found_domains = [kw for kw in domain_keywords if kw.lower() in result.lower()]
        assert len(found_domains) >= 2, (
            f"Expected at least 2 domain references in simplified output. "
            f"Found: {found_domains}. Output: {result[:200]}"
        )
