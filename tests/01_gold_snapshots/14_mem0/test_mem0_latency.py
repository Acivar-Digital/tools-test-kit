import logging
import os
import sys
from dotenv import load_dotenv

# Setup minimal logging to see MEM0_PERF
logging.basicConfig(level=logging.INFO, format="%(message)s")

# Load environment variables
load_dotenv(".env")

# Ensure Python path knows about src2
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))

try:
    from src2.core.memory.mem0_store import Mem0Store
except ImportError as e:
    print(f"Failed to import Mem0Store: {e}")
    sys.exit(1)

def main():
    print("--- Starting Mem0 Latency Test ---")
    store = Mem0Store()
    
    if not store.enabled:
        print("Mem0Store is disabled. Check your environment variables (QDRANT_URL, BGEM3_URL).")
        sys.exit(1)
        
    test_user_id = 999999999
    
    print("\n[1/2] Testing add_memory()...")
    # This invokes the LLM extraction in mem0
    dummy_text = "I am a test user and I love programming in Python. I also study Bazi and want to understand my wealth element."
    try:
        store.add_memory(user_id=test_user_id, text=dummy_text, memory_type="episodic")
    except Exception as e:
        print(f"add_memory failed: {e}")
        
    print("\n[2/2] Testing search()...")
    # This invokes vector DB search
    try:
        results = store.search(user_id=test_user_id, query="What do I study?", top_k=3)
        print(f"Search returned {len(results)} results.")
    except Exception as e:
        print(f"search failed: {e}")
        
    print("\n--- Cleaning up test user memories ---")
    try:
        store.delete_user_memories(user_id=test_user_id)
    except Exception as e:
        print(f"cleanup failed: {e}")

    print("--- Test Complete ---")

if __name__ == "__main__":
    main()
