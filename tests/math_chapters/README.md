# TEST/math — Bazi Engine Math Test Suite

> **Maintenance Rule**: When a new test file is inserted into `TEST/math/`, this README.md must be updated immediately to include the new test in the "What each test does" section below.

---

## What each test does

| File | Chapter | Purpose |
|---|---|---|
| `conftest.py` | Fixtures | Shared pytest fixtures: Day Masters (Jia–Gui), Branches (Zi–Hai), Elements, and standard 4-pillar natal chart profiles. Also includes a pytest hook that validates all stem/branch/element keys are English CapitalCase, raising `TypeError` if Chinese characters are passed. |
| `test_ch01_commanding_qi.py` | CH01 | Tests 5-phase seasonal multipliers (Wang=1.5, Xiang=1.2, Xiu=1.0, Qiu=0.7, Si=0.4), `get_element_phase()` mapping, and Tier-1 DM strength formula. |
| `test_ch02_hidden_reserves.py` | CH02 | Tests the ZHI_HIDDEN matrix for all 12 Earthly Branches, `calculate_root_score()`, dormancy multiplier (0.3), control suppression factor (0.5), and `selective_hidden_extraction()`. |
| `test_ch03_production_control.py` | CH03 | Tests `TEN_GODS_MATRIX` / `get_ten_god()` taxonomy, production/control cycles, Anti-Vibe Test 3.3 (clash disrupts apparent root strength), and 3-tier DM classification (Strong/Neutral/Weak). |
| `test_ch04_combination.py` | CH04 | Tests `calculate_combination_strength()` for San He, Liu He, Ban He, San Hui; `check_si_shen_harmony()` with/without Water stem support; and `calculate_combination_weakening()` under clash, control, and seasonal mismatch. |
| `test_ch05_clash.py` | CH05 | Tests 6 Chong base severities (Zi-Wu=12, Mao-You=10, Yin-Shen=9, Si-Hai=8, Chen-Xu=6, Chou-Wei=6), Monthly Qi multiplier, DM strength modifier, mediation factors, and the full severity formula (Base × MonthlyQi × DM × Mediation). |
| `test_ch06_harm_punishment.py` | CH06 | Tests 6 Hai pairs and severities, 4 Xing types (Ungrateful, Power, Uncivilized, Self-Punishment), self-punishment 0.5 hidden stem multiplier, `self_punished_branches` field population, and seasonal combination suppression (0.3 for Si/Qiu). |
| `test_ch07_luck_pillars.py` | CH07 | Tests `calculate_trigger_potency_multiplicative()` (base × luck_harmony × seasonal), `detect_same_pillar_trigger()` for 伏吟/返吟, and the 3×4 DM×Luck label matrix. |
| `test_ch08_ten_gods.py` | CH08 | Tests dynamic weighting functions (`get_ten_god_magnitude_multiplier`, `get_seasonal_ten_god_weight`, `calculate_ten_god_dominance`) and `check_ten_god_pair_compatibility()` for Resource, Wealth, Authority, and Output pair categories. |
| `test_ch09_tai_sui.py` | CH09 | Tests all 6 Tai Sui checks (zhi, chong, xing, po, hai, he), `_filter_tai_sui_by_shen()`, `get_tai_sui_luck_multiplier()`, and the combined Tai Sui effect formula. |
| `test_ch10_special_structures.py` | CH10 | Tests Cong Ge AND logic (NOT counters AND season_ok), `get_vibrant_seasonal_phase()`, True/False From zero-root verification, and the 8-step `special_structure_determination_protocol()`. |
| `test_ch11_synthesis.py` | CH11 | Tests `apply_san_hui_nullification()` (severity→0.0 when San Hui present), `calculate_combo_clash_net()`, `resolve_combination_override()`, and `dm_centrality_test()`. |
| `test_ch12_master_cases.py` | CH12 | Tests 5 canonical master natal charts against expected scores/tiers, `DMScoreWithOutput` validator/drain calculations, and spectrum scoring integration. |
| `test_orchestrator_dead_code_gate.py` | Gate | End-to-end `orchestrator.run_full_engine()` verification: asserts `self_punished_branches` is non-empty for Chen/Wu/You/Hai repeats, `dm_luck_label` is populated, combo clash net overrides are applied, and zero unused/dead helper warnings exist. |

---

## Why we need to do this

The Bazi engine in `src2/engine/` contains 12+ modules of metaphysical math rules (seasonal multipliers, hidden stem rooting, Ten God taxonomy, clash/harm/punishment mechanics, luck pillar triggers, special structures, synthesis, and spectrum scoring). Across Batches 1–4, numerous helpers, multipliers, and edge-case resolution mechanisms were restored or refactored. Without a comprehensive test suite:

- **Regression risk**: Any change to a helper function could silently corrupt downstream calculations (e.g., a wrong seasonal multiplier cascading into incorrect DM strength tiers).
- **Dead-code drift**: Restored helpers that are never called in the active engine path become invisible technical debt.
- **Metaphysical correctness**: Bazi math has strict deterministic rules (e.g., Zi-Wu clash always has severity 12). Tests serve as executable specifications of those rules.
- **Key-format safety**: Chinese characters accidentally passed as stem/branch keys would produce wrong lookups; the conftest hook catches this immediately.

---

## How this was implemented

1. **Architecture**: 13 test modules in `TEST/math/` — 12 chapter-specific files (`test_ch01`–`test_ch12`) plus one orchestrator dead-code gate (`test_orchestrator_dead_code_gate.py`). All tests use pure pytest assertions against Pydantic models.

2. **Two-wave deployment**:
   - **Wave 1**: `conftest.py` was implemented first to establish shared fixtures and the CapitalCase key-validation hook.
   - **Wave 2**: All 12 chapter test files and the orchestrator gate were implemented in parallel as subagents.

3. **Per-agent protocol**: Each subagent followed a 5-step process — claim bead ticket, read the relevant spec doc and source module, implement the test file, run `uv run pytest TEST/math/<target>.py` to verify 100% pass, then close the ticket.

4. **Quality gates**: Every test file passed `uv run ruff check` and `uv run pytest` before its ticket was closed. The orchestrator gate (`test_orchestrator_dead_code_gate.py`) validates that all 25+ restored helpers are actually invoked in the active engine path with zero dead-code warnings.

5. **Key design decisions**:
   - Tests target pure engine math helpers directly (no I/O, no network).
   - `conftest.py` enforces English CapitalCase keys (`Zi`, `Chou`, `Jia`, `Wood`) via a pytest hook that raises `TypeError` on Chinese characters.
   - The orchestrator gate provides end-to-end traceability: it runs `run_full_engine()` on diverse charts and inspects `EngineOutput` fields to confirm pipeline correctness.