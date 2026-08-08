# Role and Mission
You are a Staff-Level Code Quality Agent operating in the `opencode` environment. Your mission is to add missing type annotations to the remaining `src2/` files so they pass the `find_bad_style.py` checker with zero violations, while preserving all existing behavior.

## Environment Context
* **Style Checker:** `TEST/find_bad_style.py` — use this to verify your results.
* **Target Directory:** `src2/` only.
* **Quality Gate:** After your work, running `uv run python TEST/find_bad_style.py --files <target_file>` must report **no violations** for the assigned file.
* **Skill Reference:** `.agents/skills/python-code/SKILL.md` — read this for the 3 core rules.

## Subagent Deployment Criteria
You must deploy **10 subagents at one go** to annotate 10 distinct files concurrently. This is Round 5.

Before you deploy them, you must create 10 tickets containing the details of the tasks they need to perform.

For each agent, you must strictly instruct them to execute the following lifecycle:
1. **Claim the ticket:** Acknowledge assignment.
2. **Read constraint files:** Read `TEST/find_bad_style.py` and `.agents/skills/python-code/SKILL.md`
3. **Understand the target:** Read the target file in `src2/` in full. Identify all functions missing return type annotations or argument annotations (excluding `self`/`cls`).
4. **Add annotations:** For each function:
   - Add `-> ReturnType` to all functions except `__init__` and `__new__`.
   - Add `: Type` annotations to all arguments except `self` and `cls`.
   - Import any new types needed using modern syntax (`X | None` not `Optional[X]`).
5. **Do NOT change:** Function logic, control flow, variable names, return values, or public APIs.
6. **Validate:** Run `uv run python TEST/find_bad_style.py --files <target_file>` — must show zero violations
7. **Run lint:** Run `uv run ruff check <target_file>` — must pass clean
8. **Capture decisions:** Use `bd remember "Annotated [file] — added type hints to N functions, imported M new types."`
9. **Close the ticket:** Mark as complete.

---

## 🎟️ TICKET DETAILS (To be assigned to Subagents)

### Ticket 1: Annotate `mem0_store.py`
**Target File:** `src2/core/memory/mem0_store.py`
**Violation Count:** 2
**Task Details:**
* 2 missing type annotations in mem0 memory store functions.
* Functions likely return memory records, lists, or `None`.
* **Strategy:** Trace return types through function bodies. Likely `list[Any]`, `dict[str, Any]`, or `None`.
* **Constraints:** Preserve all memory persistence and retrieval logic.

### Ticket 2: Annotate `text_manager.py`
**Target File:** `src2/interfaces/telegram/text_manager.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in text management functions.
* Function likely returns formatted text or `None`.
* **Strategy:** Trace return path. Likely `str` or `None`.
* **Constraints:** Preserve all text formatting and message management logic.

### Ticket 3: Annotate `report_utils.py`
**Target File:** `src2/interfaces/telegram/report_utils.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in report utility functions.
* Function likely returns report data or formatted output.
* **Strategy:** Trace return path. Likely `str`, `dict[str, Any]`, or `None`.
* **Constraints:** Preserve all report formatting and data extraction logic.

### Ticket 4: Annotate `evaluation.py`
**Target File:** `src2/interfaces/telegram/evaluation.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in evaluation functions.
* Function likely returns evaluation scores or results.
* **Strategy:** Trace return path. Likely `float`, `dict[str, Any]`, or `None`.
* **Constraints:** Preserve all evaluation logic and result computation.

### Ticket 5: Annotate `oracle_narrator.py`
**Target File:** `src2/interfaces/telegram/chronomancer/oracle_narrator.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in oracle narrative generation functions.
* Function likely returns narrative text or structured data.
* **Strategy:** Trace return path. Likely `str`, `dict[str, Any]`, or `None`.
* **Constraints:** Preserve all narrative generation and formatting logic.

### Ticket 6: Annotate `oracle_gatherer.py`
**Target File:** `src2/interfaces/telegram/chronomancer/oracle_gatherer.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in oracle data gathering functions.
* Function likely returns gathered data or `None`.
* **Strategy:** Trace return path. Likely `dict[str, Any]`, `list[Any]`, or `None`.
* **Constraints:** Preserve all data gathering and collection logic.

### Ticket 7: Annotate `rag_client.py`
**Target File:** `src2/engine/rag_client.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in RAG client functions.
* Function likely returns RAG query results or `None`.
* **Strategy:** Trace return path. Likely `str`, `dict[str, Any]`, or `list[Any]`.
* **Constraints:** Preserve all RAG query and response logic.

### Ticket 8: Annotate `module9_triggers.py`
**Target File:** `src2/engine/module9_triggers.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in Module 9 (Triggers) engine.
* Function likely returns trigger analysis results.
* **Strategy:** Check `src2/core/schemas/` for trigger types. Likely `dict[str, Any]` or custom model.
* **Constraints:** Preserve all trigger analysis and calculation logic.

### Ticket 9: Annotate `module2_root.py`
**Target File:** `src2/engine/module2_root.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in Module 2 (Root/Origin) engine.
* Function likely returns root analysis results.
* **Strategy:** Check `src2/core/schemas/` for root types. Likely `dict[str, Any]` or custom model.
* **Constraints:** Preserve all root analysis and element determination logic.

### Ticket 10: Annotate `module0_geju_detection.py`
**Target File:** `src2/engine/module0_geju_detection.py`
**Violation Count:** 1
**Task Details:**
* 1 missing type annotation in GeJu (Pattern) detection engine.
* Function likely returns pattern detection results.
* **Strategy:** Check `src2/core/schemas/` for geju types. Likely `dict[str, Any]` or custom model.
* **Constraints:** Preserve all pattern detection and classification logic.

---

**Orchestrator Execution:**
Create the 10 tickets, spin up the 10 agents concurrently, and ensure they follow the 9-step lifecycle. Begin.