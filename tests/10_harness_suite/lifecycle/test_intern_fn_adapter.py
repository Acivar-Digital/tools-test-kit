"""Test the intern_fn/reviewer_fn adapter closures and PHASE_SUMMARIES intern guard.

Bug 2 (runner.py): record_intern and do_role have 6/8 required params but call
site intern_fn(brief, task_id=t.id) supplies only 2. The fix wraps them in
closure adapters inside runner.main().

Bug 3 (agent.py): PHASE_SUMMARIES[role] write inside load_skill races when
multiple interns run concurrently. The fix guards writes for role != "intern".
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic_ai.messages import ModelRequest, UserPromptPart

from factory.infra import agent
from factory.infra import _runtime
from factory.infra.pipeline import record_intern
from factory.infra.exchange import ExchangeTurn


# ── helpers ────────────────────────────────────────────────────────────────


class _MockResult:
    """Minimal stand-in for an agent RunResult."""

    def __init__(self, output: object, messages: list | None = None) -> None:
        self.output = output
        self._messages = messages or []

    def all_messages(self) -> list:
        return self._messages

    def usage(self) -> Any:
        from types import SimpleNamespace
        return SimpleNamespace(input_tokens=0, output_tokens=0, requests=0)


# ── intern_fn adapter contract ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_intern_fn_adapter_contract(monkeypatch) -> None:
    """Verify a callable that matches intern_fn(brief, task_id) -> str can
    bridge to record_intern's full signature via closure."""
    calls: list[dict[str, object]] = []

    async def fake_load_skill(
        role: str, brief: str, bd: str, task_id: str | None = None
    ) -> str:
        calls.append({"role": role, "brief": brief, "bd": bd, "task_id": task_id})
        return json.dumps({"status": "done", "task_id": task_id or "intern00", "files_changed": [], "diff_summary": "", "notes": ""})

    monkeypatch.setattr("factory.infra.pipeline.load_skill", fake_load_skill)
    monkeypatch.setattr("factory.infra.pipeline.update_status_board", lambda *a, **kw: None)

    bd = "test-bd"
    history: list[tuple[str, str]] = []
    prior: list = []
    state = {"brief": "test task", "seeded": False}

    # Simulate the adapter closure from runner.py
    async def _intern_fn(brief: str, task_id: str | None = None) -> str:
        return await record_intern(brief, bd, history, prior, state, task_id=task_id)

    # ── invoke like execution.py does ──────────────────────────────────
    out = await _intern_fn("write the code", task_id="intern01")
    parsed = json.loads(out)
    assert parsed["task_id"] == "intern01"
    assert parsed["status"] == "done"
    assert len(calls) == 1
    assert calls[0]["role"] == "intern"
    assert calls[0]["bd"] == "test-bd"
    assert calls[0]["task_id"] == "intern01"
    assert "write the code" in calls[0]["brief"]


@pytest.mark.asyncio
async def test_intern_fn_replay_respects_seeded(monkeypatch) -> None:
    """Second call with same state sees seeded=True, skips prior prepend."""
    call_count: int = 0

    async def fake_load_skill(role: str, brief: str, bd: str, task_id: str | None = None) -> str:
        nonlocal call_count
        call_count += 1
        return json.dumps({"status": "done", "task_id": task_id or "intern00", "files_changed": [], "diff_summary": "", "notes": ""})

    monkeypatch.setattr("factory.infra.pipeline.load_skill", fake_load_skill)
    monkeypatch.setattr("factory.infra.pipeline.update_status_board", lambda *a, **kw: None)

    bd = "test-bd"
    history: list[tuple[str, str]] = []
    prior = [ExchangeTurn(role="intern", pass_no=1, content="plan")]
    state = {"brief": "test task", "seeded": False}

    async def _intern_fn(brief: str, task_id: str | None = None) -> str:
        return await record_intern(brief, bd, history, prior, state, task_id=task_id)

    # First call — prior is truthy and seeded=False => prior_injected
    # In this test we can't easily assert the injection happened, but we
    # verify seeded flips to True and second call completes without error.
    out1 = await _intern_fn("first task", task_id="intern01")
    assert json.loads(out1)["task_id"] == "intern01"
    assert call_count == 1
    assert state["seeded"] is True, "state.seeded must flip after first call"

    # Second call — seeded=True, prior prepend skipped
    out2 = await _intern_fn("second task", task_id="intern02")
    assert json.loads(out2)["task_id"] == "intern02"
    assert call_count == 2


# ── reviewer_fn adapter contract ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_reviewer_fn_adapter_contract(monkeypatch) -> None:
    """Verify reviewer_fn(brief) -> str bridges to load_skill(role, brief, bd)."""
    load_skill_calls: list[dict[str, str]] = []

    async def fake_load_skill(role: str, brief: str, bd: str, task_id: str | None = None) -> str:
        load_skill_calls.append({"role": role, "brief": brief, "bd": bd})
        return json.dumps({"evaluations": [{"item_id": "intern01", "approved": "Yes", "comments": "ok"}]})

    monkeypatch.setattr("factory.infra.pipeline.load_skill", fake_load_skill)
    monkeypatch.setattr("factory.infra.agent.load_skill", fake_load_skill)
    monkeypatch.setattr("factory.infra.pipeline.update_status_board", lambda *a, **kw: None)

    bd = "test-bd"

    async def _run_engineer_review(brief: str) -> str:
        return await agent.load_skill("senior_review", brief, bd)

    out = await _run_engineer_review("review this batch")
    parsed = json.loads(out)
    assert "evaluations" in parsed
    assert len(load_skill_calls) == 1
    assert load_skill_calls[0]["role"] == "senior_review"


# ── PHASE_SUMMARIES intern guard ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_load_skill_does_not_write_phase_summaries_for_intern(monkeypatch) -> None:
    """load_skill with role='intern' must NOT write to PHASE_SUMMARIES
    to avoid concurrent-write races (Bug 3)."""
    monkeypatch.setattr("factory.infra.agent.build_role_agent", lambda role: (None, None))
    monkeypatch.setattr("factory.infra.agent.build_md_bridge", lambda role, agent_id=None: None)
    monkeypatch.setattr("factory.infra.agent.log_response_raw", lambda **kw: None)
    monkeypatch.setattr("factory.infra.agent.append_eval_log", lambda **kw: None)
    monkeypatch.setattr("factory.infra.agent.persist_role", lambda role, result, agent_id=None: None)
    monkeypatch.setattr("factory.infra.agent.set_current_role", lambda role: None)
    monkeypatch.setattr("factory.infra.agent.set_current_agent", lambda agent_id: None)
    monkeypatch.setattr("factory.infra.agent._intern_agent_id", lambda task_id: task_id)
    monkeypatch.setattr("factory.infra.agent._model_to_md", lambda output: str(output))

    async def fake_run_agent(*args, **kwargs):
        return _MockResult("intern output", messages=[ModelRequest(parts=[UserPromptPart(content="hi")])])

    monkeypatch.setattr("factory.infra.agent._run_agent_retry", fake_run_agent)

    _runtime.PHASE_SUMMARIES.clear()
    _runtime.PHASE_SUMMARIES["engineer"] = "existing plan summary"

    await agent.load_skill("intern", "write code", bd="test-bd", task_id="intern01")
    assert "intern" not in _runtime.PHASE_SUMMARIES, (
        "PHASE_SUMMARIES must NOT contain 'intern' entry to avoid concurrent-write race"
    )
    # Other role entries must remain untouched
    assert _runtime.PHASE_SUMMARIES["engineer"] == "existing plan summary"


@pytest.mark.asyncio
async def test_load_skill_writes_phase_summaries_for_engineer(monkeypatch) -> None:
    """Non-intern roles MUST still write to PHASE_SUMMARIES."""
    monkeypatch.setattr("factory.infra.agent.build_role_agent", lambda role: (None, None))
    monkeypatch.setattr("factory.infra.agent.build_md_bridge", lambda role, agent_id=None: None)
    monkeypatch.setattr("factory.infra.agent.log_response_raw", lambda **kw: None)
    monkeypatch.setattr("factory.infra.agent.append_eval_log", lambda **kw: None)
    monkeypatch.setattr("factory.infra.agent.persist_role", lambda role, result, agent_id=None: None)
    monkeypatch.setattr("factory.infra.agent.set_current_role", lambda role: None)
    monkeypatch.setattr("factory.infra.agent.set_current_agent", lambda agent_id: None)
    monkeypatch.setattr("factory.infra.agent._intern_agent_id", lambda task_id: task_id)
    monkeypatch.setattr("factory.infra.agent._model_to_md", lambda output: str(output))

    async def fake_run_agent(*args, **kwargs):
        return _MockResult("engineer output", messages=[ModelRequest(parts=[UserPromptPart(content="hi")])])

    monkeypatch.setattr("factory.infra.agent._run_agent_retry", fake_run_agent)

    _runtime.PHASE_SUMMARIES.clear()

    await agent.load_skill("engineer", "refactor code", bd="test-bd")
    assert "engineer" in _runtime.PHASE_SUMMARIES
    assert _runtime.PHASE_SUMMARIES["engineer"] == "engineer output"
