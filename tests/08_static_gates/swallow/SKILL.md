
---
name: anti-silent-swallow-auditing
description: Detects and eliminates silent exception swallowing, Pydantic data dropping, and silent logic fallthroughs using AST parsing, pytest caplog hooks, and strict CI configuration.
---

# Anti-Silent Swallow Auditing Skill

## 🚨 Pre-Execution Verification Checklist
Before hunting for silent swallows or writing validation code:
1. **Ruff CI Shield Check**: Verify that `pyproject.toml` or `ruff.toml` explicitly selects the blind-except and swallow rules (`BLE`, `S110`, `SIM105`, `RET503`).
2. **Pydantic Strictness**: Ensure that all Pydantic model configurations are audited. Verify `extra = "forbid"` and `validate_assignment = True` are enforced to prevent silent data discarding.
3. **Log Trap Fixture Check**: Ensure `conftest.py` contains a globally scoped fixture (using `caplog`) that explicitly fails any test emitting an unexpected `ERROR` or `CRITICAL` log.
4. **AST Target Scoping**: If running custom AST scanners, restrict the target directory strictly to the deterministic math/engine paths (e.g., `src2/engine/`) to avoid false positives in external library wrappers.

## 🏗️ Design Mindsets

### 1. The "Pydantic Black Hole" (Strict Mode Introspection)
* **Why**: By default, Pydantic applies `extra = 'ignore'`. If an engine receives malformed keys or misspelled inputs, it will silently discard them instead of exploding. In deterministic math engines, missing variables lead to default fallbacks (like multiplying by 0 instead of 1.5) without failing the test suite.
* **Action**:
  * **Dynamic Introspection**: Never rely on manual code review. Write a unit test that dynamically crawls the codebase, extracts all subclasses of `BaseModel`, and asserts their configurations.
  * **Standard Code**:
    ```python
    def test_no_silent_pydantic_swallows():
        models = get_all_pydantic_models("src2") # Using importlib/inspect
        violating = [
            m.__name__ for m in models 
            if m.model_config.get("extra") != "forbid"
            or not m.model_config.get("validate_assignment", False)
        ]
        assert not violating, f"Models allowing silent swallows: {violating}"
    ```

### 2. The "Ghost Logger" (Pytest Caplog Trap)
* **Why**: Developers often "handle" exceptions by wrapping them in a `try...except`, logging an error (`logger.error(e)`), and forgetting to re-raise it. Because the exception doesn't bubble up, unit tests completely miss the failure and report a **PASS**.
* **Action**:
  * **Global Caplog Trap**: Use Pytest's built-in `caplog` fixture to fail tests that generate severe logs, ensuring the test suite strictly correlates code health with log health.
  * **Standard Code** (in `conftest.py`):
    ```python
    import pytest, logging

    @pytest.fixture(autouse=True)
    def no_swallowed_errors(caplog):
        caplog.set_level(logging.WARNING)
        yield  # Let test run
        swallowed = [r for r in caplog.records if r.levelno >= logging.ERROR]
        if swallowed:
            pytest.fail(f"Silent exception swallowed and logged: {swallowed}")
    ```

### 3. The "Terminal Swallow" (AST Scanning)
* **Why**: Linters like Ruff catch `except Exception: pass`, but they miss complex swallows (e.g., an `except` block that performs minor cleanup, sets a fallback value, but forgets to `raise`). 
* **Action**:
  * **AST Walkers**: Write scripts utilizing Python's native `ast` module to scan `ast.Try` blocks and assert that every `except` handler eventually terminates with an `ast.Raise` or `ast.Return`.
  * **Standard Code**:
    ```python
    import ast

    def has_terminal_node(node):
        """Recursively search AST node for ast.Raise or ast.Return."""
        for child in ast.walk(node):
            if isinstance(child, (ast.Raise, ast.Return)):
                return True
        return False

    # During AST file iteration:
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for handler in node.handlers:
                if not has_terminal_node(handler.body):
                    print(f"🚨 Silent Swallow Detected on line {handler.lineno}")
    ```

### 4. Zero-Cost Static CI Gates (Linter Hardening)
* **Why**: Dynamic scripts are powerful, but CI gates provide the fastest feedback loop. If the static analyzer is missing rules, developers will introduce new silent swallows over time.
* **Action**:
  * **Strict Rule Selection**: Update the project's linter configuration.
  * **Standard Code** (in `pyproject.toml`):
    ```toml
    [tool.ruff.lint]
    select = [
        "BLE",    # flake8-blind-except (Catches blind except Exception: pass)
        "S110",   # try-except-pass (Bandit rule for silent passes)
        "SIM105", # contextlib.suppress (Discourages using contextlib to swallow)
        "RET503", # Missing return statement (Catches silent fallthroughs)
    ]
    ```

## 🗺️ Triggering Situational Skills
Based on what you are editing, load/recommend these skills:
- **Test Generation**: Load `gold-test` before implementing the `conftest.py` log traps or unit testing the Pydantic strictness.
- **Fuzzing & Mutations**: Load `extreme-testing-fuzz-mutate` to weaponize `mutmut`. Running `mutmut` while specifically mutating `raise` into `pass` is the ultimate test of the AST/Caplog traps defined in this skill.
- **Bot/API Layer**: Load `bot-testing-observability` if investigating exception swallowing at the Telegram webhook or API integration layer, where Sentry/Logfire isolation is required.

--- END OF FILE SKILL.md ---