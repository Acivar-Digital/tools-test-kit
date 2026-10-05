# 📖 Demo Setup Guide

This guide walks through running the kit's demo case studies, which exercise the `clean_python` + `remind-workflow` quality pipeline against real subagent output.

---

## Prerequisites

- **kit installed** — see the top-level `README.md` for `uv sync --all-projects`.
- **`uv`** — the kit's Python runner. Install via `curl -LsSf https://astral.sh/uv/install.sh | sh`.

---

## 1. Python Demo (clean_python anti-slop)

This is the canonical case study. A subagent was given the prompt in `case_generate.md`:

> Write a python script `generate_report.py` that reads JSON test logs from a directory, calculates statistics, and outputs a formatted Markdown summary report.

The subagent **must** route every `.py` file through the `clean_python` tool (`verify_and_commit_code`), which enforces:

- **Radon CC**: all functions < 6.
- **MyPy strict**: full type annotations on every parameter and return.
- **AST anti-slop**: no bare `except:` or `try...except Exception: pass`.
- **Ruff**: clean imports and modern Python.

### Inspect the evidence

```bash
cd demo/python
ls case_generate.md find_bad_style.py find_cc_nested.py generate_report.py
```

- `case_generate.md` — the case specification with rationale.
- `find_bad_style.py` — AST scanner for mutable defaults, missing type hints, unsafe `open()`.
- `find_cc_nested.py` — Radon cyclomatic complexity checker.
- `generate_report.py` — the clean output that passed every gate.

### Verify the output

```bash
cd demo/python
uv run python find_bad_style.py generate_report.py
uv run python find_cc_nested.py --min-cc 6 generate_report.py
```

Both commands should report **no violations**.

---

## 2. Re-running the Case Study

To scan an arbitrary Python file with the same anti-slop policy, drop it into `demo/python/` and run:

```bash
cd demo/python
uv run python find_bad_style.py <file>
```

---

## 3. TypeScript Demo (planned)

A TypeScript case study is planned to demonstrate gate parity for the `plugins/typescript/` module. It will reuse the same 4-problem anti-slop structure (monolithic functions, loose typing, swallowed exceptions, missing annotations) applied to a TS generator script.

---

## Environment

| Variable | Default | Description |
|---|---|---|
| `KIT_API_KEY` | (unset) | Optional — LLM audit tiers inside `find_hallucinations.py` |
| `KIT_LIVE` | `false` | Offline mode; set to `true` only when an LLM tier is configured |
| `DISABLE_CLEAN_PYTHON` | (unset) | Set to `true` to bypass `clean_python` linter verification (not recommended for demo runs) |
