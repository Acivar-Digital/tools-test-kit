import asyncio
import json
import logging
import os
import subprocess
import sys
from pathlib import Path

import httpx

# KIT_* bridge — honour config.load_config, keep localfree gemini fallback
sys.path.insert(0, str(Path(__file__).parents[2].resolve()))
from config import load_config

_kit_path, _kit_base_url, _kit_api_key, _kit_model, _kit_mem0 = load_config()

# --- CONFIGURATION ---
base_url = os.getenv("LOCAL_FREE_GEMINI_URL", "http://localhost:18000/v1")
api_key = os.getenv("LLM_API_KEY") or _kit_api_key or "localfreegemini"
LOCAL_URL = f"{base_url.replace('/v1', '/v1beta')}/models/gemini-3.1-flash-lite:generateContent?key={api_key}"
PROJECT_ROOT = Path(__file__).parents[3].resolve()
# Annot: TEST/tech_debt reports are baziforecaster-only; honour KIT_PATH override.
_kit_root = os.getenv("KIT_PATH", "")
VERIFIED_DEBT_PATH = Path(_kit_root) / "09_tech_debt_audit" / "reports" / "verified_tech_debt.json" if _kit_root else PROJECT_ROOT / "TEST/tech_debt/reports/verified_tech_debt.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("CleanupSwarm")

SYSTEM_PROMPT = """You are an expert software engineer specialized in safe, precise, surgical refactoring.
Your job is to fix a specific technical debt issue in a Python file.

Guidelines:
1. Preserve ALL mathematical Bazi calculations and existing business logic exactly.
2. Fix ONLY the specified line/block.
3. For "Silent Failure" issues, replace the silent `except Exception: pass` or `except: pass` with proper logging:
   - Ensure you import `logging` if it is not already present, or use an existing logger if defined (e.g. `logger.error(..., exc_info=True)`).
4. Output ONLY the complete, valid rewritten Python code. Do NOT wrap it in markdown code blocks. Do NOT include preambles or explanations. Just start with the code.
"""

def clean_llm_response(text: str) -> str:
    if not text:
        return ""
    import re
    # Strip thoughts
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thought>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip markdown blocks
    text = re.sub(r"^```[a-z]*\n", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"\n```$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    return text.strip()

def run_cmd(cmd: list[str]) -> bool:
    try:
        res = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
        return res.returncode == 0
    except Exception as e:
        logger.error(f"Failed to run command {cmd}: {e}")
        return False

def run_tests() -> bool:
    logger.info("Running Ruff Check...")
    if not run_cmd(["uv", "run", "ruff", "check", "."]):
        logger.warning("Ruff linter failed!")
        return False
    logger.info("Running project verification test suite...")
    # Annot: TEST/test_run.py is baziforecaster-only; guarded by existence check
    test_runner = PROJECT_ROOT / "TEST/test_run.py"
    if test_runner.exists():
        if not run_cmd(["uv", "run", "python", str(test_runner)]):
            logger.warning("Test suite failed!")
            return False
    else:
        logger.warning("TEST/test_run.py not found — skipping (baziforecaster-only).")
    return True

async def request_fix(file_path: Path, issue: dict) -> str:
    with open(file_path, encoding="utf-8") as f:
        file_content = f.read()

    prompt = (
        f"We are fixing a {issue['issue']} in this file.\n"
        f"The issue is at line {issue['line']}.\n"
        f"Code segment to fix:\n{issue['raw_code']}\n\n"
        f"FILE CONTENT:\n{file_content}\n"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"temperature": 0.0}
    }

    # Exponential Backoff Retries to protect against 429 or 500 errors
    max_retries = 5
    backoff = 2.0

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=150.0) as client:
                resp = await client.post(LOCAL_URL, json=payload)
                resp.raise_for_status()
                data = resp.json()
                raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                return clean_llm_response(raw_text)
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for {file_path.name}: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {backoff} seconds...")
                await asyncio.sleep(backoff)
                backoff *= 2
            else:
                logger.error(f"All cleanup LLM attempts failed for {file_path.name}")
    return ""

async def fix_issue(issue: dict):
    file_rel = issue["file"]
    file_path = PROJECT_ROOT / file_rel
    if not file_path.exists():
        logger.error(f"File {file_rel} not found.")
        return

    logger.info(f"Attempting to fix {issue['issue']} at line {issue['line']} in {file_rel}")

    # 1. Ask LLM for the fixed file content
    fixed_content = await request_fix(file_path, issue)
    if not fixed_content or len(fixed_content) < 50:
        logger.error(f"Invalid code response for {file_rel}.")
        return

    # 2. Backup current content
    with open(file_path, encoding="utf-8") as f:
        original_content = f.read()

    # 3. Write fixed content
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(fixed_content)

    # 4. Validate with linter and tests
    if run_tests():
        logger.info(f"Successfully verified fix for {file_rel} at line {issue['line']}!")
        # Automatically stage individual fix
        run_cmd(["git", "add", str(file_rel)])
    else:
        logger.warning(f"Validation failed for {file_rel}. Reverting change...")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(original_content)

async def main():
    if not VERIFIED_DEBT_PATH.exists():
        logger.error("No verified technical debt report found.")
        return

    with open(VERIFIED_DEBT_PATH, encoding="utf-8") as f:
        items = json.load(f)

    # Filter strictly for HIGH priority silent failures first to handle them safely
    high_priority = [i for i in items if i.get("priority") == "HIGH" and i.get("issue") == "Silent Failure"]

    if not high_priority:
        logger.info("No HIGH priority silent failures found. Nothing to do!")
        return

    logger.info(f"Found {len(high_priority)} verified high priority silent failures to fix.")

    for item in high_priority:
        await fix_issue(item)

if __name__ == "__main__":
    asyncio.run(main())
