"""Tests for the framework-rejected tool-call salvage path (78j9m).

Offline, no network, no LLM keys. Verifies that when pydantic-ai's own
tool-dispatch validator rejects a structurally-invalid ``final_result`` call
(e.g. MALFORMED_FUNCTION_CALL: list instead of object), the attempted payload
is reclaimed and routed through the same strict sanitizer HALT path — never
silently dropped from the batch.

Covers:
  * ``extract_tool_call_payload`` reclaims a payload from the exception.
  * A recoverable payload is salvaged (same pipeline as malformed JSON).
  * An unrecoverable payload still HALTs loud via clean_role_output.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from pydantic import BaseModel
from pydantic_ai.exceptions import UnexpectedModelBehavior

from factory.infra import output_sanitizer as osan


class _Doc(BaseModel):
    name: str
    cells: list[dict] = []


def _fake_exc(body: str | None = None, message: str | None = None) -> Exception:
    """Build an UnexpectedModelBehavior carrying the framework's error text."""

    class _Exc(UnexpectedModelBehavior):  # type: ignore[misc, valid-type]
        def __init__(self, b: str | None, m: str | None) -> None:
            self.body = b
            self.message = m

        def __str__(self) -> str:  # pragma: no cover - test stand-in
            return self.message or self.body or ""

    return _Exc(body, message)


def test_extract_tool_call_payload_from_body():
    """Reclaims a JSON-ish payload embedded in the exception body."""
    exc = _fake_exc(body='Input should be an object [input_type=list] {"name": "x"}')
    got = osan.extract_tool_call_payload(exc)
    assert got is not None
    assert '"name"' in got


def test_extract_tool_call_payload_from_message():
    """Falls back to the message attribute when body is absent."""
    exc = _fake_exc(message='{"name": "y", "cells": []}')
    got = osan.extract_tool_call_payload(exc)
    assert got is not None
    assert '"name": "y"' in got


def test_extract_tool_call_payload_recoverable():
    """Reclaimed payload that is valid still validates through clean_role_output."""
    exc = _fake_exc(body='MALFORMED_FUNCTION_CALL {"name": "ok", "cells": []}')
    raw = osan.extract_tool_call_payload(exc)
    assert raw is not None
    obj = osan.clean_role_output(raw, _Doc)
    assert isinstance(obj, _Doc)
    assert obj.name == "ok"


def test_extract_tool_call_payload_unrecoverable_halts():
    """Reclaimed but invalid payload still fails loud — no leniency."""
    exc = _fake_exc(body='MALFORMED_FUNCTION_CALL {"name": "bad", "cells": "nope"}')
    raw = osan.extract_tool_call_payload(exc)
    assert raw is not None
    try:
        osan.clean_role_output(raw, _Doc)
        raise AssertionError("expected [HALT] RuntimeError")
    except RuntimeError as e:
        assert "[HALT]" in str(e)


def test_extract_tool_call_payload_absent_returns_none():
    """If the framework exposes nothing, return None (caller then HALTs)."""
    exc = _fake_exc()
    assert osan.extract_tool_call_payload(exc) is None
