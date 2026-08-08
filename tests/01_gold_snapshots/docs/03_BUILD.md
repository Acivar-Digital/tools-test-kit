# Gold E2E — Build / Refactor / Delete List

> Companion to `02_SETUP.md`. Implementation task list for the `test_telegram01`
> concurrency channel. **Nothing is deleted yet** — delete/retire items are flagged.

---

## A. BUILD (new files)

### 1. `[baziforecaster-only: TEST/GOLD/00_infra/seed_test_users.py not in kit download]`  **[NEW]**
Idempotent seeder that pre-loads the existing customer into the `test_telegram01` platform:
- Inserts `User(tier="PAID")` (paying returning customer).
- Links `PlatformAccount(platform="test_telegram01", platform_user_id="999001001")`.
- Optionally seeds a completed `Session` for that user.
- Safe to re-run (skips if the account already exists).
- Called by `run.py` (or `start.sh`) **before** the `01_start` test, or as a standalone
  `# baziforecaster-only: TEST/GOLD/00_infra/seed_test_users.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.`.

### 2. `get_last_bot_reply()` helper  **[NEW — lives in `[baziforecaster-only: TEST/GOLD/run.py not in kit download]` or a shared `[baziforecaster-only: TEST/GOLD/_helpers.py not in kit download]`]**
Queries `chat_logs` for the latest `role='bot'` message of a given
`(platform, platform_user_id)` user. Replaces fake-Telegram intercept polling.
Recommended: extract to `[baziforecaster-only: TEST/GOLD/_helpers.py not in kit download]` so `01_start.py` and `run.py` share it.

---

## B. REFACTOR (existing files to modify)

### 1. `src2/interfaces/telegram/app.py`
- Add `POST /webhook/test` route:
  - same secret-token check + `update_id` dedupe as `/webhook`;
  - read `channel = request.headers.get("X-Test-Channel", "test_telegram01")`;
  - `background_tasks.add_task(process_webhook_logic, data, platform=channel)`.
- `process_webhook_logic(data, platform: str = "telegram")` → pass `platform` into
  `check_and_acquire_channel_lock(chat_id, platform)` and `_process_webhook_logic_inner`.
- `_process_web_webhook_logic_inner(data, platform: str = "telegram")` → pass `platform`
  into both `handle_intake(chat_id, text_val, platform=platform)` call sites.

### 2. `src2/interfaces/telegram/db.py`
- `_get_or_create_uuid(self, chat_id, platform: str = "telegram")`:
  - use `platform` in the `filter_by(platform=platform, ...)` lookup and
    `PlatformAccount(platform=platform, ...)` create;
  - **return `(uuid_val, is_new)`** instead of just `uuid_val`.
- `get_session(self, user_id, platform: str = "telegram")`,
  `update_session(self, user_id, ..., platform: str = "telegram")`,
  `get_semantic_id` / `ensure_semantic_id` → add `platform` param (default `"telegram"`,
  zero regression for the ~40 other internal callers).

### 3. `src2/interfaces/telegram/session.py`
- `get_session(chat_id, platform="telegram")` → `db.get_session(chat_id, platform)`.
- `save_session(session, platform="telegram")` → `db.update_session(..., platform)`.
- `delete_session(chat_id, platform="telegram")`.
- Surface `is_new` + `User.tier` on the returned `Session` (new optional fields) so the
  intake model can read old/new + paying/free.

### 4. `src2/interfaces/telegram/intake/intake.py`
- `handle_intake(chat_id, text, platform: str = "telegram")` → thread `platform` into
  `get_session` / `save_session`; read `is_new` + `User.tier` for branching the welcome /
  flow (new vs returning, free vs paying).

### 5. `[baziforecaster-only: TEST/GOLD/01_start/01_start.py not in kit download]`
- `SERVER_URL` → `http://127.0.0.1:8445`.
- `send_webhook(...)` → POST to `f"{SERVER_URL}/webhook/test"` with header
  `X-Test-Channel: test_telegram01` (same secret header).
- Replace `FAKE_TELEGRAM_URL` polling with `get_last_bot_reply(chat_id, "test_telegram01")`.
- Tests BOTH customers:
  - **Existing/paying** → chat_id `999001001` (seeded) → assert `is_new=False`, `tier=PAID`.
  - **New/free** → chat_id `999001002` → assert `is_new=True`, `tier=FREE`.
- Assert `PlatformAccount` exists with `platform="test_telegram01"`,
  `platform_user_id=<chat_id>`; assert welcome text captured from `chat_logs`.

### 6. `[baziforecaster-only: TEST/GOLD/run.py not in kit download]`
- `send_webhook(...)` → POST to `/webhook/test` + `X-Test-Channel` header.
- `get_session_step(chat_id)` → query `platform="test_telegram01"` (not `"telegram"`).
- Call `[baziforecaster-only: seed_test_users.py not in kit download]` before running `01_start` (or document that `start.sh` does).

### 7. `[baziforecaster-only: TEST/GOLD/00_infra/start.sh not in kit download]`
- Launch **one** production server only:
  `tmux new-session -d -s bazi-infra "uv run start2.py --skip-preflight"`.
- Remove the UAT (`test_start.py`) pane.

---

## C. DELETE / RETIRE (do NOT delete yet — flag for later)

| File | Action | Why |
|---|---|---|
| `[baziforecaster-only: TEST/GOLD/00_infra/test_start.py not in kit download]` | **RETIRE** (keep on disk) | UAT mock server no longer launched; replaced by single production server. |
| `[baziforecaster-only: TEST/GOLD/00_infra/test_control.py not in kit download]` | **RETIRE** (keep on disk) | Model-swap mock no longer used; production `controls.py` is used as-is. |
| `[baziforecaster-only: TEST/GOLD/00_infra/fake_telegram.py not in kit download]` | **RETIRE** (keep on disk) | Reply capture moves to `chat_logs`; no fake Telegram intercept server needed. |
| `[baziforecaster-only: TEST/GOLD/00_infra/start.sh not in kit download]` UAT pane | **REMOVE from script** | Only the production pane remains. |

---

## D. Do NOT touch
- `admin/controls/controls.py` — sacrosanct; real models used as-is.
- `.env` — `TELEGRAM_API_BASE=https://api.telegram.org`, real token, real webhook URL.
- Production `/webhook` route and your live Telegram bot.
- `send_telegram_message` — already mocks `999` chat_ids on `api.telegram.org`.

---

## E. Build order (suggested)
1. `db.py` (`_get_or_create_uuid` → returns `is_new` + `platform` param).
2. `session.py` (thread `platform`; surface `is_new`/`tier`).
3. `intake/intake.py` (thread `platform`; read `is_new`/`tier`).
4. `app.py` (`/webhook/test` route + header → `platform`).
5. `[baziforecaster-only: seed_test_users.py not in kit download]` (new).
6. `run.py` + `_helpers.py` (`get_last_bot_reply`, `/webhook/test`, `platform` query).
7. `01_start/01_start.py` (both-customer test).
8. `start.sh` (single server).
