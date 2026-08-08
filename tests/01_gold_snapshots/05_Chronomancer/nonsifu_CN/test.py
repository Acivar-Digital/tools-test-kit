import asyncio
import logging
import os
import sys
from pathlib import Path

# Annot: baziforecaster-only (src2.* imports). Honour KIT_PATH / TARGET_REPO override.
_kit_root = os.getenv("KIT_PATH", "") or os.getenv("TARGET_REPO", "")
PROJECT_ROOT = Path(_kit_root) if _kit_root else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment
from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env", override=True)

# Ensure LLM_BASE_URL is configured
if not os.getenv("LLM_BASE_URL"):
    raise ValueError("LLM_BASE_URL is not configured in .env.")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ChronomancerSimulation")

def sanitize_response(text: str) -> str:
    import re
    if not text:
        return ""
    # Strip thought tags (both raw and escaped HTML entity versions)
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()
    text = re.sub(r"&lt;thought&gt;.*?&lt;/thought&gt;", "", text, flags=re.DOTALL).strip()
    # Normalize LaTeX arrows to Unicode arrows
    text = text.replace(r"$\rightarrow$", "→").replace(r"\rightarrow", "→")
    text = text.replace(r"$\leftarrow$", "←").replace(r"\leftarrow", "←")
    text = text.replace(r"$\implies$", "⇒").replace(r"\implies", "⇒")
    return text


async def run_test(verbose=False, chat_id_override=None):
    user_id = chat_id_override or 999
    logger.info(f"Starting Chronomancer conversational simulation for user {user_id}...")

    # Lazy imports from src2
    from unittest.mock import AsyncMock, MagicMock

    from src2.core.memory.memory_manager import memory_manager
    from src2.core.schemas import UserProfile
    from src2.core.schemas import ValidatedPillar as Pillar
    from src2.interfaces.telegram.chronomancer import coordinator
    from src2.interfaces.telegram.chronomancer.coordinator import handle_ask, handle_daily
    from src2.interfaces.telegram.db import Database
    from src2.interfaces.telegram.session import get_session, save_session

    db = Database("bot.db")

    # Set up LLM mock conditional check (default to running the real RAG / LLM engine)
    import os
    run_real_llm = os.getenv("RUN_REAL_LLM", "true").lower() == "true"

    if not run_real_llm:
        logger.info("Mocking LLM Agents and parse_question to bypass API gateway...")
        # Mock the LLM Agents to bypass quota failures during tests
        mock_sifu = MagicMock()
        mock_sifu.run = AsyncMock()
        coordinator._get_sifu_agent = lambda: mock_sifu

        mock_simplifier = MagicMock()
        mock_simplifier.run = AsyncMock()
        coordinator._get_simplifier_agent = lambda: mock_simplifier

        # Mock parse_question to bypass IER LLM calls during tests
        from datetime import date
        async def mock_parse_question(question, **kwargs):
            q = question.lower()
            if "partner" in q:
                return {
                    "dates": [date.today()],
                    "entity": "lover",
                    "intent": "love",
                    "raw_question": question,
                    "source": "mock"
                }
            elif "job" in q or "engineer" in q or "house" in q:
                return {
                    "dates": [],
                    "entity": None,
                    "intent": "career",
                    "raw_question": question,
                    "source": "mock"
                }
            else:
                return {
                    "dates": [],
                    "entity": None,
                    "intent": "general",
                    "raw_question": question,
                    "source": "mock"
                }
        coordinator.parse_question = mock_parse_question
    else:
        logger.info("Running simulation with REAL LLM agents and RAG grounding enabled!")

    # 1. Setup User Profile in memory manager & session
    logger.info("Turn 0: Bootstrapping profile and clearing memories...")

    # Clean up DB records for test user to guarantee a fresh run
    try:
        db.delete_all_user_data(user_id)
    except Exception as e:
        logger.warning(f"Failed to clean up user data: {e}")

    # Initialize session (which automatically creates the user and links the testing semantic ID in the database)
    session = get_session(user_id)
    db.set_user_prefs(user_id, sifu_mode=0, language="English")

    # Wipe any old memories and files to keep test pristine
    await memory_manager.clear_all_user_data(user_id)
    await memory_manager.clear_all_user_data("999999")

    # Initialize UI.md as blank
    ui_md_path = Path(__file__).resolve().parent / "UI.md"
    with open(ui_md_path, "w", encoding="utf-8") as f:
        f.write("")

    # Clean up Valkey/cache db values for today's forecast
    try:
        from src2.interfaces.telegram.chronomancer.coordinator import get_sg_today
        today_str = get_sg_today().isoformat()
        db.delete_chrono_cache_for_user_date(user_id, today_str)
    except Exception as e:
        logger.warning(f"Failed to clear cache: {e}")

    # Save Tester' profile to memory manager disk
    memory_manager.get_user_dir(user_id)
    profile_path = memory_manager.get_profile_path(user_id)
    user_uuid = str(db._get_or_create_uuid(user_id))

    import json
    mock_profile_data = {
        "profile_id": user_uuid,
        "gender": "M",
        "alias": "Tester",
        "year_pillar": "丁巳",
        "month_pillar": "乙巳",
        "day_pillar": "庚辰",
        "hour_pillar": "丁丑",
        "da_yun_pillar": "庚子",
        "day_master_strength": "Weak",
        "favorable_elements": ["Metal", "Water"],
        "unfavorable_elements": ["Fire"],
        "neutral_elements": ["Earth", "Wood"],
        "structure": "Direct Wealth",
        "domain_focus": "General"
    }
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(mock_profile_data, f, indent=2)

    session.profile = UserProfile(
        profile_id=user_uuid,
        gender="M",
        alias="Tester",
        year_pillar=Pillar(stem="Ding", branch="Si"),
        month_pillar=Pillar(stem="Yi", branch="Si"),
        day_pillar=Pillar(stem="Geng", branch="Chen"),
        hour_pillar=Pillar(stem="Ding", branch="Chou"),
        da_yun_pillar=Pillar(stem="Geng", branch="Zi"),
        day_master_strength="Weak",
        favorable_elements=["Metal", "Water"],
        unfavorable_elements=["Fire"],
        neutral_elements=["Earth", "Wood"],
        structure="Direct Wealth"
    )
    session.step = "CHRONOMANCER"
    save_session(session)

    # 1. Turn 1: Language Preference Selection (/lang)
    logger.info("--- TURN 1: /lang ---")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(
            "### STEP 1\n"
            "💬 **User**: `/lang`\n\n"
            "🤖 **Bot**:\n"
            "> 🌍 *Language Selection*\n"
            "> \n"
            "> Your current reading language is set to: *English*\n"
            "> \n"
            "> Select your preferred language below:\n"
            "> [🇬🇧 English (EN)] [🇨🇳 中文 (CN)]\n"
            "> [🇮🇩 Indonesia (ID)] [🇲🇾 Malaysia (MY)]\n\n"
            "💬 **User**: (clicks [🇨🇳 中文 (CN)])\n\n"
            "🤖 **Bot**:\n"
            "> ✅ *Language updated successfully!* Reading options are now set to: *Chinese*\n"
            "> \n"
            "> _Note: System menus and technical Bazi charts remain in English._\n\n\n"
        )
    db.set_user_prefs(user_id, sifu_mode=0, language="Chinese")
    logger.info("✅ Simulated language preference switch to Chinese.")

    # 2. Turn 2: Daily Forecast Ingestion
    logger.info("--- TURN 2: /daily ---")
    if not run_real_llm:
        mock_sifu.run.return_value = MagicMock(output="Daily forecast: Today is Geng Metal day. Pay attention to wealth.")
        mock_simplifier.run.return_value = MagicMock(output="Today is Geng Metal day. Pay attention to wealth.")

    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write("### STEP 2\n💬 **User**: `/daily`\n\n🤖 **Bot**:\n> ⏳ _Chronomancer is thinking..._\n\n")
    daily_res = await handle_daily(user_id)
    print("\n[BOT DAILY FORECAST (LIVE GENERATED)]:\n", daily_res, "\n")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"🤖 **Bot**:\n> {sanitize_response(daily_res)}\n\n\n")
    assert len(daily_res.strip()) > 0, "Daily forecast narrative was empty"

    # Verify that the forecast was saved to the cache database
    cache_record = db.get_chrono_cache(user_id, today_str)
    assert cache_record is not None, "Daily forecast was not saved to DB cache"
    cache_val = cache_record.get("narrative")
    from src2.interfaces.telegram.utils import markdown_to_tg_html
    if getattr(daily_res, "parse_mode", "Markdown") == "HTML":
        if "---" in cache_val:
            parts = cache_val.split("---", 1)
            for part in parts:
                expected_part = markdown_to_tg_html(part.strip())
                assert expected_part[:100] in daily_res, f"Cached part '{expected_part[:50]}' not found in generated narrative"
        else:
            expected_part = markdown_to_tg_html(cache_val)
            assert expected_part in daily_res, "Cached narrative does not match generated narrative"
    else:
        expected_part = cache_val
        assert expected_part in daily_res, "Cached narrative does not match generated narrative"
    logger.info("✅ Verified: Daily forecast record was successfully saved to the database cache!")

    # Verify cache extraction by querying /daily again
    logger.info("--- TURN 2b: /daily Cache Ingestion Verification ---")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write("### STEP 3\n💬 **User**: `/daily` (cached)\n\n🤖 **Bot**:\n> ⏳ _Chronomancer is thinking..._\n\n")
    daily_res_cached = await handle_daily(user_id)
    print("\n[BOT DAILY FORECAST (EXTRACTED FROM CACHE)]:\n", daily_res_cached, "\n")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"🤖 **Bot**:\n> {sanitize_response(daily_res_cached)}\n\n\n")
    assert daily_res_cached.replace(" (Cached).", ". You can now ask follow-up questions.") == daily_res, "Cached narrative differs from the original"
    logger.info("✅ Verified: Daily forecast was successfully extracted from the database cache!")

    # 3. Turn 3: Follow-up question (Intent QA)
    logger.info("--- TURN 3: Follow-up Ask (Intent & Date QA) ---")
    if not run_real_llm:
        mock_sifu.run.return_value = MagicMock(output="Yes, today is a good day to meet your partner.")
        mock_simplifier.run.return_value = MagicMock(output="Yes, today is a good day to meet your partner.")

    ask_q2 = "Is today a good day to meet my partner?"
    print(f"\n[USER]: {ask_q2}")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"### STEP 4\n💬 **User**: `{ask_q2}`\n\n🤖 **Bot**:\n> ⏳ _Chronomancer is thinking..._\n\n")
    reply_q2 = await handle_ask(user_id, ask_q2)
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"🤖 **Bot**:\n> {sanitize_response(reply_q2)}\n\n\n")
    print("[BOT]:\n", reply_q2, "\n")
    assert len(reply_q2.strip()) > 0, "QA turn 2 reply was empty"

    # 4. Turn 4: Fact Injection
    logger.info("--- TURN 4: Fact Injection (Career Update) ---")
    if not run_real_llm:
        mock_sifu.run.return_value = MagicMock(output="Congratulations on starting a job in Singapore. Plan to buy a house.")
        mock_simplifier.run.return_value = MagicMock(output="Congratulations on starting a job in Singapore. Plan to buy a house.")

    ask_q3 = "I recently started a new job as a Senior Engineer, and I am planning to buy a house next month in Singapore."
    print(f"\n[USER]: {ask_q3}")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"### STEP 5\n💬 **User**: `{ask_q3}`\n\n🤖 **Bot**:\n> ⏳ _Chronomancer is thinking..._\n\n")
    reply_q3 = await handle_ask(user_id, ask_q3)
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"🤖 **Bot**:\n> {sanitize_response(reply_q3)}\n\n\n")
    print("[BOT]:\n", reply_q3, "\n")
    assert len(reply_q3.strip()) > 0, "QA turn 3 reply was empty"

    # Wait briefly for vector indexing lag
    await asyncio.sleep(1)

    # 5. Turn 5: Verify persistence (Memory QA)
    logger.info("--- TURN 5: Memory Verification (Context QA) ---")
    resolved_search_id = memory_manager._resolve_id(user_id)
    memories = memory_manager.mem_store.search(resolved_search_id, "Singapore job")
    logger.info(f"Verified memory store search results for user {user_id} (resolved: {resolved_search_id}): {memories}")
    assert any("Singapore" in m.get("text", "") or "Singapore" in m.get("memory", "") for m in memories), "Fact was not persisted to Qdrant"

    # 5. Turn 5: Memory Recall
    logger.info("--- TURN 5: Memory Recall Ask ---")
    if not run_real_llm:
        mock_sifu.run.return_value = MagicMock(output="Based on your Singapore plans, you should buy the house next month.")
        mock_simplifier.run.return_value = MagicMock(output="Based on your Singapore plans, you should buy the house next month.")

    ask_q4 = "Based on my Singapore plans, what should I look out for?"
    print(f"\n[USER]: {ask_q4}")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"### STEP 6\n💬 **User**: `{ask_q4}`\n\n🤖 **Bot**:\n> ⏳ _Chronomancer is thinking..._\n\n")
    reply_q4 = await handle_ask(user_id, ask_q4)
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"🤖 **Bot**:\n> {sanitize_response(reply_q4)}\n\n\n")
    print("[BOT]:\n", reply_q4, "\n")

    # Assert that the bot knows about the Singapore/house plans by querying memory
    assert any(keyword in reply_q4.lower() for keyword in ["singapore", "job", "engineer", "house"]), \
        f"Bot failed to recall user plans in answer: {reply_q4}"

    # 6. Turn 6: Final /daily cache verification
    logger.info("--- TURN 6: Final /daily Cache Verification ---")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write("### STEP 7\n💬 **User**: `/daily` (final cache verification)\n\n🤖 **Bot**:\n> ⏳ _Chronomancer is thinking..._\n\n")
    daily_res_final = await handle_daily(user_id)
    print("\n[BOT DAILY FORECAST (FINAL CACHED EXTRACTION)]:\n", daily_res_final, "\n")
    with open(ui_md_path, "a", encoding="utf-8") as f:
        f.write(f"🤖 **Bot**:\n> {sanitize_response(daily_res_final)}\n\n\n")
    assert daily_res_final == daily_res_cached, "Final cached narrative differs from the original"
    logger.info("✅ Verified: Daily forecast was successfully extracted from cache at the end of the simulation!")

    logger.info("Simulation completed successfully! All assertions passed.")

if __name__ == "__main__":
    asyncio.run(run_test())
