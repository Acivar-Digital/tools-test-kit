import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from factory.infra import runner
from factory.infra.control import TEMP_DIR


def _repo_root() -> Path:
    return Path(runner.__file__).resolve().parents[3]


def _cleanup(*paths: Path) -> None:
    for p in paths:
        try:
            p.unlink()
        except Exception:
            pass


def test_stage_path_absolute_temp_collapses():
    repo_root = _repo_root()
    abs_fp = str(
        repo_root / "admin" / "orchestrator" / "temp" / "src2" / "_staging_t" / "abs.py"
    )
    assert runner.stage_path(abs_fp) == str(TEMP_DIR / "src2" / "_staging_t" / "abs.py")


def test_stage_path_relative_temp_prefixes():
    assert (
        runner.stage_path("factory/temp/src2/_staging_t/rel1.py")
        == str(TEMP_DIR / "src2" / "_staging_t" / "rel1.py")
    )
    assert (
        runner.stage_path("temp/src2/_staging_t/rel2.py")
        == str(TEMP_DIR / "src2" / "_staging_t" / "rel2.py")
    )


def test_staged_zero_diff_real_edit_not_blocked():
    repo_root = _repo_root()
    fp = str(repo_root / "admin" / "orchestrator" / "temp" / "src2" / "_staging_t" / "crash.py")
    mirror = Path(runner.stage_path(fp))
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text("A\n", encoding="utf-8")
    mirror_orig = Path(str(mirror) + ".orig")
    mirror_orig.write_text("B\n", encoding="utf-8")
    try:
        assert runner.staged_zero_diff(fp) is False
    finally:
        _cleanup(mirror, mirror_orig)

    fp2 = "src2/_staging_t/crash2.py"
    mirror2 = Path(runner.stage_path(fp2))
    mirror2.parent.mkdir(parents=True, exist_ok=True)
    mirror2.write_text("A\n", encoding="utf-8")
    mirror2_orig = Path(str(mirror2) + ".orig")
    mirror2_orig.write_text("B\n", encoding="utf-8")
    try:
        assert runner.staged_zero_diff(fp2) is False
    finally:
        _cleanup(mirror2, mirror2_orig)


def test_staged_zero_diff_genuine_zero_diff():
    fp = "src2/_staging_t/zerodiff.py"
    mirror = Path(runner.stage_path(fp))
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text("X\n", encoding="utf-8")
    mirror_orig = Path(str(mirror) + ".orig")
    mirror_orig.write_text("X\n", encoding="utf-8")
    try:
        assert runner.staged_zero_diff(fp) is True
    finally:
        _cleanup(mirror, mirror_orig)


def test_staged_zero_diff_new_file_and_hallucinated():
    fp = "src2/_staging_t/newfile.py"
    mirror = Path(runner.stage_path(fp))
    mirror.parent.mkdir(parents=True, exist_ok=True)
    mirror.write_text("Y\n", encoding="utf-8")
    try:
        assert runner.staged_zero_diff(fp) is None
    finally:
        _cleanup(mirror)

    fp2 = "src2/_staging_t/does_not_exist.py"
    assert runner.staged_zero_diff(fp2) is None
