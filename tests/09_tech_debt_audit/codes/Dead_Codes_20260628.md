# 📋 Codebase Alignment & Dead Code Report: src vs src2
**Generated on 2026-06-28**

This report summarizes the dead-code audit aligning the main baseline (`src/`) against the Pydantic AI refactoring branch (`src2/`).

---

## 📊 Audit Executive Summary

* **Total Symbols Evaluated**: `237` legacy functions/classes
* **Successfully Kept / Restored**: `151` symbols
* **Finally Recommended to Drop**: `76` symbols (documented in [dead_code_deepdive_results_DropOnly.json](file:///home/yapilwsl/arthityap/baziforecaster/TEST/codes/20260626_SRC2/dead_code_deepdive_results_DropOnly.json)) (baziforeporter-only: not in standalone kit download)
* **Under Serious Review (Nuance Gap / Restorations)**: `10` accidentally dropped symbols + `billing.py` and `contradiction_resolver.py` focus areas.

---

## 🔍 Focus Area 1: `billing.py` (Promo Codes & Gatekeeping)

### Current Status
* **File Location**: [billing.py](file:///home/yapilwsl/arthityap/baziforecaster/src2/core/services/billing.py) (baziforeporter-only: not in standalone kit download)
* **Action**: **KIV (Keep In View)**.
* **Core Issue**: Currently, billing and promo code services are fully defined but unused in the refactored `src2/` branch. However, they are essential for future tier management and gatekeeping.

### Future Promo Code Gatekeeping Design
1. **Promo Code as a Gatekeeper Bypass**:
   * Instead of just updating a database column, the validation middleware (the "gatekeeper") will check `get_user_limits()` directly during incoming request parsing.
   * If a user has a valid, unexpired `PromoCode` active, their requests bypass the default `FREE` tier limits (`max_reports_per_day: 1`, `can_ask: False`) and are elevated to `PRO` or `ENTERPRISE` limits.
2. **Checking Billing Before Granting Access**:
   * The gatekeeper must intercept queries in Telegram/API routes, querying `check_rate_limit(user_id)` and checking if their subscription tier has expired.
   * If a user tries to apply a new promo code when they already have an active paid subscription tier, the billing manager should prevent double-stacking or handle the tier conversion gracefully.

---

## 🔍 Focus Area 2: `contradiction_resolver.py` (Bazi Nuance Resolution)

### Current Status
* **File Location**: [contradiction_resolver.py](file:///home/yapilwsl/arthityap/baziforecaster/src2/engine/contradiction_resolver.py) (baziforeporter-only: not in standalone kit download)
* **Action**: **Requires Serious Review & Restoration**.
* **Core Issue**: Several critical math/metaphysical logic helpers were flagged as "dead code" (unused) in the migration because the new 7-step `resolve_contradictions` function does not call them. However, their loss represents a degradation of Bazi nuance.

### Review of the Unused Functions:
1. **`apply_specificity_rule`**:
   * *What it did*: Prioritized highly specific chart signals (e.g. `exact_pillar` priority = 4) over general ones (`element_phase` priority = 2).
   * *Gap*: Bypassing this means general elemental overlaps can override specific natal pillar interactions.
2. **`calculate_combo_clash_net`**:
   * *What it did*: Computed net strength between combination and controlling branch forces to determine if a combination overrides control.
   * *Gap*: Bypassing this means we lose mathematical precision when combinations compete directly with clashes.
3. **`resolve_dm_strength_paradox`**:
   * *What it did*: Evaluated weak Daymasters under wealth pressure and checked for Luck/Annual pillar support.
   * *Gap*: Bypassing this means we fail to model whether a weak DM can survive wealth pressure using temporal support.
4. **`resolve_paradox_four_step`**:
   * *What it did*: Evolved prototype for resolving multi-signal contradictions.
   * *Gap*: Fully replaced by `resolve_contradictions` (7-step), but the 7-step pipeline forgot to incorporate the specificity and combo override sub-routines from steps 2 & 3.
5. **`calculate_temporal_weight_enhanced`**:
   * *What it did*: Supported decay-factor adjustments for temporal distances.
   * *Gap*: Left as an unused upgrade; the codebase defaulted back to the simpler `calculate_temporal_weight`.

---

## 🗺️ Recommended Next Steps

### 1. Workplan to Remove Confirmed Dead Codes
* **Actions**:
  1. Parse [dead_code_deepdive_results_DropOnly.json](file:///home/yapilwsl/arthityap/baziforecaster/TEST/codes/20260626_SRC2/dead_code_deepdive_results_DropOnly.json) to safely extract the 76 confirmed dead functions/classes. (baziforeporter-only: not in standalone kit download)
  2. Implement the edit using the Agent Guardrail:
     * Checkpoint: `uv run python agents/agent_guardrail.py checkpoint <path>`
     * Delete the code block.
     * Validate: `uv run python agents/agent_guardrail.py validate <path>`
  3. Run Targeted Gold E2E Tests:
     * `# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.` (ensure no narrative changes occurred due to pruning).

### 2. Deep-Dive Review of `contradiction_resolver.py`
* **Actions**:
  1. Determine how to re-hook the specificity rules (`apply_specificity_rule`) and combination override thresholds (`resolve_combination_override`) into the active 7-step `resolve_contradictions` pipeline.
  2. Map out unit tests for these Bazi nuances to verify they correctly influence the final chart synthesis.

### 3. Workplan to Restore Carelessly Dropped Symbols & Keep Billing KIV
* **Actions**:
  1. Re-link callers for the 10 accidentally dropped symbols (e.g. `metrics.py`, `scheduler.py`).
  2. Retain `billing.py` exactly as it is, marking it as a Keep-in-View (KIV) module for the upcoming billing/promo code gatekeeper feature.
