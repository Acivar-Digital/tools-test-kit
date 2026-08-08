"""
Unit tests for Module 7 (Shen Sha) star activation classification.
"""

from unittest.mock import patch

from src.engine.module7_shen_sha import STAR_NAME_MAP, classify_star_activation
from src.engine.shen_sha_data import SHEN_SHA_TABLE
from src.engine.stars import detect_stars


@patch("src.engine.module7_shen_sha.detect_stars")
def test_triggered_annual(mock_detect):
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "annual", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "triggered"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_triggered_da_yun(mock_detect):
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "da_yun", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "triggered"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_triggered_current_month(mock_detect):
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "current_month", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "triggered"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_suppressed_state(mock_detect):
    # If branch is in m3_clashed_branches, it should be suppressed even if in a triggered pillar
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "annual", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, ["Chou"])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "suppressed"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_latent_state(mock_detect):
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "day", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "latent"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_valence_tian_yi(mock_detect):
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "day", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["valence"] == "auspicious"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_valence_jie_sha(mock_detect):
    mock_detect.return_value = [{"star": "Jie Sha", "pillar": "day", "branch": "Si"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Jie Sha"]["valence"] == "inauspicious"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_valence_yi_ma(mock_detect):
    mock_detect.return_value = [{"star": "Yi Ma", "pillar": "day", "branch": "Yin"}]
    res = classify_star_activation({}, {}, {}, [])
    assert res["activation_matrix"]["Yi Ma"]["valence"] == "dual"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_empty_clash_list(mock_detect):
    mock_detect.return_value = [
        {"star": "Tian Yi", "pillar": "day", "branch": "Chou"},
        {"star": "Yi Ma", "pillar": "annual", "branch": "Yin"}
    ]
    res = classify_star_activation({}, {}, {}, [])
    for star in res["activation_matrix"].values():
        assert star["state"] != "suppressed"

@patch("src.engine.module7_shen_sha.detect_stars")
def test_full_clash_and_metadata(mock_detect):
    mock_detect.return_value = [
        {"star": "Tian Yi", "pillar": "day", "branch": "Chou"},
        {"star": "Yi Ma", "pillar": "annual", "branch": "Yin"}
    ]
    # Clash both branches
    res = classify_star_activation({}, {}, {}, ["Chou", "Yin"])

    # Check suppression
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "suppressed"
    assert res["activation_matrix"]["Yi Ma"]["state"] == "suppressed"

    # Check metadata
    assert "activation_matrix" in res
    assert "status" in res
    assert res["status"] == "implemented"


@patch("src.engine.module7_shen_sha.detect_stars")
def test_unknown_star_name(mock_detect, caplog):
    # Mock unknown star name
    mock_detect.return_value = [{"star": "UnknownStar", "pillar": "day", "branch": "Zi"}]
    res = classify_star_activation({}, {}, {}, [])

    # Assert no exception and it exists in matrix with default values
    assert "UnknownStar" in res["activation_matrix"]
    assert res["activation_matrix"]["UnknownStar"]["valence"] == "auspicious"

    # Assert warning was logged
    assert "not found in SHEN_SHA_TABLE" in caplog.text


def test_name_mapping_completeness():
    # 1. Representative natal chart that triggers multiple stars
    # Jia Day Master + Chou/Mao/Zi/Shen covers Tian Yi, Yang Ren, Yi Ma, Hua Gai, etc.
    natal_chart = {
        "year_pillar": {"stem": "Geng", "branch": "Shen"},
        "month_pillar": {"stem": "Ding", "branch": "Chou"},
        "day_pillar": {"stem": "Jia", "branch": "Zi"},
        "hour_pillar": {"stem": "Yi", "branch": "Mao"},
    }

    # 2. Get actual stars produced by engine
    stars = detect_stars(natal_chart)
    assert len(stars) > 0, "Test chart should trigger at least one star"

    # 3. Assert every returned star name is either in STAR_NAME_MAP or directly in SHEN_SHA_TABLE
    for s in stars:
        name = s["star"]
        lookup = STAR_NAME_MAP.get(name, name)
        assert lookup in SHEN_SHA_TABLE, f"Star '{name}' (lookup '{lookup}') missing from SHEN_SHA_TABLE"


@patch("src.engine.module7_shen_sha.detect_stars")
def test_suppressed_overrides_triggered(mock_detect):
    # star in annual pillar (would be triggered) AND branch is clashed.
    mock_detect.return_value = [{"star": "Tian Yi", "pillar": "annual", "branch": "Chou"}]
    res = classify_star_activation({}, {}, {}, ["Chou"])
    assert res["activation_matrix"]["Tian Yi Gui Ren"]["state"] == "suppressed"
