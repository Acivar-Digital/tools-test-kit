import json
import time
from datetime import UTC, datetime
from pathlib import Path

from dotenv import load_dotenv

# [baziforecaster-only: TEST/GOLD/_helpers.py and TEST/GOLD/run.py not in kit download]
from TEST.GOLD._helpers import get_last_bot_reply_record
from TEST.GOLD.run import send_webhook

load_dotenv()

PLATFORM = "test_telegram01"
SNAPSHOT_PATH = Path(__file__).parent / "snapshot.json"
UI_PATH = Path(__file__).parent / "UI.md"


def _clear_captured_values(snapshot: dict) -> None:
    """Clear previously captured values so every session starts from a clean slate."""
    for step in snapshot.get("steps", []):
        step["actual_response"] = ""
    snapshot["last_updated"] = ""
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))


def _clear_engine_session(chat_id: int) -> None:
    """Reset the engine session."""
    try:
        from src2.interfaces.telegram.db import Database

        db = Database()
        db.delete_session(chat_id, platform=PLATFORM)
    except Exception as e:
        print(f"WARN: could not clear engine session for {chat_id}: {e}")


def _assert_contains(reply: str, expected: dict, errors: list, label: str) -> bool:
    ok = True
    must = expected.get("bot_message_contains")
    if must and must not in reply:
        errors.append(f"{label}: expected substring '{must}' not found in reply")
        ok = False
    any_of = expected.get("bot_message_contains_any")
    if any_of and not any(token in reply for token in any_of):
        errors.append(f"{label}: none of {any_of} found in reply")
        ok = False
    return ok


def run_test(verbose: bool = False, chat_id_override: int | None = None) -> dict:
    result = {
        "file": "01_start.py",
        "status": "SKIP",
        "checks": [],
        "errors": [],
    }

    ui_lines = [f"# 01_start E2E — {datetime.now(UTC).isoformat()}\n"]
    try:
        snapshot = json.loads(SNAPSHOT_PATH.read_text())

        # Clear captured values at the very start of the session
        _clear_captured_values(snapshot)

        # Clear UI.md immediately so it is fresh
        UI_PATH.write_text(f"# 01_start E2E — {datetime.now(UTC).isoformat()}\n\nRunning...")

        # One-time DB cleanup for test users at the start of the test script
        try:
            from src2.interfaces.telegram.db import Database

            db = Database()
            db.delete_all_user_data(999123490, platform=PLATFORM)

            uuid_val = db._get_or_create_uuid(999123489, platform=PLATFORM)
            session = db.Session()
            try:
                from src2.core.database.models import (
                    ChatLog,
                    DailyForecast,
                    JobQueue,
                    Report,
                    Stakeholder,
                    UserPromoUsage,
                )

                session.query(ChatLog).filter_by(user_id=uuid_val).delete()
                session.query(DailyForecast).filter_by(user_id=uuid_val).filter(not DailyForecast.is_permanent).delete()
                session.query(JobQueue).filter_by(user_id=uuid_val).delete()
                session.query(Report).filter_by(user_id=uuid_val).delete()
                session.query(Stakeholder).filter_by(user_id=uuid_val).delete()
                session.query(UserPromoUsage).filter_by(user_id=uuid_val).delete()
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                db.Session.remove()
        except Exception as e:
            print(f"WARN: could not perform initial DB cleanup: {e}")

        for step in snapshot.get("steps", []):
            chat_id = chat_id_override if chat_id_override is not None else step["input"]["chat_id"]
            command = step["input"]["command"]
            expected = step.get("expected", {})

            # Fresh engine session for this user so /start rebuilds cleanly
            _clear_engine_session(chat_id)

            prev_reply_meta = get_last_bot_reply_record(chat_id, PLATFORM)

            resp = send_webhook(chat_id, command)
            result["checks"].append(
                {
                    "step": step.get("step"),
                    "label": step.get("label"),
                    "command": command,
                    "http_status": resp["status"],
                }
            )

            if expected.get("http_status") and resp["status"] != expected["http_status"]:
                result["errors"].append(
                    f"Step {step.get('step')}: HTTP {resp['status']} != expected {expected['http_status']}"
                )
                result["status"] = "FAIL"
                return result

            # Poll for the new response message, ignoring thinking status messages
            reply = None
            deadline = time.time() + 15.0  # 15s timeout
            while time.time() < deadline:
                current_meta = get_last_bot_reply_record(chat_id, PLATFORM)
                if current_meta:
                    if not prev_reply_meta or current_meta["id"] != prev_reply_meta["id"]:
                        if "Chronomancer is thinking" in current_meta["message_text"]:
                            # Status update, record it and keep waiting for actual response
                            prev_reply_meta = current_meta
                        else:
                            reply = current_meta["message_text"]
                            break
                time.sleep(0.5)

            if not reply:
                result["errors"].append(f"Step {step.get('step')}: no bot reply captured")
                result["status"] = "FAIL"
                return result

            step["actual_response"] = reply
            ui_lines.append(f"## Step {step.get('step')} — {step.get('label')} (chat {chat_id})\n\n{reply}\n")

            if not _assert_contains(reply, expected, result["errors"], f"Step {step.get('step')}"):
                result["status"] = "FAIL"
                return result

        # Persist captured answers back into the snapshot on success
        snapshot["last_updated"] = datetime.now(UTC).isoformat()
        SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False))

        result["status"] = "PASS"
    except Exception as e:
        result["errors"].append(str(e))
        result["status"] = "FAIL"
        ui_lines.append(f"\nExecution aborted due to exception: {e}\n")
    finally:
        UI_PATH.write_text("\n".join(ui_lines) + "\n")

    return result
