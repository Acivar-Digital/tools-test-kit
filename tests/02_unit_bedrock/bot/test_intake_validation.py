import os
from unittest.mock import patch

import pytest

from src2.interfaces.telegram.intake.calendar_node import _run_input_engine
from src2.interfaces.telegram.session import Session, SessionMetadata

# Bypass Mem0 initialization error
os.environ["MEM0_MODEL"] = "dummy"

@pytest.mark.asyncio
async def test_run_input_engine_dict_validation():
    """
    Test that _run_input_engine correctly handles dictionary inputs and passes them 
    to to_user_profile without raising Pydantic validation errors (json vs dict).
    """
    intake_data = {
        "year_pillar": "Jia Zi",
        "month_pillar": "Bing Yin",
        "day_pillar": "Wu Chen",
        "hour_pillar": "Geng Wu",
        "da_yun_pillar": "Xin Wei",
        "gender": "M",
        "alias": "Test Manual User",
        "day_master_strength": "Strong",
        "favorable_elements": ["Wood", "Fire"],
        "unfavorable_elements": ["Metal"],
        "neutral_elements": ["Water"]
    }

    session = Session(
        chat_id=123456789,
        metadata=SessionMetadata(intake=intake_data)
    )

    with patch("src2.interfaces.telegram.bridge.db.get_semantic_id") as mock_get_semantic_id, \
         patch("src2.engine.module0_geju.classify_ge_ju") as mock_classify_ge_ju:
        mock_get_semantic_id.return_value = "mock_semantic_id"
        mock_ge_ju_res = {
            "ge_ju": {
                "name": "Direct Wealth",
                "name_en": "Direct Wealth",
                "description": "Direct Wealth Pattern",
                "type": "Common",
                "tier": "Common",
                "bonus": 0,
                "structural_friends": [],
                "structural_enemies": [],
                    "core_elements": ["Earth"],
                    "favorable_elements": ["Earth"],
                    "unfavorable_elements": [],
                    "strength_bias": "Neutral",
            },
            "pattern_name": "Direct Wealth",
            "bonus": 0.0,
            "pattern_key": "direct_wealth",
        }
        mock_classify_ge_ju.return_value = mock_ge_ju_res

        # Act
        updated_session = await _run_input_engine(session)

        # Assert
        assert updated_session.profile is not None
        assert updated_session.profile.profile_id == "mock_semantic_id"
        assert updated_session.profile.alias == "Test Manual User"
        assert updated_session.profile.gender == "M"

        # Check that pillars were correctly parsed into Pillar schemas
        assert updated_session.profile.year_pillar.stem == "Jia"
        assert updated_session.profile.year_pillar.branch == "Zi"
        assert updated_session.profile.day_pillar.stem == "Wu"
        assert updated_session.profile.day_pillar.branch == "Chen"

        # Elements
        assert "Wood" in updated_session.profile.favorable_elements
        assert "Metal" in updated_session.profile.unfavorable_elements
