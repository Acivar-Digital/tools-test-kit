# Property-Based Fuzzing & Mutation Testing — Candidate Proposal

This document identifies 5 high-value candidates for expanding the BaZi engine's test coverage with Hypothesis fuzzing and mutmut mutation testing. Each candidate is evaluated against the four criteria from the SDET framework: mathematical risk, date/time complexity, combinatorial logic depth, and data normalization surface area.

---

### 1. Target: `_sigmoid` (module11_probability.py)
* **Location:** `src2/engine/module11_probability.py:26`
* **Why it needs fuzzing:**
  This function computes `1.0 / (1.0 + math.exp(-x))`. While Python's `math.exp()` handles `inf` and `-inf` gracefully (returning `inf` and `0.0` respectively), the function silently collapses extreme inputs to `0.0` or `1.0` without any guard or warning. If a developer later refactors this to use a different math library or removes the `1.0 +` term, a `ZeroDivisionError` could emerge. The function is also a critical input to `_luck_layer_envelope`, which multiplies its output by a range — a NaN propagated here would poison all downstream probability scores.
* **Proposed Fuzzing Strategy (Hypothesis):**
  * `st.floats(allow_nan=False, allow_infinity=True, min_value=-1e308, max_value=1e308)` for the `x` parameter.
  * **Strict properties/invariants:**
    * Output must be a finite float: `assert not math.isnan(result) and not math.isinf(result)`
    * Output must be in the valid probability range: `assert 0.0 <= result <= 1.0`
    * Output must never silently equal exactly 0.0 or 1.0 for finite inputs (a regression indicator).
* **Mutation Testing Value:**
  mutmut will catch if a developer changes `1.0 + math.exp(-x)` to `math.exp(-x)` (removing the `1.0`), which would cause `1.0 / inf = 0.0` for large positive `x` instead of the correct `~1.0`. It will also catch sign flips like `math.exp(x)` instead of `math.exp(-x)`, which inverts the sigmoid curve.

---

### 2. Target: `_get_era_medicine_ratio` (module1_macro.py)
* **Location:** `src2/engine/module1_macro.py:138`
* **Why it needs fuzzing:**
  This function divides `medicine_count` by `len(era_branches)` with a guard `if era_branches else 0.0`. The guard is a classic mutation target — if a developer removes the guard (e.g., during a refactor that assumes `era_branches` is never empty), a `ZeroDivisionError` will crash the production pipeline at runtime. The function also uses `round(..., 2)` which can silently lose precision for edge-case ratios.
* **Proposed Fuzzing Strategy (Hypothesis):**
  * `st.lists(st.sampled_from(STEM_ORDER + BRANCH_ORDER), min_size=0, max_size=20)` for `era_branches`.
  * `st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=100.0)` for `medicine_count` (clamped to valid range).
  * **Strict properties/invariants:**
    * Output must be a finite float: `assert not math.isnan(result) and not math.isinf(result)`
    * Output must be in `[0.0, 1.0]`: `assert 0.0 <= result <= 1.0`
    * When `era_branches` is empty, output must be exactly `0.0` (not `NaN` or `inf`).
    * When `medicine_count` is 0, output must be exactly `0.0`.
* **Mutation Testing Value:**
  mutmut will catch if the guard `if era_branches else 0.0` is removed or changed to `if era_branches else 1.0` (which would produce `0.0 / 1.0 = 0.0` — a silent wrong answer rather than a crash). It will also catch if `round(..., 2)` is removed, causing floating-point precision drift.

---

### 3. Target: `_get_spectrum_tier` (module13_spectrum.py)
* **Location:** `src2/engine/module13_spectrum.py:40`
* **Why it needs fuzzing:**
  This function uses a complex if/elif tree with 6 boundary thresholds (`80, 40, 10, -10, -40, -80`) to classify a continuous score into 6 tiers (`Vibrant`, `Strong`, `Mild Strong`, `Mild Weak`, `Weak`, `Follower`). Boundary off-by-one errors (`>=` vs `>`) are a classic mutation target that cause silent misclassification — a score of exactly `80.0` could be classified as `Strong` instead of `Vibrant`, or vice versa. This is a combinatorial logic trap where edge cases fall through to unhandled states.
* **Proposed Fuzzing Strategy (Hypothesis):**
  * `st.floats(allow_nan=False, allow_infinity=False, min_value=-200.0, max_value=200.0)` for the `score` parameter.
  * **Strict properties/invariants:**
    * Output must always be one of the 6 valid tier strings: `assert result in ["Vibrant", "Strong", "Mild Strong", "Mild Weak", "Weak", "Follower"]`
    * The classification must be monotonically non-increasing: for any `a > b`, `tier_index(a) <= tier_index(b)` (higher scores = stronger tiers).
    * Boundary values must be consistent: `tier(80.0) == "Vibrant"`, `tier(40.0) == "Strong"`, `tier(10.0) == "Mild Strong"`, `tier(-10.0) == "Mild Weak"`, `tier(-40.0) == "Weak"`, `tier(-80.0) == "Follower"`.
* **Mutation Testing Value:**
  mutmut is ideal here — changing `>=` to `>` at any boundary will cause a different tier assignment for boundary values. The test suite must catch these boundary regressions, and mutation testing will verify that it does.

---

### 4. Target: `get_prior_log_odds` (module11_probability.py)
* **Location:** `src2/engine/module11_probability.py:19`
* **Why it needs fuzzing:**
  This function computes `math.log(p / (1 - p))` (log-odds transformation). It has a guard for `p == 0.0` but **no guard for `p == 1.0`** — when `p=1.0`, the expression `1 - p = 0` causes a `ZeroDivisionError` in the division, or `math.log(inf)` returns `inf`. If `p` comes from a database or LLM output where `1.0` is a valid probability, this is a silent poison trap. Additionally, `p > 1.0` or `p < 0.0` would produce `math.log(negative)` which raises `ValueError`.
* **Proposed Fuzzing Strategy (Hypothesis):**
  * `st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1.0)` for the `p` parameter.
  * **Strict properties/invariants:**
    * Must not raise any exception for any valid probability input.
    * Output must be a finite float: `assert not math.isnan(result) and not math.isinf(result)`
    * For `p=0.5`, output must be `0.0` (log-odds of a fair coin is zero).
    * Output must be monotonically increasing with `p`.
* **Mutation Testing Value:**
  mutmut will catch if the `if p == 0.0: return 0.0` guard is removed (causing `math.log(0)` = `-inf`), or if the division `p / (1 - p)` is accidentally swapped to `(1 - p) / p` (inverting the log-odds). It will also catch if `math.log` is replaced with `math.log10` or `math.log2`.

---

### 5. Target: `_compute_normal_scores` (module13_spectrum.py)
* **Location:** `src2/engine/module13_spectrum.py:92`
* **Why it needs fuzzing:**
  This function computes a weighted composite score using the formula `((seasonal * 0.30) + (root * 0.35) + (balance * 0.25) + (pattern * 0.10)) * (100.0 / 26.75)`. The magic number `26.75` is a divisor that could silently produce wrong results if changed. The function also clamps intermediate values with `max(-30.0, min(30.0, ...))` and `max(-25.0, min(25.0, ...))`, which are boundary conditions that mutation testing can verify. If any weight is accidentally set to 0 or negative, the composite score loses a dimension without any error.
* **Proposed Fuzzing Strategy (Hypothesis):**
  * `st.floats(allow_nan=False, allow_infinity=False, min_value=-30.0, max_value=30.0)` for each of the 4 component scores (`seasonal_score`, `root_score`, `balance_score`, `pattern_score`).
  * **Strict properties/invariants:**
    * Output must be a finite float: `assert not math.isnan(result) and not math.isinf(result)`
    * The weighted sum before scaling must be in a bounded range.
    * The final `continuous_score` must be clamped to `[-100.0, 100.0]`.
    * If all inputs are 0, output must be 0.0.
* **Mutation Testing Value:**
  mutmut will catch if the magic number `26.75` is changed to `26.5` or `27.0` (a subtle scaling error), or if a weight like `0.30` is changed to `0.0` (silently dropping a dimension). It will also catch if the clamping `max(-100.0, min(100.0, ...))` is removed, allowing out-of-range scores to propagate.

---

### Summary

| # | Candidate | Risk Level | Fuzzing Strategy | Mutation Value |
|---|-----------|-----------|-----------------|----------------|
| 1 | `_sigmoid` | High | `st.floats(allow_infinity=True)` | Catches sign flips, denominator removal |
| 2 | `_get_era_medicine_ratio` | High | `st.lists(...)` with empty list | Catches guard removal, precision loss |
| 3 | `_get_spectrum_tier` | Critical | `st.floats()` at boundary values | Catches `>=` → `>` boundary regressions |
| 4 | `get_prior_log_odds` | Critical | `st.floats(min=0, max=1)` | Catches guard removal, log base swap |
| 5 | `_compute_normal_scores` | Medium | `st.floats()` for component scores | Catches magic number drift, weight zeroing |

**Recommended implementation order:** Start with `_get_spectrum_tier` (highest mutation value for boundary logic) and `get_prior_log_odds` (highest risk of silent data corruption), then expand to the remaining three.
