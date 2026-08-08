# Project-Wide Technical Debt Audit
Generated: test_classical_data_audit_swarm.py
Scan Directory: `alt_src`

## Executive Summary
- **Total Files with Debt**: 7
- **Total Markers Found**: 57
- **Verification Target**: Local Gemini (`v1beta`)

## Detailed Audit Log
### `src\agents\classical_sync_v4_audit_swarm.py`
#### L360 [BUG]
**Marker**: `else "TYPE BUG: still using trace.get('void_degradation') — trace is a list, not a dict"`
**Context**:
```python
            "'Void Lu/Blade' in trace — correct list membership check found"
            if kw_list_check
            else "TYPE BUG: still using trace.get('void_degradation') — trace is a list, not a dict"
        ),
    )
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

### `src\agents\phase3_swarm.py`
#### L92 [BUG]
**Marker**: `# 2. Logic: _has_meaningful_root — BUG FIX: use .get() directly, not (or {})`
**Context**:
```python
            )

            # 2. Logic: _has_meaningful_root — BUG FIX: use .get() directly, not (or {})
            root_target = (
                '    for key in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:\n'
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L125 [BUG]
**Marker**: `# 3. Logic: Kong Wang — BUG FIX: use .get() directly, not (or {})`
**Context**:
```python
            m0_content = safe_replace(m0_content, root_target, root_injection, "m0._has_meaningful_root body")

            # 3. Logic: Kong Wang — BUG FIX: use .get() directly, not (or {})
            void_target = '    if month_branch in void_branches:\n        trace.append("kong_wang_degradation")'
            void_injection = (
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L172 [BUG]
**Marker**: `# 6. Logic: Regular Pattern root_count — BUG FIX: use .get() directly`
**Context**:
```python
            m0_content = safe_replace(m0_content, reg8_target, reg8_injection, "m0.regular_8_month_logic")

            # 6. Logic: Regular Pattern root_count — BUG FIX: use .get() directly
            root_cnt_target = '        root_count = sum(1 for b in all_branches if b and h_stem in HIDDEN_STEMS.get(b, []))'
            root_cnt_injection = (
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L192 [BUG]
**Marker**: `# 7. Logic: 7K Output God Scan — BUG FIX: use .get() directly`
**Context**:
```python
            m0_content = safe_replace(m0_content, root_cnt_target, root_cnt_injection, "m0.regular_pattern_root_count")

            # 7. Logic: 7K Output God Scan — BUG FIX: use .get() directly
            out_scan_target = (
                '    if selected_ten_god == "7 Killings":\n'
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L231 [BUG]
**Marker**: `# 9. Helper: _count_ten_god_category branch logic — BUG FIX: use .get() directly`
**Context**:
```python
                )

            # 9. Helper: _count_ten_god_category branch logic — BUG FIX: use .get() directly
            m0_content = safe_replace(
                m0_content,
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L272 [BUG]
**Marker**: `# root_branch identification loop — BUG FIX: use .get() directly`
**Context**:
```python
            )

            # root_branch identification loop — BUG FIX: use .get() directly
            rb_target = (
                '    for p_name in ["day", "month", "year", "hour"]:\n'
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L303 [BUG]
**Marker**: `# Root scoring loop — BUG FIX: use .get() directly`
**Context**:
```python
            )

            # Root scoring loop — BUG FIX: use .get() directly
            root_logic_target = (
                '    for p_name, p in chart_pillars.items():\n'
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L344 [BUG]
**Marker**: `# BUG FIX 1: m13 already imports get_root_sub_score directly — no import patch needed.`
**Context**:
```python

    # --- TASK 4: Patch module13_spectrum.py ---
    # BUG FIX 1: m13 already imports get_root_sub_score directly — no import patch needed.
    # BUG FIX 2: season_target expanded to consume the original seasonal_score and clamp lines
    #            so they are not left as orphan lines after injection.
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L345 [BUG]
**Marker**: `# BUG FIX 2: season_target expanded to consume the original seasonal_score and clamp lines`
**Context**:
```python
    # --- TASK 4: Patch module13_spectrum.py ---
    # BUG FIX 1: m13 already imports get_root_sub_score directly — no import patch needed.
    # BUG FIX 2: season_target expanded to consume the original seasonal_score and clamp lines
    #            so they are not left as orphan lines after injection.
    # BUG FIX 3: All guards use .get() directly instead of (or {}).get() falsy-dict trap.
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L347 [BUG]
**Marker**: `# BUG FIX 3: All guards use .get() directly instead of (or {}).get() falsy-dict trap.`
**Context**:
```python
    # BUG FIX 2: season_target expanded to consume the original seasonal_score and clamp lines
    #            so they are not left as orphan lines after injection.
    # BUG FIX 3: All guards use .get() directly instead of (or {}).get() falsy-dict trap.
    if "transformed_branches: dict | None = None" in m13_content:
        tasks["TASK 4: Patch module13_spectrum.py"] = "SKIP"
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L368 [BUG]
**Marker**: `# BUG FIX 2: Seasonal Score — consume original seasonal_score and clamp lines in target`
**Context**:
```python
            )

            # BUG FIX 2: Seasonal Score — consume original seasonal_score and clamp lines in target
            # to prevent orphan double-assignment after injection.
            season_target = (
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L387 [BUG]
**Marker**: `# Root Score Call — BUG FIX: use .get() directly`
**Context**:
```python
            m13_content = safe_replace(m13_content, season_target, season_injection, "m13.seasonal_transformation")

            # Root Score Call — BUG FIX: use .get() directly
            m13_content = safe_replace(
                m13_content,
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L476 [BUG]
**Marker**: `# Locate taboo line robustly — BUG FIX 3: strip whitespace to avoid alignment mismatch`
**Context**:
```python
            shen_block_anchor = '    # 0.6 Shen Classification'

            # Locate taboo line robustly — BUG FIX 3: strip whitespace to avoid alignment mismatch
            taboo_candidates = [
                line for line in orch_content.splitlines()
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

### `src\bot\reliability.py`
#### L102 [BUG]
**Marker**: `# Set LOG_LEVEL=DEBUG for more verbose output`
**Context**:
```python
    # Example usage:
    # Set TELEGRAM_ADMIN_ID in your environment for testing admin alerts
    # Set LOG_LEVEL=DEBUG for more verbose output

    @with_retries(max_retries=3)
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

### `src\engine\bazi_data.py`
#### L491 [TODO]
**Marker**: `"core_elements": ["Metal"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Indirect Wealth", "Direct Resource", "Indirect Resource"],
        "structural_enemies": ["Hurt Officer", "7 Killings"],
        "core_elements": ["Metal"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Metal", "Earth"],
        "unfavorable_elements": ["Fire"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L505 [TODO]
**Marker**: `"core_elements": ["Water", "Metal"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Direct Officer"],
        "structural_enemies": ["7 Killings", "Hurt Officer"],
        "core_elements": ["Water", "Metal"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Water", "Metal"],
        "unfavorable_elements": ["Fire", "Earth"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L519 [TODO]
**Marker**: `"core_elements": ["Water"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Officer", "7 Killings"],
        "structural_enemies": ["Direct Wealth", "Indirect Wealth"],
        "core_elements": ["Water"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Water", "Metal"],
        "unfavorable_elements": ["Earth"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L533 [TODO]
**Marker**: `"core_elements": ["Fire", "Earth"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Indirect Wealth"],
        "structural_enemies": ["Direct Resource", "Indirect Resource"],
        "core_elements": ["Fire", "Earth"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L547 [TODO]
**Marker**: `"core_elements": ["Metal"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Eating God", "Hurt Officer", "Direct Resource", "Indirect Resource"],
        "structural_enemies": ["Direct Wealth", "Indirect Wealth"],
        "core_elements": ["Metal"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Water", "Wood"],
        "unfavorable_elements": ["Metal", "Earth"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L561 [TODO]
**Marker**: `"core_elements": ["Earth"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Officer", "Eating God", "Hurt Officer"],
        "structural_enemies": ["Rob Wealth", "Friend"],
        "core_elements": ["Earth"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Earth", "Fire"],
        "unfavorable_elements": ["Wood"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L575 [TODO]
**Marker**: `"core_elements": ["Fire"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Indirect Wealth"],
        "structural_enemies": ["Indirect Resource"],
        "core_elements": ["Fire"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L589 [TODO]
**Marker**: `"core_elements": ["Fire"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Indirect Wealth", "Direct Resource", "Indirect Resource"],
        "structural_enemies": ["Direct Officer"],
        "core_elements": ["Fire"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L603 [TODO]
**Marker**: `"core_elements": ["Wood"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Indirect Wealth", "Direct Officer"],
        "structural_enemies": ["Direct Resource", "Indirect Resource"],
        "core_elements": ["Wood"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Wood", "Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L617 [TODO]
**Marker**: `"core_elements": ["Wood"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["7 Killings", "Direct Officer"],
        "structural_enemies": ["Direct Wealth", "Indirect Wealth"],
        "core_elements": ["Wood"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Metal", "Fire"],
        "unfavorable_elements": ["Wood", "Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L645 [TODO]
**Marker**: `"core_elements": ["Wood"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Friend", "Rob Wealth", "Indirect Resource"],
        "structural_enemies": ["Direct Officer", "7 Killings", "Eating God", "Hurt Officer"],
        "core_elements": ["Wood"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Wood", "Water"],
        "unfavorable_elements": ["Metal"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L659 [TODO]
**Marker**: `"core_elements": ["Fire"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Eating God", "Hurt Officer", "Direct Wealth", "Indirect Wealth"],
        "structural_enemies": ["Direct Resource", "Indirect Resource", "Direct Officer", "7 Killings"],
        "core_elements": ["Fire"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Fire", "Earth"],
        "unfavorable_elements": ["Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L673 [TODO]
**Marker**: `"core_elements": ["Earth"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Wealth", "Indirect Wealth", "Eating God", "Hurt Officer"],
        "structural_enemies": ["Friend", "Rob Wealth", "Direct Resource"],
        "core_elements": ["Earth"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Earth", "Fire"],
        "unfavorable_elements": ["Wood"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L687 [TODO]
**Marker**: `"core_elements": ["Metal"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["7 Killings", "Direct Wealth", "Indirect Wealth"],
        "structural_enemies": ["Eating God", "Hurt Officer", "Direct Resource", "Indirect Resource"],
        "core_elements": ["Metal"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Metal", "Earth"],
        "unfavorable_elements": ["Fire"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L701 [TODO]
**Marker**: `"core_elements": ["Metal", "Earth"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": ["Direct Officer", "7 Killings", "Direct Wealth", "Indirect Wealth"],
        "structural_enemies": ["Direct Resource", "Indirect Resource", "Friend", "Rob Wealth"],
        "core_elements": ["Metal", "Earth"],  # TODO: Verify core_elements from classical source
        "favorable_elements": ["Metal", "Earth"],
        "unfavorable_elements": ["Wood", "Water"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L715 [TODO]
**Marker**: `"core_elements": ["Wood"],  # TODO: Verify core_elements from classical source`
**Context**:
```python
        "structural_friends": [],
        "structural_enemies": [],
        "core_elements": ["Wood"],  # TODO: Verify core_elements from classical source
        "favorable_elements": [],
        "unfavorable_elements": [],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L730 [TODO]
**Marker**: `"core_elements": ["Wood"],  # TODO: core_elements vary by stem combination — populate per instance`
**Context**:
```python
        "structural_friends": ["Friend", "Rob Wealth", "Indirect Resource"],
        "structural_enemies": ["Direct Officer", "7 Killings", "Eating God", "Hurt Officer"],
        "core_elements": ["Wood"],  # TODO: core_elements vary by stem combination — populate per instance
        "favorable_elements": ["Wood", "Water"],
        "unfavorable_elements": ["Metal"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L746 [TODO]
**Marker**: `"core_elements": ["Earth"],  # TODO: core_elements vary by stem combination — populate per instance`
**Context**:
```python
        "stem_combinations": ["Jia-Ji", "Yi-Geng", "Bing-Xin", "Ding-Ren", "Wu-Gui"],
        "structural_enemies": ["7 Killings", "Direct Officer"],
        "core_elements": ["Earth"],  # TODO: core_elements vary by stem combination — populate per instance
        "favorable_elements": ["Earth", "Fire"],
        "unfavorable_elements": ["Wood"],
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

### `src\engine\bazi_math.py`
#### L228 [TODO]
**Marker**: `"Extreme_Strong": 0.0,  # TODO: Tune Extreme_Strong DSI bonus from classical source`
**Context**:
```python
    "Follower": 3.0,
    "Neutral": 0.0,
    "Extreme_Strong": 0.0,  # TODO: Tune Extreme_Strong DSI bonus from classical source
    "Extreme_Weak": 0.0,  # TODO: Tune Extreme_Weak DSI bonus from classical source
}
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L229 [TODO]
**Marker**: `"Extreme_Weak": 0.0,  # TODO: Tune Extreme_Weak DSI bonus from classical source`
**Context**:
```python
    "Neutral": 0.0,
    "Extreme_Strong": 0.0,  # TODO: Tune Extreme_Strong DSI bonus from classical source
    "Extreme_Weak": 0.0,  # TODO: Tune Extreme_Weak DSI bonus from classical source
}

```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

### `src\engine\module13_spectrum.py`
#### L159 [BUG]
**Marker**: `# Old: (mult - 1.0) * 30.0 / 0.5  → Wang=60 (clamped), Xiu=30 (same ceiling). BUG.`
**Context**:
```python
        # T4-fix: divisor corrected from 0.5 → 1.0.
        # get_phase_multiplier returns [0.5, 2.0]; map to [-30, +30].
        # Old: (mult - 1.0) * 30.0 / 0.5  → Wang=60 (clamped), Xiu=30 (same ceiling). BUG.
        # New: (mult - 1.0) * 30.0        → Wang=30, Xiu=15, Balanced=0, Si=-15.  FIXED.
        # Interaction Blindness Fix (Phase 3): Seasonal Qi follows transformation
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

### `src\memory\mem0_store.py`
#### L11 [BUG]
**Marker**: `print("DEBUG: mem0_store.py module loading...")`
**Context**:
```python
from src.memory.constants import QDRANT_MEMORY_COLLECTION

print("DEBUG: mem0_store.py module loading...")
sys.stdout.flush()
print("DEBUG: mem0_store.py module loaded.")
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L13 [BUG]
**Marker**: `print("DEBUG: mem0_store.py module loaded.")`
**Context**:
```python
print("DEBUG: mem0_store.py module loading...")
sys.stdout.flush()
print("DEBUG: mem0_store.py module loaded.")
sys.stdout.flush()

```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L25 [BUG]
**Marker**: `print("DEBUG: Mem0Store init started")`
**Context**:
```python

    def __init__(self):
        print("DEBUG: Mem0Store init started")
        sys.stdout.flush()
        self.enabled = True
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L41 [BUG]
**Marker**: `print("DEBUG: Importing mem0 internal dependencies...")`
**Context**:
```python
        openai_base = os.environ.pop("OPENAI_BASE_URL", None)

        print("DEBUG: Importing mem0 internal dependencies...")
        sys.stdout.flush()
        # Custom Embedder for in-house BGEM3 service
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L50 [BUG]
**Marker**: `print("DEBUG: Defining InHouseBGEM3Embedder...")`
**Context**:
```python
        from mem0.llms.base import LLMBase

        print("DEBUG: Defining InHouseBGEM3Embedder...")
        sys.stdout.flush()

```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L55 [BUG]
**Marker**: `print(f"DEBUG: InHouseBGEM3Embedder.embed calling for: {text[:50]}...")`
**Context**:
```python
        class InHouseBGEM3Embedder(EmbeddingBase):
            def embed(self, text: str, memory_action=None) -> list[float]:
                print(f"DEBUG: InHouseBGEM3Embedder.embed calling for: {text[:50]}...")
                sys.stdout.flush()
                max_retries = 3
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L76 [BUG]
**Marker**: `print(f"DEBUG: InHouseBGEM3Embedder.embed SUCCESS for: {text[:50]}...")`
**Context**:
```python

                            if vector and len(vector) == 1024:
                                print(f"DEBUG: InHouseBGEM3Embedder.embed SUCCESS for: {text[:50]}...")
                                sys.stdout.flush()
                                return vector
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L114 [BUG]
**Marker**: `print(f"DEBUG: InHouseMem0LLM.generate_response calling for model: {self.model} via {self.provider}")`
**Context**:
```python
                )

                print(f"DEBUG: InHouseMem0LLM.generate_response calling for model: {self.model} via {self.provider}")
                sys.stdout.flush()

```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L185 [BUG]
**Marker**: `print("DEBUG: Setting up Memory config (Direct Bridge Config)...")`
**Context**:
```python

        try:
            print("DEBUG: Setting up Memory config (Direct Bridge Config)...")
            sys.stdout.flush()
            # Direct Bridge Setup: Chroma + Ollama (via OpenAI-compatible /v1 endpoint)
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L216 [BUG]
**Marker**: `print("DEBUG: Calling Memory.from_config (Remote Ollama Bridge)...")`
**Context**:
```python
            }

            print("DEBUG: Calling Memory.from_config (Remote Ollama Bridge)...")
            sys.stdout.flush()
            # Create memory instance
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L221 [BUG]
**Marker**: `print("DEBUG: Injecting InHouseBGEM3Embedder...")`
**Context**:
```python
            self.memory = Memory.from_config(self.config)

            print("DEBUG: Injecting InHouseBGEM3Embedder...")
            sys.stdout.flush()
            # Inject our custom in-house embedder instance
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L229 [BUG]
**Marker**: `print("DEBUG: Mem0Store init successful (Remote Whisperer Mode)")`
**Context**:
```python
            self.memory.llm = InHouseMem0LLM()

            print("DEBUG: Mem0Store init successful (Remote Whisperer Mode)")
            sys.stdout.flush()

```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L239 [BUG]
**Marker**: `print(f"DEBUG: Mem0Store init FAILED: {e}")`
**Context**:
```python

        except Exception as e:
            print(f"DEBUG: Mem0Store init FAILED: {e}")
            sys.stdout.flush()
            logger.error(f"CRITICAL: Failed to initialize mem0 Memory: {e}")
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L253 [BUG]
**Marker**: `print(f"DEBUG: add_memory started for user {user_id}")`
**Context**:
```python
            return None

        print(f"DEBUG: add_memory started for user {user_id}")
        sys.stdout.flush()
        meta = metadata or {}
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L259 [BUG]
**Marker**: `print("DEBUG: Calling self.memory.add...")`
**Context**:
```python

        try:
            print("DEBUG: Calling self.memory.add...")
            sys.stdout.flush()
            result = self.memory.add(text, user_id=str(user_id), metadata=meta)
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L262 [BUG]
**Marker**: `print("DEBUG: self.memory.add successful")`
**Context**:
```python
            sys.stdout.flush()
            result = self.memory.add(text, user_id=str(user_id), metadata=meta)
            print("DEBUG: self.memory.add successful")
            sys.stdout.flush()
            return result
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L266 [BUG]
**Marker**: `print(f"DEBUG: self.memory.add FAILED: {e}")`
**Context**:
```python
            return result
        except Exception as e:
            print(f"DEBUG: self.memory.add FAILED: {e}")
            sys.stdout.flush()
            raise
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L322 [BUG]
**Marker**: `print(f"DEBUG: search_memories started for user {user_id}")`
**Context**:
```python
            return []

        print(f"DEBUG: search_memories started for user {user_id}")
        sys.stdout.flush()
        try:
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L325 [BUG]
**Marker**: `print(f"DEBUG: Calling self.memory.search with FILTERS for query: {query[:50]}...")`
**Context**:
```python
        sys.stdout.flush()
        try:
            print(f"DEBUG: Calling self.memory.search with FILTERS for query: {query[:50]}...")
            sys.stdout.flush()
            # Use filters instead of direct user_id argument to match mem0 v1.1+ requirements
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L329 [BUG]
**Marker**: `print(f"DEBUG: self.memory.search returned {len(results) if results else 0} results")`
**Context**:
```python
            # Use filters instead of direct user_id argument to match mem0 v1.1+ requirements
            results = self.memory.search(query, filters={"user_id": str(user_id)}, limit=limit)
            print(f"DEBUG: self.memory.search returned {len(results) if results else 0} results")
            sys.stdout.flush()
            return results
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

#### L333 [BUG]
**Marker**: `print(f"DEBUG: self.memory.search FAILED: {e}")`
**Context**:
```python
            return results
        except Exception as e:
            print(f"DEBUG: self.memory.search FAILED: {e}")
            sys.stdout.flush()
            return []
```
**Verification Action**:
- [ ] Verify classical citations (if applicable)
- [ ] Logic check for falsy-dict traps
- [ ] Regression check with `test_bug_repro_suite.py`

---

