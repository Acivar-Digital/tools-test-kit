import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from factory.infra import _loopguard as lg
from tests._probe import HarnessProbe


def test_boundary_edges_logged(orch_runtime, freeze_dir, monkeypatch):
    probe = HarnessProbe(freeze_dir)
    probe.install(monkeypatch)
    agent = Agent(model=TestModel(), output_type=str, retries=0)
    agent.name = "boundary"
    import asyncio
    asyncio.run(lg.run_with_loopguard(agent, "hello prompt", phase="boundary", role="boundary"))
    # Boundary at turn level (probe)
    edges = [e["edge"] for e in probe.events]
    assert "pre_llm" in edges and "post_llm" in edges
    # Boundary at content level (harness io log)
    io_log = orch_runtime / "logs" / "runtime" / "io" / "io_boundary_boundary.log"
    assert io_log.exists(), "harness must write per-turn io log (Boundary edge)"
    text = io_log.read_text()
    assert "SENT" in text and "RECEIVED" in text, "io log must capture sent+received (4 edges)"
