"""
Unit tests for Module 9: Trigger Detection (module9_triggers.py) - V31 Pydantic V2
"""

import pytest

from src2.core.schemas.unified import (
    ChartProfile,
    KVList,
    KVPair,
    MacroAnnualData,
    MacroDecadeData,
    MacroEraBlock,
    MacroOutput,
    MacroSeasonalInfluence,
    MacroVoidAudit,
    Pillar,
    PillarMap,
    QiInteraction,
    UnifiedInteractionOutput,
)
from src2.engine.module9_triggers import (
    calculate_trigger_potency,
    detect_clash_triggers,
    detect_da_yun_triggers,
    detect_special_star_triggers,
    run_trigger_detection_adapter,
)


@pytest.fixture
def sample_stems():
    return PillarMap(
        year="Jia",
        month="Yi",
        day="Bing",
        hour="Ding",
        transit_decade="Wu",
    )


@pytest.fixture
def sample_branches():
    return PillarMap(
        year="Zi",
        month="Chou",
        day="Yin",
        hour="Mao",
        transit_decade="Chen",
    )


@pytest.fixture
def sample_profile():
    return ChartProfile(
        language="English",
        day_master="Bing",
        dm_element="Fire",
        year_pillar=Pillar(stem="Jia", branch="Zi"),
        month_pillar=Pillar(stem="Yi", branch="Chou"),
        day_pillar=Pillar(stem="Bing", branch="Yin"),
        hour_pillar=Pillar(stem="Ding", branch="Mao"),
        da_yun_pillar=Pillar(stem="Wu", branch="Chen"),
    )


@pytest.fixture
def sample_macro():
    return MacroOutput(
        void_audit=MacroVoidAudit(is_void_active=False, impact_score=0, cured_status=False),
        seasonal_influence=MacroSeasonalInfluence(
            decade_data=MacroDecadeData(
                stem_impact=1,
                branch_impact=1,
                phase=1,
                climate_label="Spring",
            ),
            annual_data=MacroAnnualData(
                tai_sui_impact=1,
                stem_impact=1,
                context_label="Annual",
            ),
            era_block=MacroEraBlock(
                era_element="Fire",
                era_label="Period 9",
                era_ceiling=9,
                era_medicine_ratio=1.0,
            ),
            annual_effect_multiplier=1.0,
            TaiSui_trigger_multiplier=1.0,
            Luck_Harmony_multiplier=1.0,
            Seasonal_multiplier=1.0,
            total_macro_modifier=0,
        ),
    )


class TestDetectClashTriggers:
    """Test clash trigger detection."""

    def test_no_clashes(self):
        result = detect_clash_triggers([])
        assert all(kv.value == "" for kv in result.items)

    def test_day_pillar_clash_high_friction(self):
        interaction = QiInteraction(
            vector="Chong",
            plane="Branch",
            is_successful=True,
            pillars=["Day"],
            impact=KVList[float](items=[KVPair[float](key="friction", value=20.0)]),
        )
        result = detect_clash_triggers([interaction])
        day_kv = next(kv for kv in result.items if kv.key == "Day")
        assert "Day pillar clash (Chong)" in day_kv.value


class TestDetectSpecialStarTriggers:
    """Test special star trigger detection."""

    def test_yang_ren_activation(self, sample_stems, sample_branches):
        # For Bing day stem, Yang Ren branch is Wu
        result = detect_special_star_triggers(sample_stems, sample_branches, "Wu", "Wu")
        assert "Yang Ren" in result

    def test_peach_blossom_activation(self, sample_stems, sample_branches):
        # Year Zi -> Peach Blossom is You
        result = detect_special_star_triggers(sample_stems, sample_branches, "Geng", "You")
        assert "Peach Blossom" in result


class TestDetectDaYunTriggers:
    """Test Da Yun triggers."""

    def test_da_yun_chong(self, sample_stems):
        # Day branch Yin -> Chong is Shen
        branches = PillarMap(
            year="Zi",
            month="Chou",
            day="Yin",
            hour="Mao",
            transit_decade="Shen",
        )
        result = detect_da_yun_triggers(sample_stems, branches)
        assert "Da Yun Chong Day" in result


class TestCalculateTriggerPotency:
    """Test trigger potency calculation levels."""

    def test_critical_level(self):
        pot = calculate_trigger_potency(10.0, 1.5, 1.2)
        assert pot.level == "critical"
        assert pot.potency == 18.0

    def test_low_level(self):
        pot = calculate_trigger_potency(2.0, 1.0, 1.0)
        assert pot.level == "low"


class TestRunTriggerDetectionAdapter:
    """Test full adapter integration."""

    def test_adapter_run(self, sample_profile, sample_macro):
        interactions = UnifiedInteractionOutput(
            all_interactions=[],
            total_friction=0.0,
        )
        res = run_trigger_detection_adapter(sample_profile, interactions, sample_macro, None, None, [])
        assert res.void_active is False
        assert isinstance(res.star_triggers, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
