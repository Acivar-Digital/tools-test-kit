import asyncio
import logging
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Adjust path to find src2
project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(project_root))

from src2.core.schemas.unified import UserProfile  # noqa: E402
from src2.engine.pydantic_prompt_engine import run_pydantic_engine  # noqa: E402
from src2.engine.transformer import to_chart_profile  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # 1. Pre-parsed Dictionary (Anti-Corruption Seam Test)
    # Mirroring Tester's Bio Data
    raw_payload = {
        "alias": "Tester",
        "gender": "M",
        "day_master_strength": "Strong",
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Water", "Wood"],
        "neutral_elements": ["Metal"],
        "year_pillar": {"stem": "Ding", "branch": "Si"},
        "month_pillar": {"stem": "Jia", "branch": "Chen"},
        "day_pillar": {"stem": "Yi", "branch": "Mao"},
        "hour_pillar": {"stem": "Ren", "branch": "Wu"},
        "da_yun_pillar": {"stem": "Ji", "branch": "Hai"},
        "day_stem_stream": "Yi",
    }

    tailoring_concerns = {
        "career": "Thinking of quitting my corporate job to start a Bazi consultancy.",
        "relationships": "Not looking for anything right now, just want peace.",
        "wealth": "Want to know if 2026 is a good year to buy a house."
    }

    logger.info("Initializing UserProfile from raw dictionary...")
    # This tests the Zero-Dict boundary (C5)
    user_profile = UserProfile.model_validate(raw_payload)

    logger.info(f"UserProfile instantiated successfully: {user_profile.alias}")

    logger.info("Converting to ChartProfile for Engine (C4)...")
    from src2.interfaces.telegram.tailoring import build_tailoring_context
    chart_profile_dict = user_profile.model_dump()
    chart_profile_dict["tailoring_concerns"] = tailoring_concerns
    chart_profile_dict["tailoring_context"] = build_tailoring_context(tailoring_concerns)

    chart_profile = to_chart_profile(chart_profile_dict)


    logger.info("Running E2E Engine (Live Production Models)...")

    # We will just print the progress and final result
    async def progress(msg):
        print(f"[PROGRESS] {msg}")

    try:
        # Executes the engine and live report models
        result = await run_pydantic_engine(
            profile_data=chart_profile,
            target_year=2026,
            progress_callback=progress
        )

        print("\n=== E2E Run Complete ===")
        if result.months:
            print(f"Generated {len(result.months)} monthly reports.")
            first_month = result.months[0]
            if hasattr(first_month, 'rationale'):
                print(f"First Month Rationale: {getattr(first_month, 'rationale')[:200]}...")
            else:
                print(f"First Month Error: {getattr(first_month, 'error', 'Unknown Error')}")

        # Dump the result to a JSON artifact
        artifact_path = Path(__file__).parent / "final_report.json"
        with open(artifact_path, "w", encoding="utf-8") as f:
            f.write(result.model_dump_json(indent=2))
        print(f"Final artifact saved to {artifact_path}")

    except Exception as e:
        logger.error(f"Engine Run Failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
