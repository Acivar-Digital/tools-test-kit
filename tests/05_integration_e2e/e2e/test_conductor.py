"""
Set 3 — Conductor Tests
========================
Three layers, all positive path only:

  Layer A — _parse_conductor_response()   → pure Python, no mocks
  Layer B — _apply_extracted()            → pure Python, no mocks
  Layer C — run_conductor() live          → real OpenRouter call (off-the-hook)

Layer C requires OPENROUTER_API_KEY in .env.
Skipped automatically if the key is absent (CI-safe).

Pass criteria
-------------
- Layer A/B: assertions on return values only.
- Layer C: after one real LLM turn, session.metadata contains a parseable
  'dob' key that includes '1977' and '04' and '28'.
"""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

# Lazy import so missing .env doesn't crash collection
from src.bot.conductor import _apply_extracted, _parse_conductor_response  # noqa: E402
from src.bot.session import Session, UserProfile  # noqa: E402

CHAT_ID = 999_000_002


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_session(mode: str = "auto") -> Session:
    s = Session(chat_id=CHAT_ID)
    s.step = "COLLECTING"
    s.metadata["intake_mode"] = mode
    s.profile = UserProfile()
    return s


# ---------------------------------------------------------------------------
# Layer A — _parse_conductor_response  (pure, no LLM)
# ---------------------------------------------------------------------------


class TestParseResponse:
    """_parse_conductor_response handles all valid conductor output shapes."""

    def _make_raw(self, reply: str, extracted: dict, all_collected: bool) -> str:
        return (
            f"REPLY: {reply}\n"
            "---\n"
            f"JSON:\n{json.dumps({'extracted': extracted, 'all_collected': all_collected, 'next_prompt': None})}"
        )

    def test_parse_standard_format(self):
        raw = self._make_raw("Thanks! What is your birth date?", {"alias": "TEST", "gender": "Male"}, False)
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert reply == "Thanks! What is your birth date?"
        assert extracted["alias"] == "TEST"
        assert extracted["gender"] == "Male"
        assert all_collected is False

    def test_parse_all_collected_true(self):
        raw = self._make_raw(
            "Thank you, computing your chart now...", {"dob": "1977-04-28 11:51", "location": "Singapore"}, True
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert all_collected is True
        assert extracted["dob"] == "1977-04-28 11:51"

    def test_parse_json_key_format(self):
        """Conductor output with JSON: label but no --- separator."""
        raw = (
            "REPLY: Please enter your date of birth.\n"
            'JSON: {"extracted": {"alias": "FY"}, "all_collected": false, "next_prompt": "DOB?"}'
        )
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert "date of birth" in reply.lower()
        assert extracted.get("alias") == "FY"
        assert all_collected is False

    def test_parse_bare_json_no_labels(self):
        """LLM sometimes drops REPLY/JSON labels and outputs bare JSON."""
        raw = '{"extracted": {"gender": "M"}, "all_collected": false, "next_prompt": "DOB?"}'
        reply, extracted, all_collected = _parse_conductor_response(raw)
        # reply may be empty string or the raw — just must not raise
        assert isinstance(reply, str)
        assert extracted.get("gender") == "M"

    def test_parse_multi_field_single_turn(self):
        """User dumps alias + gender + DOB in one message — all extracted."""
        raw = self._make_raw(
            "Great, got it!",
            {"alias": "TEST", "gender": "Male", "dob": "1977-04-28 11:51", "location": "Singapore"},
            False,
        )
        _, extracted, _ = _parse_conductor_response(raw)
        assert extracted["alias"] == "TEST"
        assert extracted["dob"] == "1977-04-28 11:51"
        assert extracted["location"] == "Singapore"

    def test_parse_malformed_json_returns_safe_defaults(self):
        """Broken JSON must not raise — must return (reply_str, {}, False)."""
        raw = "REPLY: Something went sideways\n---\nJSON: {bad json here"
        reply, extracted, all_collected = _parse_conductor_response(raw)
        assert isinstance(reply, str)
        assert extracted == {}
        assert all_collected is False

    def test_parse_dob_with_time(self):
        """DOB must preserve HH:MM when user provides it."""
        raw = self._make_raw("Got it.", {"dob": "1977-04-28 11:51"}, False)
        _, extracted, _ = _parse_conductor_response(raw)
        assert extracted["dob"] == "1977-04-28 11:51"

    def test_parse_dob_date_only_defaults_midnight(self):
        """DOB with no time defaults to 00:00 per conductor rules."""
        raw = self._make_raw("Got it.", {"dob": "1977-04-28 00:00"}, False)
        _, extracted, _ = _parse_conductor_response(raw)
        assert "1977-04-28" in extracted["dob"]


# ---------------------------------------------------------------------------
# Layer B — _apply_extracted  (pure, no LLM)
# ---------------------------------------------------------------------------


class TestApplyExtracted:
    """_apply_extracted writes fields into session correctly."""

    def test_apply_alias(self):
        s = _fresh_session()
        s = _apply_extracted(s, {"alias": "TEST"}, "auto")
        assert s.profile.alias == "TEST"

    def test_apply_gender_male_full_word(self):
        s = _fresh_session()
        s = _apply_extracted(s, {"gender": "Male"}, "auto")
        assert s.profile.gender == "M"

    def test_apply_gender_female(self):
        s = _fresh_session()
        s = _apply_extracted(s, {"gender": "Female"}, "auto")
        assert s.profile.gender == "F"

    def test_apply_gender_m_shortform(self):
        s = _fresh_session()
        s = _apply_extracted(s, {"gender": "M"}, "auto")
        assert s.profile.gender == "M"

    def test_apply_dob_goes_to_metadata(self):
        s = _fresh_session()
        s = _apply_extracted(s, {"dob": "1977-04-28 11:51"}, "auto")
        assert s.metadata["dob"] == "1977-04-28 11:51"

    def test_apply_location_goes_to_metadata(self):
        s = _fresh_session()
        s = _apply_extracted(s, {"location": "Singapore"}, "auto")
        assert s.metadata["location"] == "Singapore"

    def test_apply_computed_fields_blocked_in_auto_mode(self):
        """year_pillar is a computed field — must NOT be written in auto mode."""
        s = _fresh_session(mode="auto")
        s = _apply_extracted(s, {"year_pillar": {"stem": "Ding", "branch": "Si"}}, "auto")
        assert s.profile.year_pillar is None, "Computed field year_pillar must be ignored in AUTO mode"

    def test_apply_computed_fields_allowed_in_input_mode(self):
        """In /input mode, user-supplied pillars ARE written."""
        s = _fresh_session(mode="input")
        s = _apply_extracted(s, {"year_pillar": {"stem": "Ding", "branch": "Si"}}, "input")
        assert s.profile.year_pillar == {"stem": "Ding", "branch": "Si"}

    def test_apply_pillar_as_string(self):
        """Conductor sometimes returns pillar as 'Ding Si' string — must parse."""
        s = _fresh_session(mode="input")
        s = _apply_extracted(s, {"day_pillar": "Yi Mao"}, "input")
        assert s.profile.day_pillar == {"stem": "Yi", "branch": "Mao"}

    def test_apply_favorable_elements_list(self):
        s = _fresh_session(mode="input")
        s = _apply_extracted(s, {"favorable_elements": ["Fire", "Earth"]}, "input")
        assert set(s.profile.favorable_elements) == {"Fire", "Earth"}

    def test_apply_neutral_elements_scalar(self):
        """Conductor may return a scalar instead of list — must wrap."""
        s = _fresh_session(mode="input")
        s = _apply_extracted(s, {"neutral_elements": "Metal"}, "input")
        assert s.profile.neutral_elements == ["Metal"]

    def test_apply_non_dict_extracted_is_safe(self):
        """Malformed extracted (not a dict) must not raise."""
        s = _fresh_session()
        s = _apply_extracted(s, None, "auto")  # type: ignore[arg-type]
        assert s.profile.alias is None  # unchanged

    def test_apply_multiple_fields_one_call(self):
        """All five auto fields applied in one shot."""
        s = _fresh_session(mode="auto")
        s = _apply_extracted(
            s,
            {
                "alias": "TEST",
                "gender": "Male",
                "dob": "1977-04-28 11:51",
                "location": "Singapore",
            },
            "auto",
        )
        assert s.profile.alias == "TEST"
        assert s.profile.gender == "M"
        assert s.metadata["dob"] == "1977-04-28 11:51"
        assert s.metadata["location"] == "Singapore"


# ---------------------------------------------------------------------------
# Layer C — run_conductor() LIVE  (real OpenRouter call)
# ---------------------------------------------------------------------------

LIVE = pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"), reason="OPENROUTER_API_KEY not set — skipping live conductor tests"
)


@LIVE
class TestConductorLive:
    """
    Real LLM call. Tests the conductor end-to-end with a single user turn
    that contains all the info it needs to collect in one shot.

    Expected outcome: after one turn, session.metadata['dob'] contains
    '1977', '04', '28' and session.profile.alias is 'TEST'.
    """

    @pytest.mark.asyncio
    async def test_conductor_extracts_dob_from_natural_language(self):
        from src.bot.conductor import run_conductor
        from src.bot.session import delete_session

        delete_session(CHAT_ID)

        s = _fresh_session(mode="auto")
        s.metadata["intake_mode"] = "auto"

        # Simulate /auto init turn
        _, s = await run_conductor(s, "__init__")

        # User provides all info in one natural language sentence
        user_msg = "My name is Test Profile, alias TEST, male. Born 01 January 1990 at 11:51am in Singapore."
        reply, s = await run_conductor(s, user_msg)

        dob = s.metadata.get("dob", "")
        assert "1977" in dob, f"Year missing from dob: {dob!r}"
        assert "04" in dob or "4" in dob, f"Month missing from dob: {dob!r}"
        assert "28" in dob, f"Day missing from dob: {dob!r}"
        assert s.metadata.get("location", "").lower() in ("singapore", "sg"), (
            f"Location not captured: {s.metadata.get('location')!r}"
        )

    @pytest.mark.asyncio
    async def test_conductor_extracts_alias_and_gender(self):
        from src.bot.conductor import run_conductor
        from src.bot.session import delete_session

        delete_session(CHAT_ID)

        s = _fresh_session(mode="auto")
        _, s = await run_conductor(s, "__init__")

        reply, s = await run_conductor(
            s, "Name: Test Profile, alias TEST, gender Male, born 1977-04-28 11:51, Singapore."
        )

        assert "TEST" in s.profile.alias, f"Got alias: {s.profile.alias!r}"
        assert s.profile.gender == "M", f"Got gender: {s.profile.gender!r}"

    @pytest.mark.asyncio
    async def test_conductor_returns_none_when_all_auto_fields_collected(self):
        """
        After all 5 auto fields are in session, run_conductor must return (None, session)
        signalling the engine should run.
        """
        from src.bot.conductor import run_conductor
        from src.bot.session import delete_session

        delete_session(CHAT_ID)

        # Pre-seed all required auto fields
        s = _fresh_session(mode="auto")
        s.profile.alias = "TEST"
        s.profile.gender = "M"
        s.metadata["dob"] = "1977-04-28 11:51"
        s.metadata["location"] = "Singapore"
        # da_yun_pillar not required in auto mode (computed) — check schema
        # but alias/gender/dob/location are the 4 auto fields; if that's enough:

        reply, s = await run_conductor(s, "anything")

        assert reply is None, (
            f"Expected None (all collected) but conductor returned: {reply!r}. "
            "Check intake_schema.json auto collect_sequence against _get_collected logic."
        )

    @pytest.mark.asyncio
    async def test_conductor_does_not_ask_for_computed_fields(self):
        """
        The conductor's first reply in AUTO mode must NOT mention
        year pillar, month pillar, day pillar, or hour pillar.
        """
        from src.bot.conductor import run_conductor
        from src.bot.session import delete_session

        delete_session(CHAT_ID)

        s = _fresh_session(mode="auto")
        reply, s = await run_conductor(s, "__init__")

        if reply is None:
            pytest.skip("All fields already collected — nothing to assert")

        forbidden = ["year pillar", "month pillar", "day pillar", "hour pillar", "favorable", "unfavorable", "strength"]
        for phrase in forbidden:
            assert phrase.lower() not in reply.lower(), (
                f"Conductor asked for computed field in AUTO mode. Found '{phrase}' in: {reply!r}"
            )
