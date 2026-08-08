# Problem
The `/ask` invocation experiences severe blocking latency compared to standard inference. We suspect the bottleneck lies within the `mem0` memory lifecycle—specifically, either the vector database `search()` (reading) or the LLM-driven `add()` memory extraction (writing). We currently lack observability to quantify exactly how much time each sub-operation consumes, making it impossible to optimize the behavior.

# Approach

- **Method**: 
  1. **Telemetry Injection**: Surgically inject `time.perf_counter()` wrappers into `src2/core/memory/mem0_store.py` around the core methods (`add_memory` and `search`). We will output distinct `MEM0_PERF` telemetry logs.
  2. **Isolated Baseline Testing**: Inside `[baziforecaster-only: TEST/GOLD/14_mem0/ not in kit download]`, create a standalone script (`test_mem0_latency.py`) that strictly isolates and executes the `mem0_store.py` operations (simulating what `/ask` does) without firing the rest of the Telegram/Engine stack. 
  3. **Documentation**: Create a `README.md` or `UI.md` inside the gold folder capturing the latency baselines.

- **Tool Use**:
  - `bash`: To execute `mkdir`, run `uv run python` test commands, and manage task tracking (`bd`).
  - `/tools/replace_text.py`: To safely and surgically inject the timing logic into `src2/core/memory/mem0_store.py` without risking AST corruption.
  - `/tools/write_file.py`: To scaffold the test script and documentation in `[baziforecaster-only: TEST/GOLD/14_mem0/ not in kit download]`.

- **Use of Agents**:
  - We will manage the surgical edits directly using CLI tools.
  - We will run the tests locally to ensure we get ground truth baseline performance.

# Expected Outcome
1. `mem0_store.py` will emit loud, precise metrics (e.g., `MEM0_PERF: add_memory took 3421ms`) whenever the bot accesses memory.
2. The `[baziforecaster-only: TEST/GOLD/14_mem0/ not in kit download]` folder will house a permanent, runnable diagnostic test to baseline VPS memory performance.
3. We will have empirical data proving *exactly* which part of `mem0` is holding up the `/ask` pipeline.
