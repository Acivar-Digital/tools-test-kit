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
        "folder": "04_monthly",
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
                print(f"    [04_monthly.py] Step {step_num}: Sending '{command}'...")

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
            for _ in range(300):  # 150 seconds timeout (300 * 0.5s) to handle slow local LLM gateway
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

            display_text = intercepted_text if intercepted_text else "*[No response received within timeout]*"

            # Format UI.md as a clean, structured Telegram chat log showing both User and Bot
            with open(md_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n### STEP {step_num}\n")
                f.write(f"💬 **User**: `{command}`\n\n")
                f.write(f"🤖 **Bot**:\n> {display_text.replace('\n', '\n> ')}\n")

            # If the response contains error keywords or is a Temporary System Error, abort the test immediately
            lower_intercepted = intercepted_text.lower()
            if "experiencing high load" in lower_intercepted or "temporarily unavailable" in lower_intercepted:
                test_result["errors"].append(
                    f"Step {step_num}: Server encountered a Temporary System Error: {intercepted_text}"
                )
                break

            error_keywords = ["error:", "exception:", "failed with error", "analysis interrupted", "aborted:"]
            if any(kw in lower_intercepted for kw in error_keywords):
                test_result["errors"].append(
                    f"Step {step_num}: Intercepted message contains critical error keyword: {intercepted_text}"
                )
                break

            if not intercepted_text:
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
                        test_result["errors"].append(
                            f"Step {step_num}: Expected message to contain any: '{item}' missing"
                        )

            # Wait for bot background task to fully release lock
            time.sleep(3.0)

        # 3. For Step 8, wait for report generation to finish in the background
        if not test_result["errors"]:
            if verbose:
                print("    [04_monthly.py] Waiting for background monthly report generation to complete...")

            report_completed = False
            written_channel_msgs = set()
            # Wait up to 720 seconds (12 minutes) for monthly report compilation
            for wait_sec in range(240):
                try:
                    r = httpx.get(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)
                    if r.status_code == 200:
                        messages = r.json().get("messages", [])
                        for msg in messages:
                            # Intercept and record Qimen channel alerts
                            if msg.get("chat_id") == "@yapily_qimen":
                                msg_id = f"{msg.get('chat_id')}_{msg.get('text')}"
                                if msg_id not in written_channel_msgs:
                                    written_channel_msgs.add(msg_id)
                                    with open(md_file, "a", encoding="utf-8") as f:
                                        f.write(
                                            f"\n\n📢 **Qimen Channel Alert**:\n> {msg.get('text').replace('\n', '\n> ')}\n"
                                        )

                            if msg.get("chat_id") == chat_id and "Analysis Complete" in msg.get("text", ""):
                                report_completed = True
                                if verbose:
                                    print(f"    [04_monthly.py] Completion message intercepted: {msg.get('text')}")
                                with open(md_file, "a", encoding="utf-8") as f:
                                    f.write(f"\n\n--- BACKGROUND COMPLETION ---\n\n{msg.get('text')}\n")
                                break

                            # Abort background loop immediately if compilation fails or reports errors
                            msg_text = msg.get("text", "")
                            msg_text_lower = msg_text.lower()
                            error_keywords = [
                                "error:",
                                "exception:",
                                "failed with error",
                                "analysis interrupted",
                                "aborted:",
                            ]
                            if any(kw in msg_text_lower for kw in error_keywords):
                                test_result["errors"].append(f"Background compilation failed with alert: {msg_text}")
                                report_completed = False
                                break
                except Exception:
                    pass
                if report_completed or test_result["errors"]:
                    break
                time.sleep(3.0)

            if not report_completed:
                test_result["errors"].append("Timeout waiting for background monthly report completion message.")

        # Check generated master JSON report validity
        if not test_result["errors"]:
            try:
                reports_dir = Path(f"_prd/users/SGUSD0000{chat_id}/reports/1")
                master_files = list(reports_dir.glob("*_master.json"))
                if not master_files:
                    test_result["errors"].append(
                        "Assertion Error: No master report JSON file found under reports directory."
                    )
                else:
                    master_path = master_files[0]
                    with open(master_path, encoding="utf-8") as f:
                        master_data = json.load(f)

                    # Check for errors inside months
                    months_data = master_data.get("months", [])
                    if not months_data:
                        test_result["errors"].append("Assertion Error: Master JSON contains no monthly forecasts.")
                    else:
                        for m_idx, m_data in enumerate(months_data):
                            if "error" in m_data:
                                test_result["errors"].append(
                                    f"Assertion Error: Month {m_data.get('month_name', m_idx + 1)} has generation error: {m_data['error']}"
                                )
            except Exception as e:
                test_result["errors"].append(f"Assertion Error during master JSON validation: {e}")

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

        # 4. Update snapshot file metadata
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
