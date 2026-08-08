import asyncio
import logging
import os
import sys
from pathlib import Path

# IMPORTANT: Load dotenv so Mem0, Qdrant, and DB have credentials
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath('.'))

from src2.core.schemas.unified import UserProfile, ValidatedPillar
from src2.interfaces.telegram.chronomancer.coordinator import session_to_chart_profile
from src2.interfaces.telegram.chronomancer.oracle_coordinator import handle_oracle
from src2.interfaces.telegram.db import Database
from src2.interfaces.telegram.session import get_session, save_session

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def setup_test_user_and_stakeholder(user_id: int = 999998):
    """Seed user 999998 profile and stakeholder 'Alex' in DB."""
    db = Database()
    db.set_user_prefs(
        user_id,
        language="English",
        sifu_mode=1,
        is_premium=1,
        active_mode="ORACLE",
        oracle_query_count=0,
    )

    profile = UserProfile(
        profile_id="francis_999998",
        year_pillar=ValidatedPillar(stem="Ding", branch="Si"),
        month_pillar=ValidatedPillar(stem="Jia", branch="Chen"),
        day_pillar=ValidatedPillar(stem="Bing", branch="Yin"),
        hour_pillar=ValidatedPillar(stem="Jia", branch="Wu"),
        gender="M",
        alias="Tester",
        day_master_strength="Strong",
        favorable_elements=["Water", "Metal"],
        unfavorable_elements=["Wood", "Fire"],
        neutral_elements=["Earth"],
    )

    session = get_session(user_id)
    session.profile = profile
    save_session(session)

    # Seed stakeholder partner Alex
    db.upsert_stakeholder(
        user_id=user_id,
        relation_type="partner",
        name="Alex",
        profile_data={
            "alias": "Alex",
            "gender": "M",
            "day_pillar": {"stem": "Geng", "branch": "Wu"},
            "year_pillar": {"stem": "Geng", "branch": "Wu"},
        },
        relation_category="partner",
        sexuality_dynamic="gay",
    )
    logger.info("Test user %s and stakeholder 'Alex' seeded successfully.", user_id)
    return session, profile


async def run_oracle_pipeline_test():
    logger.info("=== Starting Oracle Mode (V34hb) E2E Verification ===")
    user_id = 999998
    session, profile = setup_test_user_and_stakeholder(user_id)
    chart_profile = session_to_chart_profile(session)
    db = Database()

    results = []

    # -------------------------------------------------------------------------
    # Turn 1: Range > 1 Year (e.g. 2027-2029) -> Annual Resolution Summary
    # -------------------------------------------------------------------------
    logger.info("--- Turn 1: Range > 1 Year (2027-2029) ---")
    q1 = "When is the best time for me to launch a major business venture between 2027 and 2029?"
    resp1 = await handle_oracle(user_id=user_id, query=q1, profile=chart_profile, sifu_mode=1)
    logger.info("Turn 1 Response Sample:\n%s", resp1[:300])

    prefs1 = db.get_user_prefs(user_id)
    count1 = prefs1.get("oracle_query_count", 0)
    assert count1 == 1, f"Expected oracle_query_count=1, got {count1}"
    assert "Mode: Oracle (Lifetime)" in resp1, "Expected Oracle footer badge in response 1"
    results.append(("Turn 1 (Range > 1 Yr)", "PASS", f"Query count={count1}"))

    await asyncio.sleep(2)

    # -------------------------------------------------------------------------
    # Turn 2: Range < 1 Year (Months in 2027) -> Monthly Resolution Breakdown
    # -------------------------------------------------------------------------
    logger.info("--- Turn 2: Range < 1 Year (Months in 2027) ---")
    q2 = "Which specific months in 2027 are best for launching?"
    resp2 = await handle_oracle(user_id=user_id, query=q2, profile=chart_profile, sifu_mode=1)
    logger.info("Turn 2 Response Sample:\n%s", resp2[:300])

    prefs2 = db.get_user_prefs(user_id)
    count2 = prefs2.get("oracle_query_count", 0)
    assert count2 == 2, f"Expected oracle_query_count=2, got {count2}"
    assert "Mode: Oracle (Lifetime)" in resp2, "Expected Oracle footer badge in response 2"
    results.append(("Turn 2 (Range < 1 Yr)", "PASS", f"Query count={count2}"))

    await asyncio.sleep(2)

    # -------------------------------------------------------------------------
    # Turn 3: Stakeholder /compat Math -> Pull Alex from Stakeholder DB Table
    # -------------------------------------------------------------------------
    logger.info("--- Turn 3: Stakeholder /compat Query ('Alex') ---")
    q3 = "How compatible am I with my business partner Alex for this venture?"
    resp3 = await handle_oracle(user_id=user_id, query=q3, profile=chart_profile, sifu_mode=1)
    logger.info("Turn 3 Response Sample:\n%s", resp3[:300])

    prefs3 = db.get_user_prefs(user_id)
    count3 = prefs3.get("oracle_query_count", 0)
    assert count3 == 3, f"Expected oracle_query_count=3, got {count3}"
    assert "Alex" in resp3 or "Stakeholder" in resp3, "Expected Alex stakeholder compatibility in response 3"
    results.append(("Turn 3 (Stakeholder /compat)", "PASS", f"Query count={count3}"))

    await asyncio.sleep(2)

    # -------------------------------------------------------------------------
    # Turn 4: Lifetime Trajectory -> Full Da Yun / Lifetime Cycle
    # -------------------------------------------------------------------------
    logger.info("--- Turn 4: Lifetime Trajectory Query ---")
    q4 = "What are my overall lifetime luck cycles and wealth turning points?"
    resp4 = await handle_oracle(user_id=user_id, query=q4, profile=chart_profile, sifu_mode=1)
    logger.info("Turn 4 Response Sample:\n%s", resp4[:300])

    prefs4 = db.get_user_prefs(user_id)
    count4 = prefs4.get("oracle_query_count", 0)
    assert count4 == 4, f"Expected oracle_query_count=4, got {count4}"
    assert "Mode: Oracle (Lifetime)" in resp4, "Expected Oracle footer badge in response 4"
    results.append(("Turn 4 (Lifetime Trajectory)", "PASS", f"Query count={count4}"))

    # -------------------------------------------------------------------------
    # Turn 5: Switch back to Ask Mode (/ask)
    # -------------------------------------------------------------------------
    logger.info("--- Turn 5: Mode Switching (/ask) ---")
    db.set_user_prefs(user_id, active_mode="ASK")
    prefs5 = db.get_user_prefs(user_id)
    assert prefs5.get("active_mode") == "ASK", f"Expected active_mode='ASK', got {prefs5.get('active_mode')}"
    results.append(("Turn 5 (Switch to /ask)", "PASS", "active_mode=ASK"))

    logger.info("\n=== Oracle Mode E2E Test Summary ===")
    for test_name, status, detail in results:
        logger.info("[%s] %s - %s", status, test_name, detail)

    logger.info("All 5 Oracle E2E turns passed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(run_oracle_pipeline_test())
    except Exception as e:
        logger.exception("Oracle E2E Pipeline Test failed with error: %s", e)
        sys.exit(1)
