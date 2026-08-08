#!/usr/bin/env python3
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SERVER_URL = os.getenv("GOLD_SERVER_URL", "http://127.0.0.1:8445").rstrip("/")
WEBHOOK_SECRET = os.getenv("GOLD_WEBHOOK_SECRET") or os.getenv("TELEGRAM_WEBHOOK_SECRET") or "00000000000000000000000000000000"
DB_URL = os.getenv("DATABASE_URL") or "postgresql+psycopg2://postgres:postgres@localhost:5432/baziforecaster"
CHAT_ID = int(os.getenv("GOLD_CHAT_ID", "999"))
# [baziforecaster-only: TEST/GOLD/actual_artifacts directory not in kit download]
OUT = Path("TEST/GOLD/actual_artifacts")  # [baziforecaster-only: not in kit download]
OUT.mkdir(parents=True, exist_ok=True)
GLOBAL_UPDATE_ID = int(time.time() * 1000)



def send_webhook(text: str, update_id: int | None = None) -> dict:
    if update_id is None:
        update_id = int(time.time() * 1000) % 1000000
    payload = {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": CHAT_ID, "is_bot": False, "first_name": "Test"},
            "chat": {"id": CHAT_ID, "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }
    req = urllib.request.Request(
        f"{SERVER_URL}/webhook",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8")
            return {"status": resp.status, "body": json.loads(body) if body else None}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "body": e.read().decode("utf-8")}
    except Exception as e:
        return {"status": 0, "body": str(e)}


def get_session_step() -> str:
    sqlite_db_path = Path(__file__).resolve().parent.parent.parent / "bot.db"
    if not sqlite_db_path.exists():
        return f"DB_ERROR: bot.db not found at {sqlite_db_path}"
    try:
        import sqlite3
        conn = sqlite3.connect(str(sqlite_db_path), timeout=5)
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT state_json FROM Sessions WHERE user_id = ?",
            (CHAT_ID,)
        ).fetchone()
        conn.close()
        if not row or not row[0]:
            return "UNKNOWN"
        state = row[0]
        if isinstance(state, str):
            state = json.loads(state)
        return state.get("step", "UNKNOWN")
    except Exception as e:
        return f"DB_ERROR:{type(e).__name__}:{e}"


def extract_bot_messages(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    messages = []
    for m in re.finditer(r"sendMessage\((.*?)\)", text, re.S):
        block = m.group(1)
        text_match = re.search(r"text=['\"](.*?)['\"]", block, re.S)
        if text_match:
            messages.append(text_match.group(1).encode("utf-8").decode("unicode_escape", errors="replace"))
    return messages


def run_scenario(name: str, steps: list[str], waits: list[int] | None = None) -> dict:
    global GLOBAL_UPDATE_ID
    waits = waits or [2] * len(steps)
    captured = []
    for idx, text in enumerate(steps):
        GLOBAL_UPDATE_ID += 1
        before = get_session_step()
        resp = send_webhook(text, GLOBAL_UPDATE_ID)
        time.sleep(waits[idx])
        after = get_session_step()
        captured.append({
            "step": idx + 1,
            "input": text,
            "http": resp,
            "session_before": before,
            "session_after": after,
        })
    return {
        "scenario": name,
        "chat_id": CHAT_ID,
        "server_url": SERVER_URL,
        "captured_at": datetime.now(UTC).isoformat(),
        "steps": captured,
        "final_session_step": get_session_step(),
    }


def main():
    scenarios = {
        "02_auto_capture": {
            "steps": [
                "/auto",
                "Name: Test Profile, Alias: TEST, Gender: Male",
                "DOB: 1977-04-28 11:51, Location: Singapore",
                "Yes",
                "Yes",
                "1",
                "1",
                "1",
            ],
            "waits": [2, 3, 10, 2, 2, 2, 2, 2],
        },
        "04_daily_capture": {
            "steps": ["/start", "/daily"],
            "waits": [2, 20],
        },
        "05_forecast_capture": {
            "steps": ["/start", "/forecast"],
            "waits": [2, 20],
        },
        "09_chrono_ask_capture": {
            "steps": ["/start", "/daily", "What about my career this month?"],
            "waits": [2, 20, 20],
        },
    }
    results = []
    for name, spec in scenarios.items():
        results.append(run_scenario(name, spec["steps"], spec["waits"]))
    out_path = OUT / f"serial_capture_{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(out_path)


if __name__ == "__main__":
    main()
