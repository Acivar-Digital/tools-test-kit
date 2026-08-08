"""
End-to-end integration test for the report pipeline.

Scenario A — Happy path:
  1. User completes intake (profile persisted to DB)
  2. Job is enqueued
  3. Worker calls run_full_report_pipeline
  4. Validation passes → pipeline proceeds (heavy stages mocked)

Scenario B — Stale job after /start:
  1. User has a pending job in the queue
  2. User sends /start → session deleted + jobs cleared
  3. Worker calls run_full_report_pipeline
  4. Validation fails → PipelineAbortError raised (NOT ValueError)
     Queue worker catches it, marks job failed, does NOT retry 5 times.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.bot.bridge import validate_profile
from src.bot.db import Database
from src.bot.reliability import PipelineAbortError
from src.bot.session import UserProfile, delete_session, get_session, save_session


def _make_complete_profile() -> UserProfile:
    return UserProfile(
        year_pillar={"stem": "Jia", "branch": "Zi"},
        month_pillar={"stem": "Yi", "branch": "Chou"},
        day_pillar={"stem": "Bing", "branch": "Yin"},
        hour_pillar={"stem": "Ding", "branch": "Mao"},
        da_yun_pillar={"stem": "Wu", "branch": "Chen"},
        day_master_strength="Strong",
        favorable_elements=["Fire", "Earth"],
        unfavorable_elements=["Water"],
        gender="M",
        alias="IntegTest",
    )


@pytest.fixture
def user_id():
    return 987654321


@pytest.fixture(autouse=True)
def cleanup(user_id):
    """Ensure no leftover session or job for the test user."""
    delete_session(user_id)
    db = Database("bot.db")
    db.clear_user_jobs(user_id)
    yield
    delete_session(user_id)
    db.clear_user_jobs(user_id)


class TestHappyPath:
    @pytest.mark.asyncio
    async def test_pipeline_proceeds_with_valid_profile(self, user_id):
        """If the session has a complete profile, validation passes and the
        pipeline proceeds past the guard. Heavy stages are mocked."""
        # 1. Persist a complete session
        session = get_session(user_id)
        session.profile = _make_complete_profile()
        session.step = "PROCESSING"
        save_session(session)

        # Sanity: profile validates
        ok, errs = validate_profile(session.profile)
        assert ok, errs

        # 2. Call pipeline with everything mocked
        from src.bot.pipeline import run_full_report_pipeline

        with (
            patch("src.bot.pipeline.send_telegram_message", new_callable=AsyncMock) as mock_msg,
            patch("src.bot.pipeline.send_developer_message", new_callable=AsyncMock),
            patch("src.engine.prompt_engine.run_engine", new_callable=AsyncMock) as mock_k3,
            patch("src.memory.memory_manager.memory_manager.cleanup_old_runs", new_callable=AsyncMock),
        ):
            # Should NOT raise
            await run_full_report_pipeline({"user_id": user_id})

        # 3. Assert pipeline was entered (user got the "initialised" message)
        calls = [str(c.args[1]) for c in mock_msg.call_args_list]
        assert any("Chronomancer" in c for c in calls), f"Expected pipeline start message, got: {calls}"

        # 4. Heavy stages were invoked
        mock_k3.assert_awaited_once()


class TestStaleJob:
    @pytest.mark.asyncio
    async def test_pipeline_aborts_gracefully_on_missing_profile(self, user_id):
        """If the session is missing/deleted, the guard must raise
        PipelineAbortError (not ValueError) so the queue worker does not
        retry 5 times."""
        # 1. Ensure NO session exists
        delete_session(user_id)
        session = get_session(user_id)
        assert session.profile.year_pillar is None  # truly empty

        from src.bot.pipeline import run_full_report_pipeline

        with (
            patch("src.bot.pipeline.send_telegram_message", new_callable=AsyncMock) as mock_msg,
            patch("src.bot.pipeline.send_developer_message", new_callable=AsyncMock),
        ):
            with pytest.raises(PipelineAbortError):
                await run_full_report_pipeline({"user_id": user_id})

        # 2. User must have been told to re-run /start
        calls = [str(c.args[1]) for c in mock_msg.call_args_list]
        assert any("incomplete or was reset" in c for c in calls), f"Expected user warning, got: {calls}"

    @pytest.mark.asyncio
    async def test_start_clears_pending_jobs(self, user_id):
        """When /start is issued, pending jobs for that user are wiped."""
        db = Database("bot.db")

        # Enqueue a job
        db.enqueue_job(user_id)
        active_before = db.get_active_jobs(user_id)
        assert len(active_before) == 1

        # Simulate /start handler
        delete_session(user_id)
        db.clear_user_jobs(user_id)

        active_after = db.get_active_jobs(user_id)
        assert len(active_after) == 0
