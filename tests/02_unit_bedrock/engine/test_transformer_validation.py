import os

from src2.core.schemas.unified import ChartProfile, Pillar, UserProfile, ValidatedPillar
from src2.engine.transformer import to_chart_profile, to_user_profile

# Bypass Mem0 initialization error
os.environ["MEM0_MODEL"] = "dummy"

def test_to_user_profile_dict_input():
    """Test that to_user_profile correctly handles dict input without validation error."""
    raw_dict = {
        "profile_id": "test_id_123",
        "day_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "hour_pillar": {"stem": "Geng", "branch": "Wu"},
        "da_yun_pillar": {"stem": "Xin", "branch": "Wei"},
        "gender": "F",
        "alias": "Alice",
        "day_master_strength": "Strong",
        "favorable_elements": ["Wood", "Water"],
        "unfavorable_elements": ["Earth"],
        "neutral_elements": ["Metal"]
    }

    # Act
    profile = to_user_profile(raw_dict)

    # Assert
    assert isinstance(profile, UserProfile)
    assert profile.profile_id == "test_id_123"
    assert profile.alias == "Alice"
    assert profile.day_pillar.stem == "Jia"
    assert profile.day_pillar.branch == "Zi"
    assert profile.gender == "F"

def test_to_chart_profile_dict_input():
    """Test that to_chart_profile correctly handles dict input without validation error."""
    raw_dict = {
        "day_master": "Jia",
        "dm_element": "Wood",
        "day_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "hour_pillar": {"stem": "Geng", "branch": "Wu"},
        "da_yun_pillar": {"stem": "Xin", "branch": "Wei"},
        "favorable_elements": ["Wood", "Water"],
        "unfavorable_elements": ["Earth"],
        "gender": "F",
        "age": 30
    }

    # Act
    chart = to_chart_profile(raw_dict)

    # Assert
    assert isinstance(chart, ChartProfile)
    assert chart.day_master == "Jia"
    assert chart.dm_element == "Wood"
    assert chart.day_pillar.stem == "Jia"
    assert chart.day_pillar.branch == "Zi"
    assert chart.age == 30

def test_to_user_profile_object_input():
    """Test that to_user_profile correctly returns the object if already a UserProfile."""
    profile_obj = UserProfile(
        profile_id="obj_id",
        day_pillar=ValidatedPillar(stem="Jia", branch="Zi"),
        month_pillar=ValidatedPillar(stem="Bing", branch="Yin"),
        year_pillar=ValidatedPillar(stem="Wu", branch="Chen")
    )
    result = to_user_profile(profile_obj)
    assert result is profile_obj

def test_to_chart_profile_object_input():
    """Test that to_chart_profile correctly returns the object if already a ChartProfile."""
    chart_obj = ChartProfile(
        day_pillar=Pillar(stem="Jia", branch="Zi"),
        month_pillar=Pillar(stem="Bing", branch="Yin"),
        year_pillar=Pillar(stem="Wu", branch="Chen")
    )
    result = to_chart_profile(chart_obj)
    assert result is chart_obj

def test_to_user_profile_json_input():
    """Test that to_user_profile correctly handles JSON string input."""
    json_str = '{"profile_id": "json_id", "day_pillar": {"stem": "Jia", "branch": "Zi"}, "month_pillar": {"stem": "Bing", "branch": "Yin"}, "year_pillar": {"stem": "Wu", "branch": "Chen"}}'
    result = to_user_profile(json_str)
    assert isinstance(result, UserProfile)
    assert result.profile_id == "json_id"
    assert result.day_pillar.stem == "Jia"

def test_to_chart_profile_json_input():
    """Test that to_chart_profile correctly handles JSON string input."""
    json_str = '{"day_master": "Jia", "day_pillar": {"stem": "Jia", "branch": "Zi"}, "month_pillar": {"stem": "Bing", "branch": "Yin"}, "year_pillar": {"stem": "Wu", "branch": "Chen"}}'
    result = to_chart_profile(json_str)
    assert isinstance(result, ChartProfile)
    assert result.day_master == "Jia"
    assert result.day_pillar.stem == "Jia"


def test_to_chart_profile_matches_constructor():
    """Verify to_chart_profile(dict) and ChartProfile(...) produce identical instances."""
    data = {
        "user_id": "12345",
        "chat_id": "12345",
        "alias": "TestUser",
        "gender": "M",
        "day_master": "Jia",
        "dm_element": "Wood",
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "month_pillar": {"stem": "Ji", "branch": "Wei"},
        "day_pillar": {"stem": "Bing", "branch": "Yin"},
        "hour_pillar": {"stem": "Geng", "branch": "Wu"},
        "da_yun_pillar": {"stem": "Xin", "branch": "Wei"},
        "favorable_elements": ["Wood", "Water"],
        "unfavorable_elements": ["Earth"],
        "neutral_elements": ["Metal"],
        "dm_strength_type": "Strong",
    }
    routed = to_chart_profile(data)
    direct = ChartProfile(**data)
    assert routed == direct
    assert routed.user_id == direct.user_id
    assert routed.chat_id == direct.chat_id
    assert routed.alias == direct.alias
    assert routed.gender == direct.gender
    assert routed.day_master == direct.day_master
    assert routed.dm_element == direct.dm_element
    assert routed.year_pillar.stem == direct.year_pillar.stem
    assert routed.year_pillar.branch == direct.year_pillar.branch
    assert routed.month_pillar.stem == direct.month_pillar.stem
    assert routed.day_pillar.stem == direct.day_pillar.stem
    assert routed.hour_pillar.stem == direct.hour_pillar.stem
    assert routed.da_yun_pillar.stem == direct.da_yun_pillar.stem
    assert routed.favorable_elements == direct.favorable_elements
    assert routed.unfavorable_elements == direct.unfavorable_elements
    assert routed.neutral_elements == direct.neutral_elements
    assert routed.dm_strength_type == direct.dm_strength_type


def test_to_user_profile_matches_model_validate():
    """Verify to_user_profile(dict) and UserProfile.model_validate(dict) produce identical instances."""
    data = {
        "profile_id": "fixed_test_id",
        "gender": "M",
        "alias": "TestUser",
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "month_pillar": {"stem": "Ji", "branch": "Wei"},
        "day_pillar": {"stem": "Bing", "branch": "Yin"},
        "hour_pillar": {"stem": "Geng", "branch": "Wu"},
        "da_yun_pillar": {"stem": "Xin", "branch": "Wei"},
        "day_master_strength": "Strong",
        "favorable_elements": ["Wood", "Water"],
        "unfavorable_elements": ["Earth"],
        "neutral_elements": ["Metal"],
        "structure": "Other",
    }
    routed = to_user_profile(data)
    direct = UserProfile.model_validate(data)
    assert routed == direct
    assert routed.profile_id == direct.profile_id
    assert routed.gender == direct.gender
    assert routed.alias == direct.alias
    assert routed.year_pillar.stem == direct.year_pillar.stem
    assert routed.year_pillar.branch == direct.year_pillar.branch
    assert routed.month_pillar.stem == direct.month_pillar.stem
    assert routed.day_pillar.stem == direct.day_pillar.stem
    assert routed.hour_pillar.stem == direct.hour_pillar.stem
    assert routed.da_yun_pillar.stem == direct.da_yun_pillar.stem
    assert routed.day_master_strength == direct.day_master_strength
    assert routed.favorable_elements == direct.favorable_elements
    assert routed.unfavorable_elements == direct.unfavorable_elements
    assert routed.neutral_elements == direct.neutral_elements
    assert routed.structure == direct.structure
