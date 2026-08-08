# Role and Mission
You are a Staff-Level Code Quality Agent operating in the `opencode` environment. Your mission is to add missing type annotations to the remaining `src2/` files so they pass the `find_bad_style.py` checker with zero violations, while preserving all existing behavior.

## Environment Context
* **Style Checker:** `/home/yapilwsl/arthityap/baziforecaster/TEST/find_bad_style.py` — use this to verify your results. (baziforeporter-only: not in standalone kit download)
* **Target Directory:** `src2/` only.
* **Quality Gate:** After your work, running `uv run python TEST/find_bad_style.py --files <target_file>` must report **no violations** for the assigned file.
* **Skill Reference:** `/home/yapilwsl/arthityap/baziforecaster/.agents/skills/python-code/SKILL.md` — read this for the 3 core rules. (baziforeporter-only: not in standalone kit download)

## Subagent Deployment Criteria
You must deploy **10 subagents at one go** to annotate 10 distinct files concurrently. This is Round 3.

Before you deploy them, you must create 10 tickets containing the details of the tasks they need to perform.

For each agent, you must strictly instruct them to execute the following lifecycle:
1. **Claim the ticket:** Acknowledge assignment.
2. **Read constraint files:** Read `/home/yapilwsl/arthityap/baziforecaster/TEST/find_bad_style.py` and `/home/yapilwsl/arthityap/baziforecaster/.agents/skills/python-code/SKILL.md` (baziforeporter-only: not in standalone kit download)
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

### Ticket 1: Annotate `pydantic_prompt_engine.py`
**Target File:** `src2/engine/pydantic_prompt_engine.py`
**Violation Count:** 4
**Task Details:**
* 4 missing type annotations in Pydantic-based prompt engine functions.
* Functions likely return prompt templates, strings, or Pydantic model instances.
* **Strategy:** Trace return values through function bodies. Check `src2/core/schemas/` for available types.
* **Constraints:** Do not alter prompt generation logic or model instantiation.

### Ticket 2: Annotate `narrative_simplifier.py`
**Target File:** `src2/engine/narrative_simplifier.py`
**Violation Count:** 4
**Task Details:**
* 4 missing type annotations in narrative simplification functions.
* Functions likely return simplified text strings or dict structures.
* **Strategy:** Trace each function's return path. Likely returns `str`, `dict[str, Any]`, or `None`.
* **Constraints:** Preserve all text simplification and narrative transformation logic.

### Ticket 3: Annotate `module14_palaces.py`
**Target File:** `src2/engine/module14_palaces.py`
**Violation Count:** 4
**Task Details:**
* 4 missing type annotations in the Palace (Module 14) engine.
* Functions likely return palace analysis results or element classifications.
* **Strategy:** Check `src2/core/schemas/` for palace-related types. Functions may return `dict[str, Any]` or custom model types.
* **Constraints:** Do not change palace analysis algorithms or element relationship logic.

### Ticket 4: Annotate `preflight.py`
**Target File:** `src2/interfaces/telegram/preflight.py`
**Violation Count:** 3
**Task Details:**
* 3 missing type annotations in preflight checks.
* Functions likely return validation results or `bool` flags.
* **Strategy:** Trace return values — likely `bool`, `str`, or `None`.
* **Constraints:** Preserve all validation logic and check ordering.

### Ticket 5: Annotate `logging_utils.py`
**Target File:** `src2/interfaces/telegram/logging_utils.py`
**Violation Count:** 3
**Task Details:**
* 3 missing type annotations in logging utility functions.
* Functions likely return `None` or formatted log strings.
* **Strategy:** Most are side-effect loggers → `-> None`. Check argument types from function bodies.
* **Constraints:** Do not change logging format strings or handler configuration.

### Ticket 6: Annotate `bgem3_bridge.py`
**Target File:** `src2/interfaces/telegram/bgem3_bridge.py`
**Violation Count:** 3
**Task Details:**
* 3 missing type annotations in the BGE-M3 embedding bridge.
* Functions likely return embeddings, lists of floats, or query results.
* **Strategy:** Functions may return `list[float]`, `list[list[float]]`, or `dict[str, Any]`. Trace return paths.
* **Constraints:** Preserve all embedding computation and query logic.

### Ticket 7: Annotate `module3_interaction.py`
**Target File:** `src2/engine/module3_interaction.py`
**Violation Count:** 3
**Task Details:**
* 3 missing type annotations in Module 3 (Interaction/Clash) engine.
* Functions likely return interaction analysis results.
* **Strategy:** Check `src2/core/schemas/` for interaction types. May return `dict[str, Any]` or custom models.
* **Constraints:** Do not alter clash analysis or interaction calculation logic.

### Ticket 8: Annotate `memory_manager.py`
**Target File:** `src2/core/memory/memory_manager.py`
**Violation Count:** 3
**Task Details:**
* 3 missing type annotations in the memory management module.
* Functions likely return memory records, conversation history, or `None`.
* **Strategy:** Trace return types through function bodies. Likely `dict[str, Any]`, `list[Any]`, or `None`.
* **Constraints:** Preserve all memory persistence and retrieval logic.

### Ticket 9: Annotate `validators.py`
**Target File:** `src2/interfaces/telegram/validators.py`
**Violation Count:** 2
**Task Details:**
* 2 missing type annotations in Telegram input validation functions.
* Functions likely return `bool`, validation error messages, or validated data.
* **Strategy:** Trace return paths. Functions may return `bool`, `str | None`, or `tuple[bool, str]`.
* **Constraints:** Preserve all validation logic and error message formatting.

### Ticket 10: Annotate `session.py`
**Target File:** `src2/interfaces/telegram/session.py`
**Violation Count:** 2
**Task Details:**
* 2 missing type annotations in session management functions.
* Functions likely return session objects, `str` identifiers, or `None`.
* **Strategy:** Check existing imports for `Session` type. Functions may return `Session | None`.
* **Constraints:** Preserve all session creation and persistence logic.

---

**Orchestrator Execution:**
Create the 10 tickets, spin up the 10 agents concurrently, and ensure they follow the 9-step lifecycle. Begin.