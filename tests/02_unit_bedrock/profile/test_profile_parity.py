# tests/test_profile_parity.py
# Run with: uv run pytest tests/test_profile_parity.py -v
#
# SET 1 — Auto / Input Parity
# Reference subject: Test Profile
#   DOB : 1977-04-28 11:51 SGT (local clock, no TST correction)
#   Sex : Male
#
# Both /auto (computed) and /input (manual entry) must converge on:
#   Year   : 丁巳  (Ding Si)
#   Month  : 甲辰  (Jia Chen)
#   Day    : 乙卯  (Yi Mao)
#   Hour   : 壬午  (Ren Wu)
#   Da Yun : 己亥  (Ji Hai)  — 2026
#   Strength: 身强 (Strong)
#   Favorable  : 火, 土  (Fire, Earth)
#   Unfavorable: 水, 木  (Water, Wood)
#   Neutral    : 金       (Metal)

import pytest

from src.tools.bazi_engine import (
    get_current_da_yun,
    get_day_master_strength,
    get_pillars,
)
from src.tools.user_profile_input import (
    apply_override,
    collect_profile_from_dob,
    get_effective_profile,
)

# ── Reference constants ──────────────────────────────────────────────────
DOB_YEAR, DOB_MONTH, DOB_DAY = 1977, 4, 28
DOB_HOUR, DOB_MINUTE = 11, 51
GENDER = "M"

EXPECTED_YEAR = "丁巳"
EXPECTED_MONTH = "甲辰"
EXPECTED_DAY = "乙卯"
EXPECTED_HOUR = "壬午"
EXPECTED_DAYUN = "己亥"
EXPECTED_STRENGTH = "身强"
EXPECTED_FAVORABLE = {"火", "土"}
EXPECTED_UNFAVORABLE = {"水", "木"}
EXPECTED_NEUTRAL = {"金"}


# ─────────────────────────────────────────────────────────────────
class TestAutoMode:
    """
    /auto path: engine computes everything from raw DOB + gender.
    Tests that each computed field matches the known reference.
    """

    @pytest.fixture(scope="class")
    def pillars(self):
        return get_pillars(DOB_YEAR, DOB_MONTH, DOB_DAY, DOB_HOUR, DOB_MINUTE)

    @pytest.fixture(scope="class")
    def strength_data(self, pillars):
        return get_day_master_strength(pillars)

    @pytest.fixture(scope="class")
    def da_yun(self):
        return get_current_da_yun(DOB_YEAR, DOB_MONTH, DOB_DAY, DOB_HOUR, DOB_MINUTE, GENDER)

    # ── Pillar tests ──────────────────────────────────────────────────

    def test_year_pillar(self, pillars):
        assert pillars["year"] == EXPECTED_YEAR, f"Year: expected {EXPECTED_YEAR}, got {pillars['year']}"

    def test_month_pillar(self, pillars):
        assert pillars["month"] == EXPECTED_MONTH, (
            f"Month: expected {EXPECTED_MONTH}, got {pillars['month']}\n"
            f"Check YEAR_STEM_MONTH_START table — 丁 year should yield 甲辰"
        )

    def test_day_pillar(self, pillars):
        assert pillars["day"] == EXPECTED_DAY, f"Day: expected {EXPECTED_DAY}, got {pillars['day']}"

    def test_hour_pillar(self, pillars):
        assert pillars["hour"] == EXPECTED_HOUR, (
            f"Hour: expected {EXPECTED_HOUR}, got {pillars['hour']}\n"
            f"11:51 local → 午 branch (11:00-13:00). No TST correction."
        )

    def test_hour_is_wu_branch(self, pillars):
        """11:51 must land in 午 hour (11:00-13:00), never 巳."""
        assert pillars["hour"][1] == "午", (
            f"Hour branch: expected 午, got {pillars['hour'][1]}. TST correction must NOT be applied."
        )

    def test_day_master_is_yi(self, pillars):
        assert pillars["day_master"] == "乙", f"Day master: expected 乙, got {pillars['day_master']}"

    # ── Da Yun test ─────────────────────────────────────────────────────

    def test_da_yun_2026(self, da_yun):
        assert da_yun["pillar"] == EXPECTED_DAYUN, (
            f"Da Yun 2026: expected {EXPECTED_DAYUN}, got {da_yun['pillar']}\n"
            f"丁 is YIN year + Male = REVERSE Da Yun. Check getYun(g_val)."
        )

    # ── Strength tests ───────────────────────────────────────────────────

    def test_strength_is_shen_qiang(self, strength_data):
        assert strength_data["strength"] == EXPECTED_STRENGTH, (
            f"Strength: expected {EXPECTED_STRENGTH}, got {strength_data['strength']}"
        )

    def test_favorable_elements(self, strength_data):
        actual = set(strength_data["favorable_elements"])
        assert actual == EXPECTED_FAVORABLE, f"Favorable: expected {EXPECTED_FAVORABLE}, got {actual}"

    def test_unfavorable_elements(self, strength_data):
        actual = set(strength_data["unfavorable_elements"])
        assert actual == EXPECTED_UNFAVORABLE, f"Unfavorable: expected {EXPECTED_UNFAVORABLE}, got {actual}"

    def test_neutral_elements(self, strength_data):
        actual = set(strength_data.get("neutral_elements", []))
        assert actual == EXPECTED_NEUTRAL, f"Neutral: expected {EXPECTED_NEUTRAL}, got {actual}"

    def test_all_five_elements_covered(self, strength_data):
        all_els = (
            set(strength_data["favorable_elements"])
            | set(strength_data["unfavorable_elements"])
            | set(strength_data.get("neutral_elements", []))
        )
        assert all_els == {"木", "火", "土", "金", "水"}, f"Not all five elements covered: {all_els}"

    def test_no_favorable_unfavorable_overlap(self, strength_data):
        overlap = set(strength_data["favorable_elements"]) & set(strength_data["unfavorable_elements"])
        assert not overlap, f"Overlap: {overlap}"


# ─────────────────────────────────────────────────────────────────
class TestInputMode:
    """
    /input path: user manually provides all 9 fields.
    Simulates what the bot receives when user types each value.
    Tests that a manually built profile with Tester’s known values
    produces an identical effective profile to the auto-computed one.
    """

    @pytest.fixture(scope="class")
    def manual_profile(self):
        """Build profile via collect_profile_from_dob then override all fields
        to simulate a user who typed everything manually (/input mode)."""
        profile = collect_profile_from_dob(DOB_YEAR, DOB_MONTH, DOB_DAY, DOB_HOUR, DOB_MINUTE)
        # Override every field with the known-correct values
        apply_override(profile, "year", EXPECTED_YEAR)
        apply_override(profile, "month", EXPECTED_MONTH)
        apply_override(profile, "day", EXPECTED_DAY)
        apply_override(profile, "hour", EXPECTED_HOUR)
        apply_override(profile, "strength", EXPECTED_STRENGTH)
        apply_override(profile, "favorable_elements", list(EXPECTED_FAVORABLE))
        apply_override(profile, "unfavorable_elements", list(EXPECTED_UNFAVORABLE))
        return profile

    def test_manual_year(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert eff["year"] == EXPECTED_YEAR

    def test_manual_month(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert eff["month"] == EXPECTED_MONTH

    def test_manual_day(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert eff["day"] == EXPECTED_DAY

    def test_manual_hour(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert eff["hour"] == EXPECTED_HOUR

    def test_manual_strength(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert eff["strength"] == EXPECTED_STRENGTH

    def test_manual_favorable(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert set(eff["favorable_elements"]) == EXPECTED_FAVORABLE

    def test_manual_unfavorable(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert set(eff["unfavorable_elements"]) == EXPECTED_UNFAVORABLE

    def test_source_is_manual_override(self, manual_profile):
        eff = get_effective_profile(manual_profile)
        assert eff["source"] == "manual_override"


# ─────────────────────────────────────────────────────────────────
class TestParityAutoVsInput:
    """
    The critical parity test:
    The effective profile from /auto must equal the effective profile
    from /input when both use Tester’s identical values.
    """

    @pytest.fixture(scope="class")
    def auto_effective(self):
        profile = collect_profile_from_dob(DOB_YEAR, DOB_MONTH, DOB_DAY, DOB_HOUR, DOB_MINUTE)
        return get_effective_profile(profile)

    @pytest.fixture(scope="class")
    def input_effective(self):
        profile = collect_profile_from_dob(DOB_YEAR, DOB_MONTH, DOB_DAY, DOB_HOUR, DOB_MINUTE)
        apply_override(profile, "year", EXPECTED_YEAR)
        apply_override(profile, "month", EXPECTED_MONTH)
        apply_override(profile, "day", EXPECTED_DAY)
        apply_override(profile, "hour", EXPECTED_HOUR)
        apply_override(profile, "strength", EXPECTED_STRENGTH)
        apply_override(profile, "favorable_elements", list(EXPECTED_FAVORABLE))
        apply_override(profile, "unfavorable_elements", list(EXPECTED_UNFAVORABLE))
        return get_effective_profile(profile)

    def test_pillars_match(self, auto_effective, input_effective):
        for key in ["year", "month", "day", "hour"]:
            assert auto_effective[key] == input_effective[key], (
                f"Parity fail on {key}: auto={auto_effective[key]}, input={input_effective[key]}"
            )

    def test_strength_matches(self, auto_effective, input_effective):
        assert auto_effective["strength"] == input_effective["strength"]

    def test_favorable_matches(self, auto_effective, input_effective):
        assert set(auto_effective["favorable_elements"]) == set(input_effective["favorable_elements"])

    def test_unfavorable_matches(self, auto_effective, input_effective):
        assert set(auto_effective["unfavorable_elements"]) == set(input_effective["unfavorable_elements"])

    def test_auto_source_is_auto(self, auto_effective):
        assert auto_effective["source"] == "auto"

    def test_input_source_is_override(self, input_effective):
        assert input_effective["source"] == "manual_override"
