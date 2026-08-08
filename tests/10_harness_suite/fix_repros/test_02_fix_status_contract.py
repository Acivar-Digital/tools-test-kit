"""Tests for factory/docs/02_fix.md — intern status-string contract.

Guards (root cause of RuntimeError: [HALT] EXECUTE phase incomplete: intern03, intern07):
  - TaskResult.status is constrained to Literal["done","blocked"] (the intern "form").
  - A mode="before" validator normalizes synonyms ("completed"/"ok"/"complete*"/
    "finished"/"success" -> "done"; "fail"/"failed"/"error" -> "blocked") so a
    intern emitting a non-canonical but valid status no longer stalls the EXECUTE
    completion scan.
  - Unknown statuses raise ValueError("status must be 'done' or 'blocked'") so
    pydantic-ai feeds the error back and HALTs after retries (no silent swallow).
  - notes / diff_summary carry Field(description=...) so the form dictates structure.
"""

from __future__ import annotations

from pydantic import ValidationError

from factory.infra import models as models_mod


def _make(status: str) -> models_mod.TaskResult:
    return models_mod.TaskResult(
        task_id="intern03",
        status=status,
        files_changed=[],
        diff_summary="",
        notes="",
    )


# --- Fix A: normalization (no EXECUTE-phase HALT for non-canonical-but-valid) ----

def test_status_completed_normalized_to_done():
    tr = _make("completed")
    assert tr.status == "done"


def test_status_ok_and_success_normalized_to_done():
    assert _make("ok").status == "done"
    assert _make("success").status == "done"
    assert _make("complete").status == "done"
    assert _make("completes").status == "done"
    assert _make("finished").status == "done"


def test_status_failed_and_error_normalized_to_blocked():
    assert _make("failed").status == "blocked"
    assert _make("fail").status == "blocked"
    assert _make("error").status == "blocked"


def test_status_normalization_is_case_insensitive():
    assert _make("COMPLETED").status == "done"
    assert _make("Completed").status == "done"
    assert _make("  OK  ").status == "done"
    assert _make("Failed").status == "blocked"


def test_canonical_status_passthrough():
    assert _make("done").status == "done"
    assert _make("blocked").status == "blocked"


# --- Fix B: explicit reject of unknown status (form lists only done|blocked) ----

def test_unknown_status_rejected():
    for bad in ("in_progress", "pending", "escalated", "wip", "n/a", "maybe"):
        try:
            _make(bad)
        except ValidationError as exc:
            assert "status must be 'done' or 'blocked'" in str(exc)
        else:
            raise AssertionError(f"expected ValidationError for status={bad!r}")


# --- Form requirement: the intern schema exposes exactly done|blocked -----------

def test_status_schema_lists_only_done_or_blocked():
    schema = models_mod.TaskResult.model_json_schema()
    enum = schema["properties"]["status"].get("enum")
    assert enum == ["done", "blocked"]


# --- Crystal-clear form: free-text fields carry description-dictated structure --

def test_notes_and_diff_summary_have_descriptions():
    props = models_mod.TaskResult.model_json_schema()["properties"]
    assert "description" in props["notes"]
    assert "description" in props["diff_summary"]
    assert "ERROR" in props["notes"]["description"]
    assert "DELIVERABLE" in props["notes"]["description"]


# --- Regression guard: existing canonical construction still works ------------

def test_existing_done_construction_untouched():
    tr = models_mod.TaskResult(
        task_id="intern01",
        status="done",
        files_changed=[],
        diff_summary="x",
        notes="ok",
    )
    assert tr.ruff_ok is True and tr.pyright_ok is True and tr.exec_ok is True
    assert tr.dep_pointers == []
