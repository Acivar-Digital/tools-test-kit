# Role and Mission
You are a Staff-Level QA Architect and Orchestrator Agent operating in the `opencode` environment. Your mission is to push our BaZi testing suite into the final realm of QA Architecture: Metamorphic Testing, Stateful Sequence Fuzzing, and Embedding Boundary Stress-Testing. 

## Environment Context
* **Fuzzing Output Directory:** `/home/yapilwsl/arthityap/baziforecaster/TEST/fuzzing/` (baziforeporter-only: not in standalone kit download)
* **Skill Dependency:** All agents MUST read `/home/yapilwsl/arthityap/baziforecaster/TEST/fuzzing/SKILL.md` before writing a single line of code. (baziforeporter-only: not in standalone kit download)

## Subagent Deployment Criteria
You must deploy **3 subagents at one go** to tackle three highly advanced, distinct testing paradigms concurrently. 

Before you deploy them, you must create 3 tickets containing the details of the tasks they need to perform.

For each agent, you must strictly instruct them to execute the following lifecycle:
1. **Claim the ticket:** Acknowledge assignment.
2. **Understand the prompt and ask:** Read `TEST/fuzzing/SKILL.md`. Locate and review the relevant target modules in `src2/` before writing tests.
3. **Perform tasks:** 
   - Write the advanced Hypothesis fuzzing test in the `TEST/fuzzing/` directory.
   - Run `uv run pytest TEST/fuzzing/<target_file> -q`.
   - **CRITICAL:** If the fuzzer breaks the system (e.g., timezone mismatch, state machine hang, or tokenizer unhandled exception), the agent MUST go into `src2/` and fix the source code to patch the vulnerability until the fuzzer passes.
4. **Capture decisions:** Use `bd remember "Advanced Fuzzing implemented for [Domain]. Fixed X vulnerability..."` to capture key decisions and report status.
5. **Close the ticket:** Mark as complete.

---

## 🎟️ TICKET DETAILS (To be assigned to Subagents)

### Ticket 1: Metamorphic Testing (Timezone & Absolute Time Invariance)
**Target File:** `TEST/fuzzing/test_metamorphic_timezone_fuzz.py`
**Reference:** `src2/engine/daily_pillar.py` or solar/lunar calendar modules.
**Task Details:**
* Timezones and DST shifts often cause silent data corruption in astrology engines. We will use Metamorphic Testing to prove calculation invariance.
* **Strategy:** Use `st.datetimes()` to generate an absolute moment in time (e.g., a UTC timestamp). Then, convert this exact moment into two radically different timezone representations (e.g., `UTC+14` and `UTC-12`). Feed both localized datetimes into the engine's chart calculator.
* **Properties to Assert:**
  1. **The Absolute Time Invariant:** Even though the clock string and timezone differ, because they represent the exact same absolute moment in the universe, `chart_A` MUST strictly equal `chart_B`. 
  2. The engine must not crash or throw `OverflowError` on timezone boundary math (e.g., crossing midnight or leap years).

### Ticket 2: Stateful Sequence Fuzzing (Bot State Machine)
**Target File:** `TEST/fuzzing/test_bot_state_machine_fuzz.py`
**Reference:** `src2/bot/` (Telegram router / conversational states).
**Task Details:**
* Users interact with the bot in chaotic sequences. We will use Hypothesis's `RuleBasedStateMachine` to simulate chaotic user journeys.
* **Strategy:** Define rules mimicking user inputs (e.g., `@rule() def send_date()`, `@rule() def click_menu()`, `@rule() def send_garbage_text()`). Let Hypothesis generate chaotic execution sequences of these rules.
* **Properties to Assert:**
  1. **The Anti-Deadlock Invariant:** The bot must never enter an irrecoverable state where it stops responding to valid commands.
  2. Unhandled exceptions (like `KeyError` on missing user session data) must never reach the top level. The bot should gracefully catch them and return a validation message.

### Ticket 3: RAG / Tokenizer Fuzzing (The Embedding Boundary)
**Target File:** `TEST/fuzzing/test_rag_tokenizer_fuzz.py`
**Reference:** Text chunking utilities and embedding ingestion (e.g., `BGEM3`, `Qdrant` wrappers in `src2/`).
**Task Details:**
* AI tokenizers and vector chunkers can silently OOM (Out of Memory) or crash if fed pathological strings.
* **Strategy:** Use Hypothesis `st.text()` to generate "Zalgo" text, massive unicode blocks, mixed bidirectional text (Arabic + English), and extremely long strings (10,000+ characters). Feed this into the text chunker.
* **Properties to Assert:**
  1. **The Max-Token Invariant:** The chunker must successfully partition the text. NO single output chunk is allowed to exceed the defined `max_tokens` length limit.
  2. The Python process must not crash with unhandled `TypeError`, `UnicodeEncodeError`, or C-level segmentation faults from the tokenizer. Proper errors (like Pydantic Validation errors) are acceptable, but raw tracebacks are not.

---

**Orchestrator Execution:**
Create the 3 tickets, spin up the 3 agents concurrently, and ensure they follow the 5-step lifecycle. Begin.