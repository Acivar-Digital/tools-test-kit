import datetime
import os

from src2.core.schemas import DailyActivities, DailyForecastRecord
from src2.engine.chart_generator import generate_7day_chart, generate_sparklines_summary
from src2.interfaces.telegram.chronomancer.forecast_store import get_or_create_7day_chart


def _build_mock_records(count: int = 7) -> list[DailyForecastRecord]:
    today = datetime.date.today()
    records = []
    for i in range(count):
        d = today + datetime.timedelta(days=i)
        r = DailyForecastRecord(
            user_id=999998,
            profile_hash="test_hash_123",
            date=d,
            stem="甲",
            branch="子",
            activities=DailyActivities.model_validate({
                "job_interview": {"score": 10 + i, "reason": "Good", "verdict": "Good"},
                "speculation": {"score": 5 - i, "reason": "Neutral", "verdict": "Neutral"},
                "love": {"score": 8, "reason": "Favorable", "verdict": "Favorable"},
                "study": {"score": 4, "reason": "Neutral", "verdict": "Neutral"},
            }),
            events=["clash"] if i == 2 else [],
        )
        records.append(r)
    return records


def test_generate_7day_chart(tmp_path):
    output_png = os.path.join(tmp_path, "chart_test.png")
    records = _build_mock_records(7)

    res_path = generate_7day_chart(records, output_png)
    assert res_path == output_png
    assert os.path.exists(output_png)
    assert os.path.getsize(output_png) > 1000  # Non-empty image file


def test_generate_sparklines_summary():
    records = _build_mock_records(7)
    text = generate_sparklines_summary(records)

    assert "📊 *1-Week Bazi Energy Breakdown*" in text
    assert "⚠️ Clash" in text  # Record index 2 has clash event


def test_get_or_create_7day_chart_caching(tmp_path, monkeypatch):
    mock_profile = {
        "year_pillar": {"stem": "甲", "branch": "辰"},
        "month_pillar": {"stem": "丙", "branch": "寅"},
        "day_pillar": {"stem": "戊", "branch": "午"},
        "hour_pillar": {"stem": "壬", "branch": "戌"},
    }

    orig_abspath = os.path.abspath
    monkeypatch.setattr("os.path.abspath", lambda p: str(tmp_path) if "scratch" in p else orig_abspath(p))

    chart_path, text = get_or_create_7day_chart(999998, mock_profile, language="English")
    assert os.path.exists(chart_path)
    assert "📊 *1-Week Bazi Energy Breakdown*" in text

    # Verify second call hits cache (modtime stays same)
    mtime_initial = os.path.getmtime(chart_path)
    chart_path_2, text_2 = get_or_create_7day_chart(999998, mock_profile, language="English")
    assert chart_path_2 == chart_path
    assert os.path.getmtime(chart_path_2) == mtime_initial
