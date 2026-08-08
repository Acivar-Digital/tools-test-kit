"""HarnessProbe — non-invasive BIFR recorder for the GOLD test suite.

Wraps ``pydantic_ai.Agent.run`` (class-level, via monkeypatch) so every model
turn is recorded without touching production code:

* Boundary  — a ``pre_llm`` / ``post_llm`` event per turn.
* Intercept  — any ``ValidationError`` / ``ModelRetry`` raised during a turn,
  with the raw error string persisted (so we can see the LLM's bad output).
* Freeze    — a per-turn JSON snapshot ``freeze_<turn>.json``
  ({loop_counter, role, timestamp}) in the probe's freeze_dir.

The harness already emits its own Boundary/Freeze artifacts (``io_*.log`` via
``_loopguard._log_turn``, ``fail_*.json`` via ``_dump_failure``); this probe
adds the missing **Intercept** capture and a uniform per-turn event stream the
gold tests assert against.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelRetry
from pydantic_core import ValidationError


class HarnessProbe:
    def __init__(self, freeze_dir: Path):
        self.events: list[dict] = []
        self.validation_failures: list[dict] = []
        self.freeze_dir = Path(freeze_dir)
        self.freeze_dir.mkdir(parents=True, exist_ok=True)
        self._turn = 0
        self._original = Agent.run

    def _freeze(self, turn: int, role: str | None) -> None:
        snap = {
            "loop_counter": turn,
            "role": role,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        (self.freeze_dir / f"freeze_{turn:03d}.json").write_text(
            json.dumps(snap, indent=2)
        )

    def _make_wrapper(self):
        original = self._original

        async def wrapped_run(self_agent, *args, **kwargs):
            self._turn += 1
            turn = self._turn
            role = kwargs.get("role") or getattr(self_agent, "name", None)
            self.events.append(
                {
                    "edge": "pre_llm",
                    "turn": turn,
                    "role": role,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            self._freeze(turn, role)
            try:
                res = await original(self_agent, *args, **kwargs)
            except (ValidationError, ModelRetry) as exc:
                self.validation_failures.append(
                    {
                        "turn": turn,
                        "role": role,
                        "type": type(exc).__name__,
                        "raw": str(exc),
                        "timestamp": datetime.now(UTC).isoformat(),
                    }
                )
                raise
            self.events.append(
                {
                    "edge": "post_llm",
                    "turn": turn,
                    "role": role,
                    "result_type": type(res).__name__,
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
            return res

        return wrapped_run

    def install(self, monkeypatch) -> None:
        """Patch ``pydantic_ai.Agent.run`` so every turn is recorded."""
        monkeypatch.setattr(Agent, "run", self._make_wrapper())
