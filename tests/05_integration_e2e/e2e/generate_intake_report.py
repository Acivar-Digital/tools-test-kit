"""
Generate intake flow report by running 4 scenarios against gemma-4-31b-it.

Usage:
    uv run python TEST/e2e/generate_intake_report.py
"""

import asyncio
import json
import os
import sys
from datetime import UTC, datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from dotenv import load_dotenv

load_dotenv()

from src.bot.conductor import _parse_conductor_response  # noqa: E402
from src.engine.openrouter import call_openrouter_async_with_history  # noqa: E402

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
    },
]


def check_pass(scenario_id, extracted):
    """Determine pass/fail for a scenario."""
    if scenario_id == 1:
        return ("alias" in extracted and extracted["alias"]) or ("gender" in extracted and extracted["gender"])
    elif scenario_id == 2:
        dob = extracted.get("dob", "")
        return "1977" in dob and ("04" in dob or "4" in dob) and "28" in dob
    elif scenario_id == 3:
        gender = extracted.get("gender", "").upper()
        location = extracted.get("location", "")
        return gender in ("M", "MALE", "男") and ("新加坡" in location or "singapore" in location.lower())
    elif scenario_id == 4:
        dob = extracted.get("dob", "")
        location = extracted.get("location", "")
        return (
            extracted.get("alias")
            and extracted.get("gender")
            and "1977" in dob
            and ("singapore" in location.lower() or "新加坡" in location)
        )
    return False


async def run_scenario(scenario):
    """Run a single scenario and return result dict."""
    messages = [{"role": "user", "content": scenario["user_input"]}]

    raw = await call_openrouter_async_with_history(
        messages=messages,
        system_prompt=scenario["system_prompt"],
        model="gemma-4-31b-it",
        preset="intake",
    )

    reply, extracted, all_collected = _parse_conductor_response(raw)
    passed = check_pass(scenario["id"], extracted)

    status = "PASS" if passed else "FAIL"
    print(f"  Scenario {scenario['id']} ({scenario['label']}): {status}")
    if extracted:
        print(f"    Extracted: {json.dumps(extracted, ensure_ascii=False)}")

    return {
        "id": scenario["id"],
        "label": scenario["label"],
        "user_input": scenario["user_input"],
        "raw_response": raw,
        "parsed_reply": reply,
        "parsed_extracted": extracted,
        "parsed_all_collected": all_collected,
        "passed": passed,
    }


def generate_report(results):
    """Write markdown report."""
    report_dir = os.path.join(os.path.dirname(__file__), "..", "reports")
    os.makedirs(report_dir, exist_ok=True)
    report_path = os.path.join(report_dir, "intake_flow_report_gemma31b.md")

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
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

    for r in results:
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

    print(f"\nReport written to: {report_path}")
    return report_path


async def main():
    if not os.getenv("INTAKE_URL"):
        print("ERROR: INTAKE_URL not set.")
        sys.exit(1)

    print("Running intake scenarios against gemma-4-31b-it...")
    results = []
    for s in SCENARIOS:
        results.append(await run_scenario(s))

    generate_report(results)

    passed = sum(1 for r in results if r["passed"])
    if passed == len(results):
        print(f"\nAll {passed}/{len(results)} scenarios passed.")
    else:
        print(f"\n{passed}/{len(results)} scenarios passed. See report for details.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
