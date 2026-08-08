import pytest
from src2.core.schemas.unified import ChartProfile, Pillar
from src2.interfaces.telegram.chronomancer.oracle_gatherer import (
    _gather_transits,
    format_transit_pillar,
)
from src2.interfaces.telegram.chronomancer.oracle_narrator import (
    ORACLE_NARRATOR_SYSTEM_PROMPT,
    get_oracle_narrator_agent,
    resolve_liu_nian,
)


def test_format_transit_pillar_grounding():
    # Yi Wood Day Master (乙)
    res_bing_wu = format_transit_pillar("乙", "丙", "午")
    assert "Stem 丙 Fire = Hurt Officer" in res_bing_wu or "Stem 丙 (Bing) Fire = Hurt Officer" in res_bing_wu
    assert "Branch 午 Fire = Eating God" in res_bing_wu or "Branch 午 (Wu) Fire = Eating God" in res_bing_wu

    res_ji_hai = format_transit_pillar("乙", "己", "亥")
    assert "Stem 己 Earth = Indirect Wealth" in res_ji_hai
    assert "Branch 亥 Water = Direct Resource" in res_ji_hai

    # Geng Metal Day Master (庚)
    res_geng_bing = format_transit_pillar("庚", "丙", "午")
    assert "Stem 丙 7 Killings" in res_geng_bing or "7 Killings" in res_geng_bing


def test_resolve_liu_nian_ten_god_grounding():
    profile = ChartProfile(
        day_master="乙",
        dm_element="Wood",
        gender="M",
        year_pillar=Pillar(stem="甲", branch="子"),
        month_pillar=Pillar(stem="丙", branch="寅"),
        day_pillar=Pillar(stem="乙", branch="巳"),
        hour_pillar=Pillar(stem="丁", branch="亥"),
        da_yun_pillar=Pillar(stem="己", branch="亥"),
    )

    transit_str = resolve_liu_nian(profile, 2026)
    assert "Year 2026 Transit (DM: 乙)" in transit_str
    assert "Hurt Officer" in transit_str
    assert "Eating God" in transit_str
    assert "Indirect Wealth" in transit_str
    assert "Direct Resource" in transit_str


@pytest.mark.asyncio
async def test_gather_transits_grounding():
    profile = ChartProfile(
        day_master="乙",
        dm_element="Wood",
        gender="M",
        year_pillar=Pillar(stem="甲", branch="子"),
        month_pillar=Pillar(stem="丙", branch="寅"),
        day_pillar=Pillar(stem="乙", branch="巳"),
        hour_pillar=Pillar(stem="丁", branch="亥"),
        da_yun_pillar=Pillar(stem="己", branch="亥"),
    )

    transits = await _gather_transits(profile, [2026])
    assert 2026 in transits
    text = transits[2026]
    assert "Year 2026 Transit (DM: 乙)" in text
    assert "Hurt Officer" in text
    assert "Eating God" in text


def test_oracle_system_prompt_mandates():
    assert "TEN GOD & FIVE ELEMENT GROUNDING MANDATE:" in ORACLE_NARRATOR_SYSTEM_PROMPT
    assert "Fire (丙/丁/巳/午) is ALWAYS Output (食神/伤官)" in ORACLE_NARRATOR_SYSTEM_PROMPT
    assert "Water (壬/癸/亥/子) is ALWAYS Resource (印)" in ORACLE_NARRATOR_SYSTEM_PROMPT
    assert "INLINE CITATION & CLASSICAL SOURCES MANDATE:" in ORACLE_NARRATOR_SYSTEM_PROMPT
    assert "ANTI-FLUFF & CONCISE STRATEGIC TONE MANDATE:" in ORACLE_NARRATOR_SYSTEM_PROMPT


def test_oracle_narrator_tool_registered():
    agent = get_oracle_narrator_agent()
    tool_names = [t.name for t in agent._function_toolset.tools.values()]
    assert "get_ten_god_and_element" in tool_names
