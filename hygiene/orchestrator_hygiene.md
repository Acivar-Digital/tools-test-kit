# kit-hygiene portability refactor
> Download → configure `.env`/`control.py` per these instructions → run on **YOUR OWN repo**.
> Zero `admin.*` coupling, configurable scan target (no hardcoded `src2/`). (v3.2)

1. **Read the room:** Read `kit-hygiene/orchestrator_hygiene.md` + the gap inventory in `kit-hygiene/reports/chunks/README.md`. Confirm `target_repo root = ai-factory`, `src2/` is the scan target (data, not dependency).
2. **Understand the target:** Every `kit-hygiene/scanners/*.py`, `kit-hygiene/daily/*.py`, `kit-hygiene/control.py`, `kit-hygiene/run-registry-scan.sh`, `kit-hygiene/.env.example`. Current reality: 14 scanners hard-import the phantom `admin.code_hygiene.scanners.*` / `admin.controls.controls` (phantom — the real modules `utils.py`, `virtual_ast_buffer.py`, `control.py` already live inside kit-hygiene); runners point at `admin/code_hygiene/scanners/...`; `.env.example` omits `HYGIENE_FILES_TO_SCAN` and `SCAN_ROOTS`; no `requirements.txt`/`.python-version`; **`utils.get_src2_files` hardcodes `src2/` and ignores `SCAN_ROOTS`, so a user cannot point it at their own repo.**
3. **Assign & perform:** Assign 🎟️ Tickets 1–4 to 4 subagents (deployment plan §6). Execute their tasks; run Ticket 4's gate at the end.
   - **CRITICAL:** Do NOT alter verdict/scanner logic in `src2/` (target repo). Edits are import-path + runner-path + config only, **inside kit-hygiene/**. Fail-loud on any missing required `KIT_*` env at import → `RuntimeError` naming the var.
4. **Capture decisions:** `bd remember "Hardened kit-hygiene portability [clone+.env+run]. Asserted 0 admin/code_hygiene refs, every scanner imports, disabled run exit=0, ruff E9/F63/F7/F82 clean, factory/ tests/ gate clean."`
5. **Close the ticket:** Mark complete when the Ticket 4 gate prints green/end-to-end.

---

## 🚀 SUBAGENT DEPLOYMENT PLAN

| Subagent | Ticket | Role | Parallel? |
|---|---|---|---|
| SA-imports | 🎟️ Ticket 1 | rewrite `admin.*` → local `control`/`utils`/`virtual_ast_buffer` imports + CREATE `scanners/_bootstrap.py` | yes |
| SB-shim | 🎟️ Ticket 2 | ADD `CONTROL_SHEET` alias in `control.py`; fix `run_all.py` + `run-registry-scan.sh` paths | yes |
| SC-config | 🎟️ Ticket 3 | `.env.example` (add `HYGIENE_FILES_TO_SCAN`), CREATE `requirements.txt`, CREATE `.python-version=3.11` | yes |
| SD-verify | 🎟️ Ticket 4 | prove end-to-end (no edits — run the gate) | gates **after** the three above |

**Sequencing:** SA + SB + SC deploy **in one turn (parallel)**. SD gates **last**,
only after SA/SB/SC each report `OK`. If any of SA/SB/SC property-assert fails,
ESCALATE before gating — do NOT hand off to SD.

## 🎟️ TICKET DETAILS

### Ticket 1: Portable imports — kill phantom `admin.*`
**Target Files:** all `kit-hygiene/scanners/*.py` (esp. the 13 `admin.controls.controls` importers + `find_registry_clashes.py` utils bridge + `kill_tries[_apply|_old|_pydantic].py` virtual_ast_buffer bridge).
**Reference:** `kit-hygiene/scanners/_bootstrap.py` (CREATE), `kit-hygiene/control.py`, `kit-hygiene/scanners/utils.py:7 get_src2_files`, `kit-hygiene/scanners/virtual_ast_buffer.py`.
**Task Details:**
* A downloader cloning `ai-factory` gets `ModuleNotFoundError` on first scanner import because every scanner does `from admin.controls.controls import CONTROL_SHEET` (or the stale `admin.code_hygiene.scanners.*` bridges), but the real homes are local modules.
* **Strategy:**
  - CREATE `kit-hygiene/scanners/_bootstrap.py` that inserts the kit-hygiene root onto `sys.path` so `from control import CONTROL_SHEET` resolves.
  - In the **13** `CONTROL_SHEET` scanners, replace:
    `from admin.controls.controls import CONTROL_SHEET  # noqa: E402`
    with:
    `from _bootstrap import *  # noqa: F401,E402`
    `from control import CONTROL_SHEET  # noqa: E402`
  - In `find_registry_clashes.py`, replace `from admin.code_hygiene.scanners.utils import get_src2_files` → `from utils import get_src2_files`; ensure `from _bootstrap import *` present so `from control import …` resolves.
  - In `kill_tries.py`, `kill_tries_apply.py`, `kill_tries_old.py`, `kill_tries_pydantic.py`, replace `from admin.code_hygiene.scanners.virtual_ast_buffer import (...)` → `from virtual_ast_buffer import (...)` (preserve imported names); add `from _bootstrap import *`.
  - In `verify_dict_access_runtime.py`, keep `from src2.core.schemas.unified import …` (src2 = target data) but add `from _bootstrap import *`.
  - In `utils.get_src2_files`: honor `SCAN_ROOTS=` env (comma-separated dirs) as the file source; only fall back to `src2` when `SCAN_ROOTS` is unset (lets users scan their own repo).
* **Properties to Assert:**
  1. `grep -rnE "from admin|admin/code_hygiene|admin\.controls" kit-hygiene --include=*.py | grep -v get_src2_files` → **0 rows**.
  2. `grep -rn "ANTIGRAVITY_MANAGER" kit-hygiene --include=*.py` → **0 rows**.
  3. `for f in kit-hygiene/scanners/*.py; do uv run python "$f" --scripts; done` → every file imports, no `ModuleNotFoundError`.
  4. `SCAN_ROOTS=kit-hygiene uv run python kit-hygiene/scanners/find_circular_deps.py --scripts` (in `--scripts`, no LLM) returns files from `kit-hygiene` — proves the scan target is env-configurable, not hardcoded `src2`.

### Ticket 2: `control.py` shim + runner path repair
**Target Files:** `kit-hygiene/control.py`, `kit-hygiene/scanners/run_all.py`, `kit-hygiene/run-registry-scan.sh`.
**Reference Functions:** `ControlSheet.scanner_model`, `SystemSettings.base_url/api_key`.
**Task Details:**
* `control.py` exposes `ControlSheet`/`SystemSettings` but 13 scanners import the name **`CONTROL_SHEET`** (legacy). Runners hardcode `admin/code_hygiene/scanners/...` and tell users to read `admin/code_hygiene/reports/`.
* **Strategy:**
  - `control.py`: ADD `CONTROL_SHEET = ControlSheet` alias (fail-fast already enforces `KIT_*` when `KIT_ENABLE_REGISTRY_CLASHES=true`).
  - `run_all.py`: `base_dir = Path(__file__).resolve().parents[1]` (was `parents[3]` pointing at the target repo root); strip phantom `admin/code_hygiene/` prefix from the 11-entry scanner list → `scanners/find_<x>.py`; fix reports path → `kit-hygiene/reports/`.
  - `run-registry-scan.sh`: `SCANNER_SCRIPT="kit-hygiene/scanners/find_registry_clashes.py"`; source `./kit-hygiene/.env` (guarded by `[ -f ]`).
* **Properties to Assert:**
  1. `grep -nE "admin/code_hygiene|admin\.controls" kit-hygiene/scanners/run_all.py kit-hygiene/run-registry-scan.sh | wc -l` → **0**.
  2. `bash -n kit-hygiene/run-registry-scan.sh` → exits 0.

### Ticket 3: `.env.example` coverage + packaging manifest
**Target Files:** `kit-hygiene/.env.example`, `kit-hygiene/requirements.txt` (CREATE), `kit-hygiene/.python-version` (CREATE).
**Reference:** `kit-hygiene/scanners/utils.py:14 HYGIENE_FILES_TO_SCAN`, external imports list.
**Task Details:**
* `.env.example` is missing `HYGIENE_FILES_TO_SCAN`; `PATH_LEAK_ROOTS` is host-hard-coded `/home,/mnt,/Users`; no dependency manifest means `uv run` only works inside ai-factory root.
* **Strategy:**
  - `.env.example`: add `HYGIENE_FILES_TO_SCAN=` (comment: optional comma-list override for `get_src2_files`); append `# REVIEW per-host` to `PATH_LEAK_ROOTS`.
  - CREATE `kit-hygiene/requirements.txt`: `openai`, `instructor`, `pydantic`, `pydantic-ai`, `radon`, `tenacity`, `logfire`, `pyyaml`.
  - CREATE `kit-hygiene/.python-version` = `3.11`.
* **Properties to Assert:**
  1. `grep -n HYGIENE_FILES_TO_SCAN kit-hygiene/.env.example` → non-empty.
  2. `cat kit-hygiene/.python-version` → `3.11`.

### Ticket 4: Prove portability end-to-end (the real gate)
**Target Files:** none (verification only).
**Reference Functions:** `find_registry_clashes.main`, every scanner `--scripts` dry path.
**Task Details:**
* Earlier "green" was only the `E9,F63,F7,F82` ruff subset. A real download-and-run proof must show every scanner importing headless and the disabled path exiting 0.
* **Strategy:** Run the gate block verbatim.
* **Properties to Assert (all must hold):**
  1. Import smoke (CWD = ai-factory root): `for f in kit-hygiene/scanners/*.py; do uv run python "$f" --scripts; done` → **no `ModuleNotFoundError`**.
  2. Disabled run: `KIT_ENABLE_REGISTRY_CLASHES=false uv run python kit-hygiene/scanners/find_registry_clashes.py --scripts ; echo exit=$?` → prints `[INFO] registry clashes disabled`, **exit=0**.
  3. Invariant: `grep -rnE "from admin|admin/code_hygiene|admin\.controls" kit-hygiene --include=*.py --include=*.sh | wc -l` → **0**.
  4. `grep -rn "ANTIGRAVITY_MANAGER" kit-hygiene --include=*.py --include=*.env.example` → **0**.
  5. `grep -rIlE "(password|api_key|secret)\s*=\s*['\"][^'\"]+['\"]" kit-hygiene --include=*.py` → **0** files (no credential literals).
  6. `uv run ruff check kit-hygiene --select E9,F63,F7,F82 --no-cache` → **All checks passed!**
  7. `uv run ruff check factory/ tests/ 2>&1 | tail -1` → **All checks passed!** (repo gate untouched).
  8. **Own-repo support:** `SCAN_ROOTS=kit-hygiene KIT_ENABLE_REGISTRY_CLASHES=false uv run python kit-hygiene/scanners/find_registry_clashes.py --scripts` exits 0 with no clash output (target is env-driven).
* **CRITICAL:** If any property fails, `ESCALATE` with the failing line verbatim — do NOT patch blind. Ship only when 1–7 all hold.

---

## Out of scope THIS pass
Behavior changes to scanner verdict logic or `src2/` source. The `reports/chunks/` placeholders (schema samples). `src2/` is scan target data, not a vendored dependency.
