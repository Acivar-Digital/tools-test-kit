"""
Set — Intake Flow Report (gemma-4-31b-it)
==========================================

Runs 4 intake scenarios against the live gemma-4-31b-it model and generates
a markdown report at TEST/reports/intake_flow_report_gemma31b.md.

Each scenario captures: user input, raw LLM response, parsed JSON, pass/fail.

Requires LOCAL_LLM_URL and LOCAL_LLM_KEY environment variables.
"""

import json
import os
import sys
from datetime import UTC, datetime

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from src.bot.conductor import _parse_conductor_response  # noqa: E402

LIVE_INTAKE = pytest.mark.skipif(
    not os.getenv("INTAKE_URL"),
    reason="INTAKE_URL not set — skipping live intake tests",
)

# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

SCENARIOS = [
    {
        "id": 1,
        "label": "Alias + Gender (minimal)",
        "user_input": "Hi, I'm Tester, male.",
        "system_prompt": """Collect the Bazi chart parameters from the user.

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
""",
        "pass_criteria": lambda extracted: (
            ("alias" in extracted and extracted["alias"])
            or ("gender" in extracted and extracted["gender"])
        ),
    },
    {
        "id": 2,
        "label": "DOB extraction",
        "user_input": "I was born on January 1, 1990 at 11:51am.",
        "system_prompt": """Collect the Bazi chart parameters from the user.

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
""",
        "pass_criteria": lambda extracted: (
            "1977" in extracted.get("dob", "")
            and ("04" in extracted.get("dob", "") or "4" in extracted.get("dob", ""))
            and "28" in extracted.get("dob", "")
        ),
    },
    {
        "id": 3,
        "label": "Chinese characters",
        "user_input": "男，出生地：新加坡",
        "system_prompt": """Collect the Bazi chart parameters from the user.

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
""",
        "pass_criteria": lambda extracted: (
            extracted.get("gender", "").upper() in ("M", "MALE", "男")
            and ("新加坡" in extracted.get("location", "") or "singapore" in extracted.get("location", "").lower())
        ),
    },
    {
        "id": 4,
        "label": "All fields (power user)",
        "user_input": "My name is Test Profile, alias TEST, male. Born 01 January 1990 at 11:51am in Singapore.",
        "system_prompt": """Collect the Bazi chart parameters from the user.

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
""",
        "pass_criteria": lambda extracted: (
            extracted.get("alias")
            and extracted.get("gender")
            and "1977" in extracted.get("dob", "")
            and ("singapore" in extracted.get("location", "").lower() or "新加坡" in extracted.get("location", ""))
        ),
    },
]

# ---------------------------------------------------------------------------
# Results storage (module-level so test and report share state)
# ---------------------------------------------------------------------------

_results: list[dict] = []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@LIVE_INTAKE
class TestIntakeFlowReport:
    """Run each scenario against live gemma-4-31b-it and collect results."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("scenario", SCENARIOS, ids=[s["label"] for s in SCENARIOS])
    async def test_intake_scenario(self, scenario):
        from src.engine.openrouter import call_openrouter_async_with_history

        messages = [{"role": "user", "content": scenario["user_input"]}]

        raw = await call_openrouter_async_with_history(
            messages=messages,
            system_prompt=scenario["system_prompt"],
            model="gemma-4-31b-it",
            preset="intake",
        )

        reply, extracted, all_collected = _parse_conductor_response(raw)

        passed = scenario["pass_criteria"](extracted)

        result = {
            "id": scenario["id"],
            "label": scenario["label"],
            "user_input": scenario["user_input"],
            "raw_response": raw,
            "parsed_reply": reply,
            "parsed_extracted": extracted,
            "parsed_all_collected": all_collected,
            "passed": passed,
        }
        _results.append(result)

        assert passed, (
            f"Scenario {scenario['id']} ({scenario['label']}) FAILED.\n"
            f"User input: {scenario['user_input']}\n"
            f"Extracted: {extracted}\n"
            f"Raw response (first 500 chars): {raw[:500]}"
        )


# ---------------------------------------------------------------------------
# Report generation helper
# ---------------------------------------------------------------------------


def _generate_report():
    """Generate markdown report from collected results."""
    if not _results:
        return

    report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "intake_flow_report_gemma31b.md")

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    total = len(_results)
    passed = sum(1 for r in _results if r["passed"])
    failed = total - passed

    lines = [
        "# Intake Flow Report — gemma-4-31b-it",
        "",
        f"**Generated:** {now}",
        "**Model:** gemma-4-31b-it (preset: intake)",
        f"**Results:** {passed}/{total} passed, {failed} failed",
        "",
        "---",
        "",
    ]

    for r in _results:
        status = "PASS" if r["passed"] else "FAIL"
        lines.append(f"## Scenario {r['id']}: {r['label']} [{status}]")
        lines.append("")
        lines.append("**User Input:**")
        lines.append("```")
        lines.append(r["user_input"])
        lines.append("```")
        lines.append("")
        lines.append("**Raw LLM Response:**")
        lines.append("```")
        lines.append(r["raw_response"])
        lines.append("```")
        lines.append("")
        lines.append("**Parsed JSON:**")
        lines.append("```json")
        lines.append(json.dumps({
            "reply": r["parsed_reply"],
            "extracted": r["parsed_extracted"],
            "all_collected": r["parsed_all_collected"],
        }, indent=2, ensure_ascii=False))
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\n>>> Report written to: {report_path}")
