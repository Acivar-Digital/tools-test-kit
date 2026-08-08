import os
import sys

import pytest
from pydantic import ValidationError

# Workaround for hyphenated folder import path in Python
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "_docs", "REVIEW", "pydantic-ai", "03_Craft_Future_Proof_Template")))

from poc_intake_flow import IntakeExtraction, run_pydantic_intake

# =====================================================================
# 1. Pydantic AI Schema Unit Tests (Validation Integrity)
# =====================================================================

def test_intake_extraction_schema_validation():
    # Valid output structure must pass
    valid_data = IntakeExtraction(
        extracted_fields={"alias": "TEST", "gender": "M"},
        next_question="What is your location of birth?",
        all_collected=False
    )
    assert valid_data.all_collected is False
    assert valid_data.extracted_fields["alias"] == "TEST"

    # Missing next_question field must raise ValidationError (unless all_collected is true/nullable)
    with pytest.raises(ValidationError):
        IntakeExtraction(
            extracted_fields={"alias": "TEST"},
            all_collected=False
            # next_question omitted
        )


# =====================================================================
# 2. Conversational Intake Flow Tests (Auto & Manual Scenarios)
# =====================================================================

@pytest.mark.asyncio
async def test_run_pydantic_intake_auto_mode():
    # Initial empty metadata structure
    session_metadata = {
        "intake_mode": "auto",
        "collected": {}
    }

    # 1. User volunteers name
    res1 = await run_pydantic_intake(session_metadata, "My name is TEST and I am a Male.")
    assert res1["all_collected"] is False
    assert "alias" in res1["metadata"]["collected"]
    assert "gender" in res1["metadata"]["collected"]
    assert res1["reply"] is not None  # Agent conversationally asks for remaining fields (DOB/Location)

    # 2. User provides DOB and Location
    res2 = await run_pydantic_intake(
        res1["metadata"],
        "I was born on June 15th, 1988 at 14:30 in Singapore."
    )

    # Verification: All required auto fields (alias, gender, dob, location) should now be present
    collected = res2["metadata"]["collected"]
    assert "dob" in collected
    assert "location" in collected

    # Assert Chronomancer_Report_Finished_Collection_Rule is triggered
    assert res2["all_collected"] is True
    assert res2["reply"] == "We will notify you here once the report is ready for your viewing. That's all."


# =====================================================================
# 3. User Rubbish / Garbage Inputs (Rigorous Test Coverage)
# =====================================================================

@pytest.mark.asyncio
async def test_user_rubbish_input_handling():
    # Start intake session
    session_metadata = {
        "intake_mode": "auto",
        "collected": {"alias": "TEST", "gender": "M"}
    }

    # User responds with absolute gibberish
    res = await run_pydantic_intake(session_metadata, "blah blah raw chicken nuggets go zoom!")

    # Verify:
    # 1. No new parameter is extracted (still has only alias and gender)
    assert len(res["metadata"]["collected"]) == 2
    assert "alias" in res["metadata"]["collected"]

    # 2. The agent does not crash and continues prompt loops for missing fields
    assert res["all_collected"] is False
    assert res["reply"] is not None
    assert len(res["reply"].strip()) > 0
