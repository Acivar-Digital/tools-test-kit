from src.engine.module1_macro import calculate_macro


def test_void_audit_active():
    # Test case with multiple negative interactions
    profile = {
        "year_pillar": {"stem": "Bing", "branch": "You"},
        "month_pillar": {"stem": "Geng", "branch": "You"},
        "day_pillar": {"stem": "Jia", "branch": "You"},
        "hour_pillar": {"stem": "Ji", "branch": "You"},
        "day_stem_stream": "Jia Yin",
        "da_yun_pillar": {"stem": "Ji", "branch": "Zi"},
        "medicine": ["Wood"],
        "taboo": ["Metal"],
        "favorable_elements": ["Wood"],
    }
    month_branch = "Zi"  # Void branch for Jia Yin
    annual_pillar = {"stem": "Bing", "branch": "Zi"}  # Creates Po interaction (-10) with You

    result = calculate_macro(profile, month_branch, annual_pillar)
    void_audit = result["macro_environmental_scan"]["void_audit"]

    assert void_audit["is_void_active"] is True
    assert void_audit["impact_score"] <= 0


def test_void_audit_cured():
    # Test case with positive interactions
    profile = {
        "year_pillar": {"stem": "Bing", "branch": "Wu"},
        "month_pillar": {"stem": "Geng", "branch": "Yin"},
        "day_pillar": {"stem": "Jia", "branch": "Yin"},
        "hour_pillar": {"stem": "Ji", "branch": "Chou"},
        "day_stem_stream": "Jia Yin",
        "da_yun_pillar": {"stem": "Ji", "branch": "Chen"},
        "medicine": ["Wood"],
        "taboo": ["Metal"],
        "favorable_elements": ["Wood"],
    }
    month_branch = "Zi"  # Void branch for Jia Yin
    annual_pillar = {"stem": "Bing", "branch": "Chen"}  # Creates San He interaction (+15)

    result = calculate_macro(profile, month_branch, annual_pillar)
    void_audit = result["macro_environmental_scan"]["void_audit"]

    assert void_audit["is_void_active"] is False
    assert void_audit["impact_score"] > 0


def test_non_void_month():
    # Test case with non-void month branch
    profile = {
        "year_pillar": {"stem": "Bing", "branch": "Wu"},
        "month_pillar": {"stem": "Geng", "branch": "Yin"},
        "day_pillar": {"stem": "Jia", "branch": "Yin"},
        "hour_pillar": {"stem": "Ji", "branch": "Chou"},
        "day_stem_stream": "Jia Yin",
        "da_yun_pillar": {"stem": "Ji", "branch": "Chen"},
        "medicine": ["Wood"],
        "taboo": ["Metal"],
        "favorable_elements": ["Wood"],
    }
    month_branch = "Yin"  # Not a void branch for Jia Yin
    annual_pillar = {"stem": "Bing", "branch": "Wu"}

    result = calculate_macro(profile, month_branch, annual_pillar)
    void_audit = result["macro_environmental_scan"]["void_audit"]

    assert void_audit["is_void_active"] is False
    assert void_audit["cured_status"] is False
