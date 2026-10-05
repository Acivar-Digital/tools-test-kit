# ❓ Demo FAQ

---

### Q1: Why is this separate from the toolkit?

The `demo/` directory is intentionally isolated from the live `hygiene/` and `tools/` code paths. It is a **case study**, not a feature — its job is to prove that the quality gates work, not to be imported by production tooling. Keeping it separate means demos can be cloned, broken, and rerun without risking drift in the core kit.

---

### Q2: Do I need an API key?

No. The Python demo's `find_bad_style.py` and `find_cc_nested.py` run fully offline — they are pure AST and Radon static analysis. The hallucination detectors (`find_hallucinations*`) are present for parity but require an LLM tier (`KIT_API_KEY` + `KIT_BASE_URL`) only if you want to exercise the LLM-audit layer.

---

### Q3: How do I add a new language demo?

1. Create `demo/<language>/` mirroring the `demo/python/` layout (case spec, scanner script, clean output).
2. The new language must have the same 4 anti-slop gates enforced: CC < 6, strict type annotations, AST-policy no-slip (`except:` / `except Exception: pass` rejections), and lint clean.
3. Add a table row to `README.md` and a `## N. <Language> Demo (planned)` section to `GUIDE.md`.

---

### Q4: How does clean_python prevent slop?

`clean_python` enforces four anti-slop guarantees that standard LLMs routinely violate without a gate:

1. **Monolithic Function Trap (CC ≥ 6)** — LLMs naturally merge CLI parsing, file scanning, JSON parsing, aggregation, and formatting into one `main()` (CC 8–14). `clean_python` rejects any function with Radon CC ≥ 6, forcing the model to extract modular helpers on the first try.

2. **Slop Error Handling (broad exception catching)** — Prompts for "robust error handling" trigger `except:` and `except Exception: pass` blocks. AST policies forbid swallowing broad exceptions without handling or re-raising.

3. **Missing or Loose Type Annotations (MyPy Failure)** — Parsing dynamic JSON requires `dict[str, Any]`, `Path`, `list[str]`, and `isinstance()` guard checks. Strict MyPy rejects bare `dict` or omitted return types, which most models skip unless forced.

4. **remind-workflow Memory Persistence** — The `remind-workflow` plugin keeps the `clean_python` requirement injected on every turn, preventing tool drift where an agent switches to a raw `write` call mid-task.

See `case_generate.md` for the full rationale applied to the `generate_report.py` case.
