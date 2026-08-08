"""
Unit tests for transformer.py — specifically the to_user_profile() function
and the json_type validation crash fix (baziforecaster-ep638).

Root cause: to_user_profile() called UserProfile.model_validate_json(raw) which
expects a JSON string. Callers in calendar_node.py and coordinator.py passed raw
Python dicts, causing a json_type TypeError crash during manual intake.

Fix: to_user_profile() now handles dict input via UserProfile.model_validate().
Callers also switched to UserProfile.model_validate() directly.
"""
import pytest
from pydantic import ValidationError

from src2.core.schemas.unified import UserProfile
from src2.engine.transformer import to_user_profile

VALID_PILLAR = {"stem": "Jia", "branch": "Zi"}


def _make_profile_dict():
    return {
        "profile_id": "test-profile-001",
        "day_pillar": VALID_PILLAR,
        "month_pillar": VALID_PILLAR,
        "year_pillar": VALID_PILLAR,
        "hour_pillar": VALID_PILLAR,
        "da_yun_pillar": VALID_PILLAR,
        "gender": "M",
        "alias": "TestUser",
        "day_master_strength": "Weak",
    }


class TestToUserProfileDictInput:
    """Verify to_user_profile() accepts dict input (the crash fix)."""

    def test_dict_input_does_not_crash(self):
        """Passing a dict must not raise json_type TypeError."""
        profile = to_user_profile(_make_profile_dict())
        assert isinstance(profile, UserProfile)
        assert profile.profile_id == "test-profile-001"
        assert profile.alias == "TestUser"

    def test_dict_input_with_minimal_fields(self):
        """Dict with only required fields should validate."""
        minimal = {
            "day_pillar": VALID_PILLAR,
            "month_pillar": VALID_PILLAR,
            "year_pillar": VALID_PILLAR,
        }
        profile = to_user_profile(minimal)
        assert isinstance(profile, UserProfile)
        assert profile.day_master_strength.value == "Weak"

    def test_dict_input_preserves_favorable_elements(self):
        """Elements lists in dict input should be preserved."""
        data = _make_profile_dict()
        data["favorable_elements"] = ["Wood", "Water"]
        data["unfavorable_elements"] = ["Fire"]
        profile = to_user_profile(data)
        assert profile.favorable_elements == ["Wood", "Water"]
        assert profile.unfavorable_elements == ["Fire"]


class TestToUserProfileStringInput:
    """Verify to_user_profile() still accepts JSON string input (backward compat)."""

    def test_string_input_still_works(self):
        """JSON string input must still work after the dict fix."""
        import json
        profile = to_user_profile(json.dumps(_make_profile_dict()))
        assert isinstance(profile, UserProfile)
        assert profile.profile_id == "test-profile-001"

    def test_string_input_invalid_json_raises(self):
        """Invalid JSON string should raise ValidationError."""
        with pytest.raises((ValidationError, ValueError)):
            to_user_profile("not valid json {")


class TestToUserProfileObjectInput:
    """Verify to_user_profile() still accepts UserProfile objects (backward compat)."""

    def test_userprofile_object_passes_through(self):
        """Passing an existing UserProfile should return it as-is."""
        original = UserProfile.model_validate(_make_profile_dict())
        result = to_user_profile(original)
        assert result is original


class TestUserProfileModelValidate:
    """Verify UserProfile.model_validate() works directly with dict (caller-side fix)."""

    def test_model_validate_with_dict(self):
        """UserProfile.model_validate() must accept dict input."""
        profile = UserProfile.model_validate(_make_profile_dict())
        assert isinstance(profile, UserProfile)
        assert profile.gender.value == "M"

    def test_model_validate_with_invalid_pillar_raises(self):
        """Invalid pillar combination should raise ValidationError."""
        bad_data = _make_profile_dict()
        bad_data["day_pillar"] = {"stem": "Jia", "branch": "Chou"}
        with pytest.raises(ValidationError):
            UserProfile.model_validate(bad_data)

    def test_model_validate_with_none_pillar_raises(self):
        """Missing required pillar should raise ValidationError."""
        bad_data = _make_profile_dict()
        del bad_data["day_pillar"]
        with pytest.raises(ValidationError):
            UserProfile.model_validate(bad_data)


class TestManualIntakeScenario:
    """Simulate the exact dict structure from calendar_node.py _run_input_engine."""

    def test_input_engine_dict_structure(self):
        """The exact dict from _run_input_engine must produce a valid UserProfile."""
        from src2.core.schemas import ValidatedPillar as Pillar

        dp = Pillar(stem="Jia", branch="Zi")
        mp = Pillar(stem="Yi", branch="Chou")
        yp = Pillar(stem="Bing", branch="Yin")
        hp = Pillar(stem="Ding", branch="Mao")
        dyp = Pillar(stem="Wu", branch="Chen")

        profile = UserProfile.model_validate(
            {
                "profile_id": "test-uuid-123",
                "day_pillar": dp,
                "month_pillar": mp,
                "year_pillar": yp,
                "hour_pillar": hp,
                "da_yun_pillar": dyp,
                "gender": "M",
                "alias": "TEST",
                "day_master_strength": "Weak",
            }
        )
        assert profile.profile_id == "test-uuid-123"
        assert profile.alias == "TEST"
        assert profile.day_pillar.stem == "Jia"
        assert profile.day_pillar.branch == "Zi"

    def test_input_engine_via_to_user_profile(self):
        """The same dict passed through to_user_profile() must also work."""
        from src2.core.schemas import ValidatedPillar as Pillar

        dp = Pillar(stem="Jia", branch="Zi")
        mp = Pillar(stem="Yi", branch="Chou")
        yp = Pillar(stem="Bing", branch="Yin")
        hp = Pillar(stem="Ding", branch="Mao")
        dyp = Pillar(stem="Wu", branch="Chen")

        profile = to_user_profile(
            {
                "profile_id": "test-uuid-123",
                "day_pillar": dp,
                "month_pillar": mp,
                "year_pillar": yp,
                "hour_pillar": hp,
                "da_yun_pillar": dyp,
                "gender": "M",
                "alias": "TEST",
                "day_master_strength": "Weak",
            }
        )
        assert isinstance(profile, UserProfile)
        assert profile.alias == "TEST"
