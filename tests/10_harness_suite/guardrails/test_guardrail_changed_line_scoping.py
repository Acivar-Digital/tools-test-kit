"""Regression tests that scope guardrail pyright
errors to the lines the intern actually CHANGED.

Root cause (hbh1 HALT): ``guardrail_check.py`` held interns accountable for
pre-existing errors on lines they never touched (Defect B). Architectural
principle: a intern must only be held accountable for errors it introduced on the
lines it changed ("other intern's shit is our shit").

These tests monkeypatch the pyright ``subprocess`` so they run without pyright
installed and without touching real source.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.tools import guardrail_check as gc


class _FakeCompleted:
    def __init__(self, stdout: str, returncode: int = 1):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def _fake_pyright(stdout: str):
    """Return a subprocess.run replacement emitting ``stdout`` as pyright text."""

    def _run(*args, **kwargs):
        return _FakeCompleted(stdout)

    return _run


def test_parse_pyright_error():
    fp, line = gc._parse_pyright_error(
        "src2/engine/foo.py:2:5 - error: Cannot assign to attribute"
    )
    assert fp is not None and fp.endswith("foo.py")
    assert line == 2
    # lines without "error" are ignored
    assert gc._parse_pyright_error("foo.py:2:5 - info: just a note") == (None, None)
    # malformed lines return None
    assert gc._parse_pyright_error("garbage with no location") == (None, None)


def test_changed_lines_from_diff_parses(tmp_path: Path):
    live = tmp_path / "live.py"
    live.write_text("line1\nline2\nline3\n")
    staged = tmp_path / "foo.py"
    staged.write_text("line1\nline2 modified\nline3\n")
    diff = gc.diff_staged_vs_original(staged, live)
    changed = gc._changed_lines_from_diff(diff)
    assert changed is not None
    assert changed == {2}

    # Insert a line -> new line counted as changed.
    staged.write_text("line1\nline2 modified\ninserted\nline3\n")
    diff2 = gc.diff_staged_vs_original(staged, live)
    changed2 = gc._changed_lines_from_diff(diff2)
    assert changed2 is not None
    assert 2 in changed2
    assert 3 in changed2  # the newly inserted line

    # No diff / no original -> None (whole-file fallback).
    assert gc._changed_lines_from_diff("no diff") is None
    assert gc._changed_lines_from_diff("no original") is None


def test_typecheck_file_scopes_to_changed_lines(tmp_path: Path, monkeypatch):
    live = tmp_path / "orig.py"
    live.write_text("line1\nline2\nline3\n")
    staged = tmp_path / "foo.py"
    staged.write_text("line1\nline2 modified\nline3\n")

    diff = gc.diff_staged_vs_original(staged, live)
    changed = gc._changed_lines_from_diff(diff)
    assert changed == {2}

    # pyright reports BOTH an error on the changed line (2) and a pre-existing
    # error on the untouched line (1). Only the changed-line one must block.
    out = (
        "foo.py:2:5 - error: NEW error on the line the intern edited\n"
        "foo.py:1:1 - error: PRE-EXISTING error the intern never touched\n"
    )
    monkeypatch.setattr(gc.subprocess, "run", _fake_pyright(out))

    ok, text = gc.typecheck_file(str(staged), changed=changed)
    assert ok is False
    # only the changed-line error is reported
    assert "NEW error on the line the intern edited" in text
    assert "PRE-EXISTING error the intern never touched" not in text


def test_typecheck_file_clean_edit_passes(tmp_path: Path, monkeypatch):
    live = tmp_path / "orig.py"
    live.write_text("line1\nline2\nline3\n")
    staged = tmp_path / "foo.py"
    staged.write_text("line1\nline2 modified\nline3\n")

    diff = gc.diff_staged_vs_original(staged, live)
    changed = gc._changed_lines_from_diff(diff)

    # only pre-existing error on untouched line 1 -> intern is NOT blocked
    out = "foo.py:1:1 - error: PRE-EXISTING error the intern never touched\n"
    monkeypatch.setattr(gc.subprocess, "run", _fake_pyright(out))

    ok, _ = gc.typecheck_file(str(staged), changed=changed)
    assert ok is True


def test_typecheck_file_falls_back_whole_file_without_diff(tmp_path: Path, monkeypatch):
    staged = tmp_path / "foo.py"
    staged.write_text("line1\nline2\nline3\n")
    # No diff (changed=None) -> whole-file scope: any error blocks.
    out = "foo.py:1:1 - error: some error\n"
    monkeypatch.setattr(gc.subprocess, "run", _fake_pyright(out))

    ok, _ = gc.typecheck_file(str(staged), changed=None)
    assert ok is False  # whole-file fallback still catches the error


def test_typecheck_union_scopes_per_file(tmp_path: Path, monkeypatch):
    live_a = tmp_path / "live_a.py"
    live_b = tmp_path / "live_b.py"
    live_a.write_text("a1\na2\na3\n")
    live_b.write_text("b1\nb2\nb3\n")
    staged_a = tmp_path / "a.py"
    staged_b = tmp_path / "b.py"
    staged_a.write_text("a1\na2 edited\na3\n")
    staged_b.write_text("b1\nb2 edited\nb3\n")

    changed_a = gc._changed_lines_from_diff(gc.diff_staged_vs_original(staged_a, live_a))
    changed_b = gc._changed_lines_from_diff(gc.diff_staged_vs_original(staged_b, live_b))
    changed_map = {staged_a.name: changed_a, staged_b.name: changed_b}
    edited_names = {staged_a.name, staged_b.name}

    # error on a changed line in a.py (2) -> blocks; pre-existing error in b.py (1) -> ignored
    out = (
        "a.py:2:5 - error: NEW error in a (changed line)\n"
        "b.py:1:1 - error: PRE-EXISTING error in b (untouched)\n"
    )
    monkeypatch.setattr(gc.subprocess, "run", _fake_pyright(out))

    ok, text = gc.typecheck_union([staged_a, staged_b], changed_map=changed_map, edited_names=edited_names)
    assert ok is False
    assert "NEW error in a (changed line)" in text
    assert "PRE-EXISTING error in b (untouched)" not in text


def test_typecheck_union_clean_passes(tmp_path: Path, monkeypatch):
    live_a = tmp_path / "live_a.py"
    live_b = tmp_path / "live_b.py"
    live_a.write_text("a1\na2\na3\n")
    live_b.write_text("b1\nb2\nb3\n")
    staged_a = tmp_path / "a.py"
    staged_b = tmp_path / "b.py"
    staged_a.write_text("a1\na2 edited\na3\n")
    staged_b.write_text("b1\nb2 edited\nb3\n")

    changed_a = gc._changed_lines_from_diff(gc.diff_staged_vs_original(staged_a, live_a))
    changed_b = gc._changed_lines_from_diff(gc.diff_staged_vs_original(staged_b, live_b))
    changed_map = {staged_a.name: changed_a, staged_b.name: changed_b}
    edited_names = {staged_a.name, staged_b.name}

    # only pre-existing errors on untouched lines -> both pass
    out = (
        "a.py:1:1 - error: PRE-EXISTING error in a\n"
        "b.py:3:3 - error: PRE-EXISTING error in b\n"
    )
    monkeypatch.setattr(gc.subprocess, "run", _fake_pyright(out))

    ok, _ = gc.typecheck_union([staged_a, staged_b], changed_map=changed_map, edited_names=edited_names)
    assert ok is True
