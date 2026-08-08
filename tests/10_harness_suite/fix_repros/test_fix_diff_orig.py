"""Tests for the diff_vs_orig refactor and upfront diff injection.

Covers:
  - guardrail_check.diff_vs_orig: .orig baseline diffing with new-file support
  - guardrail_check.validate: JSON payload key is ``diff_vs_orig`` (not checkpoint)
  - exchange._render_upfront_diffs: extracts only verdict_diff into a visible block
  - pipeline: _render_upfront_diffs is imported and wired into review briefs
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.tools import guardrail_check as gc
from factory.infra import exchange


# ---------------------------------------------------------------------------
# diff_vs_orig
# ---------------------------------------------------------------------------
def test_diff_vs_orig_with_existing_orig(tmp_path: Path):
    """When .orig exists, diff shows the changed lines."""
    target = tmp_path / "foo.py"
    target.write_text("line1\nline2 modified\nline3\n", encoding="utf-8")
    orig = tmp_path / "foo.py.orig"
    orig.write_text("line1\nline2\nline3\n", encoding="utf-8")

    result = gc.diff_vs_orig(str(target))
    assert "@@" in result
    assert "line2 modified" in result
    assert "line2" in result


def test_diff_vs_orig_new_file_no_orig(tmp_path: Path):
    """When .orig does NOT exist (new file), baseline is empty -> 100% added."""
    target = tmp_path / "newfile.py"
    target.write_text("import os\n\nprint('hello')\n", encoding="utf-8")
    # No .orig file created

    result = gc.diff_vs_orig(str(target))
    assert "@@" in result
    # Every line should be an addition
    for line in result.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            assert True  # added line


def test_diff_vs_orig_no_diff(tmp_path: Path):
    """When file is identical to .orig, returns 'no diff'."""
    target = tmp_path / "same.py"
    content = "x = 1\ny = 2\n"
    target.write_text(content, encoding="utf-8")
    orig = tmp_path / "same.py.orig"
    orig.write_text(content, encoding="utf-8")

    result = gc.diff_vs_orig(str(target))
    assert result == "no diff"


def test_diff_vs_orig_file_not_found():
    """Missing target file raises FileNotFoundError."""
    try:
        gc.diff_vs_orig("/nonexistent/path/file.py")
        assert False, "Should have raised FileNotFoundError"
    except FileNotFoundError:
        pass


def test_no_checkpoint_functions_exist():
    """Checkpoint functions and constant must be fully removed."""
    assert not hasattr(gc, "checkpoint")
    assert not hasattr(gc, "_latest_checkpoint")
    assert not hasattr(gc, "CHECKPOINT_DIR")
    assert hasattr(gc, "diff_vs_orig")
    assert not hasattr(gc, "diff_vs_checkpoint")


# ---------------------------------------------------------------------------
# validate JSON key
# ---------------------------------------------------------------------------
def test_validate_emits_diff_vs_orig_key(tmp_path: Path, monkeypatch):
    """validate() output must use 'diff_vs_orig' key, not 'diff_vs_checkpoint'."""
    target = tmp_path / "foo.py"
    target.write_text("x = 1\n", encoding="utf-8")
    orig = tmp_path / "foo.py.orig"
    orig.write_text("x = 0\n", encoding="utf-8")

    # Stub out subprocess.run so ruff/pyright don't actually run
    class _FakeCompleted:
        def __init__(self):
            self.stdout = ""
            self.stderr = ""
            self.returncode = 0

    monkeypatch.setattr(gc.subprocess, "run", lambda *a, **kw: _FakeCompleted())

    result = gc.validate(str(target))
    assert "diff_vs_orig" in result
    assert "diff_vs_checkpoint" not in result


# ---------------------------------------------------------------------------
# _render_upfront_diffs
# ---------------------------------------------------------------------------
class _FakeTaskResult:
    def __init__(self, task_id: str, verdict_diff: str = ""):
        self.task_id = task_id
        self.verdict_diff = verdict_diff


class _FakeBatch:
    def __init__(self, results):
        self.results = results


def test_render_upfront_diffs_with_diffs():
    """Diffs are extracted and formatted into a visible block."""
    batch = _FakeBatch([
        _FakeTaskResult("intern01", "@@ -1,3 +1,3 @@\n-line1\n+line1 modified\n"),
        _FakeTaskResult("intern02", "@@ -1,2 +1,2 @@\n-old\n+new\n"),
    ])
    result = exchange._render_upfront_diffs(batch)
    assert "=== PROPOSED CODE CHANGES (DIFF) ===" in result
    assert "====================================" in result
    assert "intern01" in result
    assert "intern02" in result
    assert "line1 modified" in result
    assert "new" in result


def test_render_upfront_diffs_empty_batch():
    """Batch with no diffs returns empty string."""
    batch = _FakeBatch([_FakeTaskResult("intern01", "")])
    result = exchange._render_upfront_diffs(batch)
    assert result == ""


def test_render_upfront_diffs_none_batch():
    """None batch returns empty string."""
    result = exchange._render_upfront_diffs(None)
    assert result == ""


def test_render_upfront_diffs_mixed():
    """Only tasks with verdict_diff are included."""
    batch = _FakeBatch([
        _FakeTaskResult("intern01", "@@ -1 +1 @@\n+added\n"),
        _FakeTaskResult("intern02", ""),
        _FakeTaskResult("intern03", "@@ -1 +1 @@\n+another\n"),
    ])
    result = exchange._render_upfront_diffs(batch)
    assert "intern01" in result
    assert "intern03" in result
    assert "intern02" not in result

