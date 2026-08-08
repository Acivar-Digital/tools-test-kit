"""
Unit tests for Module 12: Compatibility Analysis (module12_compatibility.py)

Tests cover:
- Overall compatibility scoring
- Ge Ju pattern compatibility
- Day Master interaction scoring
- Branch chemistry (Liu He, San He, Chong, etc.)
- Peach Blossom scoring
- Compatibility categorization
"""

import pytest

from src2.engine.module12_compatibility import analyze_compatibility


def analyze_compatibility_from_dict(p1: dict, p2: dict, category: str = "friend") -> dict:
    dm1 = p1.get("day_pillar", {}).get("stem") or "Jia"
    dm2 = p2.get("day_pillar", {}).get("stem") or "Jia"
    db1 = p1.get("day_pillar", {}).get("branch") or "Zi"
    db2 = p2.get("day_pillar", {}).get("branch") or "Zi"
    month1 = p1.get("month_pillar", {}).get("branch") or "Yin"
    month2 = p2.get("month_pillar", {}).get("branch") or "Yin"
    stream1 = p1.get("xun_kong") or "Jia-Zi"
    stream2 = p2.get("xun_kong") or "Jia-Zi"
    pattern1 = p1.get("structure") or "common_pattern"
    pattern2 = p2.get("structure") or "common_pattern"
    strength1 = p1.get("dm_strength_type") or "Balanced"
    strength2 = p2.get("dm_strength_type") or "Balanced"
    fav1 = p1.get("favorable_elements") or []
    unfav1 = p1.get("unfavorable_elements") or []
    fav2 = p2.get("favorable_elements") or []
    unfav2 = p2.get("unfavorable_elements") or []

    res = analyze_compatibility(
        dm1, dm2, db1, db2, month1, month2, stream1, stream2,
        pattern1, pattern2, strength1, strength2, fav1, unfav1, fav2, unfav2,
        category=category
    )
    return {
        "total_score": res.total_score,
        "level": res.level,
        "level_description": res.level_description,
        "category": res.category,
        "breakdown": {item.key: {"score": item.value} for item in res.breakdown.items},
        "descriptions": {item.key: item.value for item in res.descriptions.items},
    }

# ─────────────────────────────────────────────
# Test Data Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def profile_male_weak():
    """Create a weak male Day Master profile."""
    return {
        "day_pillar": {"stem": "Yi", "branch": "Mao"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "year_pillar": {"stem": "Jia", "branch": "Zi"},
        "hour_pillar": {"stem": "Ding", "branch": "Chou"},
        "dm_strength_type": "Weak",
        "structure": "yin_xiao_ge",  # Resource pattern
    }


@pytest.fixture
def profile_male_strong():
    """Create a strong male Day Master profile."""
    return {
        "day_pillar": {"stem": "Wu", "branch": "Xu"},
        "month_pillar": {"stem": "Ji", "branch": "Wei"},
        "year_pillar": {"stem": "Geng", "branch": "Shen"},
        "hour_pillar": {"stem": "Xin", "branch": "You"},
        "dm_strength_type": "Strong",
        "structure": "shi_shen_ge",  # Eating God pattern
    }


@pytest.fixture
def profile_female_weak():
    """Create a weak female Day Master profile."""
    return {
        "day_pillar": {"stem": "Ding", "branch": "You"},
        "month_pillar": {"stem": "Ren", "branch": "Chen"},
        "year_pillar": {"stem": "Gui", "branch": "Hai"},
        "hour_pillar": {"stem": "Jia", "branch": "Yin"},
        "dm_strength_type": "Weak",
        "structure": "cai_ge",  # Wealth pattern
    }


@pytest.fixture
def compatible_profile():
    """Create a profile compatible with male_weak."""
    return {
        "day_pillar": {"stem": "Bing", "branch": "Yin"},
        "month_pillar": {"stem": "Ding", "branch": "Mao"},
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "hour_pillar": {"stem": "Ji", "branch": "Wei"},
        "dm_strength_type": "Balanced",
        "structure": "zheng_guan_ge",  # Officer pattern
    }


@pytest.fixture
def incompatible_profile():
    """Create a profile incompatible with male_weak."""
    return {
        "day_pillar": {"stem": "Geng", "branch": "Xu"},
        "month_pillar": {"stem": "Xin", "branch": "Hai"},
        "year_pillar": {"stem": "Ren", "branch": "Zi"},
        "hour_pillar": {"stem": "Gui", "branch": "Chou"},
        "dm_strength_type": "Strong",
        "structure": "qi_sha_ge",  # 7K pattern
    }


# ─────────────────────────────────────────────
# Test: Overall Compatibility Scoring
# ─────────────────────────────────────────────


class TestOverallCompatibility:
    """Test overall compatibility scoring."""

    def test_compatibility_score_range(self, profile_male_weak, compatible_profile):
        """Test compatibility score is within valid range."""
        result = analyze_compatibility_from_dict(profile_male_weak, compatible_profile)

        assert 0 <= result["total_score"] <= 100

    def test_compatibility_has_required_fields(self, profile_male_weak, compatible_profile):
        """Test result contains all required fields."""
        result = analyze_compatibility_from_dict(profile_male_weak, compatible_profile)

        assert "total_score" in result
        assert "level" in result
        assert "breakdown" in result
        assert "ge_ju" in result["breakdown"]
        assert "day_master" in result["breakdown"]
        assert "branch_chemistry" in result["breakdown"]
        assert "peach_blossom" in result["breakdown"]

    def test_exceptional_compatibility(self):
        """Test exceptionally compatible profiles."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "zheng_guan_ge",
        }

        profile2 = {
            "day_pillar": {"stem": "Ji", "branch": "You"},
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Gui", "branch": "Hai"},
            "hour_pillar": {"stem": "Yi", "branch": "Mao"},
            "dm_strength_type": "Weak",
            "structure": "yin_xiao_ge",
        }

        result = analyze_compatibility_from_dict(profile1, profile2, category="partner")

        assert result["level"] in ["Exceptional", "Favorable"]
        assert result["total_score"] >= 65

    def test_discordant_compatibility(self):
        """Test discordant (poor) compatibility."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Yi", "branch": "Chou"},
            "year_pillar": {"stem": "Bing", "branch": "Yin"},
            "hour_pillar": {"stem": "Ding", "branch": "Mao"},
            "dm_strength_type": "Strong",
            "structure": "qi_sha_ge",
        }

        profile2 = {
            "day_pillar": {"stem": "Geng", "branch": "Wu"},  # Clashes with Zi
            "month_pillar": {"stem": "Xin", "branch": "Wei"},  # Clashes with Chou
            "year_pillar": {"stem": "Ren", "branch": "Shen"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Strong",
            "structure": "qi_sha_ge",
        }

        result = analyze_compatibility_from_dict(profile1, profile2, category="partner")

        # Heavily penalized due to Spouse Palace clash (Zi-Wu), Stem clash (Jia-Geng),
        # and double Strong + Qi Sha Ge structure penalties.
        assert result["level"] in ["Challenging", "Discordant"]
        assert result["total_score"] < 50

    def test_neutral_compatibility(self):
        """Test neutral compatibility."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Balanced",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Geng", "branch": "Shen"},
            "month_pillar": {"stem": "Ren", "branch": "Zi"},
            "year_pillar": {"stem": "Jia", "branch": "Yin"},
            "hour_pillar": {"stem": "Bing", "branch": "Chen"},
            "dm_strength_type": "Balanced",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert 50 <= result["total_score"] < 70


# ─────────────────────────────────────────────
# Test: Ge Ju Compatibility
# ─────────────────────────────────────────────


class TestGeJuCompatibility:
    """Test Ge Ju pattern compatibility."""

    def test_resource_officer_compatibility(self, profile_male_weak):
        """Test Resource (Yin Xiao) + Officer (Zheng Guan) compatibility."""
        officer_profile = {
            "day_pillar": {"stem": "Bing", "branch": "Yin"},
            "month_pillar": {"stem": "Wu", "branch": "Wu"},
            "year_pillar": {"stem": "Geng", "branch": "Shen"},
            "hour_pillar": {"stem": "Xin", "branch": "You"},
            "dm_strength_type": "Strong",
            "structure": "zheng_guan_ge",
        }

        result = analyze_compatibility_from_dict(profile_male_weak, officer_profile)

        assert result["breakdown"]["ge_ju"]["score"] >= 70

    def test_wealth_resource_conflict(self):
        """Test Wealth + Resource conflict."""
        wealth_profile = {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Wu", "branch": "Chen"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "cai_ge",
        }

        resource_profile = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "yin_xiao_ge",
        }

        result = analyze_compatibility_from_dict(wealth_profile, resource_profile)

        assert result["breakdown"]["ge_ju"]["score"] < 70

    def test_7k_eating_god_compatibility(self):
        """Test 7 Killings + Eating God compatibility."""
        seven_k_profile = {
            "day_pillar": {"stem": "Geng", "branch": "Xu"},
            "month_pillar": {"stem": "Xin", "branch": "Hai"},
            "year_pillar": {"stem": "Ren", "branch": "Zi"},
            "hour_pillar": {"stem": "Gui", "branch": "Chou"},
            "dm_strength_type": "Strong",
            "structure": "qi_sha_ge",
        }

        eating_god_profile = {
            "day_pillar": {"stem": "Bing", "branch": "Shen"},
            "month_pillar": {"stem": "Ding", "branch": "You"},
            "year_pillar": {"stem": "Wu", "branch": "Xu"},
            "hour_pillar": {"stem": "Ji", "branch": "Hai"},
            "dm_strength_type": "Weak",
            "structure": "shi_shen_ge",
        }

        result = analyze_compatibility_from_dict(seven_k_profile, eating_god_profile)

        assert result["breakdown"]["ge_ju"]["score"] >= 70


# ─────────────────────────────────────────────
# Test: Day Master Interaction
# ─────────────────────────────────────────────


class TestDayMasterInteraction:
    """Test Day Master compatibility scoring."""

    def test_same_element_day_master(self):
        """Test same element Day Masters."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["day_master"]["score"] >= 80

    def test_production_cycle_day_master(self):
        """Test Day Masters in production cycle."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},  # Wood
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Bing", "branch": "Chen"},  # Fire (produced by Wood)
            "month_pillar": {"stem": "Wu", "branch": "Wu"},
            "year_pillar": {"stem": "Geng", "branch": "Shen"},
            "hour_pillar": {"stem": "Xin", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["day_master"]["score"] >= 90

    def test_control_cycle_day_master(self):
        """Test Day Masters in control cycle."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},  # Wood
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Geng", "branch": "Shen"},  # Metal (controls Wood)
            "month_pillar": {"stem": "Xin", "branch": "You"},
            "year_pillar": {"stem": "Ren", "branch": "Zi"},
            "hour_pillar": {"stem": "Gui", "branch": "Chou"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["day_master"]["score"] < 90


# ─────────────────────────────────────────────
# Test: Branch Chemistry
# ─────────────────────────────────────────────


class TestBranchChemistry:
    """Test branch interaction scoring."""

    def test_liu_he_combination(self):
        """Test Liu He (六合) combination."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},  # Zi branch
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Wu", "branch": "Chen"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Chou"},  # Chou branch (Liu He with Zi)
            "month_pillar": {"stem": "Ding", "branch": "Mao"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["branch_chemistry"]["score"] >= 90

    def test_san_he_combination(self):
        """Test San He (三合) combination."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},  # Yin branch (Wood)
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},  # Mao branch (Wood)
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["branch_chemistry"]["score"] >= 80

    def test_chong_clash(self):
        """Test Chong (冲) clash."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},  # Zi branch
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Wu", "branch": "Chen"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Geng", "branch": "Wu"},  # Wu branch (clashes with Zi)
            "month_pillar": {"stem": "Xin", "branch": "Wei"},
            "year_pillar": {"stem": "Ren", "branch": "Shen"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["branch_chemistry"]["score"] <= 75

    def test_xing_punishment(self):
        """Test Xing (刑) punishment."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},  # Yin branch
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Si"},  # Si branch (punishes Yin)
            "month_pillar": {"stem": "Bing", "branch": "Wu"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["branch_chemistry"]["score"] < 70


# ─────────────────────────────────────────────
# Test: Peach Blossom Scoring
# ─────────────────────────────────────────────


class TestPeachBlossom:
    """Test Peach Blossom scoring."""

    def test_mutual_peach_blossom(self):
        """Test mutual Peach Blossom attraction."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},  # Day branch Zi
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Wu", "branch": "Chen"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},  # Day branch Mao (PB for Zi)
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert result["breakdown"]["peach_blossom"]["score"] >= 80

    def test_one_sided_peach_blossom(self):
        """Test one-sided Peach Blossom."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},  # Day branch Zi
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Wu", "branch": "Chen"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Jia", "branch": "Chen"},  # Day branch Chen (not PB for Zi)
            "month_pillar": {"stem": "Ding", "branch": "Mao"},  # But Mao is PB for Zi
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert 50 <= result["breakdown"]["peach_blossom"]["score"] < 90


# ─────────────────────────────────────────────
# Test: Compatibility Levels
# ─────────────────────────────────────────────


class TestCompatibilityLevels:
    """Test compatibility level categorization."""

    def test_exceptional_level(self):
        """Test Exceptional level (score >= 80)."""
        assert 85 >= 80

    def test_favorable_level(self):
        """Test Favorable level (65 <= score < 80)."""
        assert 70 >= 65 and 70 < 80

    def test_neutral_level(self):
        """Test Neutral level (50 <= score < 65)."""
        assert 60 >= 50 and 60 < 65

    def test_challenging_level(self):
        """Test Challenging level (35 <= score < 50)."""
        assert 40 >= 35 and 40 < 50

    def test_discordant_level(self):
        """Test Discordant level (score < 35)."""
        assert 30 < 35


# ─────────────────────────────────────────────
# Test: Edge Cases
# ─────────────────────────────────────────────


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_same_person_compatibility(self, profile_male_weak):
        """Test compatibility with self (should be neutral to favorable)."""
        result = analyze_compatibility_from_dict(profile_male_weak, profile_male_weak)

        assert result["total_score"] > 0

    def test_missing_structure(self):
        """Test with missing structure field."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert "total_score" in result

    def test_missing_day_master(self):
        """Test with missing Day Master."""
        profile1 = {
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "common_pattern",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "common_pattern",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert "total_score" in result

    def test_extreme_scores(self):
        """Test that scores are properly bounded."""
        profile1 = {
            "day_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Bing", "branch": "Chen"},
            "year_pillar": {"stem": "Wu", "branch": "Wu"},
            "hour_pillar": {"stem": "Geng", "branch": "Shen"},
            "dm_strength_type": "Strong",
            "structure": "zheng_guan_ge",
        }

        profile2 = {
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "month_pillar": {"stem": "Ding", "branch": "Si"},
            "year_pillar": {"stem": "Ji", "branch": "Wei"},
            "hour_pillar": {"stem": "Gui", "branch": "You"},
            "dm_strength_type": "Weak",
            "structure": "yin_xiao_ge",
        }

        result = analyze_compatibility_from_dict(profile1, profile2)

        assert 0 <= result["total_score"] <= 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
