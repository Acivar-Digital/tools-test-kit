import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from factory.infra import _loopguard as lg


def test_replay_frozen_history_runs_once(orch_runtime, monkeypatch):
    # 1) Produce a "frozen" history by running once and capturing all_messages().
    src = Agent(model=TestModel(), output_type=str, retries=0)
    src.name = "src"
    res1 = asyncio.run(lg.run_with_loopguard(src, "seed prompt", phase="src", role="src"))
    frozen = res1.all_messages()
    assert frozen, "freeze step must yield a non-empty history"

    # 2) Replay: inject the frozen history into a FRESH agent, single run.
    replay = Agent(model=TestModel(), output_type=str, retries=0)
    replay.name = "replay"
    res2 = asyncio.run(
        lg.run_with_loopguard(replay, "replay prompt", history=list(frozen), phase="replay", role="replay")
    )
    assert res2 is not None
    assert hasattr(res2, "output"), "replay must return a result object"
    assert isinstance(res2.output, str)
