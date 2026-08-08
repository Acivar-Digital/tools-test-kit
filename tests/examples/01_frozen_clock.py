"""Frozen-clock + mocked-LLM test pattern.

Lesson: centralize every source of nondeterminism (the clock, the LLM call)
behind a swappable hook. A test then patches the hook to freeze time and stub
the LLM, producing fully-reproducible snapshots.

One dependency only: pytest.
"""
from __future__ import annotations

import datetime as dt
import sys


ZERO = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.timezone.utc)


def _now() -> dt.datetime:
    """Indirection point: the single source of 'current time' for the module."""
    return dt.datetime.now(tz=dt.timezone.utc)


def _llm(prompt: str, *, now: dt.datetime) -> dict:
    """Pure stand-in for an LLM call. Same inputs => same output."""
    return {"prompt": prompt, "called_at": now.isoformat(), "text": "stub-response"}


def snapshot() -> dict:
    n = _now()
    return {
        "clock": n.isoformat(),
        "first": _llm("first", now=n),
        "second": _llm("second", now=n),
    }


def test_frozen_clock_is_deterministic(monkeypatch) -> None:
    mod = sys.modules[__name__]
    monkeypatch.setattr(mod, "_now", lambda: ZERO)

    a = snapshot()
    b = snapshot()

    assert a == b                                              # frozen => identical
    assert a["clock"] == "2024-01-01T12:00:00+00:00"
    assert a["first"]["called_at"] == a["second"]["called_at"]  # same `now` reused


if __name__ == "__main__":
    sys.modules[__name__]._now = lambda: ZERO
    s = snapshot()
    assert s["clock"] == "2024-01-01T12:00:00+00:00"
    print("01_frozen_clock OK", s["clock"])
