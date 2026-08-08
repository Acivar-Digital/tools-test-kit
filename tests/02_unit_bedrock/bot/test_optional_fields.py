import pytest
from pydantic import ValidationError

from src.bot.bridge import validate_profile
from src.bot.session import UserProfile


def test_validate_profile_three_pillar():
    """Verify that a 3-pillar profile (missing hour_pillar) is valid."""
    profile = UserProfile(
        year_pillar={"stem": "Jia", "branch": "Zi"},
        month_pillar={"stem": "Yi", "branch": "Chou"},
        day_pillar={"stem": "Bing", "branch": "Yin"},
        hour_pillar=None,  # Optional!
        da_yun_pillar={"stem": "Wu", "branch": "Chen"},
        day_master_strength="Strong",
        favorable_elements=["Fire", "Earth"],
        unfavorable_elements=["Water"],
        neutral_elements=[],  # Optional!
        gender="M",
        alias="ThreePillarTest",
    )
    ok, errors = validate_profile(profile)
    assert ok, f"Expected 3-pillar profile to be valid, but got errors: {errors}"


def test_validate_profile_missing_required():
    """Verify that missing a required pillar (e.g. day_pillar) fails validation."""
    with pytest.raises(ValidationError):
        UserProfile(
            year_pillar={"stem": "Jia", "branch": "Zi"},
            month_pillar={"stem": "Yi", "branch": "Chou"},
            day_pillar=None,  # Required!
            hour_pillar={"stem": "Ding", "branch": "Mao"},
            da_yun_pillar={"stem": "Wu", "branch": "Chen"},
            day_master_strength="Strong",
            favorable_elements=["Fire"],
            unfavorable_elements=["Water"],
            gender="M",
            alias="MissingDayTest",
        )
