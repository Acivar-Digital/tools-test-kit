# Quick Start

## What you can run with a download

A bare checkout of `tests/` with **no API keys and no `.env`** runs only the
cloner-safe stubs in `examples/` (7 pattern stubs `01_*`–`06_*` + this live-smoke
attestation, the 8th cloner-runnable file):

```bash
cd kit-tests
KIT_LIVE=false uv run pytest examples -q        # runs the 7 cloner-safe stubs — no .env needed
```

> `uv run pytest -q` runs the **same** thing: `pyproject.toml` pins `testpaths = ["examples"]`,
> so an unqualified `uv run pytest -q` collects `examples/` only (the 10 baziforecaster-only
> dirs are excluded — see callout below).

## What is NOT cloner-runnable (baziforecaster-only, ignored by default)

The `01_gold_snapshots` through `10_harness_suite` dirs are **NOT in the download's
run surface**. They hardcode `TEST`/`GOLD` or import `src2.*`, and are excluded by:

- `tests/conftest.py` — `collect_ignore` lists every `0N_*` dir (not collected).
- `pyproject.toml` — `[tool.pytest.ini_options]` sets `testpaths = ["examples"]` (only `examples/`).
- `tests/conftest.py` — `collect_ignore` lists every `0N_*` dir (defense-in-depth).

`math_chapters/` and `param_flows/` are also optional in-kit slices that import
`src2.*` and need baziforecaster's source tree (plus `sqlalchemy`) installed —
they are outside the download run surface and never collected by default.

```bash
uv run pytest math_chapters param_flows -q   # optional slices (need baziforecaster src2 + sqlalchemy)
```

## The KIT_LIVE=true journey (proven by a cloner-safe smoke test)

To run the live LLM slices, copy `.env.example` -> `.env`, then set the env vars
and point at a real kit server:

```bash
cp .env.example .env
KIT_LIVE=true KIT_PATH=/your/kit KIT_BASE_URL=https://... KIT_MODEL=gemma-2 KIT_MEM0_MODEL=gemma-2-vision KIT_API_KEY=sk-... \
  uv run pytest examples/test_kit_live_smoke.py -q
```

This journey is **attested** by `examples/test_kit_live_smoke.py` (the 8th
cloner-runnable file in `examples/`, numbered after the `01_*`–`06_*` pattern stubs
— it itself runs with `KIT_LIVE=false`): it imports the real `config.py` in a
subprocess and asserts the fail-fast behavior.

### Fail-fast behavior

`config.py` reads `KIT_LIVE` at **import time**. If `KIT_LIVE=true` and any required
var is unset, it raises immediately:

```
RuntimeError: KIT_LIVE=true but missing required env: KIT_PATH, KIT_BASE_URL, KIT_MODEL, KIT_API_KEY — set them in tests/.env.
```

So a misconfigured live run **fails loudly and by name** before any test executes.

### KIT_MODEL and KIT_MEM0_MODEL are independent (granular)

These two knobs control **separate** layers and are NOT collapsed into one value:

- `KIT_MODEL` (`-> CHRONO_MODEL`) — the chronomancer layer model.
- `KIT_MEM0_MODEL` (`-> MEM0_MODEL`) — the mem0-synthesis layer model.

They default to distinct mock names (`mock-chrono-model` / `mock-mem0-model`) so
granularity is observable. `examples/06_kit_mem0_model.py` exercises this contract.

---

That's it. `uv` resolves `pytest` + `hypothesis` from `pyproject.toml`; no virtualenv
or system packages required.

## Requirements
- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) (or any Python with `pytest`+`hypothesis`)

## Browse
- [`README.md`](README.md) — the story + layer table.
- [`STRUCTURE.md`](STRUCTURE.md) — exact layout + curation rules per layer.
- [`orchestrator.md`](orchestrator.md) — how this kit was built (reproducible).
