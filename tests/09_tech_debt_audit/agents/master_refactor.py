import asyncio
import logging
import sys
from pathlib import Path

# Ensure we can import base_agent from the same directory
sys.path.append(str(Path(__file__).parent))

from base_agent import apply_diff, call_gemini

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MasterRefactor")

TASKS = [
    {
        "file": "src/engine/prompt_engine.py",
        "instruction": "Split this 1060-line file into a modular structure. Extract Stage 1 (MAKER) logic into a new file 'src/engine/prompt_maker.py', Stage 2 (CHECKER) into 'src/engine/prompt_checker.py', and Stage 3/4 into 'src/engine/prompt_stitcher.py'. Update the original file to import and orchestrate these new modules. Ensure all dependencies and helper functions are correctly shared."
    },
    {
        "file": "src/engine/openrouter.py",
        "instruction": "Modularize this file. Extract the XML parsing and RAG retrieval logic into a new utility file 'src/engine/llm_utils.py'. Keep the core API calling logic in openrouter.py. Ensure the AsyncClient handling remains robust."
    },
    {
        "file": "src/bot/app.py",
        "instruction": "Refactor this monolith. Extract Telegram command handlers into a new package 'src/bot/handlers/'. Each major command (/start, /forecast) should have its own file. Keep only the main app initialization and middleware in app.py."
    },
    {
        "file": "src/engine/module3_interaction.py",
        "instruction": "Reduce complexity and nesting. Split the clash/penalty/harm logic into a separate file 'src/engine/interactions_core.py'. Keep the high-level orchestration in the original file."
    },
    {
        "file": "src/bot/chronomancer_handler.py",
        "instruction": "Modularize the intake states. Extract the 'CHOOSING', 'COLLECTING', and 'CONFIRM' state logic into a separate state-machine module 'src/bot/intake_states.py'."
    },
    {
        "file": "src/engine/module0_geju.py",
        "instruction": "Extract the large _GE_JU_DETECTION_RULES and lookup tables into a separate data file 'src/engine/ge_ju_data.py'. Leave only the detection logic in the main file."
    }
]

async def run_agent(task_id, task):
    file_path = task["file"]
    instruction = task["instruction"]

    logger.info(f"[Agent {task_id}] Starting refactor for {file_path}...")

    # Read the current content
    try:
        with open(file_path, encoding="utf-8") as f:
            current_code = f.read()
    except Exception as e:
        logger.error(f"[Agent {task_id}] Failed to read {file_path}: {e}")
        return

    prompt = f"""### TASK: ARCHITECTURAL REFACTORING
You are a senior systems architect. Your goal is to modularize the following file to improve maintainability and reduce file size.

### TARGET FILE: {file_path}
### INSTRUCTION: {instruction}

### CURRENT CODE:
{current_code}

### OUTPUT RULES:
1. Return ONLY the updated code for the target file {file_path}.
2. If the instruction asks for new files, provide them in a CLEARLY MARKED format like:
   FILE: [path]
   [code]
   ---
3. Ensure the target file imports all newly created modules correctly.
4. Maintain 100% functional parity. Do not change logic, only structure.
5. Use absolute imports (src.engine...) or relative as per the project style.
"""

    new_code = await call_gemini(prompt)

    if "ERROR" in new_code:
        logger.error(f"[Agent {task_id}] LLM Error for {file_path}: {new_code}")
        return

    # For this refactor, we assume the LLM returns the updated main file and possibly instructions for new files.
    # In a real swarm, we'd parse multiple files. For this agentic pass, we'll focus on the main file update.
    apply_diff(file_path, new_code)
    logger.info(f"[Agent {task_id}] Completed refactor for {file_path}.")

async def main():
    logger.info(f"Starting Refactor Swarm with {len(TASKS)} tasks...")

    tasks = []
    for i, task in enumerate(TASKS):
        tasks.append(run_agent(i + 1, task))
        # 5 second staggered start to avoid local congestion
        await asyncio.sleep(5)

    await asyncio.gather(*tasks)
    logger.info("Refactor Swarm completed successfully.")

if __name__ == "__main__":
    asyncio.run(main())
