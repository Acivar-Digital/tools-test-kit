import pytest
from unittest.mock import AsyncMock, patch
from src2.core.schemas.unified import ChartProfile, UserProfile, ValidatedPillar
from src2.interfaces.telegram.chronomancer.coordinator import session_to_chart_profile
from src2.interfaces.telegram.session import Session


def test_session_to_chart_profile():
    profile_data = UserProfile(
        alias="TestUser",
        gender="M",
        day_master_strength="Strong",
        year_pillar=ValidatedPillar(stem="Ding", branch="Si"),
        month_pillar=ValidatedPillar(stem="Yi", branch="Si"),
        day_pillar=ValidatedPillar(stem="Geng", branch="Chen"),
        favorable_elements=["Water"],
        unfavorable_elements=["Fire"],
        neutral_elements=["Earth"],
    )
    session = Session(chat_id=12345, profile=profile_data)
    cp = session_to_chart_profile(session)

    assert isinstance(cp, ChartProfile)
    assert cp.alias == "TestUser"
    assert cp.gender == "M"
    assert cp.day_master == "Geng"
    assert cp.year_pillar.stem == "Ding"
    assert cp.year_pillar.branch == "Si"
    assert cp.favorable_elements == ["Water"]
