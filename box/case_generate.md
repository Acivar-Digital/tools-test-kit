# Case Specification: Generate New Script Test (`box/case_generate.md`)

## Goal
Test whether the subagent autonomously adheres to `clean_python` quality rules (AST anti-slop, Ruff, MyPy strict typing, and Radon CC < 6) when given a **minimal, natural user prompt** to write a brand-new script from scratch.

---

## Candidate Prompt to Send to Subagent

```text
Write a python script `box/generate_report.py` that reads JSON test logs from a directory, calculates statistics (total tests, pass/fail counts, average execution time, and error distribution), and outputs a formatted Markdown summary report. Make sure it includes robust error handling and CLI argument parsing.
```

---

## Expected Autonomous Behavior

1. **Tool Usage**:
   - The subagent must use the `clean_python` tool (`verify_and_commit_code`) to create `box/generate_report.py`.
   - Must NOT use standard `write` or `edit` tools for `.py` files.

2. **Quality Enforcement**:
   - **Radon CC**: All functions must have Cyclomatic Complexity < 6.
   - **MyPy Strict**: Complete type annotations (`dict[str, Any]`, `Path`, `list[str]`, etc.).
   - **AST Anti-Slop**: No bare `except:` or swallowed `try...except Exception: pass` blocks.
   - **Ruff**: Clean imports, modern Python standards.

---

## Instructions for User

Please review this proposed test case. If approved, reply to deploy the subagent to execute this prompt!

---

## Rationale: Why This Use Case Demonstrates Plugin & Tool Effectiveness

### 1. The Monolithic Function Trap (High Cyclomatic Complexity)
When asked to build a utility script handling CLI parsing, file scanning, JSON parsing, statistics aggregation, and Markdown formatting, **an LLM's natural instinct is to write a single monolithic function** (`main()` or `process_logs()`).

Without CC enforcement, standard LLMs generate nested loops + conditionals + inline formatting in one block, resulting in Cyclomatic Complexity **CC = 8–14**.

### 2. "Slop" Error Handling (Broad Exception Catching)
When prompted for "robust error handling", standard LLMs fall back on bad habits:
- Swallowing exceptions: `try: ... except Exception: pass`
- Bare catch blocks: `except:`
- Catch-all logging wrappers that hide underlying structure.

AST anti-slop policies strictly forbid swallowing broad exceptions without handling or logging.

### 3. Missing or Loose Type Annotations (MyPy Failure)
Parsing dynamic JSON data into statistics requires handling nested dictionaries and optional fields.
- **Standard LLM approach**: Omits type annotations or uses unhelpful types like `def process_file(data: dict):`.
- **Strict MyPy requirement**: Requires explicit parameter types (`dict[str, Any]`), return types (`ReportStats`), guard checks (`isinstance()`), and non-None handling. Most models skip this extra effort unless forced.

### 4. How `remind-workflow` & `clean_python` Prevent Slop
- **Continuous Prompt Injection**: The `remind-workflow` plugin keeps the `clean_python` requirement in active memory on every turn, preventing tool drift.
- **Correct-by-Construction Gating**: `clean_python` intercepts write payloads before they reach disk. If the LLM attempts to generate a monolithic function (CC $\ge$ 6) or loose types, `clean_python` rejects the file and returns exact diagnostic errors, forcing the model to modularize the code into clean helper functions on the first try.
