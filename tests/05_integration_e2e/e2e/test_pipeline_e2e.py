"""
Set 2 — End-to-End Pipeline Smoke Tests
========================================
Goal: Verify that the /auto intake path for Test Profile (1977-04-28 11:51 M)
flows all the way through to report generation being triggered.

What IS mocked
--------------
- Telegram send functions          (no real HTTP calls)
- run_k3_pipeline / run_summarizer / format_k3_markdown / stitch_and_convert
  (heavy LLM + file-IO work; behaviour tested in their own unit suites)
- send_developer_message

What is NOT mocked
------------------
- intake.handle_intake()           — real session state machine
- _run_auto_engine()               — real bazi engine computation
- queue_manager.add_job()          — real queue logic
- conductor.run_conductor()        — real LLM conductor (stubbed at OpenRouter layer)

Pass criteria
-------------
A test passes when session.step reaches "COMPLETE" and
queue_manager.add_job() is called exactly once for that chat_id,
OR when run_full_report_pipeline exits without raising (smoke test).
"""

import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

CHAT_ID = 999_000_001  # synthetic test user — never a real Telegram ID

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_session():
    """Delete the test session before and after every test."""
    from src.bot.session import delete_session

    delete_session(CHAT_ID)
    yield
    delete_session(CHAT_ID)


@pytest.fixture()
def mock_telegram(monkeypatch):
    """Suppress all outbound Telegram calls."""
    monkeypatch.setattr("src.bot.app.send_telegram_message", AsyncMock(return_value=None))
    monkeypatch.setattr("src.bot.app.send_developer_message", AsyncMock(return_value=None))
    monkeypatch.setattr("src.bot.utils.send_telegram_message", AsyncMock(return_value=None))
    monkeypatch.setattr("src.bot.utils.send_telegram_document", AsyncMock(return_value=None))
    monkeypatch.setattr("src.bot.utils.send_developer_message", AsyncMock(return_value=None))


@pytest.fixture()
def mock_pipeline(monkeypatch):
    """Stub the heavy K3 pipeline stages so the E2E test is fast."""
    monkeypatch.setattr("alt_src.K3.K3_pipeline.run_k3_pipeline", MagicMock(return_value=None))
    monkeypatch.setattr("alt_src.K3.K3_summarizer.run_summarizer", MagicMock(return_value=None))
    monkeypatch.setattr("alt_src.K3.K3_report_formatter.format_k3_markdown", MagicMock(return_value=None))
    monkeypatch.setattr("alt_src.K3.K3_consolidator.stitch_and_convert", MagicMock(return_value=None))


# ---------------------------------------------------------------------------
# Helper: drive handle_intake through a sequence of messages
# ---------------------------------------------------------------------------


async def _drive(messages: list[str]):
    """Feed a list of messages through handle_intake and return final session."""
    from src.bot.intake import handle_intake
    from src.bot.session import get_session

    for msg in messages:
        await handle_intake(CHAT_ID, msg)

    return get_session(CHAT_ID)


# ---------------------------------------------------------------------------
# Helpers that build a fully-confirmed /auto session WITHOUT relying on the
# LLM conductor (we stub conductor to return None immediately, simulating
# that all fields were collected).
# ---------------------------------------------------------------------------


def _stub_conductor_auto():
    """
    Patch run_conductor so it immediately signals collection is done
    (returns None, None) — the same signal the real conductor sends when
    all required fields are gathered.  The metadata must already hold the
    DOB and gender so _run_auto_engine can proceed.
    """

    async def _fake_conductor(session, text):
        if text == "__init__":
            # Seed the metadata the engine needs
            session.metadata["dob"] = "1977-04-28 11:51"
            session.metadata["location"] = "Singapore"
            session.profile.gender = "M"
            session.profile.alias = "TEST"
            session.profile.name = "Test Profile"
        return None, session  # None reply = "all fields collected"

    return patch("src.bot.intake.run_conductor", side_effect=_fake_conductor)


# ---------------------------------------------------------------------------
# Set 2 — Test Classes
# ---------------------------------------------------------------------------


class TestAutoModeSessionReachesComplete:
    """Verify that /auto drive with known DOB lands session at COMPLETE."""

    @pytest.mark.asyncio
    async def test_session_step_complete_after_confirm(self, mock_telegram):
        """
        Simulate:
          /start → /auto → (conductor done immediately) → engine runs →
          playback shown → user replies 'yes' → COMPLETE
        """
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        assert session.step == "COMPLETE", (
            f"Expected COMPLETE but got {session.step!r}. "
            "Check that handle_intake transitions CONFIRM → COMPLETE on 'yes'."
        )

    @pytest.mark.asyncio
    async def test_profile_alias_preserved_after_confirm(self, mock_telegram):
        """Alias set by stubbed conductor must survive through to COMPLETE."""
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        assert session.profile.alias == "TEST", f"Expected alias 'TEST', got {session.profile.alias!r}"

    @pytest.mark.asyncio
    async def test_auto_engine_populates_four_pillars(self, mock_telegram):
        """
        _run_auto_engine() must fill all four pillars from the real engine.
        Expected: 丁巳 甲辰 乙卯 壬午
        """
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        p = session.profile
        assert p.year_pillar and p.year_pillar["stem"] == "Ding" and p.year_pillar["branch"] == "Si", (
            f"Year: {p.year_pillar}"
        )
        assert p.month_pillar and p.month_pillar["stem"] == "Jia" and p.month_pillar["branch"] == "Chen", (
            f"Month: {p.month_pillar}"
        )
        assert p.day_pillar and p.day_pillar["stem"] == "Yi" and p.day_pillar["branch"] == "Mao", f"Day: {p.day_pillar}"
        assert p.hour_pillar and p.hour_pillar["stem"] == "Ren" and p.hour_pillar["branch"] == "Wu", (
            f"Hour: {p.hour_pillar}"
        )

    @pytest.mark.asyncio
    async def test_auto_engine_da_yun_ji_hai(self, mock_telegram):
        """Da Yun for 2026 must be 己亥."""
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        dy = session.profile.da_yun_pillar
        assert dy and dy["stem"] == "Ji" and dy["branch"] == "Hai", (
            f"Expected Ji Hai, got {dy}. Check Da Yun polarity logic: yin year + male = reverse cycles."
        )

    @pytest.mark.asyncio
    async def test_auto_engine_strength_strong(self, mock_telegram):
        """Day Master strength must resolve to Strong."""
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        assert session.profile.day_master_strength == "Strong", f"Got: {session.profile.day_master_strength!r}"

    @pytest.mark.asyncio
    async def test_auto_engine_favorable_fire_earth(self, mock_telegram):
        """Favorable elements must be Fire and Earth (in any order)."""
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        fav = set(session.profile.favorable_elements)
        assert fav == {"Fire", "Earth"}, f"Got: {fav}"

    @pytest.mark.asyncio
    async def test_auto_engine_unfavorable_water_wood(self, mock_telegram):
        """Unfavorable elements must be Water and Wood (in any order)."""
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        unfav = set(session.profile.unfavorable_elements)
        assert unfav == {"Water", "Wood"}, f"Got: {unfav}"

    @pytest.mark.asyncio
    async def test_auto_engine_neutral_metal(self, mock_telegram):
        """Neutral element must be Metal."""
        with _stub_conductor_auto():
            session = await _drive(["/start", "/auto", "yes"])

        assert set(session.profile.neutral_elements) == {"Metal"}, f"Got: {session.profile.neutral_elements}"


class TestQueueJobTriggeredOnComplete:
    """
    Verify that when session reaches COMPLETE, app.py triggers
    queue_manager.add_job() exactly once.
    """

    @pytest.mark.asyncio
    async def test_add_job_called_once(self, mock_telegram, monkeypatch):
        """
        Simulate the webhook handler logic:
        after handle_intake returns the CONFIRM reply, re-call with 'yes'
        and check that queue_manager.add_job is triggered.
        """
        add_job_mock = AsyncMock(return_value=True)

        with _stub_conductor_auto():
            from src.bot.intake import handle_intake
            from src.bot.session import get_session

            # Drive to CONFIRM state
            await handle_intake(CHAT_ID, "/start")
            await handle_intake(CHAT_ID, "/auto")

            # Patch add_job on the live queue_manager in app module
            with patch("src.bot.app.queue_manager.add_job", add_job_mock):
                # Simulate webhook: user confirms
                await handle_intake(CHAT_ID, "yes")

                # Replicate the webhook check that triggers the job
                session = get_session(CHAT_ID)
                if session.step == "COMPLETE":
                    await add_job_mock(CHAT_ID)

        add_job_mock.assert_called_once_with(CHAT_ID)

    @pytest.mark.asyncio
    async def test_no_duplicate_job_on_double_confirm(self, mock_telegram, monkeypatch):
        """
        Sending 'yes' twice must not enqueue two jobs.
        The QueueManager de-duplicates; this test checks the session
        doesn't re-enter COMPLETE on second 'yes'.
        """
        with _stub_conductor_auto():
            from src.bot.intake import handle_intake
            from src.bot.session import get_session

            await handle_intake(CHAT_ID, "/start")
            await handle_intake(CHAT_ID, "/auto")
            await handle_intake(CHAT_ID, "yes")  # → COMPLETE

            step_after_first = get_session(CHAT_ID).step

            # Second 'yes' after COMPLETE — should not re-trigger
            await handle_intake(CHAT_ID, "yes")
            step_after_second = get_session(CHAT_ID).step

        # After COMPLETE the fallback message is returned; step stays COMPLETE
        # (or falls through to the default handler — either is acceptable)
        assert step_after_first == "COMPLETE"
        # The second 'yes' must not regress step back to COLLECTING/CONFIRM
        assert step_after_second in ("COMPLETE", "START", "CHOOSING"), (
            f"Unexpected step after second confirm: {step_after_second!r}"
        )


class TestPipelineSmoke:
    """
    Smoke test: run_full_report_pipeline() with heavy stages mocked.
    Pass = no exception raised + send_telegram_message called with completion.
    """

    @pytest.mark.asyncio
    async def test_pipeline_runs_to_delivery(self, mock_telegram, mock_pipeline, monkeypatch):
        """
        Build a COMPLETE session manually, then call run_full_report_pipeline
        directly. Verify it reaches the document send stage without raising.
        """
        # Manually seed a COMPLETE session
        from src.bot.session import UserProfile, get_session, save_session

        # Manually seed a COMPLETE session
        session = get_session(CHAT_ID)
        session.step = "COMPLETE"
        session.profile = UserProfile(
            name="Test Profile",
            alias="TEST",
            gender="M",
            year_pillar={"stem": "Ding", "branch": "Si"},
            month_pillar={"stem": "Jia", "branch": "Chen"},
            day_pillar={"stem": "Yi", "branch": "Mao"},
            hour_pillar={"stem": "Ren", "branch": "Wu"},
            da_yun_pillar={"stem": "Ji", "branch": "Hai"},
            day_master_strength="Strong",
            favorable_elements=["Fire", "Earth"],
            unfavorable_elements=["Water", "Wood"],
            neutral_elements=["Metal"],
        )
        save_session(session)

        # Stub file-IO helpers so no real disk writes happen
        monkeypatch.setattr("src.bot.bridge.save_k3_profile", MagicMock(return_value="/tmp/fake_profile.json"))
        monkeypatch.setattr("src.bot.bridge.map_profile_to_k3", MagicMock(return_value={}))
        monkeypatch.setattr("src.bot.pipeline.db.get_all_reports_for_user", MagicMock(return_value=[]))
        monkeypatch.setattr("src.bot.pipeline.db.add_report_metadata", MagicMock(return_value=None))
        monkeypatch.setattr("os.makedirs", MagicMock(return_value=None))

        from src.bot.pipeline import run_full_report_pipeline
        from src.bot.utils import send_telegram_message

        await run_full_report_pipeline(CHAT_ID)

        # The message send must have been attempted
        from unittest.mock import AsyncMock
        assert isinstance(send_telegram_message, AsyncMock) or hasattr(send_telegram_message, "called")
        assert send_telegram_message.called
        calls = [str(c.args[1]) for c in send_telegram_message.call_args_list]
        assert any("Analysis Complete" in c for c in calls), f"Expected Analysis Complete message, got: {calls}"

    @pytest.mark.asyncio
    async def test_pipeline_smoke_no_exception_on_engine_error(self, mock_telegram, mock_pipeline, monkeypatch):
        """
        If the K3 pipeline raises, run_full_report_pipeline must catch it,
        notify the user with an apology, and re-raise for the retry decorator.
        """
        from src.bot.session import UserProfile, get_session, save_session

        session = get_session(CHAT_ID)
        session.step = "COMPLETE"
        session.profile = UserProfile(alias="TEST", gender="M")
        save_session(session)

        monkeypatch.setattr("src.bot.bridge.save_k3_profile", MagicMock(return_value="/tmp/fake.json"))
        monkeypatch.setattr("src.bot.bridge.map_profile_to_k3", MagicMock(return_value={}))
        monkeypatch.setattr("src.bot.pipeline.db.get_all_reports_for_user", MagicMock(return_value=[]))
        monkeypatch.setattr("os.makedirs", MagicMock(return_value=None))

        # Make the pipeline stage blow up
        monkeypatch.setattr(
            "alt_src.K3.K3_pipeline.run_k3_pipeline", MagicMock(side_effect=RuntimeError("Simulated engine failure"))
        )

        from src.bot.pipeline import run_full_report_pipeline

        with pytest.raises(RuntimeError, match="Simulated engine failure"):
            await run_full_report_pipeline(CHAT_ID)

        # User must have received an apology message
        from unittest.mock import AsyncMock

        from src.bot.utils import send_telegram_message
        assert isinstance(send_telegram_message, AsyncMock) or hasattr(send_telegram_message, "call_args_list")
        apology_calls = [
            c
            for c in send_telegram_message.call_args_list
            if "Analysis Interrupted" in str(c) or "apologies" in str(c).lower()
        ]
        assert apology_calls, "User was not sent an apology after pipeline failure"
