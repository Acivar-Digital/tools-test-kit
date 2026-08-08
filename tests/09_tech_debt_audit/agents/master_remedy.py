import asyncio
import sys
from pathlib import Path

# Project Root
project_root = Path(__file__).parents[3].resolve()
sys.path.append(str(Path(__file__).parent))

from base_agent import apply_diff, call_gemini  # noqa: E402

TASKS = [
    {
        "id": 1,
        "name": "Data Auditor",
        "file": "src2/core/schemas/unified.py",
        "instruction": "Verify the 16 'core_elements' markers. Use the provided Classical RAG context to ensure mathematical correctness. Remove the TODO markers after verification.",
        "extra_context": "RAG FINDINGS: 'Zheng Guan' is Metal. 'Fei Tian Lu Ma' is Water/Metal. 'Resource' is Water. 'Wealth' is Earth. 'Eating God' is Fire. 'Hurt Officer' is Fire. 'Cong Er' is Fire. 'Cong Cai' is Earth. 'Cong Sha' is Metal."
    },
    {
        "id": 2,
        "name": "Math Tuner",
        "file": "src/engine/bazi_math.py",
        "instruction": "Tune the Extreme_Strong (L228) and Extreme_Weak (L229) DSI bonuses. Set them to 1.5 and -1.5 respectively based on common classical weighting for specialized patterns.",
        "extra_context": ""
    },
    {
        "id": 3,
        "name": "Swarm Logic",
        "file": "src/agents/phase3_swarm.py",
        "instruction": "Fix all 12 'BUG FIX' markers. Ensure all dictionary access uses .get() instead of (or {}).get() to avoid falsy-dict traps. Remove the BUG comments after fixing.",
        "extra_context": ""
    },
    {
        "id": 4,
        "name": "Spectrum Fixer",
        "file": "src/engine/module13_spectrum.py",
        "instruction": "Fix the seasonal phase multiplier bug at L159. Ensure the mapping to [-30, +30] is implemented as: (mult - 1.0) * 30.0.",
        "extra_context": ""
    },
    {
        "id": 5,
        "name": "Memory Cleaner",
        "file": "src/memory/mem0_store.py",
        "instruction": "Replace all raw print() statements with logger.debug(). Ensure logging is used throughout the module.",
        "extra_context": ""
    },
    {
        "id": 6,
        "name": "Reliability Fixer",
        "file": "src/bot/reliability.py",
        "instruction": "Replace the DEBUG print at L102 with proper logging.",
        "extra_context": ""
    },
    {
        "id": 7,
        "name": "Audit Swarm Fixer",
        "file": "src/agents/classical_sync_v4_audit_swarm.py",
        "instruction": "Fix the 'TYPE BUG' at L360. Ensure the code handles trace as a list, not a dict.",
        "extra_context": ""
    }
]

async def run_agent(task):
    file_path = project_root / task["file"]
    print(f"[AGENT {task['id']}] Starting: {task['name']} on {task['file']}...")

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    prompt = f"TASK: {task['instruction']}\nCONTEXT: {task['extra_context']}\n\nFILE CONTENT:\n{content}\n\nReturn the ENTIRE updated file content. Do not include any explanation or markdown blocks."

    updated_content = await call_gemini(prompt)

    if "ERROR" in updated_content:
        print(f"[AGENT {task['id']}] FAILED: {updated_content}")
    else:
        apply_diff(str(file_path), updated_content)
        print(f"[AGENT {task['id']}] SUCCESS: Remediation applied to {task['file']}.")

async def main():
    print("--- STARTING REMEDIATION SWARM (7 AGENTS, 5s STAGGER) ---")

    for i, task in enumerate(TASKS):
        if i > 0:
            print(f"Waiting 5 seconds before firing Agent {task['id']}...")
            await asyncio.sleep(5)

        # Run in background to simulate parallel agents
        asyncio.create_task(run_agent(task))

    # Wait for all background tasks to finish
    await asyncio.sleep(60) # Buffer for LLM latency
    print("\n--- ALL AGENTS HAVE REPORTED ---")

if __name__ == "__main__":
    asyncio.run(main())
