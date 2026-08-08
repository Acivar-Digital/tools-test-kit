import json
import os
import time
from pathlib import Path

import httpx

GOLD_DIR = Path(__file__).resolve().parent.parent
SNAP_FILE = Path(__file__).resolve().parent / "snapshot.json"
FAKE_TELEGRAM_URL = "http://127.0.0.1:9999"
SERVER_URL = os.getenv("SERVER_URL", "http://127.0.0.1:8445")
WEBHOOK_SECRET = "00000000000000000000000000000000"


def send_webhook(chat_id: int, text: str) -> dict:
    update_id = int(time.time() * 1000) % 1000000
    payload = {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": chat_id, "is_bot": False, "first_name": "Test"},
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }

    headers = {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
    }

    try:
        resp = httpx.post(f"{SERVER_URL}/webhook", json=payload, headers=headers, timeout=120.0)
        return {"status": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"status": 0, "body": str(e)}


def run_test(verbose: bool = False, chat_id_override: int | None = None) -> dict:
    results = {
        "folder": "02_auto",
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "tests": [],
    }

    test_result = {
        "file": "snapshot.json",
        "status": "FAIL",
        "checks": [],
        "errors": [],
    }

    try:
        with open(SNAP_FILE, encoding="utf-8") as f:
            snapshot = json.load(f)

        chat_id = (
            chat_id_override if chat_id_override is not None else snapshot.get("test_user", {}).get("chat_id", 999)
        )

        # Reset user data in DB to ensure locked flow is triggered correctly
        try:
            from src2.interfaces.telegram.db import Database
            db = Database()
            db.delete_all_user_data(chat_id)
            from src2.interfaces.telegram.session import delete_session
            delete_session(chat_id)
        except Exception as e:
            print(f"Warning: Failed to clear DB data for user {chat_id}: {e}")

        # Initialize UI.md as blank
        md_file = Path(__file__).resolve().parent / "UI.md"
        with open(md_file, "w", encoding="utf-8") as f:
            f.write("")

        # 2. Iterate steps
        for step in snapshot.get("steps", []):
            step_num = step.get("step", 0)
            inp = step.get("input", {})
            expected = step.get("expected", {})

            # Reset user data and session before starting Path B (Step 8)
            if step_num == 8:
                try:
                    from src2.interfaces.telegram.db import Database
                    db = Database()
                    db.delete_all_user_data(chat_id)
                    from src2.interfaces.telegram.session import delete_session
                    delete_session(chat_id)
                except Exception as e:
                    print(f"Warning: Failed to clear DB data for user {chat_id} at Step 8: {e}")

            command = inp.get("command", inp.get("text", ""))
            step_chat_id = chat_id_override if chat_id_override is not None else inp.get("chat_id", chat_id)

            if verbose:
                print(f"    [02_auto.py] Step {step_num}: Sending '{command}'...")

            # Clear intercepted queue right before sending to capture only new responses
            try:
                httpx.delete(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)
            except Exception as e:
                test_result["errors"].append(f"Step {step_num}: Failed to clear fake Telegram queue: {e}")
                break

            # Send update to webhook
            resp = send_webhook(step_chat_id, command)
            test_result["checks"].append({"step": step_num, "command": command, "http_status": resp["status"]})

            # Assert HTTP Status
            expected_http = expected.get("http_status", 200)
            if resp["status"] != expected_http:
                test_result["errors"].append(
                    f"Step {step_num}: HTTP status {resp['status']} != expected {expected_http}"
                )
                break

            # Poll for the intercepted response message(s)
            intercepted_text = ""
            deadline = time.time() + 30.0  # 30s timeout for downstream LLM generation/reports
            while time.time() < deadline:
                try:
                    r = httpx.get(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)
                    if r.status_code == 200:
                        messages = r.json().get("messages", [])
                        matching_messages = [
                            msg.get("text", "")
                            for msg in messages
                            if msg.get("chat_id") == step_chat_id
                            and "Chronomancer is thinking" not in msg.get("text", "")
                        ]
                        if matching_messages:
                            intercepted_text = "\n\n".join(matching_messages)
                            break
                except Exception:
                    pass
                time.sleep(0.5)

            if not intercepted_text:
                test_result["errors"].append(f"Step {step_num}: Timeout waiting for message to be intercepted.")
                break

            if "Temporary System Error" in intercepted_text:
                test_result["errors"].append(f"Step {step_num}: Server returned a Temporary System Error: {intercepted_text.strip()}")
                with open(md_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n--- STEP {step_num} ({command}) ---\n\n{intercepted_text}\n")
                break

            # Verify contains assertion
            contains_str = expected.get("bot_message_contains")
            if contains_str and contains_str not in intercepted_text:
                test_result["errors"].append(f"Step {step_num}: Expected message to contain '{contains_str}'")

            # Append the raw intercepted markdown to UI.md
            with open(md_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n--- STEP {step_num} ({command}) ---\n\n{intercepted_text}\n")

            # Wait for bot background task to fully release lock
            time.sleep(3.0)

        # 3. Update snapshot file metadata
        snapshot["last_updated"] = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        with open(SNAP_FILE, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

        if not test_result["errors"]:
            test_result["status"] = "PASS"
            results["passed"] += 1
        else:
            results["failed"] += 1

        results["tests"].append(test_result)
        return results

    except Exception as e:
        test_result["errors"].append(f"Unexpected error: {e}")
        results["failed"] += 1
        results["tests"].append(test_result)
        return results
