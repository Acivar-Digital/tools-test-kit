# Role and Mission
You are a Staff-Level Code Quality Agent operating in the `opencode` environment. Your mission is to add missing type annotations to the remaining `src2/` files so they pass the `find_bad_style.py` checker with zero violations, while preserving all existing behavior.

## Environment Context
* **Style Checker:** `/home/yapilwsl/arthityap/baziforecaster/TEST/find_bad_style.py` — use this to verify your results. (baziforeporter-only: not in standalone kit download)
* **Target Directory:** `src2/` only.
* **Quality Gate:** After your work, running `uv run python TEST/find_bad_style.py --files <target_file>` must report **no violations** for the assigned file.
* **Skill Reference:** `/home/yapilwsl/arthityap/baziforecaster/.agents/skills/python-code/SKILL.md` — read this for the 3 core rules. (baziforeporter-only: not in standalone kit download)

## Subagent Deployment Criteria
You must deploy **10 subagents at one go** to annotate 10 distinct files concurrently. This is Round 2 — the first 10 files were completed in Round 1.

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

### Ticket 1: Annotate `prompt_engine.py`
**Target File:** `src2/engine/prompt_engine.py`
**Violation Count:** 10
**Task Details:**
* 10 missing type annotations in the prompt engine core functions.
* Functions likely return prompt templates, strings, or dict configurations.
* **Strategy:** Trace return values through function bodies. Check `src2/engine/pydantic_prompt_engine.py` for related type patterns.
* **Constraints:** Do not alter prompt generation logic or template formatting.

### Ticket 2: Annotate `__init__.py`
**Target File:** `src2/engine/__init__.py`
**Violation Count:** 10
**Task Details:**
* 10 missing type annotations in the engine package init — likely factory functions and re-exports.
* These may be simple wrapper functions that delegate to submodules.
* **Strategy:** Identify return types by reading the function bodies. Often these wrap calls to imported functions — match the delegate's return type.
* **Constraints:** Do not change any import statements or re-export structure. Preserve all `__all__` definitions.

### Ticket 3: Annotate `utils.py`
**Target File:** `src2/interfaces/telegram/utils.py`
**Violation Count:** 9
**Task Details:**
* 9 missing type annotations in Telegram utility functions.
* Functions likely handle user IDs, chat IDs, and message formatting — primitives or `str`/`int` returns.
* **Strategy:** Most functions probably return simple types (`str`, `int`, `bool`, `list[str]`). Trace each return path.
* **Constraints:** Preserve all formatting logic and external API call formatting.

### Ticket 4: Annotate `stars.py`
**Target File:** `src2/engine/stars.py`
**Violation Count:** 9
**Task Details:**
* 9 missing type annotations in the stars (astrological) engine.
* Functions likely return star classifications or numerical scores.
* **Strategy:** Check `src2/core/schemas/` for star-related types. Use `str` for star names, `int`/`float` for scores.
* **Constraints:** Do not change astrological calculations or star classification rules.

### Ticket 5: Annotate `ui_components.py`
**Target File:** `src2/interfaces/telegram/ui_components.py`
**Violation Count:** 7
**Task Details:**
* 7 missing type annotations in UI component builders for Telegram messages.
* Functions likely return message strings, inline keyboard objects, or `dict` configurations.
* **Strategy:** Functions probably return `str` or `dict[str, Any]`. Trace each function's final return statement.
* **Constraints:** Preserve all UI layout logic and keyboard formatting.

### Ticket 6: Annotate `conductor.py`
**Target File:** `src2/interfaces/telegram/conductor.py`
**Violation Count:** 6
**Task Details:**
* 6 missing type annotations in the conductor/orchestrator layer.
* Functions coordinate between multiple subsystems — may return orchestration results.
* **Strategy:** Trace return values through function bodies. Results may be `dict[str, Any]`, `str`, or `None`.
* **Constraints:** Do not alter orchestration flow or state management.

### Ticket 7: Annotate `queue_worker.py`
**Target File:** `src2/interfaces/telegram/queue_worker.py`
**Violation Count:** 5
**Task Details:**
* 5 missing type annotations in background job workers.
* Functions likely return `None` (side-effect workers) or job results.
* **Strategy:** Most functions are void workers — annotate with `-> None`. Check args against the `Session` type and job data structures.
* **Constraints:** Preserve all queue processing and job lifecycle logic.

### Ticket 8: Annotate `rotator.py`
**Target File:** `src2/core/rotator.py`
**Violation Count:** 5
**Task Details:**
* 5 missing type annotations in the API key rotator.
* Functions likely return key strings, model names, or rotation status.
* **Strategy:** Functions probably return `str`, `list[str]`, or `None`. Trace each return path.
* **Constraints:** Preserve all key selection and rotation logic.

### Ticket 9: Annotate `security.py`
**Target File:** `src2/interfaces/telegram/security.py`
**Violation Count:** 4
**Task Details:**
* 4 missing type annotations in security/authorization functions.
* Functions likely return `bool` or `str` (user identifiers).
* **Strategy:** These are simple validation/check functions — annotate with `bool` return types and `int`/`str`/`ChatMemberUpdated` argument types as appropriate.
* **Constraints:** Preserve all security checks and access control logic.

### Ticket 10: Annotate `reliability.py`
**Target File:** `src2/interfaces/telegram/reliability.py`
**Violation Count:** 4
**Task Details:**
* 4 missing type annotations in reliability/metrics reporting.
* Functions likely return `None` or metrics summary strings.
* **Strategy:** Trace function bodies for return types. May need `dict[str, Any]` for metrics payloads.
* **Constraints:** Preserve all metric collection and reporting logic.

---

**Orchestrator Execution:**
Create the 10 tickets, spin up the 10 agents concurrently, and ensure they follow the 9-step lifecycle. Begin.