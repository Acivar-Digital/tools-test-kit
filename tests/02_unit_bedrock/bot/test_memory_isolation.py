"""
verify_isolation.py — Verify logical isolation in the consolidated memory architecture.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

import respx
from httpx import Response

from src.memory.memory_manager import memory_manager


async def test_isolation():
    respx.post("http://localhost:8002/v1/embeddings").respond(200, json=[[0.1] * 1024])

    user_a = 11111
    user_b = 22222

    print(f"--- Populating memories for User A ({user_a}) ---")
    await memory_manager.add_memory(user_a, "My secret code is ALPHA-99", memory_type="semantic")

    print(f"--- Populating memories for User B ({user_b}) ---")
    await memory_manager.add_memory(user_b, "My secret code is BETA-77", memory_type="semantic")

    print("\n--- Verifying User A isolation ---")
    context_a = await memory_manager.get_memory_context(user_a, "What is my secret code?")
    print(f"Context A: {context_a}")
    if "ALPHA-99" in context_a and "BETA-77" not in context_a:
        print("✅ User A isolation verified.")
    else:
        print("❌ User A isolation FAILED.")

    print("\n--- Verifying User B isolation ---")
    context_b = await memory_manager.get_memory_context(user_b, "What is my secret code?")
    print(f"Context B: {context_b}")
    if "BETA-77" in context_b and "ALPHA-99" not in context_b:
        print("✅ User B isolation verified.")
    else:
        print("❌ User B isolation FAILED.")

    # Cleanup
    print("\n--- Cleaning up test data ---")
    await memory_manager.clear_all_user_data(user_a)
    await memory_manager.clear_all_user_data(user_b)
    print("Cleanup complete.")

if __name__ == "__main__":
    asyncio.run(test_isolation())
