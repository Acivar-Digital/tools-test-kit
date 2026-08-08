"""BIFR Step 3 (Freeze) gold test.

Asserts the harness serializes a per-turn state snapshot (loop counter +
timestamp) so a crash can be post-mortemed from the iteration before it died.

Filename pattern confirmed in factory/test/_probe.py:
    freeze_{turn:03d}.json   (e.g. freeze_001.json, freeze_002.json, ...)

Snapshot JSON keys confirmed in _probe._freeze:
    {"loop_counter": int, "role": str|None, "timestamp": iso-str}
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from pydantic_ai import Agent
from pydantic_ai.models.test import TestModel

from factory.infra import _loopguard as lg
from tests._probe import HarnessProbe


def test_freeze_writes_per_turn_snapshot(orch_runtime, freeze_dir, monkeypatch):
    probe = HarnessProbe(freeze_dir)
    probe.install(monkeypatch)
    agent = Agent(model=TestModel(), output_type=str, retries=0)
    agent.name = "freeze"
    asyncio.run(lg.run_with_loopguard(agent, "p", phase="freeze", role="freeze"))
    files = sorted(freeze_dir.glob("freeze_*.json"))
    assert files, "Freeze must write at least one per-turn snapshot"
    data = json.loads(files[0].read_text())
    assert "loop_counter" in data and "timestamp" in data, "snapshot must carry loop_counter + timestamp"
    assert data["loop_counter"] == 1
    # snapshot count must match the number of model turns the probe saw
    assert len(files) == probe._turn
