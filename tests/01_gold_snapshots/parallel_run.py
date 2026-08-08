#!/usr/bin/env python3
"""Run conservative GOLD tests in isolated local workers."""

from __future__ import annotations

import argparse
import json
import os
import signal
import sqlite3
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
GOLD_DIR = PROJECT_ROOT / "TEST" / "GOLD"
PARALLEL_DIR = GOLD_DIR / "_parallel"
RESULTS_DIR = PARALLEL_DIR / "results"
DEFAULT_WEBHOOK_SECRET = "00000000000000000000000000000000"

WORKER_GROUPS = {
    1: ["02_auto", "04_daily", "05_forecast", "09_chrono_ask"],
    2: ["02_auto", "06_forecast_category"],
}


@dataclass
class WorkerConfig:
    worker_id: int
    port: int
    chat_id: int
    worker_dir: Path
    db_file: Path
    log_file: Path
    results_file: Path
    server_url: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run isolated GOLD workers")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--base-port", type=int, default=8450)
    parser.add_argument("--base-chat-id", type=int, default=999000)
    parser.add_argument("--server-url-template", default="http://127.0.0.1:{port}")
    return parser.parse_args()


def env_for_worker(config: WorkerConfig) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "APP_HOST": "127.0.0.1",
            "APP_PORT": str(config.port),
            "BOT_DB_PATH": str(config.db_file),
            "BOT_LOG_DIR": str(config.worker_dir),
            "DATABASE_URL": "",
            "GOLD_SERVER_URL": config.server_url,
            "GOLD_DB_FILE": str(config.db_file),
            "GOLD_LOG_FILE": str(config.log_file),
            "GOLD_CHAT_ID": str(config.chat_id),
            "GOLD_WORKER_ID": str(config.worker_id),
            "GOLD_RESULTS_FILE": str(config.results_file),
            "SKIP_NGROK": "1",
            "SKIP_TELEGRAM_WEBHOOK": "1",
        }
    )
    return env


def wait_for_health(config: WorkerConfig, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{config.server_url}/health", timeout=5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(1)
    return False


def start_server(config: WorkerConfig) -> subprocess.Popen:
    config.worker_dir.mkdir(parents=True, exist_ok=True)
    stdout = (config.worker_dir / "server_stdout.log").open("a", encoding="utf-8")
    process = subprocess.Popen(
        ["uv", "run", "start.py"],
        cwd=str(PROJECT_ROOT),
        env=env_for_worker(config),
        stdout=stdout,
        stderr=subprocess.STDOUT,
        text=True,
        preexec_fn=os.setsid,
    )
    if not wait_for_health(config):
        stop_process(process)
        raise RuntimeError(f"Worker {config.worker_id} server did not become healthy")
    return process


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGTERM)
        process.wait(timeout=10)
    except Exception:
        try:
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        except Exception:
            pass


def run_gold(config: WorkerConfig, tests: list[str], snapshots: list[str] | None = None) -> dict:
    cmd = [
        sys.executable,
        "TEST/GOLD/run.py",  # [baziforecaster-only: not in kit download]
        "--server-url",
        config.server_url,
        "--db-file",
        str(config.db_file),
        "--log-file",
        str(config.log_file),
        "--chat-id",
        str(config.chat_id),
        "--worker-id",
        str(config.worker_id),
        "--results-file",
        str(config.results_file),
        "--no-start-server",
    ]
    for test_name in tests:
        cmd.extend(["--test", test_name])
    for snapshot in snapshots or []:
        cmd.extend(["--snapshot", snapshot])

    completed = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True, capture_output=True)
    result_file = config.results_file
    status = "OK" if completed.returncode == 0 else "ERROR"
    payload: dict = {
        "worker_id": config.worker_id,
        "tests": tests,
        "status": status,
        "returncode": completed.returncode,
    }
    if result_file.exists():
        payload.update(json.loads(result_file.read_text()))
    else:
        payload.update(
            {
                "stdout": completed.stdout[-4000:],
                "stderr": completed.stderr[-4000:],
            }
        )
    return payload


def wait_for_report(config: WorkerConfig, timeout: int = 180) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = sqlite3.connect(config.db_file)
            row = conn.execute("SELECT COUNT(*) FROM Reports WHERE user_id = ?", (config.chat_id,)).fetchone()
            conn.close()
            if row and row[0] > 0:
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def build_worker(worker_id: int, args: argparse.Namespace) -> WorkerConfig:
    worker_dir = PARALLEL_DIR / f"worker_{worker_id}"
    return WorkerConfig(
        worker_id=worker_id,
        port=args.base_port + worker_id - 1,
        chat_id=args.base_chat_id + worker_id * 1000,
        worker_dir=worker_dir,
        db_file=worker_dir / "bot.db",
        log_file=worker_dir / "bot_stdout.log",
        results_file=worker_dir / "results.json",
        server_url=args.server_url_template.format(port=args.base_port + worker_id - 1),
    )


def main() -> int:
    args = parse_args()
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    processes: list[subprocess.Popen] = []
    summaries: list[dict] = []
    try:
        for worker_id in range(1, args.workers + 1):
            config = build_worker(worker_id, args)
            process = start_server(config)
            processes.append(process)

            seed_tests = ["02_auto"]
            seed_result = run_gold(config, seed_tests)
            if not wait_for_report(config):
                summaries.append(
                    {
                        "worker_id": worker_id,
                        "status": "SEED_FAILED",
                        "reason": "No report found after /auto seeding",
                        "seed_result": seed_result,
                    }
                )
                continue

            tests = WORKER_GROUPS.get(worker_id, ["02_auto"])
            run_tests = [test for test in tests if test != "02_auto"]
            snapshots = ["snapshot_best.json", "snapshot_career.json"] if worker_id == 2 else None
            summaries.append(run_gold(config, run_tests, snapshots=snapshots))
    finally:
        for process in processes:
            stop_process(process)

    merged = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workers": summaries,
        "passed": all(item.get("status") == "OK" for item in summaries),
    }
    merged_file = RESULTS_DIR / "merged.json"
    merged_file.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(json.dumps(merged, indent=2))
    return 0 if merged["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
