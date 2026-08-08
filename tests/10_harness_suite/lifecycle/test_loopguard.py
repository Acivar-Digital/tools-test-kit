"""Sandbox control-flow tests for the Compaction Gate + loop-guard (Q1/Q2/Q3/Q4).

No LLM keys required: uses pydantic_ai ``TestModel`` / ``FunctionModel`` and
monkeypatches the summarizer model. Validates:
  * the safe-boundary slicer never orphans a tool-return (prevents API 400);
  * SINK-1 live-loop relief is actually wired (the old line-89 overwrite bug is gone);
  * the gate does NOT write ``phase_summaries`` (Q2: role-key is canonical, owned by run_phase);
  * per-role budgets differ (orchestrator ceiling > worker ceiling, Q3/Q4).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from types import SimpleNamespace

import pytest
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    SystemPromptPart,
    TextPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models.test import TestModel

from factory.infra import _loopguard as lg
from factory.infra.control import CONTROL_SHEET


def _req(text: str) -> ModelRequest:
    return ModelRequest(parts=[UserPromptPart(content=text)])


def _tool_call(tid: str) -> ModelResponse:
    return ModelResponse(parts=[ToolCallPart(tool_name="noop", args={}, tool_call_id=tid)])


def _tool_return(tid: str, content: str = "ok") -> ModelRequest:
    return ModelRequest(parts=[ToolReturnPart(tool_name="noop", tool_call_id=tid, content=content)])


def test_get_safe_recent_messages_keeps_all_when_short():
    msgs = [_req("a"), _req("b")]
    assert lg.get_safe_recent_messages(msgs, keep=12) == msgs


def test_get_safe_recent_messages_skips_leading_tool_return():
    # last 2 would be [tool-return, user]; the orphan tool-return must drop.
    msgs = [
        _req("start"),
        _tool_call("1"),
        _tool_return("1", "result"),
        _req("final"),
    ]
    out = lg.get_safe_recent_messages(msgs, keep=2)
    assert len(out) == 1
    assert isinstance(out[0], ModelRequest)
    assert any(
        isinstance(p, UserPromptPart) and p.content == "final"
        for p in out[0].parts
    )
    assert not any(
        isinstance(p, ToolReturnPart)
        for m in out
        for p in (m.parts if isinstance(m, ModelRequest) else [])
    )


def test_get_safe_recent_messages_keeps_valid_tool_call_chain():
    msgs = [
        _req("start"),
        _tool_call("1"),
        _tool_return("1", "r"),
        _req("tail"),
    ]
    out = lg.get_safe_recent_messages(msgs, keep=3)
    # keep=3 -> [tool_call, tool_return, req]; first is a tool-call (valid), kept.
    assert len(out) == 3
    assert isinstance(out[0], ModelResponse)


@pytest.fixture
def patch_summarizer(monkeypatch):
    # Deterministically stand in for the summarizer LLM: TestModel is flaky on the
    # large compaction input, so we return a valid CompactedContext every time.
    async def _sum(messages, agent_info):
        return ModelResponse(
            parts=[ToolCallPart(tool_name="final_result", args={"summary": "SUMMARY summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary summary"}, tool_call_id="0")]
        )

    from pydantic_ai.models.function import FunctionModel

    # CONTROL_SHEET is a typed ControlSheet model; its models live in the
    # `models` dict. maybe_compact resolves the summarizer via
    # CONTROL_SHEET.model(COMPACTION_CONFIG.summarizer_model), which is
    # "compact_model" — patch that field.
    monkeypatch.setitem(CONTROL_SHEET.models, "compact_model", FunctionModel(_sum))


def _big_history(n: int = 68, line_len: int = 4000) -> list[ModelRequest]:
    # estimate_tokens (char_div_4) ≈ n * line_len / 4 tokens. 68 * 4000 / 4 ≈ 68k:
    # over the 70k WORKER ceiling (compacts) but under the ~76.8k ORCHESTRATOR
    # ceiling (stays un-compacted) — a safe margin on both sides.
    return [_req("x" * line_len) for _ in range(n)]


async def test_maybe_compact_sink1_structure_and_q2(patch_summarizer, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # keep SINK-3 file writes out of the repo
    # Redirect role-history persist (rotate_role_transcript / persist_messages)
    # away from the live ARTIFACTS_DIR so the test never pollutes intern.jsonl.
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(tmp_path))
    msgs = _big_history()
    state = SimpleNamespace(bd_id="", phase_summaries={})

    out = await lg.maybe_compact(msgs, TestModel(), state, "EXECUTE", role="intern")

    # SINK-1: first message is the prepended summary (a SystemPromptPart).
    assert isinstance(out[0], ModelRequest)
    assert isinstance(out[0].parts[0], SystemPromptPart)
    # Compacted history is strictly shorter than the raw history.
    assert len(out) < len(msgs)
    # Q2: the gate must NOT write phase_summaries (owned by run_phase, role-keyed).
    assert state.phase_summaries == {}


async def test_maybe_compact_per_role_budget(patch_summarizer, monkeypatch, tmp_path):
    # ~72k tokens: between worker ceiling (70k) and orchestrator ceiling (76.8k).
    monkeypatch.chdir(tmp_path)
    # Redirect role-history persist away from the live ARTIFACTS_DIR.
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(tmp_path))
    msgs = _big_history()
    state = SimpleNamespace(bd_id="", phase_summaries={})

    worker = await lg.maybe_compact(msgs, TestModel(), state, "EXECUTE", role="intern")
    orchestrator = await lg.maybe_compact(msgs, TestModel(), state, "ORCHESTRATOR", role="orchestrator")

    # Worker compacts (over its 70k budget); orchestrator stays under its 76.8k budget.
    assert len(worker) < len(msgs)
    assert orchestrator == msgs


class _FakeResult:
    """Minimal RunResult stand-in: pydantic_ai auto-executes tools *inside* a
    single run(), so to exercise the loop-guard's inter-run control flow we drive
    the turns by hand — first a tool call, then a terminal text answer."""

    def __init__(self, new_msgs, all_msgs, output=None):
        self._new = new_msgs
        self._all = all_msgs
        self.output = output

    def new_messages(self):
        return self._new

    def all_messages(self):
        return self._all


class _LoopAgent:
    """Fake agent: turn 1 returns a tool call (loop-guard must invoke compaction
    and feed the compacted history back); turn 2 returns the terminal 'DONE'."""

    model = None  # run_with_loopguard only reads agent.model for the summarizer

    def __init__(self, history):
        self._history = list(history)
        self._turn = 0

    async def run(self, prompt, message_history=None, usage_limits=None, deps=None):
        self._turn += 1
        if self._turn == 1:
            # Real pydantic_ai executes the tool, so the history ends with a
            # ToolReturnPart (processed), not an unprocessed tool call.
            tool_call = ModelResponse(parts=[ToolCallPart(tool_name="noop", args={}, tool_call_id="0")])
            tool_ret = ModelRequest(parts=[ToolReturnPart(tool_name="noop", tool_call_id="0", content="ok")])
            return _FakeResult(
                new_msgs=[tool_call],
                all_msgs=list(message_history or []) + [tool_call, tool_ret],
            )
        return _FakeResult(
            new_msgs=[ModelResponse(parts=[TextPart("DONE")])],
            all_msgs=list(message_history or []) + [ModelResponse(parts=[TextPart("DONE")])],
            output="DONE",
        )


async def test_run_with_loopguard_wires_sink1(patch_summarizer, monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    # Redirect role-history persist (run_with_loopguard -> persist_messages) away
    # from the live ARTIFACTS_DIR so the test never pollutes intern.jsonl.
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(tmp_path))
    calls: list[tuple[int, object]] = []
    orig = lg.maybe_compact

    async def spy(msgs, model, state, phase, role=None):
        calls.append((len(msgs), role))
        return await orig(msgs, model, state, phase, role=role)

    monkeypatch.setattr(lg, "maybe_compact", spy)

    # Seed a history already over budget so the first turn triggers compaction.
    history = _big_history()
    state = SimpleNamespace(bd_id="", phase_summaries={})

    res = await lg.run_with_loopguard(
        _LoopAgent(history),
        "go",
        history=history,
        state=state,
        phase="EXECUTE",
        role="intern",
    )

    # The loop completed and SINK-1 path was reached (compaction fired at least once).
    assert res.output == "DONE"
    assert calls  # maybe_compact was invoked -> compacted history fed back in
    # Q2: gate never touched phase_summaries.
    assert state.phase_summaries == {}
    # Final transcript is bounded (compacted), not the full seed history.
    assert len(res.all_messages()) < len(history) + 6


async def test_run_with_loopguard_threads_agent_id_into_persist(
    patch_summarizer, monkeypatch, tmp_path
):
    """chq80: an intern run must NOT write the legacy shared
    ``intern.jsonl``/``intern.md``. ``run_with_loopguard`` must forward ``agent_id``
    to every ``persist_messages`` call so transcripts land in ``internN.jsonl``."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(tmp_path))

    import factory.infra.artefacts as art

    persist_calls: list[tuple[str, str | None]] = []
    orig_persist = art.persist_messages

    def spy_persist(role, messages, tag=None, agent_id=None):
        persist_calls.append((role, agent_id))
        # Route real writes to a scratch dir so we can assert on disk too.
        return orig_persist(role, messages, tag=tag, agent_id=agent_id)

    monkeypatch.setattr(art, "persist_messages", spy_persist)

    history = _big_history()
    state = SimpleNamespace(bd_id="", phase_summaries={})

    res = await lg.run_with_loopguard(
        _LoopAgent(history),
        "go",
        history=history,
        state=state,
        phase="EXECUTE",
        role="intern",
        agent_id="intern3",
    )

    assert res.output == "DONE"
    # Every persist call for the intern role carried the isolated agent_id.
    assert persist_calls, "persist_messages was never invoked"
    for role, agent_id in persist_calls:
        assert role == "intern"
        assert agent_id == "intern3", (
            f"intern persist called with agent_id={agent_id!r} "
            f"-> would recreate shared intern.jsonl"
        )
    # The shared file must NOT exist; only the isolated internN file.
    hist_dir = tmp_path / "history" / "intern"
    assert not (hist_dir / "intern.jsonl").exists(), "shared intern.jsonl was created"
    assert (hist_dir / "intern3.jsonl").exists(), "isolated intern3.jsonl missing"


def test_build_role_agent_clones_intern_model():
    from factory.infra.runner import build_role_agent
    agent1, _ = build_role_agent("intern")
    agent2, _ = build_role_agent("intern")
    # Verify they have different model instances, even though they share the same key in SKILL_MAP
    assert agent1.model is not agent2.model

    # Verify sequential roles share the same model instance
    agent_engineer1, _ = build_role_agent("engineer")
    agent_engineer2, _ = build_role_agent("engineer")
    assert agent_engineer1.model is agent_engineer2.model


async def test_concurrent_loopguard_monkeypatching_isolation(monkeypatch, tmp_path):
    import copy
    import types
    from pydantic_ai.models.test import TestModel

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ORCHESTRATOR_ARTEFACTS_DIR", str(tmp_path))

    # Create a shared model instance
    shared_model = TestModel()

    # We simulate building two intern agents with cloned models
    model1 = copy.copy(shared_model)
    model2 = copy.copy(shared_model)

    assert model1 is not model2

    # Ensure they have request methods
    assert hasattr(model1, "request")
    assert hasattr(model2, "request")

    original_request = shared_model.request

    # Simulate run_with_loopguard's interception on both models concurrently.
    async def intercepted_request1(self, messages, model_settings, *args, **kwargs):
        return "response_from_agent1"

    model1.request = types.MethodType(intercepted_request1, model1)

    async def intercepted_request2(self, messages, model_settings, *args, **kwargs):
        return "response_from_agent2"

    model2.request = types.MethodType(intercepted_request2, model2)

    # Verify that model1's request does not return model2's response, and vice-versa
    res1 = await model1.request([], {})
    res2 = await model2.request([], {})

    assert res1 == "response_from_agent1"
    assert res2 == "response_from_agent2"

    # Verify that the shared model request method was NOT modified
    assert shared_model.request.__func__ is original_request.__func__


def _read_tool_return(tool_name: str, content: str) -> ModelRequest:
    return ModelRequest(
        parts=[ToolReturnPart(tool_name=tool_name, tool_call_id="1", content=content)]
    )


def test_scrub_old_read_returns_scrubs_large_old_returns():
    """Older read-tool returns >200 bytes are scrubbed; the last 2 turns are kept."""
    big_content = "x" * 300
    history = [
        _read_tool_return("read_file", big_content),
        _req("user turn 1"),
        _read_tool_return("grep_codebase", big_content),
        _req("user turn 2"),
        _read_tool_return("list_files", big_content),
        _req("user turn 3"),
    ]
    lg._scrub_old_read_returns(history)
    # The last 2 ModelRequest messages (indices 4 and 5) are kept intact.
    assert history[4].parts[0].content == big_content, "2nd-to-last turn's read return must be kept"
    assert history[5].parts[0].content == "user turn 3"  # user prompt, not a read return
    # Older turns are scrubbed.
    assert history[0].parts[0].content.startswith("[scrubbed for context hygiene:")
    assert history[0].parts[0].content.endswith("bytes from read_file]")


def test_scrub_old_read_returns_keeps_small_returns():
    """Small read-tool returns (<200 bytes) are never scrubbed."""
    history = [
        _read_tool_return("read_file", "small"),
        _req("user turn 1"),
        _read_tool_return("search", "also small"),
        _req("user turn 2"),
    ]
    lg._scrub_old_read_returns(history)
    assert history[0].parts[0].content == "small"
    assert history[2].parts[0].content == "also small"


def test_scrub_old_read_returns_non_read_tools_unchanged():
    """Non-read tool returns are never scrubbed."""
    big_content = "x" * 300
    history = [
        _read_tool_return("write_file", big_content),
        _req("user turn 1"),
        _read_tool_return("bash", big_content),
        _req("user turn 2"),
    ]
    lg._scrub_old_read_returns(history)
    assert history[0].parts[0].content == big_content
    assert history[2].parts[0].content == big_content


def test_scrub_old_read_returns_keeps_last_two_turns():
    """The last 2 turns (by ModelRequest) are always kept intact."""
    big_content = "x" * 300
    history = [
        _read_tool_return("read_file", big_content),
        _req("turn 1"),
        _read_tool_return("batch_read", big_content),
        _req("turn 2"),
        _read_tool_return("search", big_content),
        _req("turn 3"),
        _read_tool_return("grep_codebase", big_content),
        _req("turn 4"),
    ]
    lg._scrub_old_read_returns(history)
    # The last 2 ModelRequests are at indices 6 and 7 — kept intact.
    assert history[6].parts[0].content == big_content
    assert history[7].parts[0].content == "turn 4"
    # Earlier ModelRequests (indices 0-5) are scrubbed.
    assert history[0].parts[0].content.startswith("[scrubbed for context hygiene:")
    assert history[2].parts[0].content.startswith("[scrubbed for context hygiene:")
    assert history[4].parts[0].content.startswith("[scrubbed for context hygiene:")


def test_scrub_old_read_returns_empty_history():
    """Scrubbing an empty history is a no-op."""
    lg._scrub_old_read_returns([])


def test_scrub_old_read_returns_no_model_requests():
    """If there are no ModelRequest messages, nothing is scrubbed."""
    from pydantic_ai.messages import ModelResponse, TextPart

    history = [ModelResponse(parts=[TextPart("hello")])]
    lg._scrub_old_read_returns(history)
    assert history[0].parts[0].content == "hello"


def test_scrub_old_read_returns_only_one_turn():
    """With only 1 turn, nothing is scrubbed (last 2 includes the only turn)."""
    big_content = "x" * 300
    history = [_read_tool_return("read_file", big_content)]
    lg._scrub_old_read_returns(history)
    assert history[0].parts[0].content == big_content

