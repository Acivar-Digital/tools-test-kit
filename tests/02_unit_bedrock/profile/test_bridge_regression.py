import pytest

from src.tools.user_profile_input import (
    OVERRIDABLE_FIELDS,
    apply_override,
    collect_profile_from_dob,
    get_effective_profile,
)


class TestUserProfileInput:
    def test_collect_profile_returns_structure(self):
        profile = collect_profile_from_dob(1985, 3, 15, 14, 0)
        assert "pillars" in profile
        assert "strength_data" in profile
        assert profile["source"] == "auto"
        assert profile["overrides"] == {}

    def test_apply_override_strength(self):
        profile = collect_profile_from_dob(1985, 3, 15, 14, 0)
        apply_override(profile, "strength", "身弱")
        assert profile["strength_data"]["strength"] == "身弱"
        assert profile["source"] == "manual_override"
        assert "strength" in profile["overrides"]

    def test_apply_override_day_pillar(self):
        profile = collect_profile_from_dob(1985, 3, 15, 14, 0)
        apply_override(profile, "day", "庚午")
        assert profile["pillars"]["day"] == "庚午"

    def test_apply_invalid_field_raises(self):
        profile = collect_profile_from_dob(1985, 3, 15, 14, 0)
        with pytest.raises(ValueError):
            apply_override(profile, "nonexistent_field", "abc")

    def test_get_effective_profile_is_flat(self):
        profile = collect_profile_from_dob(1985, 3, 15, 14, 0)
        eff = get_effective_profile(profile)
        # Should be a flat dict — no nested dicts for pillars/strength_data
        assert "pillars" not in eff
        assert "strength_data" not in eff
        assert "day_master" in eff
        assert "strength" in eff
        assert "source" in eff

    def test_override_reflected_in_effective_profile(self):
        profile = collect_profile_from_dob(1985, 3, 15, 14, 0)
        apply_override(profile, "strength", "中和")
        eff = get_effective_profile(profile)
        assert eff["strength"] == "中和"
        assert eff["source"] == "manual_override"

    def test_overridable_fields_list_complete(self):
        expected = {
            "year",
            "month",
            "day",
            "hour",
            "day_master",
            "strength",
            "favorable_elements",
            "unfavorable_elements",
        }
        assert set(OVERRIDABLE_FIELDS) == expected
