"""
Unit tests for Axiom 8.2.2 (Dynamic Proximity) and Axiom 11.3.2 (Severe Clash Overrides) in src2.
"""

from unittest.mock import MagicMock

from src2.engine.contradiction_resolver import resolve_contradictions
from src2.engine.module6_ten_gods import get_cycle_proximity


def test_get_cycle_proximity():
    # Peer is adjacent to Peer, Output, and Resource
    assert get_cycle_proximity("Peer", "Peer") == 1.0
    assert get_cycle_proximity("Peer", "Output") == 1.0
    assert get_cycle_proximity("Peer", "Resource") == 1.0

    # Peer is separated by 1 step from Wealth and Influence
    assert get_cycle_proximity("Peer", "Wealth") == 0.8
    assert get_cycle_proximity("Peer", "Influence") == 0.8

    # Invalid categories default to 0.5
    assert get_cycle_proximity("Peer", "Invalid") == 0.5


def test_severe_clash_override_contradiction():
    profile = MagicMock(
        year_pillar=MagicMock(stem="Jia", branch="Zi"),
        month_pillar=MagicMock(stem="Ji", branch="Chou"),
        day_pillar=MagicMock(stem="Jia", branch="Zi"),
        hour_pillar=MagicMock(stem="Yi", branch="Mao"),
        strength_profile={"classification": "Neutral", "continuous_score": 5.0, "spectrum_tier": "Mild Weak"},
        age=30,
        dm_strength_type=None,
    )

    disruptor = MagicMock(type="Chong", branches=["Zi", "Wu"], severity=16.0)
    combo = MagicMock(type="Liu He", branches=["Zi", "Chou"], element="Earth")

    interactions = MagicMock(
        active_disruptors=[disruptor],
        beneficial_combinations=[combo],
        active_alliances=[combo],
    )

    engine_results = MagicMock(
        interactions=interactions,
        ge_ju={"name_en": "Direct Wealth", "tier": "Common"},
        strength_profile={"classification": "Neutral", "continuous_score": 5.0},
        engine_outputs=None,
        causal_results=[],
        oracle_results=[],
    )

    result = resolve_contradictions(profile, engine_results)

    assert len(interactions.beneficial_combinations) == 0
    assert len(interactions.active_alliances) == 0
    assert len(result.override_trace) > 0
