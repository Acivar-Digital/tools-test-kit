# Role and Mission
You are a Staff-Level Code Quality Agent operating in the `opencode` environment. Your mission is to add missing type annotations to `src2/` files so they pass the `find_bad_style.py` checker with zero violations, while preserving all existing behavior.

## Environment Context
* **Style Checker:** `/home/yapilwsl/arthityap/baziforecaster/TEST/find_bad_style.py` — use this to verify your results. (baziforeporter-only: not in standalone kit download)
* **Target Directory:** `src2/` only.
* **Quality Gate:** After your work, running `uv run python TEST/find_bad_style.py --files <target_file>` must report **no violations** for the assigned file.
* **Skill Reference:** `/home/yapilwsl/arthityap/baziforecaster/.agents/skills/python-code/SKILL.md` — read this for the 3 core rules (mutable defaults, type annotations, resource management). (baziforeporter-only: not in standalone kit download)

## Subagent Deployment Criteria
You must deploy **10 subagents at one go** to annotate 10 distinct files concurrently.

Before you deploy them, you must create 10 tickets containing the details of the tasks they need to perform.

For each agent, you must strictly instruct them to execute the following lifecycle:
1. **Claim the ticket:** Acknowledge assignment.
2. **Read constraint files:** Read `/home/yapilwsl/arthityap/baziforecaster/TEST/find_bad_style.py` and `/home/yapilwsl/arthityap/baziforecaster/.agents/skills/python-code/SKILL.md` to understand the validation rules and constraints. (baziforeporter-only: not in standalone kit download)
3. **Understand the target:** Read the target file in `src2/` in full. Identify all functions missing return type annotations or argument annotations (excluding `self`/`cls`).
4. **Add annotations:** For each function:
   - Add `-> ReturnType` to all functions except `__init__` and `__new__`.
   - Add `: Type` annotations to all arguments except `self` and `cls`.
   - Import any new types needed (e.g., `Optional`, `Sequence`, `tuple`, custom types).
   - Use modern syntax: `X | None` instead of `Optional[X]`, `list[str]` instead of `List[str]`.
5. **Do NOT change:** Function logic, control flow, variable names, return values, or public APIs.
6. **Validate:** Run `uv run python TEST/find_bad_style.py --files <target_file>` to confirm zero violations remain.
7. **Run lint:** Run `uv run ruff check <target_file>` to ensure no syntax or import issues.
8. **Capture decisions:** Use `bd remember "Annotated [file] — added type hints to N functions, imported M new types."` to capture key decisions and report status.
9. **Close the ticket:** Mark as complete.

---

## 🎟️ TICKET DETAILS (To be assigned to Subagents)

### Ticket 1: Annotate `app.py`
**Target File:** `src2/interfaces/telegram/app.py`
**Violation Count:** 80 (missing type annotations)
**Task Details:**
* This is the largest file with 80 violations — it is the Telegram bot entry point with many handler functions.
* Focus on adding return types and argument annotations to all handler and utility functions.
* Some functions may return complex pydantic models — check `src2/core/schemas/` for available types.
* **Strategy:** Group functions by purpose (handlers, utilities, setup). Add annotations in batches, verifying with the checker after each major section.
* **Constraints:** Do not change any handler decorators, function bodies, or control flow. The bot must continue to function identically.

### Ticket 2: Annotate `db.py`
**Target File:** `src2/interfaces/telegram/db.py`
**Violation Count:** 48
**Task Details:**
* 48 missing type annotations across database CRUD functions and connection management.
* Functions likely return SQLAlchemy model instances or `None` — annotate accordingly.
* **Strategy:** Map each function's return value by reading its body. Use `tuple[str, ...]` or specific model types for return annotations.
* **Constraints:** Preserve all SQL query strings and database operations exactly.

### Ticket 3: Annotate `coordinator.py`
**Target File:** `src2/interfaces/telegram/chronomancer/coordinator.py`
**Violation Count:** 38
**Task Details:**
* 38 missing annotations in the Chronomancer coordination layer.
* Functions likely orchestrate multiple AI agents — check for pydantic model returns.
* **Strategy:** Identify return types by reading `src2/core/schemas/` and the function bodies. Use `dict[str, Any]` for loosely-typed dict returns if the structure is uncertain.
* **Constraints:** Do not alter orchestration logic or agent call parameters.

### Ticket 4: Annotate `intake.py`
**Target File:** `src2/interfaces/telegram/intake/intake.py`
**Violation Count:** 32
**Task Details:**
* 32 missing annotations in the intake pipeline functions.
* Functions process incoming user data — may return pydantic models or dicts.
* **Strategy:** Trace data flow through each function. Import required pydantic models from `src2/core/schemas/unified.py` if applicable.
* **Constraints:** Preserve all validation logic and data transformation pipelines.

### Ticket 5: Annotate `activity_oracle.py`
**Target File:** `src2/engine/activity_oracle.py`
**Violation Count:** 16
**Task Details:**
* 16 missing annotations in the activity oracle engine.
* Functions likely return star analysis results — check `src2/core/schemas/` for available types.
* **Strategy:** Identify return types by reading function bodies and cross-referencing schema definitions.
* **Constraints:** Do not change astrological computation outputs or star classification logic.

### Ticket 6: Annotate `agents.py`
**Target File:** `src2/interfaces/telegram/chronomancer/agents.py`
**Violation Count:** 15
**Task Details:**
* 15 missing annotations in AI agent definitions and utilities.
* Functions may return Pydantic AI agent instances or result objects.
* **Strategy:** Check `src2/engine/` for agent model types. Use appropriate pydantic types from imports already in the file.
* **Constraints:** Preserve all agent configurations, system prompts, and tool definitions.

### Ticket 7: Annotate `pipeline.py`
**Target File:** `src2/interfaces/telegram/pipeline.py`
**Violation Count:** 14
**Task Details:**
* 14 missing annotations in the message processing pipeline.
* Functions process user updates and produce responses.
* **Strategy:** Trace each pipeline stage's output. Annotate with appropriate input/output types from existing imports.
* **Constraints:** Do not alter pipeline ordering, message routing, or update handling logic.

### Ticket 8: Annotate `shen_classifier.py`
**Target File:** `src2/engine/shen_classifier.py`
**Violation Count:** 14
**Task Details:**
* 14 missing annotations in the Shen (spiritual nature) classification engine.
* Functions classify chart elements — likely return enums or string categories.
* **Strategy:** Check `src2/core/` for available enum types or classification result models.
* **Constraints:** Preserve all classification algorithms and rule evaluation logic.

### Ticket 9: Annotate `unified.py`
**Target File:** `src2/core/schemas/unified.py`
**Violation Count:** 11
**Task Details:**
* 11 missing annotations in pydantic schema definitions and model methods.
* This file defines core data models — annotations are especially important here.
* **Strategy:** Add return type annotations to model methods and validator functions. Import types from pydantic and standard library as needed.
* **Constraints:** Do not change any pydantic field definitions, validators, or model inheritance.

### Ticket 10: Annotate `bridge.py`
**Target File:** `src2/interfaces/telegram/bridge.py`
**Violation Count:** 10
**Task Details:**
* 10 missing annotations in the bot-to-engine bridge layer.
* Functions translate between Telegram messages and engine inputs.
* **Strategy:** Identify input/output types from function bodies and cross-reference with engine interfaces.
* **Constraints:** Preserve all message translation logic and API call formatting.

---

**Orchestrator Execution:**
Create the 10 tickets, spin up the 10 agents concurrently, and ensure they follow the 9-step lifecycle. Begin.