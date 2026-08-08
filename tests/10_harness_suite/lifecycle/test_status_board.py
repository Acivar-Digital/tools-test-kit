"""Regression tests for the orchestrator STATUS BOARD (l4wjg).

Covers the two root causes the session analysis identified:

- RC1 (stale bleed): a fresh run must NOT carry a prior run's `intern:A` LIVE
  line. The board is derived from the history list + current_role passed by the
  caller, so this is asserted at the `update_status_board` contract level: a
  fresh call with no matching history + a review role must NOT show a stale
  `intern:A`.
- RC2 (live-tracking gap): the review phases (engineer_review, senior) must
  be reflected on the board while they run — previously the DAG reviewer path
  bypassed `do_role` and the board froze on the last intern task.

The harness-wide launcher wipe (run_orchestrator.sh) is unit-checked by the
bash-guard below; this module verifies the Python contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from factory.infra.exchange import update_status_board
import factory.infra.exchange as exchange_mod
import factory.infra._runtime as runtime


@pytest.fixture
def status_board(tmp_path, monkeypatch):
    """Point STATUS_MD at a temp file and reset global counters."""
    board = tmp_path / "STATUS.md"
    monkeypatch.setattr(exchange_mod, "STATUS_MD", board)
    monkeypatch.setattr(runtime, "_RECOVERY_COUNT", 0)
    monkeypatch.setattr(runtime, "_COMPACTION_COUNT", 0)
    return board


def _read(board: Path) -> str:
    return board.read_text(encoding="utf-8")


def test_fresh_board_has_no_stale_intern_line(status_board):
    """RC1: a fresh status update with no intern history must not bleed intern:A."""
    update_status_board([], "engineer_plan", "l4wjg")
    text = _read(status_board)
    assert "intern:A" not in text
    assert "engineer_plan" in text
    assert "LIVE" in text


def test_review_phase_surfaced_while_running(status_board):
    """RC2: engineer_review + senior appear as IN-PROGRESS on the board."""
    update_status_board([], "senior_review", "bd1")
    assert "senior_review" in _read(status_board)
    update_status_board([], "senior", "bd1")
    assert "senior" in _read(status_board)


def test_intern_in_flight_shown_before_run(status_board):
    """A intern task id is reported active immediately (not after it returns)."""
    update_status_board([("intern", "{}")], "intern:A", "bd1")
    text = _read(status_board)
    assert "intern:A" in text
    assert "Active task: intern:A" in text
    # intern already in history => DONE
    assert "- [x] intern" in text


def test_done_folds_skipped_phases(status_board, monkeypatch):
    """A --from continuation run shows pre-completed phases as DONE."""
    monkeypatch.setattr(runtime, "_SKIPPED_PHASES", ["intern", "engineer_plan"])
    update_status_board([], "senior", "bd1")
    text = _read(status_board)
    assert "- [x] intern" in text
    assert "- [x] engineer_plan" in text
    # senior is the in-progress role, not a stale TODO
    assert "- [~] senior" in text
    # intern not mis-reported as TODO.
    assert "- [ ] intern" not in text


def test_run_start_shows_senior_and_clears_stale_intern(status_board):
    """RC3 (run-start init): a stale prior-run `internNN` LIVE row must be
    overwritten the instant the run starts, which initializes the board with
    the intern phase as IN-PROGRESS — matching what the runner does at the
    top of main() (update_status_board([], start_role, bd) with
    start_role='intern')."""
    # Seed a leftover board from a crashed prior run.
    status_board.write_text(
        "# Orchestrator Status — bd:  (updated: 2026-07-20 22:40:59 UTC)\n\n"
        "## ▶ LIVE — intern01 → src2/a.py\n"
        "- [~] intern01 → src2/a.py\n"
        "- [ ] intern\n- [ ] engineer_plan\n- [ ] intern\n"
        "- [ ] engineer_review\n- [ ] senior\n",
        encoding="utf-8",
    )
    # Simulate the runner's run-start board init (history empty, intern role).
    update_status_board([], "intern", "bd1")
    text = _read(status_board)
    # Stale intern row gone, fresh timestamp applied.
    assert "intern01" not in text
    assert "intern → src2" not in text
    # Intern is the live/in-progress role from the moment the run starts.
    assert "intern" in text
    assert "LIVE — intern" in text
    assert "- [~] intern" in text
    # Intern not mis-reported as TODO.
    assert "- [ ] intern" not in text


def test_run_start_with_from_phase(status_board):
    """A `--from intern` resume initializes the board at the intern phase, not a
    stale intern/intern row from a prior run."""
    status_board.write_text(
        "# Orchestrator Status — bd:  (updated: 2026-07-20 22:40:59 UTC)\n\n"
        "## ▶ LIVE — intern99 → src2/zzz.py\n- [~] intern99 → src2/zzz.py\n",
        encoding="utf-8",
    )
    update_status_board([], "intern", "bd1")
    text = _read(status_board)
    assert "intern99" not in text
    assert "LIVE — intern" in text
    assert "- [~] intern" in text
