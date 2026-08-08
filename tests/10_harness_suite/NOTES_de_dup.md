# De-dup note — `agent_guardrail.*` / `find_hallucinations.py` lineage

These two files exist in **three** places in the shipped kit (plus the live source).

## Matrix

| file | `08_static_gates/`<br>(Phase-1, baziforecaster-sourced) | `10_harness_suite/_shared/`<br>(Phase-2, from `ai-factory/tests/`) | live source `ai-factory/tests/` |
|---|---|---|---|
| `agent_guardrail.py` | 736 lines (byte-identical) | 736 lines (byte-identical) | 736 lines (byte-identical) |
| `agent_guardrail.json` | present | present | present |
| `find_hallucinations.py` | 300 lines (un-linted) | 299 lines (lint-cleaned) | 299 lines (lint-cleaned) |

## How the diff arises

`agent_guardrail.py` is **byte-identical** everywhere — baziforecaster and `ai-factory/tests/`
share the same canonical copy. The Phase-1 `_source/` mirror therefore produced a 08 copy
identical to the harness source.

`find_hallucinations.py` differs by **one line**: the harness copy in `ai-factory/tests/`
had `from typing import Optional` removed by the repo's own lint gate
(`uv run ruff check factory/ tests/`, F401). The 08 copy was taken from the `_source/`
mirror *before* that lint fix, so it retains the unused import (300 lines vs 299).

## Decision

**Keep all three.** They honestly reflect two different points in time:
- `10/_shared/find_hallucinations.py` = canonical **lint-clean** harness version (299 lines).
- `08/find_hallucinations.py` = vendored **community** version from `_source/` (300 lines).

Neither overwrites the other. Do **not** run a blanket "dedup identical files" pass:
`agent_guardrail.py` is intentionally shared provenance; `find_hallucinations.py` is
intentionally a 1-line diff and should stay so the lineage is visible.

## Verify

```bash
# agent_guardrail.py is identical across all three live paths
diff kit-tests/08_static_gates/agent_guardrail.py \
     kit-tests/10_harness_suite/_shared/agent_guardrail.py   # → no output

# find_hallucinations.py: 08 (un-linted) vs 10/_shared (lint-clean)
diff kit-tests/08_static_gates/find_hallucinations.py \
     kit-tests/10_harness_suite/_shared/find_hallucinations.py   # → one line: `from typing import Optional`
```

Original `ai-factory/tests/` is never modified by this kit build; the "lint-cleaned" 299-line
version is the *current* live file state, not a kit rewrite of it.
