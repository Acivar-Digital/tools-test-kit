# ruff: noqa: E402
import pytest

pytest.skip("Legacy alt_src module removed", allow_module_level=True)


from dotenv import load_dotenv

# Load API keys BEFORE any local imports
load_dotenv()

import asyncio  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import sys  # noqa: E402
import traceback  # noqa: E402
from pathlib import Path  # noqa: E402

os.environ["K3_DISPATCH_INTERVAL"] = "5.0"

# --- MONKEYPATCHING FOR LIVE RUN ---
from alt_src.K3.k3_consolidator import stitch_and_convert  # noqa: E402
from alt_src.K3.k3_pipeline import run_k3_pipeline  # noqa: E402
from alt_src.K3.k3_summarizer import run_summarizer  # noqa: E402

from src.bot.bridge import map_profile_to_k3  # noqa: E402
from src.bot.session import UserProfile  # noqa: E402

# Import engine components


async def progress_logger(msg: str):
    print(f"  [LIVE] {msg}")

async def test_live_production_pipeline():
    print("--- STARTING LIVE PRODUCTION PIPELINE (REAL OPENROUTER CALLS) ---")

    if not os.getenv("OPENROUTER_API_KEY"):
        print("FAIL: ERROR: OPENROUTER_API_KEY not found in .env file.")
        return

    # 1. SETUP DATA
    chat_id = 999000001
    profile = UserProfile(
        name="Test Profile",
        alias="Tester",
        gender="M",
        year_pillar={"stem": "Ding", "branch": "Si"},
        month_pillar={"stem": "Jia", "branch": "Chen"},
        day_pillar={"stem": "Yi", "branch": "Mao"},
        hour_pillar={"stem": "Ren", "branch": "Wu"},
        da_yun_pillar={"stem": "Ji", "branch": "Hai"},
        da_yun_start_year=2023,
        day_master_strength="Strong",
        favorable_elements=["Fire", "Earth"],
        unfavorable_elements=["Water", "Wood"],
        neutral_elements=["Metal"]
    )

    tailoring_concerns = {
        "career": "1. Growth: Is this a good year to seek a promotion or salary raise in my current role?",
        "relationships": "1. New Love: What are my prospects for meeting a new romantic partner this year?",
        "wealth": "1. High Growth: Is 2026 favorable for aggressive investments and new wealth creation?",
        "health": "1. Vitality: Which months should I prioritise rest and avoid over-exertion?",
        "health_concern": "1" # Sleep & energy levels
    }

    # 2. PREPARE DIRECTORIES
    artifact_dir = Path("TEST/reports/live_run_francis")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    profile_path = artifact_dir / "profile.json"
    master_json_path = artifact_dir / "master.json"
    summary_md_path = artifact_dir / "executive_summary.md"
    summary_json_path = artifact_dir / "summary.json"
    final_html_path = artifact_dir / "final_report_live.html"

    # Save the profile for the pipeline to load
    k3_profile = map_profile_to_k3(profile, chat_id, dob="1990-01-01", tailoring_concerns=tailoring_concerns)
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(k3_profile, f, indent=2, ensure_ascii=False)

    print(f"[Step 1/4] Data Ready. Profile saved to {profile_path}")

    # 3. RUN K3 PIPELINE (LIVE Phase A + Phase B)
    print("[Step 2/4] Running 12-Month LLM Pipeline (Phase A/B)...")
    try:
        import logging

        import alt_src.K3.k3_pipeline as k3p
        # Stream logs to console
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('  [LOG] %(levelname)s: %(message)s'))
        k3p.logger.addHandler(handler)
        k3p.logger.setLevel("DEBUG")

        # We pass the real paths and progress logger
        results, failed_months = await run_k3_pipeline(
            profile_path=str(profile_path),
            output_path=str(master_json_path),
            progress_callback=progress_logger
        )
        if failed_months:
             print(f"FAIL: Pipeline had failed months: {failed_months}")
             # We won't return yet, let's see if master.json was partially written
        else:
             print(f"OK: Master JSON generated at {master_json_path}")
    except Exception as e:
        print(f"FAIL: PIPELINE CRASHED: {e}")
        traceback.print_exc()
        return

    # 4. RUN SUMMARIZER (LIVE)
    print("[Step 3/4] Running Annual Summarizer (Live LLM)...")
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: run_summarizer(
            k3_json_path=str(master_json_path),
            output_md_path=str(summary_md_path),
            output_json_path=str(summary_json_path),
            live_api=True,
            progress_callback=progress_logger,
            loop=loop
        ))
        print(f"OK: Executive Summary generated at {summary_md_path}")
    except Exception as e:
        print(f"FAIL: SUMMARIZER FAILED: {e}")
        traceback.print_exc()
        return

    # 5. CONVERT TO PREMIUM HTML
    print("[Step 4/4] Converting to Premium HTML...")
    try:
        stitch_and_convert(str(summary_md_path), str(final_html_path))
        print(f"OK: FINAL HTML READY: {final_html_path}")
    except Exception as e:
        print(f"FAIL: CONSOLIDATOR FAILED: {e}")
        return

    print("\n--- LIVE PRODUCTION RUN COMPLETE ---")
    print(f"Final Report: {final_html_path.absolute()}")

if __name__ == "__main__":
    asyncio.run(test_live_production_pipeline())
