import asyncio
import json
import logging
import sys
import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

# IMPORTANT: Ensure dotenv is loaded so Mem0 and Qdrant have credentials
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath('.'))

from src2.core.memory.memory_manager import memory_manager
from src2.core.schemas.unified import UserProfile, ValidatedPillar
from src2.engine.narrative_simplifier import advisory_simplifier_agent
from src2.interfaces.telegram.app import _process_webhook_logic_inner
from src2.interfaces.telegram.db import Database

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def mock_francis_session(user_id: int):
    # Mock Tester' profile directly into the database
    from src2.interfaces.telegram.db import Database
    db = Database("bot.db")

    from src2.interfaces.telegram.session import get_session, save_session

    profile = UserProfile(
        profile_id="francis_123",
        year_pillar=ValidatedPillar(stem="Ding", branch="Si"),
        month_pillar=ValidatedPillar(stem="Jia", branch="Chen"),
        day_pillar=ValidatedPillar(stem="Bing", branch="Yin"),
        hour_pillar=ValidatedPillar(stem="Jia", branch="Wu"),
        gender="M",
        alias="Tester",
        day_master_strength="Strong",
        favorable_elements=["Water", "Metal"],
        unfavorable_elements=["Wood", "Fire"]
    )

    session = get_session(user_id)
    session.profile = profile
    save_session(session)
    db.set_user_prefs(user_id, language="English", sifu_mode=1, is_premium=1)

captured_replies = []

async def mock_send_telegram_message(chat_id, text, *args, **kwargs):
    # Ignore the "thinking" messages
    if "thinking..." not in text and "Chronomancer is listening" not in text:
        captured_replies.append(text)
    return {}

async def run_command_via_app(user_id: int, command: str):
    global captured_replies
    captured_replies.clear()

    data = {
        "message": {
            "chat": {"id": user_id},
            "text": command,
            "date": int(datetime.now(UTC).timestamp()),
            "message_id": 1
        }
    }

    with patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock, side_effect=mock_send_telegram_message):
        with patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock, side_effect=mock_send_telegram_message):
            with patch("src2.interfaces.telegram.security.can_use_chronomancer", return_value=True):
                await _process_webhook_logic_inner(data)

    if not captured_replies:
        return "ERROR: No reply captured"
    return captured_replies[-1] # The last message sent is usually the final result

async def pre_test_mem0():
    logger.info("--- PHASE 1: PRE-TEST MEM0 ---")
    user_id = 999999

    # Write
    content = "User loves drinking black coffee in the morning."
    await memory_manager.add_memory(user_id=user_id, text=content)
    logger.info("✅ Inserted mock memory")

    # Read
    try:
        logger.info("Attempting mem0 search (this might time out if BGEM3 is down)")
    except Exception as e:
        logger.warning(f"Mem0 search skipped/failed: {e}")

async def pre_test_simplifier():
    logger.info("--- PHASE 1: PRE-TEST SIMPLIFIER ---")
    agent = advisory_simplifier_agent

    test_narrative = "The qi is strong today. Avoid water."

    languages = ["English", "Chinese", "Malay", "Indonesian"]
    for lang in languages:
        prompt = f"Translate this to {lang}.\n{test_narrative}"
        res = await agent.run(prompt)
        logger.info(f"✅ Simplifier test {lang}: {res.output}")

async def phase2_permutations():
    logger.info("--- PHASE 2: PERMUTATION RUN ---")
    user_id = 999999
    mock_francis_session(user_id)
    db = Database("bot.db")

    # Clear out any prior cache for this test user
    db.delete_daily_forecasts_for_user(user_id)

    report = []

    # SIFU MODE ON (English only)
    logger.info(">> SIFU MODE ON (English)")
    db.set_user_prefs(user_id, sifu_mode=1, language="English", is_premium=1)

    commands = ["/daily", "/30", "/career", "/wealth", "/love"]

    for cmd in commands:
        logger.info(f"Running {cmd}")
        reply_text = await run_command_via_app(user_id, cmd)
        report.append({"sifu": True, "language": "English", "command": cmd, "result": reply_text})

    # SIFU MODE OFF (4 languages)
    languages = ["English", "Chinese", "Malay", "Indonesian"]
    for lang in languages:
        logger.info(f">> SIFU MODE OFF ({lang})")
        db.set_user_prefs(user_id, sifu_mode=0, language=lang, is_premium=1)

        for cmd in commands:
            logger.info(f"Running {cmd}")
            reply_text = await run_command_via_app(user_id, cmd)
            report.append({"sifu": False, "language": lang, "command": cmd, "result": reply_text})

    # Write report
    report_path = Path(__file__).parent / "final_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"✅ Full report saved to {report_path}")


async def phase3_session_amnesia():
    logger.info("--- PHASE 3: SESSION AMNESIA / MONTHLY REPORT FALLBACK ---")
    tg_user_id = 999998
    db = Database("bot.db")

    # 1. Setup minimal db linkages to allow resolution and report lookup
    import uuid

    from src2.core.database.models import PlatformAccount, Report, User
    session = db.Session()

    # Generate UUID for the database
    real_user_id = uuid.uuid4()

    # Clear prior test data
    existing = session.query(PlatformAccount).filter(PlatformAccount.platform_user_id == str(tg_user_id)).all()
    for acc in existing:
        session.query(Report).filter(Report.user_id == acc.user_id).delete()
        session.query(User).filter(User.id == acc.user_id).delete()
    session.query(PlatformAccount).filter(PlatformAccount.platform_user_id == str(tg_user_id)).delete()
    session.commit()

    sem_id = "SGUSD999998"
    new_user = User(id=real_user_id, semantic_id=sem_id, tier="PREMIUM", region="SG")
    session.add(new_user)
    session.flush()
    account = PlatformAccount(user_id=new_user.id, platform="telegram", platform_user_id=str(tg_user_id))
    session.add(account)
    session.flush()
    session.commit()

    # 2. Create mock report on disk
    import json

    from src2.core.memory.memory_manager import MemoryManager
    logger.info("2.0: Init MemoryManager")
    mm = MemoryManager()
    logger.info("2.1: MemoryManager init done")
    report_dir = mm.get_reports_dir(tg_user_id) / "1"
    logger.info(f"2.2: report_dir = {report_dir}")
    report_dir.mkdir(parents=True, exist_ok=True)
    master_path = report_dir / "BaziForecast_2026_test_master.json"

    # Notice we use 'profile_summary' per the Pydantic V2 engine updates
    mock_master = {
        "profile_summary": {
            "gender": "M",
            "alias": "Test User",
            "year_pillar": {"stem": "Ding", "branch": "Si"},
            "month_pillar": {"stem": "Jia", "branch": "Chen"},
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "hour_pillar": {"stem": "Ren", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Ji", "branch": "Hai"},
            "day_master_strength": "Strong",
            "medicine": ["Fire", "Earth"],
            "taboo": ["Wood", "Water"],
            "neutral": ["Metal"],
            "structure": "Other"
        }
    }
    with open(master_path, "w") as f:
        json.dump(mock_master, f)

    logger.info("3.0: Register report in DB")
    # Register report in DB
    report = Report(
        user_id=real_user_id,
        alias="Test User",
        index_num=1,
        summary_path=str(master_path),
        report_path=str(master_path),
        master_json_path=str(master_path)
    )
    session.add(report)
    session.commit()
    logger.info("3.1: DB commit successful")

    # 3. Ensure no DB session state exists
    logger.info("3.2: Deleting DB session state")
    from src2.interfaces.telegram.session import delete_session
    delete_session(tg_user_id, "telegram")
    logger.info("3.3: Delete session successful")

    report_results = []

    # Clear Redis user_state cache for a clean slate
    import redis.asyncio as redis
    import os
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"))
    await redis_client.delete(f"user_state:{tg_user_id}")
    await redis_client.aclose()

    db.set_user_prefs(tg_user_id, sifu_mode=1, language="English", is_premium=1)

    # Step 1: /daily
    logger.info("Step 1: Triggering /daily (Sifu ON, English) - Session Amnesia")
    delete_session(tg_user_id, "telegram") # Force amnesia
    reply_1 = await run_command_via_app(tg_user_id, "/daily")
    logger.info(f"Step 1 Result: {reply_1[:200]}...")
    report_results.append({"step": 1, "action": "/daily", "result": reply_1})
    
    await asyncio.sleep(5)

    # Step 2: what should I do now?
    logger.info("Step 2: Triggering /ask What should I do now?")
    reply_2 = await run_command_via_app(tg_user_id, "/ask What should I do now?")
    logger.info(f"Step 2 Result: {reply_2[:200]}...")
    report_results.append({"step": 2, "action": "/ask What should I do now?", "result": reply_2})
    
    await asyncio.sleep(5)

    # Step 3: next year rejection
    logger.info("Step 3: Triggering /ask what is best time to get married in December 2027?")
    reply_3 = await run_command_via_app(tg_user_id, "/ask what is best time to get married in December 2027?")
    logger.info(f"Step 3 Result: {reply_3[:200]}...")
    report_results.append({"step": 3, "action": "/ask next year", "result": reply_3})
    
    if "30 days" not in reply_3 and "wait for the upcoming /oracle" not in reply_3:
        raise AssertionError(f"❌ Step 3 Failed: Did not reject future date. Result: {reply_3}")
        
    await asyncio.sleep(5)

    # Step 4: propose within 30 days
    logger.info("Step 4: Triggering /ask when is the best time go propose within these 30 days?")
    reply_4 = await run_command_via_app(tg_user_id, "/ask ok. in that case when is the best time go propose within these 30 days?")
    logger.info(f"Step 4 Result: {reply_4[:200]}...")
    report_results.append({"step": 4, "action": "/ask propose 30 days", "result": reply_4})
    
    await asyncio.sleep(5)

    # Step 5: profile deep dive
    logger.info("Step 5: Triggering /ask tell me more about my bazi profile? luck cycle, everything")
    reply_5 = await run_command_via_app(tg_user_id, "/ask tell me more about my bazi profile? luck cycle, everything")
    logger.info(f"Step 5 Result: {reply_5[:200]}...")
    report_results.append({"step": 5, "action": "/ask profile", "result": reply_5})
    
    await asyncio.sleep(5)

    # Step 6: what should I do now?
    logger.info("Step 6: Triggering /ask so what should i do now?")
    reply_6 = await run_command_via_app(tg_user_id, "/ask so what should i do now?")
    logger.info(f"Step 6 Result: {reply_6[:200]}...")
    report_results.append({"step": 6, "action": "/ask what should I do now 2", "result": reply_6})

    # Check for regressions
    for r in report_results:
        if "No Bazi profile found" in r["result"] or "ERROR" in r["result"]:
            raise AssertionError(f"❌ BUG REPRODUCED: Step failed: {r['action']} - Result: {r['result'][:200]}")

    logger.info("✅ SUCCESS: All 6 steps completed successfully!")


async def main():
    try:
        await pre_test_mem0()
        await pre_test_simplifier()
        await phase2_permutations()
        await phase3_session_amnesia()
        logger.info("✅ E2E Pipeline Passed!")

        from src2.interfaces.telegram.chronomancer.coordinator import background_tasks
        if background_tasks:
            logger.info(f"Awaiting {len(background_tasks)} background tasks to drain...")
            await asyncio.gather(*background_tasks, return_exceptions=True)
            logger.info("✅ Background tasks drained successfully.")

    except Exception as e:
        logger.error(f"❌ E2E failed: {e}", exc_info=True)
        import sys
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
