# 📚 Kit Demo Case Studies

The `demo/` directory showcases reproducible case studies that prove the kit's quality gates — `clean_python` + `remind-workflow` — reliably reject monolithic, loosely-typed, and "slop"-handling code in favor of modular, strictly-typed, policy-compliant output.

Each demo is a self-contained scenario: a single natural-language prompt fed to a subagent that must produce code passing AST anti-slop checks, strict MyPy, Ruff, and Radon cyclomatic complexity (CC) < 6. The results are captured here as evidence.

---

## Included Demos

| Demo | Language | Proof Target | Quick Run |
|---|---|---|---|
| Python anti-slop case study | Python | `clean_python` intercepts monolithic functions (CC $\ge$ 6), loose typing, and swallowed exceptions, forcing modular helpers | `cd demo/python && uv run python find_bad_style.py generate_report.py` |
| TypeScript case study | TypeScript | (planned) — same gate parity for TS plugins | N/A |

> `demo/python/` contains the original `box/` artifacts: the case specification (`case_generate.md`), the anti-slop scanner (`find_bad_style.py`), the CC checker (`find_cc_nested.py`), hallucination detectors, and the generated `generate_report.py` that passed every gate.

---

## Quick Execution

### 1. Clone and enter the kit

```bash
git clone <repo-url> kit
cd kit
```

### 2. Install `uv` and sync dependencies

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync --all-projects
```

### 3. Run the Python anti-slop case study

```bash
cd demo/python
uv run python find_bad_style.py generate_report.py
```

The scanner reports zero violations — `generate_report.py` was produced by a subagent that could only write code if `clean_python` accepted it (CC < 6, full type annotations, no bare `except:`).
