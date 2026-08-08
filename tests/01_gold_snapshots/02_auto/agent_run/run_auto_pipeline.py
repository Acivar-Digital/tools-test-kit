import asyncio
import logging
from pathlib import Path
import sys
import os

project_root = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src2.core.schemas.unified import UserProfile
from src2.interfaces.telegram.session import Session, SessionMetadata
from src2.interfaces.telegram.intake.calendar_node import _run_auto_engine
from src2.interfaces.telegram.tailoring import build_tailoring_context
from src2.engine.transformer import to_chart_profile
from src2.engine.pydantic_prompt_engine import run_pydantic_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Dummy DB dependency for calendar_node's db.get_semantic_id
import src2.interfaces.telegram.bridge as bridge
class MockDB:
    def get_semantic_id(self, chat_id):
        return f"mock_semantic_{chat_id}"
    def get_user_prefs(self, chat_id):
        return {"language": "English"}
bridge.db = MockDB()

async def main():
    # 1. Mock Session Setup
    session = Session(chat_id=123)
    session.metadata = SessionMetadata()
    session.metadata.dob = "1977-04-28 11:51"
    session.metadata.location = "Singapore"
    session.metadata.intake = {"gender": "M", "alias": "Tester"}
    
    tailoring_concerns = {
        "career": "Is this a good year to seek a promotion or salary raise in my current role?",
        "relationships": "What are my prospects for meeting a new romantic partner this year?",
        "wealth": "Is 2026 favorable for aggressive investments and new wealth creation?"
    }
    session.metadata.tailoring_concerns = tailoring_concerns

    logger.info("Running _run_auto_engine to generate profile from DOB...")
    session = await _run_auto_engine(session)
    
    user_profile = session.profile
    if not user_profile:
        raise ValueError("Profile generation failed")
    logger.info(f"Generated Auto Profile: {user_profile.model_dump_json(indent=2)}")

    logger.info("Simulating map_profile_to_k3 mapping...")
    # Emulate bridge.py:map_profile_to_k3
    chart_profile_dict = user_profile.model_dump()
    chart_profile_dict["tailoring_concerns"] = session.metadata.tailoring_concerns
    chart_profile_dict["tailoring_context"] = build_tailoring_context(session.metadata.tailoring_concerns)
    
    logger.info("Validating ChartProfile at C5 boundary...")
    chart_profile = to_chart_profile(chart_profile_dict)
    
    logger.info(f"Tailoring Context attached: {bool(chart_profile.tailoring_context)}")

    logger.info("Running E2E Engine (Live Production Models)...")
    
    async def progress(msg):
        print(f"[PROGRESS] {msg}")

    # Output artifact
    output_path = Path(__file__).parent / "final_report.json"

    try:
        result = await run_pydantic_engine(
            profile_data=chart_profile,
            output_path=str(output_path),
            target_year=2026,
            progress_callback=progress
        )
        
        print("\n=== Auto E2E Run Complete ===")
        if result.months:
            print(f"Generated {len(result.months)} monthly reports.")
            
        print(f"Final artifact saved to {output_path}")
        
    except Exception as e:
        logger.error(f"Engine Run Failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(main())
