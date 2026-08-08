"""BIFR Step 2 (Intercept) — GOLD harness test.

Asserts that when the LLM returns INVALID structured output, the harness does NOT
silently spin: it catches ``pydantic_core.ValidationError`` (and ``ModelRetry``),
records it through ``HarnessProbe`` into ``probe.validation_failures``, and persists
a ``fail_<phase>_<role>.json`` via ``_loopguard._dump_failure``.

No edits to production code. Deterministic — no LLM keys required.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import asyncio

import pydantic
import pytest
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.models.function import FunctionModel
from pydantic_core import ValidationError

from factory.infra import _loopguard as lg
from tests._probe import HarnessProbe

# ── Confirmed FunctionModel user_func signature (pydantic_ai 2.3.0) ──────────
# FunctionModel calls the user function as:
#     await function(messages: list[ModelMessage], agent_info: AgentInfo)
# where `agent_info.output_tools` is a list[ToolDefinition] (one per output type)
# and each ToolDefinition has `.name` (default "final_result" for a single
# output_type). This is NOT the (messages, model_settings, model_req_params) triple
# implied by the task brief — we adapt to the real signature here.
#
# Why we raise ValidationError from the function instead of returning a ToolCallPart
# with invalid args:
#   For an `output_type` agent, pydantic_ai wraps ANY output-validation failure into
#   `UnexpectedModelBehavior("Exceeded maximum output retries")` via
#   `_agent_graph.GraphAgentState.consume_output_retry` (see _agent_graph.py:
#   ModelRequestNode._build_retry_node -> consume_output_retry, and _output.py
#   validation handler -> ToolRetryError -> consume_output_retry). The raw
#   `ValidationError` therefore NEVER escapes `Agent.run` when triggered by bad tool
#   args — it is always converted to `UnexpectedModelBehavior`.
#   A `ValidationError` raised directly from the model function, however, propagates
#   out of `FunctionModel.request()` untouched (before the output-validation wrapper
#   runs), so it reaches the harness/probe as a genuine `ValidationError`. This is
#   the faithful, deterministic analogue of "the LLM returned output that failed
#   validation" and is the only path that exercises HarnessProbe's ValidationError
#   branch. The result is identical from the harness's perspective: the turn failed
#   validation, the raw error is captured, and the run is persisted (not spun).

_req_tool_name_cache: str = "final_result"


def _build_validation_error() -> ValidationError:
    """A genuine pydantic_core.ValidationError: x must be an int, got a str."""
    return ValidationError.from_exception_data(
        "Strict",
        [
            {
                "type": "int_type",
                "loc": ("x",),
                "input": "not_an_int",
                "ctx": {"error": "Input should be a valid integer"},
            }
        ],
    )


async def bad_model(messages, agent_info):
    """Simulate an LLM turn whose output fails pydantic validation."""
    # Realistic trigger would be a ToolCallPart with invalid args, e.g.:
    #   tool_name = agent_info.output_tools[0].name if agent_info.output_tools else "final_result"
    #   return ModelResponse(parts=[ToolCallPart(tool_name=tool_name, args='{"x": "not_an_int"}')])
    # but under pydantic_ai 2.3.0 that surfaces as UnexpectedModelBehavior, not
    # ValidationError (see module docstring). Raising ValidationError directly is the
    # deterministic equivalent that reaches the harness's Intercept capture.
    raise _build_validation_error()


def test_intercept_validation_error(orch_runtime, freeze_dir, monkeypatch):
    """Invalid LLM output must be caught + persisted, not silently retried."""
    probe = HarnessProbe(freeze_dir)
    probe.install(monkeypatch)

    class Strict(pydantic.BaseModel):
        x: int

    agent = Agent(model=FunctionModel(bad_model), output_type=Strict, retries=0)
    agent.name = "intercept"

    with pytest.raises((ValidationError, Exception)):
        asyncio.run(
            lg.run_with_loopguard(agent, "p", phase="intercept", role="intercept")
        )

    # Intercept: the harness must have recorded the validation failure.
    assert probe.validation_failures, "Intercept must record the validation failure"
    assert probe.validation_failures[0]["type"] == "ValidationError"
    assert probe.validation_failures[0]["raw"], "raw error string must be captured"

    # Loopguard must persist the failure dump on any exception.
    fail = orch_runtime / "logs" / "runtime" / "fail_intercept_intercept.json"
    assert fail.exists(), "harness must persist fail_*.json on validation failure"


@pytest.mark.skip(
    reason=(
        "ModelRetry cannot deterministically propagate out of Agent.run, so the "
        "probe's ModelRetry branch is unreachable via a FunctionModel in pydantic_ai "
        "2.3.0. A ModelRetry raised from the model function is intercepted by "
        "ModelRequestNode (except exceptions.ModelRetry -> _build_retry_node) which "
        "consumes one output-retry budget via consume_output_retry; with retries=0 "
        "the FIRST ModelRetry is converted into "
        "UnexpectedModelBehavior('Exceeded maximum output retries'), and with "
        "retries>0 the function raises ModelRetry on every call so the budget is "
        "always exhausted -> same UnexpectedModelBehavior escapes. Even a direct "
        "ModelRetry raise from the function never reaches HarnessProbe's "
        "(ValidationError, ModelRetry) handler as a ModelRetry. Skipping rather than "
        "faking green."
    )
)
def test_intercept_model_retry(orch_runtime, freeze_dir, monkeypatch):
    probe = HarnessProbe(freeze_dir)
    probe.install(monkeypatch)

    class Strict(pydantic.BaseModel):
        x: int

    async def retry_model(messages, agent_info):
        raise ModelRetry("retry now")

    agent = Agent(model=FunctionModel(retry_model), output_type=Strict, retries=0)
    agent.name = "intercept"
    with pytest.raises((ModelRetry, Exception)):
        asyncio.run(
            lg.run_with_loopguard(agent, "p", phase="intercept", role="intercept")
        )
    assert probe.validation_failures[0]["type"] == "ModelRetry"
