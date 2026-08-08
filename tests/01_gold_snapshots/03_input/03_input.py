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
        resp = httpx.post(f"{SERVER_URL}/webhook", json=payload, headers=headers, timeout=60.0)
        return {"status": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}
    except Exception as e:
        return {"status": 0, "body": str(e)}

def run_test(verbose: bool = False, chat_id_override: int | None = None) -> dict:
    results = {
        "folder": "03_input",
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

        chat_id = chat_id_override if chat_id_override is not None else snapshot.get("test_user", {}).get("chat_id", 999)

        # Reset user data in DB to ensure locked flow is triggered correctly
        try:
            from src2.interfaces.telegram.db import Database
            db = Database()
            db.delete_all_user_data(chat_id)
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

            command = inp.get("command", inp.get("text", ""))
            step_chat_id = chat_id_override if chat_id_override is not None else inp.get("chat_id", chat_id)

            if verbose:
                print(f"    [03_input.py] Step {step_num}: Sending '{command}'...")

            # Clear intercepted queue right before sending to capture only new responses
            try:
                httpx.delete(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)
            except Exception as e:
                test_result["errors"].append(f"Step {step_num}: Failed to clear fake Telegram queue: {e}")
                break

            # Send update to webhook
            resp = send_webhook(step_chat_id, command)
            test_result["checks"].append({
                "step": step_num,
                "command": command,
                "http_status": resp["status"]
            })

            # Assert HTTP Status
            expected_http = expected.get("http_status", 200)
            if resp["status"] != expected_http:
                test_result["errors"].append(f"Step {step_num}: HTTP status {resp['status']} != expected {expected_http}")
                break

            # Poll for the intercepted response message(s)
            intercepted_text = ""
            for _ in range(120):
                try:
                    r = httpx.get(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)
                    if r.status_code == 200:
                        messages = r.json().get("messages", [])
                        matching_messages = [
                            msg.get("text", "")
                            for msg in messages
                            if msg.get("chat_id") == step_chat_id and "Chronomancer is thinking" not in msg.get("text", "")
                        ]
                        if matching_messages:
                            intercepted_text = "\n\n".join(matching_messages)
                            break
                except Exception:
                    pass
                time.sleep(0.5)

            # If the response is a Temporary System Error, abort the test immediately
            if "experiencing high load" in intercepted_text or "temporarily unavailable" in intercepted_text:
                with open(md_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n--- STEP {step_num} ({command}) ---\n\n{intercepted_text}\n")
                test_result["errors"].append(f"Step {step_num}: Server encountered a Temporary System Error: {intercepted_text}")
                break

            # Always append the user command and the intercepted response first to UI.md
            with open(md_file, "a", encoding="utf-8") as f:
                display_text = intercepted_text if intercepted_text else "*[No response received within timeout]*"
                f.write(f"\n\n--- STEP {step_num} ({command}) ---\n\n{display_text}\n")

            if not intercepted_text:
                # If there are no contains assertions, we can tolerate empty intercepts for setup steps
                contains_any = expected.get("bot_message_contains_any")
                if contains_any:
                    test_result["errors"].append(f"Step {step_num}: Timeout waiting for message to be intercepted.")
                    break
            else:
                # Verify contains assertions if specified
                contains_str = expected.get("bot_message_contains")
                if contains_str and contains_str not in intercepted_text:
                    test_result["errors"].append(f"Step {step_num}: Expected message to contain '{contains_str}'")

                contains_any = expected.get("bot_message_contains_any", [])
                for item in contains_any:
                    if item not in intercepted_text:
                        test_result["errors"].append(f"Step {step_num}: Expected message to contain any: '{item}' missing")

            # Wait for bot background task to fully release lock
            time.sleep(3.0)

        # Try to read the generated K3 profile from disk and append to UI.md as Markdown table
        try:
            from src2.core.memory.memory_manager import memory_manager
            # [baziforecaster-only: TEST/GOLD/utils.py not in kit download]
            from TEST.GOLD.utils import format_engine_profile_markdown
            profile_path = memory_manager.get_profile_path(chat_id)
            if profile_path.exists():
                with open(profile_path, encoding="utf-8") as pf:
                    k3_data = json.load(pf)
                md_table = format_engine_profile_markdown(k3_data)
                with open(md_file, "a", encoding="utf-8") as f:
                    f.write(f"\n\n{md_table}\n")
        except Exception as e:
            print(f"Warning: Could not append K3 profile to UI.md: {e}")

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
