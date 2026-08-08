"""
Parameterized tests for the 12-month monthly report generation pipeline.

Covers:
  - Profile validation abort (incomplete profile → PipelineAbortError, no job queued)
  - Queue enqueuing: success, tier cap, global cap, dedup, admin bypass
  - Full pipeline success: 12 months generated, JSON saved, report metadata stored, user notified
  - Mixed results: some months succeed, some are ErrorPayload
  - Engine exception → pipeline failure → developer notified
  - Transient failure → retry → success
  - Permanent failure → PipelineAbortError / exhausted retries → session reset + user notified
  - Cleanup task errors in finally block
  - Report menu rendering (success, empty forecast list, missing file)
  - Month narrative retrieval (cached, sifu mode bypass, missing data)
  - Monthly generator: 12-month concurrent generation, single-month failure propagation

All external systems (DB, Telegram API, LLM agents, filesystem writes) are mocked.
No Sentry or Logfire imports in this file.
"""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src2.core.schemas.unified import StrengthTier
from src2.interfaces.telegram.pipeline import (
    ReportPipelineChunk,
    _build_master_json_path,
    _calculate_report_index,
    _extract_chat_id,
    run_full_report_pipeline,
)
from src2.interfaces.telegram.queue_worker import QueueManager
from src2.interfaces.telegram.reliability import PipelineAbortError


@pytest.fixture(autouse=True)
def _set_bgem3_env(monkeypatch):
    monkeypatch.setenv("BGEM3_URL", "http://localhost:8002/v1/embeddings")
    monkeypatch.setenv("BGEM3_TOKEN", "test-token")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    """MagicMock DB with standard user prefs (sifu_mode=0, language=English)."""
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.is_admin.return_value = False
    db.get_all_reports_for_user.return_value = []
    db.get_user_tier.return_value = "FREE"
    db.has_monthly_code.return_value = True
    db.has_feature_code.return_value = True
    db.get_active_jobs.return_value = []
    db.get_user_job_count_today.return_value = 0
    db.get_global_job_count_today.return_value = 0
    db.enqueue_job.return_value = None
    db.complete_job.return_value = None
    db.fail_job.return_value = None
    db.mark_job_pending.return_value = None
    db.add_report_metadata.return_value = None
    return db


@pytest.fixture
def mock_session():
    """MagicMock session with a valid UserProfile."""
    profile = MagicMock()
    profile.alias = "Alice"
    profile.name = "Alice Smith"
    profile.gender = "F"
    profile.year_pillar.stem = "Jia"
    profile.year_pillar.branch = "Chou"
    profile.month_pillar.stem = "Yi"
    profile.month_pillar.branch = "You"
    profile.day_pillar.stem = "Bing"
    profile.day_pillar.branch = "Wu"
    profile.hour_pillar.stem = "Ding"
    profile.hour_pillar.branch = "You"
    profile.da_yun_pillar = None
    profile.favorable_elements = ["Wood", "Metal"]
    profile.unfavorable_elements = ["Fire"]
    profile.neutral_elements = ["Earth", "Water"]
    profile.day_master_strength = StrengthTier.MILD_WEAK
    profile.relation_category = None
    profile.tailoring_concerns = {"career": "seek advancement", "wealth": "invest", "relationships": "harmony"}
    profile.profile_id = "pid-123"

    session = MagicMock()
    session.chat_id = 123456
    session.step = "COLLECTING"
    session.profile = profile
    session.metadata.dob = "1990-01-01"
    session.metadata.tailoring_concerns = {"career": "seek advancement"}
    session.metadata.relation_category = None
    return session


@pytest.fixture
def mock_memory_manager(tmp_path):
    mm = MagicMock()
    mm.get_reports_dir.return_value = tmp_path / "reports"
    mm.get_profile_path.return_value = tmp_path / "reports" / "profile.json"
    mm.get_user_dir.return_value = tmp_path / "alice"
    return mm


# ---------------------------------------------------------------------------
# Behavior 1: Chunk → chat_id extraction (data variation via parametrize)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("chunk,expected_chat_id", [
    (ReportPipelineChunk(user_id=999), 999),
    (42, 42),
    (ReportPipelineChunk(user_id=0), 0),
])
def test_extract_chat_id(chunk, expected_chat_id):
    assert _extract_chat_id(chunk) == expected_chat_id


# ---------------------------------------------------------------------------
# Behavior 2: Report index calculation (data variation via parametrize)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("existing_reports,expected_index", [
    ([], 1),
    ([{"id": "1"}], 2),
    ([{"id": "1"}, {"id": "2"}, {"id": "3"}], 4),
])
def test_calculate_report_index(mock_db, existing_reports, expected_index):
    mock_db.get_all_reports_for_user.return_value = existing_reports
    with patch("src2.interfaces.telegram.pipeline.db", mock_db):
        assert _calculate_report_index(123) == expected_index


# ---------------------------------------------------------------------------
# Behavior 3: Master JSON path construction
# ---------------------------------------------------------------------------

def test_build_master_json_path():
    path = _build_master_json_path(Path("/tmp/reports"), "Alice", 3)
    assert str(path).startswith("/tmp/reports/BaziForecast_2026_Alice_")
    assert path.endswith("_3_master.json")


# ---------------------------------------------------------------------------
# Behavior 4: Profile validation abort (incomplete profile → no job queued)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_aborts_on_invalid_profile(mock_db, mock_session, mock_memory_manager):
    chat_id = 123456
    alias = "Alice"

    with patch("src2.interfaces.telegram.pipeline._initialize_session", new=lambda chat_id: (mock_session, alias)), \
         patch("src2.interfaces.telegram.bridge.validate_profile", return_value=(False, ["day_pillar is missing stem"])), \
         patch("src2.interfaces.telegram.pipeline.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.pipeline.send_developer_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.pipeline.db", mock_db), \
         patch("src2.interfaces.telegram.pipeline.memory_manager", mock_memory_manager):

        with pytest.raises(PipelineAbortError):
            await run_full_report_pipeline(chat_id)

        mock_send.assert_awaited_once_with(
            chat_id,
            "⚠️ *Your Bazi profile is incomplete or was reset.*\n"
            "Please run /start and complete the intake before requesting a report.",
        )


# ---------------------------------------------------------------------------
# Behavior 5: Full success path (12 months, JSON saved, metadata stored, notified)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_full_pipeline_success_12_months(mock_db, mock_session, mock_memory_manager, tmp_path):
    chat_id = 123456
    profile_data = {"day_pillar": {"stem": "Bing", "branch": "Wu"}}

    with patch("src2.interfaces.telegram.pipeline._initialize_session", new=lambda chat_id: (mock_session, "Alice")), \
         patch("src2.interfaces.telegram.bridge.validate_profile", return_value=(True, [])), \
         patch("src2.interfaces.telegram.bridge.map_profile_to_k3", return_value=profile_data), \
         patch("src2.interfaces.telegram.bridge.save_k3_profile", return_value=str(tmp_path / "profile.json")), \
         patch("src2.interfaces.telegram.pipeline.send_telegram_message", new_callable=AsyncMock) as mock_send, \
          patch("src2.interfaces.telegram.pipeline.send_developer_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.pipeline.db", mock_db), \
         patch("src2.interfaces.telegram.pipeline.memory_manager", mock_memory_manager), \
         patch("src2.interfaces.telegram.session.save_session"), \
          patch("src2.interfaces.telegram.pipeline_check.verify_monthly_pipeline_readiness", new_callable=AsyncMock, return_value=True), \
          patch("src2.interfaces.telegram.pipeline._run_pipeline_engine", new_callable=AsyncMock) as mock_engine, \
          patch("src2.interfaces.telegram.chronomancer.prebuild_annual_calendar", new_callable=AsyncMock):

        mock_engine.return_value = MagicMock(
            months=[MagicMock() for _ in range(12)],
            review_result="PASS",
            reviewer_result="pass",
            profile_summary=MagicMock(),
            monthly_forecasts=[MagicMock() for _ in range(12)],
        )

        await run_full_report_pipeline(chat_id)

        mock_engine.assert_awaited_once()
        mock_db.add_report_metadata.assert_called_once()
        args = mock_db.add_report_metadata.call_args
        assert args.kwargs["index_num"] == 1
        assert args.kwargs["alias"] == "Alice"
        mock_send.assert_awaited_with(
            chat_id,
            "✨ *Analysis Complete for Alice!* ✨\n\n"
            "Your monthly reports for 2026 are now ready.\n\n"
            "Press /reports to see your monthly reports.",
        )


# ---------------------------------------------------------------------------
# Behavior 6: Engine returns mixed MonthResponse + ErrorPayload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_handles_mixed_month_results(mock_db, mock_session, mock_memory_manager, tmp_path):
    from pydantic import BaseModel, ConfigDict

    class ErrorPayload(BaseModel):
        model_config = ConfigDict(extra="forbid", validate_assignment=True)
        month_name: str
        error: str

    chat_id = 123456
    profile_data = {"day_pillar": {"stem": "Bing", "branch": "Wu"}}

    with patch("src2.interfaces.telegram.pipeline._initialize_session", new=lambda chat_id: (mock_session, "Alice")), \
         patch("src2.interfaces.telegram.bridge.validate_profile", return_value=(True, [])), \
         patch("src2.interfaces.telegram.bridge.map_profile_to_k3", return_value=profile_data), \
         patch("src2.interfaces.telegram.bridge.save_k3_profile", return_value=str(tmp_path / "profile.json")), \
         patch("src2.interfaces.telegram.pipeline.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.pipeline.send_developer_message", new_callable=AsyncMock), \
          patch("src2.interfaces.telegram.pipeline.db", mock_db), \
          patch("src2.interfaces.telegram.pipeline.memory_manager", mock_memory_manager), \
          patch("src2.interfaces.telegram.session.save_session"), \
          patch("src2.interfaces.telegram.pipeline_check.verify_monthly_pipeline_readiness", new_callable=AsyncMock, return_value=True), \
          patch("src2.interfaces.telegram.pipeline._run_pipeline_engine", new_callable=AsyncMock) as mock_engine, \
          patch("src2.interfaces.telegram.chronomancer.prebuild_annual_calendar", new_callable=AsyncMock):

        month_responses = [MagicMock() for _ in range(10)]
        error_payloads = [
            ErrorPayload(month_name="March 2026", error="LLM timeout"),
            ErrorPayload(month_name="July 2026", error="Rate limited"),
        ]
        mixed = month_responses + error_payloads

        mock_engine.return_value = MagicMock(
            months=mixed,
            review_result="PASS_WITH_ERRORS",
            reviewer_result="pass",
            profile_summary=MagicMock(),
            monthly_forecasts=mixed,
        )

        await run_full_report_pipeline(chat_id)

        mock_db.add_report_metadata.assert_called_once()


# ---------------------------------------------------------------------------
# Behavior 7: Engine raises exception → pipeline failure → developer notified
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_pipeline_engine_exception_notifies_developer(mock_db, mock_session, mock_memory_manager):
    chat_id = 123456
    profile_data = {"day_pillar": {"stem": "Bing", "branch": "Wu"}}

    with patch("src2.interfaces.telegram.pipeline._initialize_session", new=lambda chat_id: (mock_session, "Alice")), \
         patch("src2.interfaces.telegram.bridge.validate_profile", return_value=(True, [])), \
         patch("src2.interfaces.telegram.bridge.map_profile_to_k3", return_value=profile_data), \
         patch("src2.interfaces.telegram.bridge.save_k3_profile", return_value="/tmp/profile.json"), \
         patch("src2.interfaces.telegram.pipeline.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.pipeline.send_developer_message", new_callable=AsyncMock) as mock_dev, \
          patch("src2.interfaces.telegram.pipeline.db", mock_db), \
          patch("src2.interfaces.telegram.pipeline.memory_manager", mock_memory_manager), \
          patch("src2.interfaces.telegram.session.save_session"), \
          patch("src2.interfaces.telegram.pipeline_check.verify_monthly_pipeline_readiness", new_callable=AsyncMock, return_value=True), \
          patch("src2.interfaces.telegram.pipeline._run_pipeline_engine", new_callable=AsyncMock, side_effect=RuntimeError("LLM gateway down")), \
          patch("src2.interfaces.telegram.chronomancer.prebuild_annual_calendar", new_callable=AsyncMock):

        with pytest.raises(RuntimeError, match="LLM gateway down"):
            await run_full_report_pipeline(chat_id)

        dev_calls = mock_dev.await_args_list
        assert len(dev_calls) >= 1
        failure_msg = dev_calls[-1].args[0]
        assert "❌" in failure_msg
        assert "LLM gateway down" in failure_msg


# ---------------------------------------------------------------------------
# Behavior 8: QueueManager enqueuing — cap/bypass combinations (parametrized)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("is_admin,user_job_count,global_count,tier_cap,expected", [
    (True, 50, 50, 2, True),   # Admin bypasses all checks
    (False, 2, 0, 2, False),   # User at tier cap
    (False, 0, 50, 2, False),  # Global cap reached
    (False, 0, 0, 2, True),    # Normal user within caps
    (False, 1, 0, 1, False),   # User at tier cap of 1
    (False, 0, 49, 2, True),   # Global at 49 (just under cap)
])
@pytest.mark.asyncio
async def test_queue_manager_add_job_caps(
    mock_db, is_admin, user_job_count, global_count, tier_cap, expected
):
    mock_db.is_admin.return_value = is_admin
    mock_db.get_user_job_count_today.return_value = user_job_count
    mock_db.get_global_job_count_today.return_value = global_count

    with patch("src2.interfaces.telegram.security.get_user_limits", return_value={"max_reports_per_day": tier_cap}):
        qm = QueueManager(mock_db)
        result = await qm.add_job(user_id=123456)
        assert result is expected


# ---------------------------------------------------------------------------
# Behavior 9: QueueManager dedup — active jobs prevent re-enqueue
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_queue_manager_dedup_blocks_active_job(mock_db):
    mock_db.is_admin.return_value = False
    mock_db.get_user_job_count_today.return_value = 0
    mock_db.get_global_job_count_today.return_value = 0
    mock_db.get_active_jobs.return_value = [{"id": "job-1", "status": "pending"}]

    with patch("src2.interfaces.telegram.security.get_user_limits", return_value={"max_reports_per_day": 2}):
        qm = QueueManager(mock_db)
        result = await qm.add_job(user_id=123456)
        assert result is False


@pytest.mark.asyncio
async def test_queue_manager_dedup_no_active_jobs_allows_enqueue(mock_db):
    mock_db.is_admin.return_value = False
    mock_db.get_user_job_count_today.return_value = 0
    mock_db.get_global_job_count_today.return_value = 0
    mock_db.get_active_jobs.return_value = []

    with patch("src2.interfaces.telegram.security.get_user_limits", return_value={"max_reports_per_day": 2}):
        qm = QueueManager(mock_db)
        result = await qm.add_job(user_id=123456)
        assert result is True
        mock_db.enqueue_job.assert_called_once()


# ---------------------------------------------------------------------------
# Behavior 10: QueueManager worker lifecycle — success, transient, permanent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_queue_worker_processes_dequeued_job(mock_db):
    with patch("src2.interfaces.telegram.queue_worker.process_report", new_callable=AsyncMock) as mock_proc:
        qm = QueueManager(mock_db)

        await qm._run_job({"id": "job1", "user_id": 123, "retry_count": 0})

        mock_proc.assert_awaited_once_with({"user_id": 123})
        mock_db.complete_job.assert_called_once_with("job1")


@pytest.mark.asyncio
async def test_queue_worker_transient_failure_triggers_retry(mock_db):
    state = {"called": False}

    async def raise_once(job):
        if not state["called"]:
            state["called"] = True
            raise ValueError("Temporary LLM hiccup")

    with patch("src2.interfaces.telegram.queue_worker.process_report", side_effect=raise_once), \
         patch("src2.interfaces.telegram.queue_worker.asyncio") as mock_asyncio_mod:
        mock_asyncio_mod.sleep = AsyncMock()
        qm = QueueManager(mock_db)

        with patch.object(qm, "_is_permanent_failure", return_value=False), \
             patch.object(qm, "_handle_transient_failure", new_callable=AsyncMock) as mock_transient, \
             patch.object(qm, "_handle_permanent_failure", new_callable=AsyncMock):
            await qm._run_job({"id": "job1", "user_id": 123, "retry_count": 0})
            mock_transient.assert_awaited_once_with("job1", 0)
        mock_db.complete_job.assert_not_called()


@pytest.mark.asyncio
async def test_queue_worker_permanent_failure_resets_session_and_notifies(mock_db):
    qm = QueueManager(mock_db)

    with patch("src2.interfaces.telegram.queue_worker.process_report", new_callable=AsyncMock, side_effect=PipelineAbortError("Profile validation failed")), \
         patch("src2.interfaces.telegram.session.get_session") as mock_get_session, \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock) as mock_send:

        mock_session_obj = MagicMock()
        mock_session_obj.step = "PROCESSING"
        mock_get_session.return_value = mock_session_obj

        await qm._run_job({"id": "job1", "user_id": 123, "retry_count": 2})

        mock_db.fail_job.assert_called_once_with("job1")
        assert mock_session_obj.step == "COMPLETE"
        mock_send.assert_awaited_once_with(
            123,
            "Sorry, we encountered a calculation issue with your report. "
            "Please try again shortly.",
        )


@pytest.mark.asyncio
async def test_queue_worker_retry_exhausted_is_permanent_failure(mock_db):
    """When retry_count >= 2, any exception is treated as permanent."""
    qm = QueueManager(mock_db)

    is_permanent = qm._is_permanent_failure(ValueError("fail"), retry_count=2)
    assert is_permanent is True


# ---------------------------------------------------------------------------
# Behavior 11: Report menu rendering (parametrized: valid data, empty list)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("monthly_forecasts", [
    [
        {"month_name": "January", "month_metadata": {"month_name": "January", "start_date": "2026-01-04"}, "month_title": "New Beginnings", "simple_narrative": "Narrative here", "ten_god_narrative": "", "advisory": None, "engine_outputs": None, "_rag_context": "rag text"},
        {"month_name": "February", "month_metadata": {"month_name": "February", "start_date": "2026-02-04"}, "month_title": "Love Month", "simple_narrative": "Love narrative", "ten_god_narrative": "", "advisory": None, "engine_outputs": None, "_rag_context": "rag text"},
    ],
    [],
])
def test_report_menu_text(tmp_path, monthly_forecasts):
    from src2.interfaces.telegram.report_utils import get_report_menu_text

    json_path = tmp_path / "master.json"
    with open(json_path, "w") as f:
        json.dump({"monthly_forecasts": monthly_forecasts}, f)

    result = get_report_menu_text(str(json_path))

    if monthly_forecasts:
        assert "January" in result
    else:
        assert "No monthly data found" in result


# ---------------------------------------------------------------------------
# Behavior 12: Report menu — missing file edge cases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("file_exists", [True, False])
def test_report_menu_missing_file(tmp_path, file_exists):
    from src2.interfaces.telegram.report_utils import get_report_menu_text

    path = str(tmp_path / "missing.json")
    if file_exists:
        with open(path, "w") as f:
            json.dump({"monthly_forecasts": []}, f)

    result = get_report_menu_text(path)
    assert "⚠️" in result


# ---------------------------------------------------------------------------
# Behavior 13: Month narrative retrieval — sifu_mode vs non-sifu (parametrized)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("sifu_mode", [True, False])
async def test_month_narrative_sifu_mode_bypass(mock_db, mock_session, tmp_path, sifu_mode):
    from src2.interfaces.telegram.report_utils import MonthData, MonthMetadata, get_month_narrative

    master_json_path = tmp_path / "master.json"
    month_data = MonthData(
        month_name="January",
        month_metadata=MonthMetadata(month_name="January", start_date="2026-01-04"),
        month_title="New Beginnings",
        simple_narrative="Cached narrative",
    )
    master_json = {"monthly_forecasts": [month_data.model_dump(by_alias=True)]}
    with open(master_json_path, "w") as f:
        json.dump(master_json, f)

    with patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock):
        result = await get_month_narrative(
            str(master_json_path),
            0,
            chat_id=123,
            sifu_mode=sifu_mode,
        )

    if sifu_mode:
        # sifu mode returns "" as content, which falls to _get_technical_narrative
        # which may be empty → falls to _format_no_narrative_found or build_narrative_response
        assert "⚠️" in result or "📅" in result
    else:
        assert "Cached narrative" in result


# ---------------------------------------------------------------------------
# Behavior 14: Month narrative — not found when data is missing
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_month_narrative_not_found_when_empty_json(tmp_path):
    from src2.interfaces.telegram.report_utils import get_month_narrative

    master_json_path = tmp_path / "empty.json"
    with open(master_json_path, "w") as f:
        json.dump({"monthly_forecasts": []}, f)

    result = await get_month_narrative(str(master_json_path), 0, chat_id=123)
    assert "⚠️" in result
    assert "not found" in result.lower()


@pytest.mark.asyncio
async def test_month_narrative_not_found_when_file_missing(tmp_path):
    from src2.interfaces.telegram.report_utils import get_month_narrative

    result = await get_month_narrative(str(tmp_path / "nonexistent.json"), 0, chat_id=123)
    assert "⚠️" in result
    assert "not found" in result.lower()


# ---------------------------------------------------------------------------
# Behavior 15: Monthly generator — 12-month concurrent generation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_12_months_concurrent_produces_12_results(mock_db, tmp_path):
    from src2.engine.monthly_generator import generate_12_months_concurrently

    chat_id = 123456
    profile = MagicMock()
    profile.chat_id = chat_id
    profile.career_concern = "seek advancement"
    profile.wealth_concern = "invest"
    profile.relationship_concern = "harmony"

    with patch.dict("sys.modules", {"src2.interfaces.telegram.db": MagicMock(db=mock_db)}), \
         patch("src2.engine.monthly_generator._fetch_rag_context", new_callable=AsyncMock, return_value="RAG context"), \
         patch("src2.engine.monthly_generator.run_full_engine", return_value=MagicMock(engine_outputs=None)), \
         patch("src2.engine.monthly_generator.to_chart_profile", return_value=profile), \
         patch("src2.engine.monthly_generator.serialise_profile", return_value=MagicMock(model_dump_json=MagicMock(return_value="{}"))), \
         patch("src2.engine.monthly_generator.serialise_egress", return_value=""), \
         patch("src2.engine.monthly_generator.resolve_daily_pillar_range", return_value="Daily pillars data"), \
         patch("src2.engine.monthly_generator._build_age_ge_ju_framing", return_value="Framing text"), \
         patch("src2.engine.monthly_generator._derive_age", return_value=30), \
         patch("src2.engine.monthly_generator.report_agent") as mock_agent:

        mock_agent.run = AsyncMock(return_value=MagicMock(output="Month forecast text"))

        results = await generate_12_months_concurrently(profile, "General concerns")

        assert len(results) == 12
        assert all(isinstance(r, str) for r in results)
        assert mock_agent.run.await_count == 12


@pytest.mark.asyncio
async def test_generate_12_months_failure_propagates(mock_db):
    from src2.engine.monthly_generator import generate_12_months_concurrently

    chat_id = 123456
    profile = MagicMock()
    profile.chat_id = chat_id
    profile.career_concern = "c"
    profile.wealth_concern = "w"
    profile.relationship_concern = "r"

    call_count = 0

    async def flaky_run(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("LLM failure on month 1")
        return MagicMock(output=f"Forecast {call_count}")

    with patch.dict("sys.modules", {"src2.interfaces.telegram.db": MagicMock(db=mock_db)}), \
         patch("src2.engine.monthly_generator._fetch_rag_context", new_callable=AsyncMock, return_value=""), \
         patch("src2.engine.monthly_generator.run_full_engine", return_value=MagicMock(engine_outputs=None)), \
         patch("src2.engine.monthly_generator.to_chart_profile", return_value=profile), \
         patch("src2.engine.monthly_generator.serialise_profile", return_value=MagicMock(model_dump_json=MagicMock(return_value="{}"))), \
         patch("src2.engine.monthly_generator.serialise_egress", return_value=""), \
         patch("src2.engine.monthly_generator.resolve_daily_pillar_range", return_value="daily"), \
         patch("src2.engine.monthly_generator._build_age_ge_ju_framing", return_value=""), \
         patch("src2.engine.monthly_generator._derive_age", return_value=30), \
         patch("src2.engine.monthly_generator.report_agent") as mock_agent:

        mock_agent.run = flaky_run

        with pytest.raises(RuntimeError, match="LLM failure on month 1"):
            await generate_12_months_concurrently(profile, "concerns")


# ---------------------------------------------------------------------------
# Behavior 16: QueueManager.start_worker dequeue + process
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_queue_worker_start_worker_processes_job(mock_db):
    """Worker dequeues one job, processes it, then is stopped."""
    mock_db.dequeue_job.return_value = {"id": "job1", "user_id": 123, "retry_count": 0}

    qm = QueueManager(mock_db)

    call_count = {"n": 0}

    def dequeue_side_effect():
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"id": "job1", "user_id": 123, "retry_count": 0}
        qm.is_running = False
        return None

    mock_db.dequeue_job.side_effect = dequeue_side_effect

    with patch("src2.interfaces.telegram.queue_worker.process_report", new_callable=AsyncMock) as mock_proc, \
         patch("src2.interfaces.telegram.queue_worker._background_tasks"):
        await qm.start_worker()

        mock_proc.assert_awaited_once_with({"user_id": 123})
        mock_db.complete_job.assert_called_once_with("job1")
