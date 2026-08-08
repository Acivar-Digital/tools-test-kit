"""Tests for string output resilience in the orchestrator runner."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))



class MockOutput:
    """Mock output object with no model_dump_json method."""
    def __init__(self, value: str):
        self.value = value

    def __str__(self):
        return self.value


class MockResult:
    """Mock RunResult with an output and usage."""
    def __init__(self, output: any):
        self.output = output
        self._messages = []

    def all_messages(self) -> list:
        return self._messages

    def usage(self) -> SimpleNamespace:
        return SimpleNamespace(input_tokens=0, output_tokens=0, requests=0)


@pytest.mark.asyncio
async def test_load_skill_string_output(monkeypatch) -> None:
    """Verify load_skill handles non-Pydantic string outputs and serializes cleanly."""
    from factory.infra import agent, _runtime
    monkeypatch.setattr("factory.infra.agent.build_role_agent", lambda role: (None, None))
    monkeypatch.setattr("factory.infra.agent.build_md_bridge", lambda role, agent_id=None: None)
    monkeypatch.setattr("factory.infra.agent.log_response_raw", lambda **kw: None)
    monkeypatch.setattr("factory.infra.agent.append_eval_log", lambda **kw: None)
    monkeypatch.setattr("factory.infra.agent.persist_role", lambda role, result, agent_id=None: None)

    mock_result = MockResult("This is a raw markdown or string plan output")
    async def fake_run_agent(*args, **kwargs):
        return mock_result

    monkeypatch.setattr("factory.infra.agent._run_agent_retry", fake_run_agent)
    
    validated_json = await agent.load_skill(role="intern", brief="Verify me", bd="dummy-bd")
    
    assert validated_json == "This is a raw markdown or string plan output"
    assert _runtime.RAW_OUTPUTS["intern"] == "This is a raw markdown or string plan output"
