#!/usr/bin/env python3
"""run_all.py -- fire every orchestrator test file in parallel, then report.

Each test_*.py (and the bifr/ sub-suite) runs as its OWN pytest subprocess so a
slow or hanging file cannot block the others. Files run concurrently via a
ThreadPoolExecutor; the timeout-fire tests prove the harness itself trips on
timeouts, so a truly wedged file is the only thing that can stall a worker and
it is bounded by --per-file-timeout.

No new dependencies. Run from anywhere:

    uv run python factory/test/run_all.py
    uv run python factory/test/run_all.py --workers 16
    uv run python factory/test/run_all.py test_loopguard.py test_state.py
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent

_SUMMARY_RE = re.compile(
    r"(\d+) (passed|failed)|(\d+) error|(\d+) skipped|"
    r"(failed|error) exiting|no tests ran",
)


@dataclass
class FileResult:
    path: Path
    rc: int
    passed: int = 0
    failed: int = 0
    error: int = 0
    skipped: int = 0
    duration: float = 0.0
    timed_out: bool = False
    output: str = ""


def discover(root: Path) -> list[Path]:
    files: list[Path] = []
    for p in sorted(root.rglob("test_*.py")):
        if "build" in p.parts or p.parent.name == "__pycache__":
            continue
        files.append(p)
    return files


def parse_summary(out: str, rc: int) -> tuple[int, int, int, int]:
    passed = failed = error = skipped = 0
    for line in out.splitlines():
        if "passed" in line or "failed" in line or "error" in line:
            m = re.search(r"(\d+) passed", line)
            if m:
                passed = int(m.group(1))
            m = re.search(r"(\d+) failed", line)
            if m:
                failed = int(m.group(1))
            m = re.search(r"(\d+) error", line)
            if m:
                error = int(m.group(1))
            m = re.search(r"(\d+) skipped", line)
            if m:
                skipped = int(m.group(1))
    if rc != 0 and failed == 0 and error == 0 and passed == 0:
        error = 1
    return passed, failed, error, skipped


def run_one(path: Path, per_file_timeout: int) -> FileResult:
    start = time.monotonic()
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", str(path), "-q", "-p", "no:cacheprovider"],
            capture_output=True, text=True, cwd=HERE, timeout=per_file_timeout,
        )
        rc = proc.returncode
        out = proc.stdout + proc.stderr
        timed_out = False
    except subprocess.TimeoutExpired as e:
        rc = -1
        out = (e.stdout or b"").decode(errors="replace") + (e.stderr or b"").decode(errors="replace")
        out += f"\n[run_all] FILE TIMED OUT after {per_file_timeout}s\n"
        timed_out = True
    dur = time.monotonic() - start
    p, f, err, s = parse_summary(out, rc)
    return FileResult(path=path, rc=rc, passed=p, failed=f, error=err,
                      skipped=s, duration=dur, timed_out=timed_out, output=out)


def main() -> int:
    ap = argparse.ArgumentParser(description="Run all orchestrator tests in parallel.")
    ap.add_argument("files", nargs="*", help="optional subset of test files/dirs")
    ap.add_argument("--workers", type=int, default=min(16, (os.cpu_count() or 4) * 2),
                    help="concurrent pytest subprocesses (default: min(16, cpus*2))")
    ap.add_argument("--per-file-timeout", type=int, default=300,
                    help="hard kill a single file's run after N seconds (default 300)")
    args = ap.parse_args()

    if args.files:
        targets: list[Path] = []
        for f in args.files:
            p = (HERE / f).resolve()
            if p.is_dir():
                targets.extend(discover(p))
            else:
                targets.append(p)
    else:
        targets = discover(HERE)

    if not targets:
        print("No test files found.", file=sys.stderr)
        return 2

    print(f"== run_all: {len(targets)} test files, {args.workers} workers, "
          f"{args.per_file_timeout}s/file ceiling ==")
    results: list[FileResult] = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(run_one, t, args.per_file_timeout): t for t in targets}
        for fut in as_completed(futs):
            r = fut.result()
            results.append(r)
            tag = "TIMEOUT" if r.timed_out else ("FAIL" if r.rc != 0 else "ok")
            print(f"  [{tag:7}] {r.path.name:42} "
                  f"{r.passed}p {r.failed}f {r.error}e {r.skipped}s "
                  f"({r.duration:5.1f}s)")

    results.sort(key=lambda r: r.path.name)
    tot_p = sum(r.passed for r in results)
    tot_f = sum(r.failed for r in results)
    tot_e = sum(r.error for r in results)
    tot_s = sum(r.skipped for r in results)
    failed_files = [r for r in results if r.rc != 0]

    print("\n" + "=" * 70)
    print("REPORT")
    print("=" * 70)
    for r in results:
        status = "TIMEOUT" if r.timed_out else ("FAIL" if r.rc != 0 else "PASS")
        print(f"  {status:7} {r.path.name}")
    print("-" * 70)
    print(f"  files={len(results)} passed={tot_p} failed={tot_f} "
          f"error={tot_e} skipped={tot_s}")
    if failed_files:
        print(f"\n  {len(failed_files)} file(s) with failures:")
        for r in failed_files:
            print(f"    - {r.path.name} (rc={r.rc})")
        print("\n  First failure tail:")
        print(_tail(failed_files[0].output))
    print("=" * 70)
    return 1 if failed_files else 0


def _tail(text: str, n: int = 25) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])


if __name__ == "__main__":
    raise SystemExit(main())
