import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure we can import base_agent from the same directory
sys.path.append(str(Path(__file__).parent))

from base_agent import apply_diff, call_gemini  # noqa: E402

# Annot: TEST/unit/ paths are baziforecaster-only; honour KIT_PATH / TARGET_REPO override.
_kit_root = os.getenv("KIT_PATH", "") or os.getenv("TARGET_REPO", "")
TEST_BASE = Path(_kit_root) if _kit_root else Path(".")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MasterTester")

TASKS = [
    {
        "file": str(TEST_BASE / "TEST/unit/chronomancer/test_chronomancer_output.py"),
        "instruction": "Fix imports. The logic previously in prompt_engine.py has been moved to src.engine.prompt_maker. Update imports accordingly."
    },
    {
        "file": str(TEST_BASE / "TEST/unit/chronomancer/test_chronomancer_reconstruct.py"),
        "instruction": "Fix imports. Ensure all references to prompt_engine functions point to their new modular locations (prompt_maker, prompt_checker, etc.)."
    },
    {
        "file": str(TEST_BASE / "TEST/unit/engine/test_llm_presets.py"),
        "instruction": "Update imports for openrouter and prompt_engine. Logic has been modularized."
    },
    {
        "file": str(TEST_BASE / "TEST/unit/test_mcp_super_tools.py"),
        "instruction": "Fix the ImportError. All MCP tools are located in 'codebase.mcp_codebase'. Do NOT use 'src.mcp'. Use 'codebase.mcp_codebase' for all imports."
    },
    {
        "file": str(TEST_BASE / "TEST/unit/bot/test_repro_bug_simplifier.py"),
        "instruction": "Fix imports to match the new modular structure in src/bot/handlers/."
    }
]

async def run_repair(task_id, task):
    file_path = task["file"]
    instruction = task["instruction"]

    logger.info(f"[Repair Agent {task_id}] Repairing {file_path}...")

    try:
        with open(file_path, encoding="utf-8") as f:
            current_code = f.read()
    except Exception as e:
        logger.error(f"[Repair Agent {task_id}] Failed to read {file_path}: {e}")
        return

    prompt = f"""### TASK: TEST SUITE REPAIR
The project architecture has changed. You must update the following test file to fix broken imports and function references.

### TARGET FILE: {file_path}
### INSTRUCTION: {instruction}

### PROJECT ARCHITECTURE HINTS:
- src/engine/prompt_engine.py -> orchestrator only.
- src/engine/prompt_maker.py -> contains make_month, _derive_age, etc.
- src/engine/prompt_checker.py -> contains check_month.
- src/engine/prompt_stitcher.py -> contains stitch_report.
- src/bot/app.py -> split into src/bot/handlers/*.

### CURRENT CODE:
{current_code}

### OUTPUT RULES:
1. Return ONLY the updated code for {file_path}.
2. No preamble, no markdown.
"""

    new_code = await call_gemini(prompt)
    if "ERROR" in new_code:
        logger.error(f"[Repair Agent {task_id}] LLM Error for {file_path}: {new_code}")
        return

    apply_diff(file_path, new_code)
    logger.info(f"[Repair Agent {task_id}] Repaired {file_path}.")

async def main():
    logger.info("Starting Test Suite Repair Swarm...")
    tasks = []
    for i, task in enumerate(TASKS):
        tasks.append(run_repair(i + 1, task))
        await asyncio.sleep(5)

    await asyncio.gather(*tasks)
    logger.info("Test Suite Repair completed.")

if __name__ == "__main__":
    asyncio.run(main())
