---
name: bazi-testing-conventions
description: Enforces BaZi project testing standards, including Pytest patterns, Pydantic schema utilization (ChartProfile, Pillar), and the strict English CapitalCase key-format convention (no Chinese characters).
---

# Bazi Testing Conventions & Schema Skill

## 🚨 Pre-Test Verification Checklist
Before writing or modifying any Bazi math tests:
1. **CapitalCase Check**: Verify that absolutely NO Chinese characters (e.g., '甲', '子', '木', '正印') are used as test inputs, keys, or expected outputs. All references must be English CapitalCase (e.g., 'Jia', 'Zi', 'Wood', 'Direct Resource').
2. **Validation Seam Injection**: Ensure the test file imports and utilizes `assert_key_format_convention` from `TEST.math.conftest` to run recursive checks on all output structures.
3. **Pydantic Model Usage**: Verify that mock chart data is constructed using `ChartProfile` and `Pillar` classes from `src2.core.schemas.unified`, NOT raw Python dictionaries.
4. **Type Hinting**: Ensure all Pytest test functions are strictly type-hinted (e.g., `def test_function_name() -> None:`).

## 🏗️ Design Mindsets

### 1. The "CapitalCase Rule" (No Chinese Characters)
* **Why**: The Bazi engine's internal lookup tables, dictionaries, and downstream database operations rely on strict English string matching. Passing native Chinese characters will cause silent lookup failures, `KeyError`s, and immediately trigger the `conftest.py` `TypeError`/`AssertionError` hooks.
* **Action**:
  * **Stems**: Use `"Jia", "Yi", "Bing", "Ding", "Wu", "Ji", "Geng", "Xin", "Ren", "Gui"`.
  * **Branches**: Use `"Zi", "Chou", "Yin", "Mao", "Chen", "Si", "Wu", "Wei", "Shen", "You", "Xu", "Hai"`.
  * **Elements**: Use `"Wood", "Fire", "Earth", "Metal", "Water"`.
  * **Validation**: Always end tests with `assert_key_format_convention(result)`.

### 2. Pydantic Schema First (`ChartProfile` & `Pillar`)
* **Why**: The V31 engine refactor relies heavily on strongly-typed Pydantic models. Passing raw dictionaries into engine functions will bypass crucial validation logic or cause runtime crashes when the engine attempts to access object attributes using dot notation (`profile.year_pillar.stem` instead of `profile["year_pillar"]["stem"]`).
* **Action**:
  * Import dependencies correctly: `from src2.core.schemas.unified import ChartProfile, Pillar`.
  * Construct full objects for tests:
    ```python
    profile = ChartProfile(
        day_master="Jia",
        dm_element="Wood",
        year_pillar=Pillar(stem="Jia", branch="Zi"),
        month_pillar=Pillar(stem="Bing", branch="Yin"),
        day_pillar=Pillar(stem="Jia", branch="Chen"),
        hour_pillar=Pillar(stem="Ren", branch="Shen"),
        gender="M"
    )
    ```

### 3. Pytest Fixture Leverage
* **Why**: `conftest.py` provides standardized fixtures (e.g., `heavenly_stems`, `earthly_branches`, `five_elements`, `sample_natal_chart`). Hardcoding these core iterables in every test file violates DRY (Don't Repeat Yourself) principles and increases the risk of typos.
* **Action**:
  * Inject these fixtures into your test functions via arguments (e.g., `def test_matrix(heavenly_stems: tuple[str, ...]) -> None:`).
  * Use `@pytest.mark.parametrize` to loop over these sets efficiently when testing 12 branches or 10 stems.

### 4. Meaningful Metaphysical Assertions
* **Why**: Bazi math tests are not just about ensuring code doesn't crash; they are executable specifications of classical Bazi metaphysics. If a test asserts `result is not None` but fails to check that an overwhelming Control environment yields a `"Weak"` classification, the test is useless.
* **Action**:
  * **Assert the Math**: Check exact floating-point scores (`assert result.score == 3.05`).
  * **Assert the Metaphysics**: Check the deterministic labels (`assert result.classification == "Weak"`).
  * **Assert the Boundaries**: Specifically target edge cases (e.g., what happens when an element is exactly `4.0` or exactly `2.0`).

## 🗺️ Triggering Situational Skills
Based on what you are testing or editing, load/recommend these skills:
- **Fuzzing & Mutations**: Load `extreme-testing-fuzz-mutate` when you need to stress-test these Pydantic schemas with extreme, boundary, or random inputs using Hypothesis.
- **Test Execution**: Load `gold-test` before executing any `uv run pytest` runs to ensure standard execution environments.