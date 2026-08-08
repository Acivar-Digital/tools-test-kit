import json
import os
import subprocess
import sys
import time
from pathlib import Path

LOG_FILE = Path(__file__).resolve().parent.parent.parent / "logs" / "bot.log"
TELEMETRY_DIR = Path(__file__).resolve().parent.parent.parent / "logs" / "training_data"


def get_python_pids():
    """Get PIDs of all python processes running test/server (excluding this one)."""
    current_pid = os.getpid()
    try:
        output = subprocess.check_output(["pgrep", "-f", "python"]).decode()
        return [int(pid) for pid in output.split() if int(pid) != current_pid]
    except Exception:
        return []


def monitor_logs():
    print(f"👁️ Watchdog starting, monitoring:\n  - Logs: {LOG_FILE}\n  - Telemetry: {TELEMETRY_DIR}")

    last_inode = None
    f = None

    while True:
        # 1. Check Telemetry Directory for HTTP 4xx/5xx errors
        if TELEMETRY_DIR.exists():
            for error_file in TELEMETRY_DIR.glob("error_*.json"):
                try:
                    with open(error_file, encoding="utf-8") as ef:
                        error_data = json.load(ef)

                    print(f"\n🚨 {'-' * 40} TELEMETRY HTTP ERROR DETECTED {'-' * 40}")
                    print(f"URL:        {error_data.get('url')}")
                    print(f"Status:     {error_data.get('status_code')}")
                    print(f"Request:    {error_data.get('request')}")
                    print(f"Response:   {error_data.get('response')}")
                    print("-" * 105)

                    # Clean up the file so we don't process it again
                    error_file.unlink()
                except Exception as e:
                    print(f"Failed to read error file {error_file}: {e}")

                print("💥 Terminating all Python processes...")
                pids = get_python_pids()
                for pid in pids:
                    try:
                        os.kill(pid, 9)
                        print(f"Killed process {pid}")
                    except Exception:
                        pass
                sys.exit(1)

        # 2. Check standard logs
        if not LOG_FILE.exists():
            time.sleep(0.5)
            continue

        try:
            stat = LOG_FILE.stat()
            current_inode = stat.st_ino
        except Exception:
            time.sleep(0.5)
            continue

        # If file rotated (inode changed) or not opened yet, open/reopen it
        if current_inode != last_inode:
            if f:
                f.close()
            f = open(LOG_FILE, encoding="utf-8", errors="ignore")
            # If it's a new file (rotation), read from the start.
            # If it's the very first open, seek to end so we only watch new entries.
            if last_inode is None:
                f.seek(0, os.SEEK_END)
            last_inode = current_inode
            print(f"🔄 Watchdog opened/reopened log file (inode: {current_inode})")

        line = f.readline()
        if not line:
            time.sleep(0.1)
            continue

        # Check for error patterns (including the user-facing system error message)
        if (
            "ERROR" in line
            or "Traceback" in line
            or "Exception" in line
            or "ValueError" in line
            or "Temporary System Error" in line
        ):
            print(f"\n🚨 Watchdog detected error in logs: {line.strip()}")

            # Fetch next few lines if available to print context
            time.sleep(0.5)
            context = []
            for _ in range(25):
                next_line = f.readline()
                if next_line:
                    context.append(next_line.strip())
            if context:
                print("Context:\n" + "\n".join(context))

            print("💥 Terminating all Python processes...")
            pids = get_python_pids()
            for pid in pids:
                try:
                    os.kill(pid, 9)
                    print(f"Killed process {pid}")
                except Exception:
                    pass

            sys.exit(1)


if __name__ == "__main__":
    monitor_logs()
