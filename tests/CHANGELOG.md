# Changelog

All notable changes to the `kit-tests/` test kit are documented here.
This project deliberately follows [Keep a Changelog](https://keepachangelog.com/)
semantics.

The format is based on [Semantic Versioning](https://semver.org/):

## [Unreleased]

### Added
- `examples/06_kit_mem0_model.py` — cloner-runnable stub proving `KIT_MEM0_MODEL` is
  observable and remains granular vs `KIT_MODEL`. No network; collected by pytest.
- `examples/test_kit_live_smoke.py` — `KIT_LIVE` config gate + fail-fast/journey smoke
  test (`KIT_LIVE=false` skips; `KIT_LIVE=true` all-vars PASSES; missing var raises
  `RuntimeError` naming the variable).
- Root `conftest.py` — single source of truth owning the canonical `KIT_*` → legacy-env
  bridge (`KIT_MODEL`→`CHRONO_MODEL`, `KIT_MEM0_MODEL`→`MEM0_MODEL`) and the
  `collect_ignore` list for the 10 baziforecaster-only `0N_*` slices.
- `.env.example` — canonical env-var contract (`KIT_LIVE`, `KIT_PATH`, `KIT_BASE_URL`,
  `KIT_API_KEY`, `KIT_MODEL`, `KIT_MEM0_MODEL`).
- `.gitkeep` — ensures the `kit-tests/` directory survives fresh checkout/extraction.
- `CHANGELOG.md` — this file.

### Changed
- `config.py` `SystemSettings` — fail-loud shim over `KIT_*`; stdlib `os` only;
  defaults are laptop mocks so `import config` and `pytest examples` pass with no
  `.env`. When `KIT_LIVE=true`, missing any of `{KIT_PATH, KIT_BASE_URL, KIT_MODEL,
  KIT_API_KEY}` → `RuntimeError`.
- README.md / QUICKSTART.md — corrected run-surface honesty: `testpaths=["examples"]`
  lives in `pyproject.toml` (not `infra/pytest.ini`); the 10 baziforecaster-only dirs
  are documented as auto-ignored; async-only `infra/pytest.ini` clarified (asyncio_mode
  + markers only; not the cloner entry point).

### Fixed
- `infra/pytest.ini` explosion under `pytest -c infra/pytest.ini` — stripped
  `testpaths`/`addopts`/`python_files` that detonated (relative path resolution +
  import-time `sys.exit` in ignored slices). Now async+markers-only; cloner entry
  remains `uv run pytest` (pyproject `testpaths=examples` + root `conftest.py`
  `collect_ignore`).

### Security / Privacy (scrub pass)
- **Deleted 13 Tier-1 files** containing real PII + secret-sauce prose:
  - `reports/francis_yap_monthly_master.json` (194 KB)
  - `reports/francis_monthly_run.json` (353 KB)
  - `reports/francis_yap_report.md`, `reports/francis_yap_monthly_report.md`
  - `reports/verification/profile_francis.md`
  - `reports/intake_flow_report_gemma31b.md`
  - `reports/chronomancer_report.md`
  - `01_gold_snapshots/03_input/agent_run/final_report.json` (170 KB)
  - `01_gold_snapshots/02_auto/agent_run/final_report.json` (176 KB)
  - `01_gold_snapshots/02_auto/agent_run/final_report_month_{01..12}.yaml` (12 files)
  - `01_gold_snapshots/05_Chronomancer/agent_run/final_report.json`
- **Anonymized 44 Tier-2 files**: `Francis Yap`→`Test Profile`, `FYCL`→`TEST`,
  `187049734`→`999000001`, `1977-05-05`→`1990-01-01`, bare `Francis`→`Tester`.
- **Sanitized 9 credential literals** to obviously-fake placeholders
  (`00000000000000000000000000000000`, `sk-REPLACE_ME_WITH_REAL_KEY`,
  `1234567890:AAYourBotTokenHere`, `YOUR-API-KEY-HERE`) across
  `01_gold_snapshots/`.

### Removed
- Stale cache artifacts (`__pycache__/`, `.pytest_cache/`, `.hypothesis/`, `*.pyc`,
  `*.egg-info`) ensured absent from committed state via `.gitignore`.

### Notes
- **Not all tests pass** at this cut: the baziforecaster-only slices
  (`01_gold_snapshots/`, `02_unit_bedrock/`, `04_bug_repros/`, `05_integration_e2e/`,
  `10_harness_suite/`, `math_chapters/`) require the baziforecaster `src2.*` source
  tree + `sqlalchemy` and are **out of scope for the cloner download**. They are
  excluded from default collection by root `conftest.py` `collect_ignore`.
- Validated cloner surface remains green: `uv run pytest examples -q` (14/14) with
  `KIT_LIVE=false`; full journey (`KIT_LIVE=true` + all `KIT_*` vars) PASS; fail-fast
  names the missing variable.

## [0.1.0] — 2026-08-08
Initial extraction of the `kit-tests/` community test kit from the baziforecaster
monorepo, configurable via canonical `KIT_*` env vars (single `.env`, offline-safe).
