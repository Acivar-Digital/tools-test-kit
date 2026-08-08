import pytest
import json
from src2.core.schemas.unified import UserProfile, ChartProfile
from src2.interfaces.telegram.bridge import map_profile_to_k3

def test_replicate_chartprofile_crash():
    """
    Validates that map_profile_to_k3 returns objects that can be parsed
    by ChartProfile.model_validate_json without throwing a ValidationError.
    """
    profile = UserProfile.model_validate({
        "alias": "Tester",
        "gender": "M",
        "year_pillar": {"stem": "Ding", "branch": "Si"},
        "month_pillar": {"stem": "Jia", "branch": "Chen"},
        "day_pillar": {"stem": "Yi", "branch": "Mao"},
        "hour_pillar": {"stem": "Ren", "branch": "Wu"},
        "da_yun_pillar": {"stem": "Ji", "branch": "Hai"},
        "day_master_strength": "Strong",
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Water", "Wood"],
        "neutral_elements": ["Metal"]
    })
    
    k3_data = map_profile_to_k3(profile, chat_id=999000001)
    json_str = json.dumps(k3_data)
    
    try:
        chart_profile = ChartProfile.model_validate_json(json_str)
    except Exception as e:
        pytest.fail(f"ChartProfile validation failed: {e}")
        
    assert chart_profile.year_pillar.stem == "Ding"
    assert chart_profile.year_pillar.branch == "Si"
    assert chart_profile.strength_profile is not None
    assert chart_profile.strength_profile.spectrum_tier == "Strong"
