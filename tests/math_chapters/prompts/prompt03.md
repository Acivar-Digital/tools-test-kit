# Role and Mission
You are a Staff-Level QA Architect and Orchestrator Agent operating in the `opencode` environment. Your mission is to harden our existing Bazi Math test suite, specifically focusing on **Chapter 03: The Logic of Production-Control (DM Strength Determination)**. You will build rigorous edge-case and boundary tests to ensure the deterministic engine never violates classical Bazi principles, exact Tier 1 formulas, or Ten God interaction rules.

## Environment Context
* **Test Directory:** `/home/yapilwsl/arthityap/baziforecaster/TEST/math/` (baziforeporter-only: not in standalone kit download)
* **Reference File:** `TEST/math/test_ch03_production_control.py` (Append tests here or create `TEST/math/test_ch03_edge_cases.py`)
* **Source Modules:** `src2/engine/module2_root.py`, `src2/engine/module3_interaction.py`, `src2/engine/bazi_data.py`
* **Skill Dependency:** All agents MUST read and strictly adhere to `TEST/math/SKILL.md` (Bazi Testing Conventions) before writing a single line of code. Absolutely NO Chinese characters; enforce English CapitalCase for all elements/stems/branches, and use pure Pydantic models.

## Subagent Deployment Criteria
You must deploy **3 subagents at one go** to tackle three distinct mathematical boundaries and metaphysical edge cases concurrently. 

Before you deploy them, you must create 3 tickets containing the details of the tasks they need to perform.

For each agent, you must strictly instruct them to execute the following lifecycle:
1. **Claim the ticket:** Acknowledge assignment.
2. **Understand the target:** Read the relevant source code in `src2/engine/` and the existing tests in `TEST/math/`. 
3. **Perform tasks:** 
   - Write the Pytest unit test(s) in the `TEST/math/` directory.
   - Run `uv run pytest TEST/math/<target_file> -q`.
   - **CRITICAL:** If the test exposes a bug or crashes the engine, the agent MUST go into `src2/engine/` and fix the source code to patch the vulnerability until the test passes.
4. **Capture decisions:** Use `bd remember "Hardened Chapter 03 [Domain]. Asserted X boundary..."` to capture key decisions and report status.
5. **Close the ticket:** Mark as complete.

---

## 🎟️ TICKET DETAILS (To be assigned to Subagents)

### Ticket 1: Hardening 贪合忘克 (Greedy for Combination, Forgets to Control)
**Target File:** `TEST/math/test_ch03_edge_cases.py`
**Reference Functions:** `get_suspended_stems` in `src2/engine/module3_interaction.py` and `calculate_dm_strength_tier1` in `src2/engine/module2_root.py`
**Task Details:**
* A fundamental classical rule is 贪合忘克 (Tan He Wang Ke): If a stem is involved in a Heavenly Stem Combination (天干五合), its attention is "occupied" and it suspends its normal Control/Production toward the Day Master.
* **Strategy:** Construct two `ChartProfile` objects for a `Jia` (Wood) DM. 
  - Chart A has a `Geng` (Metal) stem controlling the DM.
  - Chart B has a `Geng` (Metal) stem AND an `Yi` (Wood) stem. `Yi` and `Geng` form a Heavenly Stem Combination.
* **Properties to Assert:**
  1. The `control_dm` score in Chart B MUST be mathematically lower than the `control_dm` score in Chart A, proving that the `Yi-Geng` combination successfully suspended `Geng`'s control.
  2. Assert that `get_suspended_stems` correctly flags `Geng` and `Yi` as suspended.

### Ticket 2: Floating-Point Boundaries of the Tier 1 Strength Formula
**Target File:** `TEST/math/test_ch03_edge_cases.py`
**Reference Function:** `calculate_dm_strength_tier1` and `classify_dm_strength` in `src2/engine/module2_root.py`
**Task Details:**
* The Tier 1 formula is exact: `(Root * 2.0) + Support - (Control * 1.5)`. The thresholds are `Strong >= 4.0`, `Weak <= 2.0`, and Neutral otherwise. Floating-point imprecision (e.g., `3.999999`) or incorrect penalty weights can break the classification.
* **Strategy:** Manually inject specific root, support, and control values into the classification logic to hit the exact mathematical boundaries.
* **Properties to Assert:**
  1. **The Exact Boundaries:** Assert that a mathematically calculated score of exactly `4.0` returns `"Strong"` and exactly `2.0` returns `"Weak"`.
  2. **The 1.5x Penalty Check:** Construct a scenario where `Support = 3.0` and `Control = 2.0` (with 0 Root). Since `(0*2) + 3.0 - (2.0*1.5) = 0.0`, the chart should evaluate to `"Weak"`, proving the `1.5x` Control penalty correctly overwhelms the numerical Support advantage.

### Ticket 3: Anti-Vibe Test 3.3 - Dual Effects of Clash on a Fire DM
**Target File:** `TEST/math/test_ch03_edge_cases.py`
**Reference Function:** `calculate_clash_adjusted_dm_score` in `src2/engine/module2_root.py` and `get_ten_god`
**Task Details:**
* Anti-Vibe Test 3.3 corrects a common amateur mistake: Assuming Metal is "Control" for a Fire DM. For a `Bing` (Fire) DM, Metal is Wealth, and Water is Control. A clash (e.g., `Yin-Shen`) surfaces BOTH support (Wood/Fire from `Yin`) and control (Water from `Shen`).
* **Strategy:** Feed a `ChartProfile` with a `Bing` (Yang Fire) DM containing a `Yin` branch and a `Shen` branch, and pass them as `clashed_branches`. 
* **Properties to Assert:**
  1. Extract the surfaced stems from `Shen`. Assert `Geng` (Metal) evaluates strictly to `"Indirect Wealth"` via `get_ten_god` (not a controller).
  2. Assert `Ren` (Water) from `Shen` evaluates to `"7 Killings"` (Control).
  3. Assert that the `clash_adjusted_dm_score` experiences simultaneous spikes in `root_dm`/`support_dm` (from `Yin`'s `Jia/Bing`) AND `control_dm` (from `Shen`'s `Ren`), proving the engine calculates the chaotic dual-nature of the clash rather than a flat, one-directional penalty.