import asyncio
import json
import logging
import os
import re
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
MAX_CONCURRENT_AGENTS = 5
STAGGER_DELAY_SECONDS = 8.0

# Resolve PROJECT_ROOT inside the active baziforecaster directory
PROJECT_ROOT = Path(__file__).parents[3].resolve()
# Annot: TEST/tech_debt reports are baziforecaster-only; honour KIT_PATH override.
_kit_root = os.getenv("KIT_PATH", "")
REPORT_PATH = Path(_kit_root) / "09_tech_debt_audit" / "reports" / "raw_swarm_discovery.json" if _kit_root else PROJECT_ROOT / "TEST/tech_debt/reports/raw_swarm_discovery.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("DiscoverySwarm")

# --- PROMPT ---
SYSTEM_PROMPT = """You are a strict, read-only Python code scanner.
Your ONLY job is to output a raw JSON array of technical debt found in the provided file.
Look for:
1. "Silent Failures": `except Exception: pass` or `except: pass`
2. "Stray Tags": Any `TODO`, `FIXME`, `HACK`, or `BUG` comments.
3. "God Functions": Any function that exceeds 60 lines.
4. "Deep Nesting": Logic nested more than 4 levels deep.

Output FORMAT EXACTLY like this (and nothing else):
[
  {"line": 42, "issue": "Silent Failure", "raw_code": "except Exception: pass"},
  {"line": 105, "issue": "Stray Tag", "raw_code": "# TODO: fix this math"}
]
If no debt is found, return an empty array: []
Do NOT use markdown blocks (no ```json). Return ONLY the raw JSON array.
"""

def clean_llm_response(text: str) -> str:
    if not text:
        return "[]"
    # Strip reasoning tags
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<thought>.*", "", text, flags=re.DOTALL | re.IGNORECASE)
    # Strip markdown code blocks
    text = re.sub(r"^```[a-z]*\n", "", text, flags=re.MULTILINE | re.IGNORECASE)
    text = re.sub(r"\n```$", "", text, flags=re.MULTILINE | re.IGNORECASE)
    return text.strip()

async def scan_file(file_path: Path, semaphore: asyncio.Semaphore) -> list:
    """Reads a file and sends it to the LLM while respecting the concurrency limit with retry logic."""
    async with semaphore:
        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            logger.error(f"Could not read {file_path.name}: {e}")
            return []

        # Skip tiny files or empty init files
        if len(content.splitlines()) < 10:
            return []

        payload = {
            "contents": [{"role": "user", "parts": [{"text": f"FILE: {file_path.name}\n\nCONTENT:\n{content}"}]}],
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "generationConfig": {"temperature": 0.0}
        }

        max_retries = 5
        base_delay = 2.0
        max_delay = 32.0

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    resp = await client.post(LOCAL_URL, json=payload)

                    if resp.status_code == 429:
                        if attempt == max_retries:
                            logger.error(f"HTTP 429 Rate Limit exceeded after {max_retries} attempts for {file_path.name}")
                            return []
                        delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                        logger.warning(f"HTTP 429 Rate Limit on {file_path.name}. Retrying in {delay}s (attempt {attempt}/{max_retries})...")
                        await asyncio.sleep(delay)
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
                    clean_json = clean_llm_response(raw_text)

                    # Parse the JSON array
                    debt_items = json.loads(clean_json)

                    # Append the file name to every item found
                    for item in debt_items:
                        item["file"] = str(file_path.relative_to(PROJECT_ROOT))

                    if debt_items:
                        logger.warning(f"Found {len(debt_items)} debt items in {file_path.name}")
                    else:
                        logger.info(f"Clean: {file_path.name}")

                    return debt_items

            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON from LLM for {file_path.name}")
                return []
            except httpx.HTTPStatusError as e:
                # Other HTTP errors (like 500 etc) should also be retried or logged
                if e.response.status_code == 429:
                    # Handled above, but just in case raise_for_status caught it
                    if attempt == max_retries:
                        logger.error(f"HTTP 429 Rate Limit exceeded after {max_retries} attempts for {file_path.name}")
                        return []
                    delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                    logger.warning(f"HTTP 429 Rate Limit exception on {file_path.name}. Retrying in {delay}s (attempt {attempt}/{max_retries})...")
                    await asyncio.sleep(delay)
                    continue
                else:
                    logger.error(f"HTTP Error on {file_path.name}: {e}")
                    return []
            except httpx.RequestError as e:
                if attempt == max_retries:
                    logger.error(f"Network error on {file_path.name} after {max_retries} attempts: {e}")
                    return []
                delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
                logger.warning(f"Network/Request error on {file_path.name} ({e}). Retrying in {delay}s (attempt {attempt}/{max_retries})...")
                await asyncio.sleep(delay)
                continue
            except Exception as e:
                logger.error(f"LLM Error on {file_path.name}: {e}")
                return []

        return []

async def orchestrate_swarm():
    # 1. Target strictly production directories
    target_dirs = ["src/engine", "src/bot", "src/memory"]
    target_files = []

    for d in target_dirs:
        dir_path = PROJECT_ROOT / d
        if dir_path.exists():
            for f in dir_path.rglob("*.py"):
                # Ignore init files, cached files, and the scheduler
                if f.name != "scheduler.py" and f.name != "__init__.py" and "__pycache__" not in str(f):
                    target_files.append(f)

    logger.info(f"Targeting {len(target_files)} production files for Discovery.")

    # 2. Setup concurrency control
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)
    tasks = []

    # 3. Drip feed the tasks to protect the proxy
    for file in target_files:
        tasks.append(asyncio.create_task(scan_file(file, semaphore)))
        # Wait staggered seconds before queueing the next request
        await asyncio.sleep(STAGGER_DELAY_SECONDS)

    # 4. Wait for all agents to return
    logger.info("All agents deployed. Waiting for completion...")
    results = await asyncio.gather(*tasks)

    # 5. Flatten the list of lists
    all_debt = [item for sublist in results for item in sublist]

    # 6. Save report
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_debt, f, indent=2)

    logger.info(f"SWARM COMPLETE. Found {len(all_debt)} total debt items.")
    logger.info(f"Report saved to {REPORT_PATH}")

if __name__ == "__main__":
    asyncio.run(orchestrate_swarm())
