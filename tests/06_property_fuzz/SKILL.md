---
name: extreme-testing-fuzz-mutate
description: Enforces property-based fuzzing (Hypothesis) and mutation testing (Mutmut) paradigms to achieve SQLite-grade robustness, avoiding silent NaN/Infinity leaks and false-positive test passes.
---

# Property-Based Fuzzing & Mutation Testing Skill

## 🚨 Pre-Test Verification Checklist
Before writing fuzzing tests or running mutation audits:
1. **NaN/Infinity Guard Check**: Verify that any test validating floating-point outputs explicitly imports `math` and asserts `not math.isnan(val)` and `not math.isinf(val)`. `isinstance(val, float)` is NOT sufficient.
2. **Strategy Alignment**: Ensure you are using native Hypothesis strategies (e.g., `st.dates()`, `st.floats(allow_nan=False)`) rather than generating raw integers and manually filtering them with `try/except` or `assume()`.
3. **Mutation Scoping Check**: Verify that `mutmut` is strictly scoped to the target module via `pyproject.toml` (e.g., `source_paths = ["src2/engine/"]`). NEVER run an unscoped `mutmut run` on the entire repository.
4. **Boundary Expansion**: Ensure fuzzing boundaries for numerical limits allow for edge cases like `0.0`, negative numbers, and infinity (`allow_infinity=True` for inputs, but blocked for outputs).

## 🏗️ Design Mindsets

### 1. The "Silent Poison" Trap (NaN & Infinity Isolation)
* **Why**: In Python, both `NaN` (Not a Number) and `Infinity` are technically evaluated as `float`. If an engine calculates `Infinity * 0` or `1e300 * 1e300`, it returns `NaN` or `Infinity`. If your fuzzing test only asserts `isinstance(result, float)`, the test will **PASS**, but the engine just leaked data corruption that will crash the frontend or database.
* **Action**:
  * **Explicit Guards**: Always assert mathematical boundaries.
  * **Standard Code**:
    ```python
    assert isinstance(result, float)
    assert not math.isnan(result), "Engine leaked a NaN value!"
    assert not math.isinf(result), "Engine leaked Infinity!"
    ```

### 2. Avoiding Fuzzer Hallucinations (`assume` vs. Native Strategies)
* **Why**: If you use `try/except/return` in a fuzzing test (e.g., catching a `ValueError` for an invalid date like Year -5000) or heavily use `assume()`, Hypothesis marks the test as a **PASSED TEST** or throws `FailedHealthCheck.too_many_discards`. You are creating false positives where the engine isn't actually being tested.
* **Action**:
  * **Strict Ban on Try/Except Escapes**: Never catch and return on validation errors inside a fuzzing run to skip bad data.
  * **Native Generators**: Use Hypothesis's built-in strategies to generate extreme but strictly valid data types (e.g., use `st.dates(min_value=date(1,1,1), max_value=date(9999,12,31))` instead of generating 3 random integers and hoping it makes a valid date).

### 3. Property-Based Assertions (The "Garbage Thrower")
* **Why**: Normal unit tests check if `A + B = C`. Fuzzing checks properties. You cannot assert a specific output because the input is completely random garbage.
* **Action**:
  * **Test Invariants**: Assert properties that must ALWAYS be true. 
  * Examples: "The engine must never throw an unhandled exception", "The output score must never exceed the provided era_ceiling", "The returned enum must always belong to the valid schema."

### 4. The "Saboteur" (Mutation Testing Rules of Engagement)
* **Why**: Mutation testing (`mutmut`) tests your tests by injecting deliberate bugs (e.g., changing `>` to `>=`, or `+` to `-`). If your tests pass while the code is broken, your test suite has blind spots. However, mutation testing causes a combinatorial explosion of test runs.
* **Action**:
  * **Strict Scoping**: Always configure `[tool.mutmut]` in `pyproject.toml` to target ONLY the specific deterministic engine directory.
  * **Runner Script**: Ensure developers have a simple executable (e.g., `run_mutations.sh`) that automates `mutmut run`, `mutmut results`, and `mutmut html` generation.

## 🗺️ Triggering Situational Skills
Based on what you are editing, load/recommend these skills:
- **Test Execution**: Load `gold-test` before executing any pytest runs.
- **Deterministic Engines**: Load this skill (`extreme-testing-fuzz-mutate`) whenever building or refactoring core math engines, parsers, or orchestrators that require absolute stability.
- **Bot Integrations**: Load `bot-testing-observability` if the output of the fuzzed engine is being wired to a user-facing Telegram or API boundary.