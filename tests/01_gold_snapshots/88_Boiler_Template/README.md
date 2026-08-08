# 🗺️ Gold Test Boilerplate Architecture

This directory serves as the architectural blueprint for all Gold E2E tests in the BaziForecaster project. Any new Gold Test (e.g., `13_relationship`, `14_transit`) should follow this exact pattern to ensure clean separation of concerns, automated preflighting, and seamless Git-backed visual diffing.

---

## 📂 Standard Gold Test Directory Structure

Every gold test suite must reside in a dedicated folder under `[baziforecaster-only: TEST/GOLD/ not in kit download]` named `[index]_[test_name]/` and contain these five files:

```text
[baziforecaster-only: TEST/GOLD/ not in kit download][index]_[test_name]/
├── path.md             # 1. Path Spec (Conceptual success/failure flows & behaviors)
├── snapshot.json       # 2. Input Spec (Declarative inputs and expected outcomes)
├── [test_name].py       # 3. Test Logic (Sends webhooks, polls fake TG, writes UI.md)
├── UI.md                # 4. Captured Reality (Rendered chat history and alerts)
└── run_[test_name].py   # 5. Orchestrator (Config swap, preflight, run, auto-commit)
```

---

## 🛠️ The 5 Components of a Gold Test

### 1. `path.md` (The Path Specification)
A conceptual markdown file defining the success and failure paths of the feature. It documents exactly what behaviors, alerts, logs, and database states are expected.
> 💡 **Testing Strategy**: The main gold test folder focuses strictly on executing the **Success Path** (happy path). Negative test cases and failure paths are kept in separate subfolders or dedicated folders to keep the main test clean and readable.

### 2. `snapshot.json` (The Input Specification)
A declarative JSON file that defines the mock user profile, the sequence of inputs (commands or text), and the expected HTTP status codes or message substrings.

### 3. `[test_name].py` (The Test Logic)
The execution engine for the test. It:
*   Clears any existing data for the test user from the database.
*   Sends mock Telegram updates to the `/webhook` endpoint.
*   Polls the fake Telegram server (`/intercepted`) for the bot's responses.
*   Asserts that the responses match the criteria in `snapshot.json`.
*   Writes the interaction log in real-time to `UI.md`.

### 4. `UI.md` (The Captured Reality)
A markdown file that acts as a human-readable chat log of the test run. Because it is checked into Git, any change in the engine's behavior, tone, or formatting immediately shows up as a clean `git diff` for developer review. **This is our un-hallucinated ground truth.**

### 5. `run_[test_name].py` (The Lifecycle Orchestrator)
The top-level developer script. It wraps the entire lifecycle:
1.  **Swaps** the configuration to Gold mode.
2.  **Preflights** the environment (checks DB, Valkey, APIs).
3.  **Executes** the test.
4.  **Auto-commits** `UI.md` if the test passes and changes are detected.

---

## 📋 Boilerplate Code Templates

### A. The Test Logic (`[test_name].py`)

```python
import json
import time
from pathlib import Path
import httpx

GOLD_DIR = Path(__file__).resolve().parent.parent
SNAP_FILE = Path(__file__).resolve().parent / "snapshot.json"
FAKE_TELEGRAM_URL = "http://127.0.0.1:9999"
SERVER_URL = "http://127.0.0.1:8445"
WEBHOOK_SECRET = "00000000000000000000000000000000"

def send_webhook(chat_id: int, text: str) -> dict:
    update_id = int(time.time() * 1000) % 1000000
    payload = {
        "update_id": update_id,
        "message": {
            "message_id": update_id,
            "from": {"id": chat_id, "is_bot": False, "first_name": "TestUser"},
            "chat": {"id": chat_id, "type": "private"},
            "date": int(time.time()),
            "text": text,
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": WEBHOOK_SECRET,
    }
    resp = httpx.post(f"{SERVER_URL}/webhook", json=payload, headers=headers, timeout=30.0)
    return {"status": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}

def run_test(verbose: bool = False, chat_id_override: int | None = None) -> dict:
    results = {"folder": Path(__file__).parent.name, "passed": 0, "failed": 0, "skipped": 0, "tests": []}
    test_result = {"file": "snapshot.json", "status": "FAIL", "checks": [], "errors": []}

    try:
        with open(SNAP_FILE, encoding="utf-8") as f:
            snapshot = json.load(f)

        chat_id = chat_id_override or snapshot.get("test_user", {}).get("chat_id", 999)

        # Clear DB to ensure clean state
        try:
            from src2.interfaces.telegram.db import Database
            db = Database()
            db.delete_all_user_data(chat_id)
        except Exception as e:
            print(f"Warning: Failed to clear DB data: {e}")

        # Reset UI.md
        md_file = Path(__file__).resolve().parent / "UI.md"
        md_file.write_text("", encoding="utf-8")

        # Run steps
        for step in snapshot.get("steps", []):
            step_num = step.get("step", 0)
            inp = step.get("input", {})
            expected = step.get("expected", {})
            command = inp.get("command", inp.get("text", ""))

            # Clear intercepted queue
            httpx.delete(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)

            # Send webhook
            resp = send_webhook(chat_id, command)
            test_result["checks"].append({"step": step_num, "command": command, "http_status": resp["status"]})

            if resp["status"] != expected.get("http_status", 200):
                test_result["errors"].append(f"Step {step_num}: HTTP status {resp['status']} != expected {expected.get('http_status')}")
                break

            # Poll for response
            intercepted_text = ""
            for _ in range(60):  # 30 seconds timeout
                try:
                    r = httpx.get(f"{FAKE_TELEGRAM_URL}/intercepted", timeout=2.0)
                    if r.status_code == 200:
                        messages = r.json().get("messages", [])
                        matching = [m.get("text", "") for m in messages if m.get("chat_id") == chat_id and "thinking" not in m.get("text", "")]
                        if matching:
                            intercepted_text = "\n\n".join(matching)
                            break
                except Exception:
                    pass
                time.sleep(0.5)

            # Log to UI.md
            with open(md_file, "a", encoding="utf-8") as f:
                f.write(f"\n\n### STEP {step_num}\n💬 **User**: `{command}`\n\n🤖 **Bot**:\n> {intercepted_text.replace('\n', '\n> ')}\n")

            if not intercepted_text:
                test_result["errors"].append(f"Step {step_num}: Timeout waiting for response.")
                break

            # Assertions
            contains_str = expected.get("bot_message_contains")
            if contains_str and contains_str not in intercepted_text:
                test_result["errors"].append(f"Step {step_num}: Response missing expected text: '{contains_str}'")
                break

            time.sleep(1.0)

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
```

---

### B. The Orchestrator (`run_[test_name].py`)

```python
import sys
import subprocess
from pathlib import Path

# Extract the test name from folder naming: e.g. "04_monthly"
TEST_NAME = Path(__file__).resolve().parent.name.split("_", 1)[1]
# [baziforecaster-only: TEST/GOLD/ directory not in kit download]
UI_MD_PATH = f"TEST/GOLD/{Path(__file__).resolve().parent.name}/UI.md"  # [baziforecaster-only: not in kit download]

def run_cmd(cmd: str, exit_on_fail: bool = True) -> tuple[int, str]:
    print(f"Executing: {cmd}")
    process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    
    output_lines = []
    for line in iter(process.stdout.readline, ""):
        sys.stdout.write(line)
        sys.stdout.flush()
        output_lines.append(line)
        
    process.wait()
    output = "".join(output_lines)
    
    if process.returncode != 0 and exit_on_fail:
        print(f"\n❌ Command failed with exit code {process.returncode}: {cmd}")
        sys.exit(process.returncode)
        
    return process.returncode, output

def main():
    print(f"=== 🚀 Starting Automated Gold Test Orchestrator ({TEST_NAME}) ===")
    
    # 1. Swap config to UAT/Gold mode
    # [baziforecaster-only: TEST/GOLD/swap_config.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.]
    code, _ = run_cmd("uv run python TEST/GOLD/swap_config.py --mode gold", exit_on_fail=False)  # [baziforecaster-only: not in kit download]
    if code != 0:
        # [baziforecaster-only: TEST/GOLD/swap_config.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.]
        run_cmd("uv run python TEST/GOLD/swap_config.py")  # [baziforecaster-only: not in kit download]
        
    # 2. Run Preflight Diagnostics
    run_cmd("uv run python -m src2.interfaces.telegram.preflight")

    # 3. Execute the Gold Test
    print(f"\n🏃 Running {TEST_NAME} gold test...")
    # [baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.]
    test_code, _ = run_cmd(f"uv run python TEST/GOLD/run.py --test {TEST_NAME}", exit_on_fail=False)  # [baziforecaster-only: not in kit download]
    
    if test_code != 0:
        print(f"\n❌ Gold test {TEST_NAME} FAILED (Exit Code: {test_code}).")
        sys.exit(test_code)
        
    print(f"\n🎉 Gold test {TEST_NAME} PASSED successfully!")
    
    # 4. Check for changes and auto-commit
    git_status_code, status_out = run_cmd(f"git status --porcelain {UI_MD_PATH}", exit_on_fail=False)
    if git_status_code == 0 and status_out.strip():
        print("\n📝 Detected changes in gold baseline. Committing...")
        run_cmd(f"git add {UI_MD_PATH}")
        run_cmd(f'git commit -m "test(gold): update {TEST_NAME} gold baseline"')
        print("✅ Baseline committed successfully.")
    else:
        print("\nℹ️ No changes detected in the gold baseline. Nothing to commit.")

if __name__ == "__main__":
    main()
```

---

### C. The Configuration (`snapshot.json`)

```json
{
  "test_user": {
    "chat_id": 999
  },
  "steps": [
    {
      "step": 1,
      "input": {
        "command": "/start"
      },
      "expected": {
        "http_status": 200,
        "bot_message_contains": "Welcome to BaziForecaster"
      }
    }
  ]
}
```
