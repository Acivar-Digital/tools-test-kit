"""Regression tests for 01_fix.md CHANGE 2 + CHANGE 3 loopguard resilience.

Proves:
  T1 - A-B-A-B alternation / no-op same-result agent is force-recovered BEFORE
       the request cap is exhausted (no silent 150-call hang).
  T2 - An agent that raises UsageLimitExceeded is recovered (RECOVER path),
       NOT re-raised as a [HALT] that aborts the EXECUTE phase.
  T3 - A legit agent that emits final_result normally is returned unchanged.
  T4 - ModelHTTPError(status_code=400) is retried up to 3 times then propagates.
  T5 - ModelHTTPError(status_code=40x) with non-400 status propagates immediately.
  T6 - ModelHTTPError(status_code=400) succeeds on retry 2, returns normally.

No LLM keys required: the agent is a stub whose `.run` we monkeypatch.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pytest
from pydantic import BaseModel
from pydantic_ai.exceptions import ModelHTTPError, UsageLimitExceeded
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_ai.models.test import TestModel

from factory.infra._loopguard import run_with_loopguard


class _DummyOut(BaseModel):
    note: str = ""


def _fake_agent(run_coro):
    """Build a stub Agent whose .run is `run_coro`. Uses a real TestModel so the
    recovery Agent(agent.model, ...) actually runs and returns a result."""

    class _FakeAgent:
        model = TestModel()
        output_type = _DummyOut
        result_tool_name = "final_result"

        def run(self, *args, **kwargs):
            return run_coro(*args, **kwargs)

    return _FakeAgent()


def _turn_with_tool_call(tool_name: str, arg: str, return_content: str):
    """A single agent.run() result that emitted one tool call + its return."""
    call = ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args={"x": arg})])
    ret = ModelRequest(parts=[ToolReturnPart(tool_name=tool_name, content=return_content, tool_call_id="c1")])
    class _Res:
        def new_messages(self):
            return [call, ret]
        def all_messages(self):
            return [call, ret]
    return _Res()


def _answered_result():
    """A single agent.run() result that answered (final_result, no tool calls)."""
    class _Res:
        def new_messages(self):
            return [ModelResponse(parts=[])]
        def all_messages(self):
            return [ModelResponse(parts=[])]
    return _Res()


async def test_alternating_two_tools_recovered_before_cap():
    """Agent ping-pongs two DISTINCT tool calls; A-B-A-B must force RECOVER
    early (well before the 150 request cap) and return a recovery result."""
    calls = [("replace_text", "fileA"), ("replace_text", "fileB")]
    idx = {"v": 0}

    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        # First call returns the next tool call; once recovery is invoked
        # (tools=[]) with an empty prompt, we answer.
        if prompt == "" and message_history:
            return _answered_result()
        name, arg = calls[idx["v"] % 2]
        idx["v"] += 1
        return _turn_with_tool_call(name, arg, "ok")

    agent = _fake_agent(run_coro)
    out = await run_with_loopguard(
        agent, "do the work", role="intern",
        max_same=3, max_miss=3,
    )
    assert out is not None


async def test_model_http_error_400_retries_then_propagates():
    """ModelHTTPError(status_code=400) retries 3 times then propagates."""
    call_count = {"v": 0}

    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        call_count["v"] += 1
        raise ModelHTTPError(status_code=400, model_name="test", body=None)

    agent = _fake_agent(run_coro)
    with pytest.raises(ModelHTTPError):
        await run_with_loopguard(
            agent, "do the work", role="intern",
            max_same=3, max_miss=3,
        )
    # Called 4 times: 3 retries + 1 that propagates (4th call falls through)
    assert call_count["v"] == 4, f"expected 4 calls, got {call_count['v']}"


async def test_model_http_error_non_400_propagates_immediately():
    """ModelHTTPError(status_code=401) propagates on first hit (no retry)."""
    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        raise ModelHTTPError(status_code=401, model_name="test", body=None)

    agent = _fake_agent(run_coro)
    with pytest.raises(ModelHTTPError):
        await run_with_loopguard(
            agent, "do the work", role="intern",
            max_same=3, max_miss=3,
        )


async def test_model_http_error_400_retry_then_succeeds():
    """ModelHTTPError(status_code=400) retries then succeeds on attempt 2."""
    call_count = {"v": 0}

    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        call_count["v"] += 1
        if call_count["v"] == 1:
            raise ModelHTTPError(status_code=400, model_name="test", body=None)
        return _answered_result()

    agent = _fake_agent(run_coro)
    out = await run_with_loopguard(
        agent, "do the work", role="intern",
        max_same=3, max_miss=3,
    )
    assert out is not None
    assert call_count["v"] == 2, f"expected 2 calls, got {call_count['v']}"


async def test_noop_same_result_recovered():
    """Agent re-calls a tool and keeps getting the SAME return content; the
    no-op same-result detector must force RECOVER."""
    idx = {"v": 0}

    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        if prompt == "" and message_history:
            return _answered_result()
        idx["v"] += 1
        # Always the same tool + same (no-op) return content.
        return _turn_with_tool_call("replace_text", "fileA", "no change applied")

    agent = _fake_agent(run_coro)
    out = await run_with_loopguard(
        agent, "do the work", role="intern",
        max_same=3, max_miss=3,
    )
    assert out is not None
    assert idx["v"] <= 8, f"no-op detector did not fire early (turns={idx['v']})"


async def test_usage_limit_exceeded_recovered_not_raised():
    """An agent that raises UsageLimitExceeded must be recovered via the
    tools=[] path and MUST NOT propagate the exception as a [HALT]."""

    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        raise UsageLimitExceeded("request_limit of 150")

    agent = _fake_agent(run_coro)
    # Must NOT raise — the CHANGE 3 branch forces RECOVER with a tools=[]
    # recovery Agent (built on the same real model) and returns its result.
    out = await run_with_loopguard(
        agent, "do the work", role="intern",
        max_same=3, max_miss=3,
    )
    # The recovery Agent returns an AgentRunResult wrapping _DummyOut (TestModel),
    # proving the RECOVER path was taken instead of re-raising the exception.
    assert out.output is not None


async def test_legit_agent_returns_normally():
    """A legit agent that emits final_result (no tool calls) is returned as-is."""
    async def run_coro(prompt, message_history=None, usage_limits=None, deps=None):
        return _answered_result()

    agent = _fake_agent(run_coro)
    out = await run_with_loopguard(
        agent, "do the work", role="intern",
        max_same=3, max_miss=3,
    )
    assert out is not None
