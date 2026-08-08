import pytest

from src.engine.orchestrator import run_full_engine


@pytest.fixture
def sample_profile():
    return {
        "year_pillar": "Ding Si",
        "month_pillar": "Yi Si",
        "day_pillar": "Jia Chen",  # Jia Chen stream, void is Yin, Mao
        "hour_pillar": "Ding Chou",
        "da_yun_pillar": "Geng Zi",
        "day_master_strength": "Weak",
        "dm_strength_type": "Weak",
        "favorable_elements": ["Metal", "Water"],
        "unfavorable_elements": ["Fire"],
        "neutral_elements": ["Earth", "Wood"],
        "medicine": ["Metal", "Water"],
        "taboo": ["Fire"],
        "day_stem_stream": "Jia Chen",  # Matches Jia Chen day
    }


def test_case_3_1_daily_forecast(sample_profile):
    """Test Case 3.1: Daily forecast generation (Engine check)"""
    # Check if engine runs for a specific month
    result = run_full_engine(sample_profile, target_month_idx=1)  # Mar 2026 (Xin Mao)
    assert "engine_outputs" in result
    assert "module_8" in result["engine_outputs"]
    assert "total_structural_score" in result["engine_outputs"]["module_8"]


def test_case_3_3_score_consistency(sample_profile):
    """Test Case 3.3: Score consistency across months"""
    # Run for two different months and compare
    res1 = run_full_engine(sample_profile.copy(), target_month_idx=1)
    res2 = run_full_engine(sample_profile.copy(), target_month_idx=2)

    score1 = res1["engine_outputs"]["module_8"]["total_structural_score"]
    score2 = res2["engine_outputs"]["module_8"]["total_structural_score"]

    # Scores should exist and be numbers
    assert isinstance(score1, (int, float))
    assert isinstance(score2, (int, float))

    # Scores should be in range 35-80
    assert 35 <= score1 <= 80
    assert 35 <= score2 <= 80


def test_case_3_4_void_period_detection(sample_profile):
    """Test Case 3.4: Void period detection"""
    # Jia Chen Day Pillar, void is Yin, Mao
    res1 = run_full_engine(sample_profile, target_month_idx=0)  # Feb (Yin)
    void_audit = res1["engine_outputs"]["module_1"]["macro_environmental_scan"]["void_audit"]
    # If the month is detected as void, it will be either active OR cured.
    assert void_audit["is_void_active"] is True or void_audit["cured_status"] is True
