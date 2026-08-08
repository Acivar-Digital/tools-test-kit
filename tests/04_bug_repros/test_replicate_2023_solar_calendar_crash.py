from datetime import date

from src2.engine.daily_pillar import get_month_anchor_for_date
from src2.engine.solar_calendar import ANNUAL_PILLAR
from src2.interfaces.telegram.chronomancer.agents import compute_shen_sha_context, compute_structural_map


def test_get_month_anchor_for_date_handles_unsupported_years_gracefully():
    """Ensure dates in unsupported years (e.g. 2024, 2023) return None instead of raising NotImplementedError."""
    anchor = get_month_anchor_for_date(date(2024, 8, 6))
    assert anchor is None


def test_structural_map_skips_unsupported_dates_without_crashing():
    """Ensure compute_structural_map skips dates outside loaded solar calendar without raising uncaught exceptions."""
    sample_profile = {
        "year_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "day_pillar": {"stem": "Wu", "branch": "Shen"},
        "hour_pillar": {"stem": "Geng", "branch": "Wu"},
    }
    result = compute_structural_map(sample_profile, [date(2024, 8, 6)], ANNUAL_PILLAR)
    assert isinstance(result, str)


def test_shen_sha_context_skips_unsupported_dates_without_crashing():
    """Ensure compute_shen_sha_context skips dates outside loaded solar calendar without raising uncaught exceptions."""
    sample_profile = {
        "year_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "day_pillar": {"stem": "Wu", "branch": "Shen"},
        "hour_pillar": {"stem": "Geng", "branch": "Wu"},
    }
    result = compute_shen_sha_context(sample_profile, [date(2024, 8, 6)], ANNUAL_PILLAR, {})
    assert isinstance(result, str)
