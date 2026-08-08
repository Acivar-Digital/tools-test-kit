#!/usr/bin/env python3
"""
Standalone monthly forecast runner.

Usage:
    # baziforecaster-only: TEST/GOLD/08_month_read/run_monthly.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. [--chat-id 12345]

Creates a mock session in DB, then calls run_pipeline_direct(chat_id).
No Telegram webhook needed — runs entirely offline.

Prerequisites:
    - DB must be initialized (run `uv run start2.py` at least once)
    - .env must have BAZI_ENGINE_CONCURRENCY set
    - LLM proxy must be reachable (for Pydantic AI agent calls)
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

from src.bot.schemas import Pillar, UserProfile
from src.bot.session import Session, delete_session, save_session

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── Mock data ──────────────────────────────────────────────────────────────
# Test Profile's real chart (from _prd/users/99999/)
MOCK_PROFILE = UserProfile(
    alias="Test Profile",
    gender="M",
    day_pillar=Pillar(stem="Ren", branch="Chen"),
    month_pillar=Pillar(stem="Yi", branch="Si"),
    year_pillar=Pillar(stem="Ji", branch="Wei"),
    hour_pillar=Pillar(stem="Gui", branch="Chou"),
    dob="1990-06-15 08:30",
    location="Singapore",
    day_master_strength="Balanced",
    favorable_elements=["Water", "Wood"],
    unfavorable_elements=["Fire", "Earth"],
)

MOCK_CHAT_ID = 99999  # Test Profile's real Telegram chat_id


async def setup_mock_session(chat_id: int, profile: UserProfile) -> None:
    """Create or reset a session in DB with mock profile data."""
    # Clean slate
    try:
        delete_session(chat_id)
    except Exception:
        pass

    session = Session(
        chat_id=chat_id,
        step="CONFIRM",
        profile=profile,
        metadata={
            "dob": profile.dob,
            "tailoring_concerns": "career growth and relationship timing",
        },
    )
    save_session(session)
    logger.info(f"Mock session created for chat_id={chat_id} alias={profile.alias}")


async def main():
    parser = argparse.ArgumentParser(description="Run monthly forecast for a mock user")
    parser.add_argument("--chat-id", type=int, default=MOCK_CHAT_ID, help="Telegram chat_id")
    parser.add_argument("--alias", type=str, default=MOCK_PROFILE.alias, help="User alias")
    args = parser.parse_args()

    # Apply custom alias if provided
    profile = MOCK_PROFILE.model_copy(update={"alias": args.alias})

    logger.info("=" * 60)
    logger.info("  Monthly Forecast Runner")
    logger.info(f"  chat_id : {args.chat_id}")
    logger.info(f"  alias   : {args.alias}")
    logger.info(f"  profile : {profile.year_pillar.stem} {profile.year_pillar.branch} / "
                f"{profile.month_pillar.stem} {profile.month_pillar.branch} / "
                f"{profile.day_pillar.stem} {profile.day_pillar.branch} / "
                f"{profile.hour_pillar.stem} {profile.hour_pillar.branch}")
    logger.info("=" * 60)

    # 1. Setup mock session
    await setup_mock_session(args.chat_id, profile)
    logger.info("✅ Mock session saved to DB")

    # 2. Import and run pipeline
    from src.engine.pydantic_prompt_engine import run_pipeline_direct

    logger.info("🚀 Starting pipeline...")
    start = datetime.now()
    await run_pipeline_direct(args.chat_id)
    elapsed = (datetime.now() - start).total_seconds()

    logger.info(f"✅ Pipeline completed in {elapsed:.1f}s")
    logger.info("Check DB Reports table and report directory for output.")


if __name__ == "__main__":
    asyncio.run(main())
