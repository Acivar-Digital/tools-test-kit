import json
import os
from datetime import date

import pytest

from src2.core.schemas.unified import ChartProfile, DailyActivities, Pillar, RankedDay, UserProfile, ValidatedPillar
from src2.engine.activity_oracle import score_day
from src2.interfaces.telegram.chronomancer.agents import (
    MonthlyReportMonthItem,
    _extract_month_from_master,
    _get_composite_score,
)
from src2.interfaces.telegram.chronomancer.coordinator import _format_forecast_output, session_to_chart_profile
from src2.interfaces.telegram.session import Session


def test_monthly_report_month_item_str_advisory():
    data = {
        "month_name": "Geng Yin",
        "month_metadata": {"start_date": "2026-02-04T00:00:00+08:00", "month_name": "Geng Yin"},
        "advisory": "This is a direct string advisory for testing.",
    }
    item = MonthlyReportMonthItem.model_validate(data)
    assert item.advisory == "This is a direct string advisory for testing."
    assert item.get_effective_narrative() == "This is a direct string advisory for testing."


def test_monthly_report_month_item_dict_advisory():
    data = {
        "month_name": "Geng Yin",
        "month_metadata": {"start_date": "2026-02-04T00:00:00+08:00", "month_name": "Geng Yin"},
        "advisory": {
            "career": "Career advice for Geng Yin.",
            "wealth": "Wealth advice for Geng Yin.",
        },
    }
    item = MonthlyReportMonthItem.model_validate(data)
    assert isinstance(item.advisory, dict)
    narrative = item.get_effective_narrative()
    assert "Career:\nCareer advice for Geng Yin." in narrative
    assert "Wealth:\nWealth advice for Geng Yin." in narrative


def test_monthly_report_month_item_nested_dict_and_list_advisory():
    data = {
        "month_name": "Xin Mao",
        "month_metadata": {"start_date": "2026-03-05T00:00:00+08:00", "month_name": "Xin Mao"},
        "advisory": {
            "career": {"summary": "Nested career overview.", "bullet_points": ["Focus on delivery", "Mitigate risk"]},
            "wealth": ["Consolidate assets", "Avoid speculative trades"],
        },
    }
    item = MonthlyReportMonthItem.model_validate(data)
    narrative = item.get_effective_narrative()
    assert "Career:\nSummary:\nNested career overview." in narrative
    assert "- Focus on delivery" in narrative
    assert "Wealth:\n- Consolidate assets" in narrative


def test_monthly_report_in_memory_master_fixture():
    master_fixture = {
        "months": [
            {
                "month_name": "Geng Yin",
                "month_metadata": {"start_date": "2026-02-04T00:00:00+08:00", "month_name": "Geng Yin"},
                "advisory": {"career": "Fixture career guidance.", "wealth": "Fixture wealth guidance."},
            }
        ]
    }
    month_item = _extract_month_from_master(master_fixture, "2026-02-15")
    assert month_item is not None
    assert month_item.get_effective_month_name() == "Geng Yin"
    narrative = month_item.get_effective_narrative()
    assert "Career:\nFixture career guidance." in narrative


def test_monthly_report_real_master_file_parsing():
    master_path = "_prd/users/SGUSD0000015/reports/2/BaziForecast_2026_FY_owns_20260724_2_master.json"
    if not os.path.exists(master_path):
        pytest.skip("Master JSON file not present in environment")

    with open(master_path, encoding="utf-8") as f:
        master = json.load(f)

    month_item = _extract_month_from_master(master, "2026-03-01")
    assert month_item is not None
    assert month_item.get_effective_month_name() == "Geng Yin"
    narrative = month_item.get_effective_narrative()
    assert len(narrative) > 500
    assert "Career" in narrative


def test_session_to_chart_profile_and_score_day_integration():
    user_prof = UserProfile(
        profile_id="test_user_1",
        alias="TestUser",
        gender="M",
        year_pillar=ValidatedPillar(stem="Bing", branch="Wu"),
        month_pillar=ValidatedPillar(stem="Geng", branch="Yin"),
        day_pillar=ValidatedPillar(stem="Yi", branch="Si"),
        hour_pillar=ValidatedPillar(stem="Ding", branch="Hai"),
        da_yun_pillar=ValidatedPillar(stem="Xin", branch="Mao"),
        day_master_strength="Weak",
    )
    session = Session(chat_id=123456, profile=user_prof)
    chart_profile = session_to_chart_profile(session)

    assert isinstance(chart_profile, ChartProfile)
    assert chart_profile.alias == "TestUser"
    assert chart_profile.day_master == "Yi"

    day_pillar = Pillar(stem="Jia", branch="Zi")
    month_pillar = Pillar(stem="Geng", branch="Yin")
    year_pillar = Pillar(stem="Bing", branch="Wu")

    # score_day accepts ChartProfile and creates EngineContext without ValidationError
    scored = score_day(day_pillar, chart_profile, month_pillar, year_pillar)
    assert scored is not None
    assert scored.activities is not None


def test_get_composite_score_computes_from_individual_activities():
    from src2.core.schemas.unified import ActivityScore

    acts = DailyActivities(
        job_interview=ActivityScore(score=10, reason="", verdict="Fair"),
        love=ActivityScore(score=15, reason="", verdict="Good"),
        speculation=ActivityScore(score=5, reason="", verdict="Challenging"),
        study=ActivityScore(score=8, reason="", verdict="Fair"),
    )

    class FakeResult:
        activities = acts

    score = _get_composite_score(FakeResult())
    assert score == 10  # (10 + 15 + 5 + 8) / 4 = 9.5 → round to 10


def test_get_composite_score_returns_zero_when_no_activities():
    class FakeResult:
        activities = None

    assert _get_composite_score(FakeResult()) == 0


def test_get_composite_score_returns_zero_when_empty():
    acts = DailyActivities()

    class FakeResult:
        activities = acts

    assert _get_composite_score(FakeResult()) == 0


def test_format_forecast_output_uses_pydantic_attributes():
    from src2.core.schemas.unified import ActivityScore

    acts = DailyActivities(
        job_interview=ActivityScore(score=12, reason="", verdict="Good"),
        love=ActivityScore(score=8, reason="", verdict="Fair"),
        speculation=ActivityScore(score=15, reason="", verdict="Excellent"),
        study=ActivityScore(score=6, reason="", verdict="Challenging"),
    )

    class FakeDayResult:
        date = date(2026, 8, 1)
        activities = acts
        stem = "甲"
        branch = "子"
        events = []
        hourly_scores = {}

    output = _format_forecast_output(5, [FakeDayResult()])
    assert "Overall" in output
    assert "Aug 01" in output
    assert "Score:" in output or "Opportunity" in output or "Caution" in output


def test_format_forecast_output_sorts_by_composite_score():
    from src2.core.schemas.unified import ActivityScore

    acts_high = DailyActivities(
        job_interview=ActivityScore(score=18, reason="", verdict="Excellent"),
        love=ActivityScore(score=16, reason="", verdict="Excellent"),
        speculation=ActivityScore(score=14, reason="", verdict="Good"),
        study=ActivityScore(score=12, reason="", verdict="Good"),
    )
    acts_low = DailyActivities(
        job_interview=ActivityScore(score=2, reason="", verdict="Challenging"),
        love=ActivityScore(score=1, reason="", verdict="Challenging"),
        speculation=ActivityScore(score=3, reason="", verdict="Challenging"),
        study=ActivityScore(score=2, reason="", verdict="Challenging"),
    )

    class FakeDayResult:
        def __init__(self, d, a):
            self.date = d
            self.activities = a
            self.stem = "甲"
            self.branch = "子"
            self.events = []
            self.hourly_scores = {}

    high = FakeDayResult(date(2026, 8, 1), acts_high)
    low = FakeDayResult(date(2026, 8, 2), acts_low)

    output = _format_forecast_output(5, [low, high])
    lines = [line for line in output.strip().split("\n") if line.strip()]
    high_line = next(line for line in lines if "Aug 01" in line)
    low_line = next(line for line in lines if "Aug 02" in line)
    assert lines.index(high_line) < lines.index(low_line)


def test_format_category_forecast():
    from src2.interfaces.telegram.chronomancer.coordinator import _format_category_forecast

    ranked = [
        RankedDay(date="2026-08-01", score=18, verdict="Excellent", reason="Strong career alignment", stem="甲", branch="子"),
        RankedDay(date="2026-08-02", score=12, verdict="Stable", reason="Moderate career support", stem="乙", branch="丑"),
        RankedDay(date="2026-08-03", score=5, verdict="Mild Caution", reason="Career headwinds", stem="丙", branch="寅"),
    ]
    worst_ranked = [
        RankedDay(date="2026-08-15", score=2, verdict="Caution", reason="Career risk", stem="丁", branch="卯"),
    ]
    output = _format_category_forecast(ranked, worst_ranked, "career", date(2026, 8, 1), date(2026, 8, 30))
    assert "career" in output.lower()
    assert "Top 3" in output
    assert "Worst 3" in output
    assert "Best Opportunity" in output
    assert "Balanced / Neutral" in output
    assert "Mild Caution" in output
    assert "Proceed with Caution" in output
    assert "Use /ask to view details" in output
    assert "Next 30 days only" in output
    assert "Aug 01" in output
    assert "Aug 15" in output
