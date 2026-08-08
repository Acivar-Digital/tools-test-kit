# ruff: noqa: E402
import pytest

pytest.skip("Legacy alt_src module removed", allow_module_level=True)

import asyncio
import json
import os
from pathlib import Path

import pytest
from alt_src.K3.k3_pipeline import generate_annual_summary

from src.bot.bridge import map_profile_to_k3
from src.bot.db import Database
from src.bot.report_utils import get_month_narrative, get_report_menu_text
from src.bot.session import UserProfile
from src.engine.orchestrator import run_full_engine

# Setup a test DB
TEST_DB_PATH = "test_menu.db"

@pytest.fixture
def db():
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)
    database = Database(TEST_DB_PATH)
    yield database
    database.close()
    if os.path.exists(TEST_DB_PATH):
        os.remove(TEST_DB_PATH)

@pytest.mark.asyncio
async def test_report_menu_flow(db):
    print("\n--- Testing Granular Report Menu Flow ---")

    chat_id = 123456789
    alias = "Tester"

    # 1. Setup Profile
    profile = UserProfile(
        name="Test User",
        alias=alias,
        gender="M",
        year_pillar={"stem": "Geng", "branch": "Wu"},
        month_pillar={"stem": "Ji", "branch": "Mao"},
        day_pillar={"stem": "Yi", "branch": "Mao"},
        hour_pillar={"stem": "Ren", "branch": "Wu"},
        da_yun_pillar={"stem": "Gui", "branch": "Si"}
    )

    k3_profile = map_profile_to_k3(profile, chat_id, dob="1990-01-01")

    # 2. Mock 12 months (Simplified)
    results = []
    for i in range(12):
        res = run_full_engine(k3_profile, i)
        # Mock narrative content
        res["engine_outputs"]["module_6a"] = {
            "content": f"Deep-dive analysis for {res['month_metadata']['month_name']}..."
        }
        results.append(res)

    summary = generate_annual_summary(results)

    master_json = {
        "profile_summary": k3_profile,
        "monthly_forecasts": results,
        "annual_summary": summary
    }

    # 3. Save Master JSON
    test_report_dir = Path("TEST/reports/test_report")
    test_report_dir.mkdir(parents=True, exist_ok=True)
    master_json_path = str(test_report_dir / "master.json")

    with open(master_json_path, "w", encoding="utf-8") as f:
        json.dump(master_json, f, indent=2)

    # 4. Add to DB
    db.add_report_metadata(
        user_id=chat_id,
        alias=alias,
        index_num=1,
        summary_path="dummy_summary.md",
        report_path="dummy_report.md",
        master_json_path=master_json_path
    )

    # 5. Verify Menu Text
    menu_text = get_report_menu_text(master_json_path)
    # print("\nGenerated Menu:") # Avoid emoji print error on Windows

    assert "Your 2026 Monthly Forecasts" in menu_text
    # Month names can vary by engine version (Feb or Chinese name)
    assert "/1." in menu_text
    assert "/12." in menu_text

    # 6. Verify Individual Month Narratives
    # Month 1 (February)
    m1_narrative = get_month_narrative(master_json_path, 0)
    # print("\nMonth 1 Narrative Snippet:")
    # print(m1_narrative[:100])
    assert "Deep-dive analysis for" in m1_narrative

    # Month 12 (January 2027)
    m12_narrative = get_month_narrative(master_json_path, 11)
    # print("\nMonth 12 Narrative Snippet:")
    # print(m12_narrative[:100])
    assert "Deep-dive analysis for" in m12_narrative

    # 7. Test invalid selection
    invalid = get_month_narrative(master_json_path, 15)
    assert "Invalid month selection" in invalid

    print("\n✅ Granular Report Menu Flow Verified!")

if __name__ == "__main__":
    asyncio.run(test_report_menu_flow(Database(TEST_DB_PATH)))
