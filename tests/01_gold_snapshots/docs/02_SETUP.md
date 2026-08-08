# Gold E2E — True Concurrency Setup (Production = Test Channel)

> Status: **INFRASTRUCTURE SETUP PLAN ONLY.** No code changed yet.

---

## 1. The Mental Model

**ONE** server instance: `uv run start2.py` on port **8445** (production).
Real `.env`, real bot token, real models from `controls.py`, real Telegram webhook.

Two independent traffic sources hit this one server **concurrently**:

| Source | Route | Channel name | Platform ID (`PlatformAccount.platform`) | DB isolation key |
|---|---|---|---|---|
| **You (Tester)** — Telegram app | `POST /webhook` | `telegram` | `telegram` | `(telegram, 999000001)` |
| **Gold Test Runner** — channel 01 | `POST /webhook/test` (+ header `X-Test-Channel: test_telegram01`) | **`test_telegram01`** | **`test_telegram01`** | `(test_telegram01, 999001001)` |
| Future channels 02..50 | `POST /webhook/test` (+ header `X-Test-Channel: test_telegramNN`) | `test_telegramNN` | `test_telegramNN` | `(test_telegramNN, ...)` |

- **Channel name = `test_telegram01`** (and `test_telegram02` … `test_telegram50` as needed).
- **Platform ID = channel name** — the exact `test_telegramNN` string is written into
  `PlatformAccount.platform` and used as the isolation key. It is a *registered* platform
  just like `telegram` or `whatsapp`.
- **One route serves ALL test channels:** `POST /webhook/test`. The specific channel is
  carried in the request header `X-Test-Channel: test_telegram01`. `app.py` reads that
  header → `platform = channel_name` → passes it down. This means 10 or 50 channels
  "whack the system" through a single endpoint with zero new routes.
- Telegram only allows one webhook per bot token, so your chat stays on `/webhook`
  (8445). The test runner never registers a Telegram webhook — it POSTs simulated
  updates directly to the local `/webhook/test` endpoint. No collision.

Both processed concurrently by FastAPI's async loop. Each source has its own
`PlatformAccount` + `Session` + `User` row → zero cross-contamination.

---

## 2. Test Channel = Registered Platform (how "registration" works)

When the test runner POSTs `/webhook/test` with `chat_id=999001001`, the server resolves
identity via `db._get_or_create_uuid(chat_id, platform="test_telegram01")`:

- **First time (NEW user):** no `PlatformAccount(platform="test_telegram01", platform_user_id="999001001")`
  exists → a `User` (default `tier="FREE"`) is created and linked.
  → returns `is_new = True`.
- **Subsequent time (OLD/returning user):** the `PlatformAccount` already exists → the
  existing `User` is returned.
  → returns `is_new = False`.

This IS the registration. The test channel is a first-class platform in `platform_accounts`.

### Pre-seeded existing user (so the test covers BOTH old and new customers)
Before the `01_start` test runs, **one existing customer must already live inside the
`test_telegram01` platform**. This is done by a seed step (idempotent) that inserts:
- `User(tier="PAID")` (a *paying* returning customer) — covers "old + paying".
- `PlatformAccount(platform="test_telegram01", platform_user_id="999001001")`.
- Optionally a completed `Session` so the returning-user branch is exercised.

The `01_start` test then exercises two paths:
- **Existing customer** → chat_id `999001001` → `is_new=False`, `tier=PAID`.
- **New customer** → a different chat_id (e.g. `999001002`) → `is_new=True`, `tier=FREE`.
This proves the intake model can distinguish old/new AND paying/free on the same channel.

### Old/New + Paying/Free visibility for the intake model
The intake flow (`handle_intake`) must be able to read:
- **Old vs New** → `is_new` returned by `_get_or_create_uuid` (or: does the
  `PlatformAccount` already exist).
- **Paying vs Free** → `User.tier` (`"FREE"` = free; `"PAID"` / `"PRO"` = paying).

Today `handle_intake` only touches `Session`, not `User`. The setup enables this by
threading `is_new` + `User.tier` into the intake so it can branch the welcome / flow.
(New users get the standard `/start` welcome; returning/paying users can be greeted
differently — that branching is future logic, but the **data is now available**.)

---

## 3. How a Test Request Flows

```
[baziforecaster-only: TEST/GOLD/01_start/01_start.py not in kit download]
  └─ POST http://127.0.0.1:8445/webhook/test
        headers:
          X-Telegram-Bot-Api-Secret-Token: <same secret>
          X-Test-Channel: test_telegram01
        body: {update_id, message:{chat:{id:999001001}, text:"/start"}}
                    │
                    ▼
@app.post("/webhook/test")                       [NEW in app.py]
  - same secret-token check + update_id dedupe as /webhook
  - channel = request.headers.get("X-Test-Channel", "test_telegram01")
  - background_tasks.add_task(process_webhook_logic, data, platform=channel)
                    │
                    ▼
process_webhook_logic(data, platform="test_telegram01")
  - check_and_acquire_channel_lock(chat_id, platform)        # Valkey per-(user,channel) lock
  - _process_webhook_logic_inner(data, platform)
        └─ handle_intake(chat_id, text, platform="test_telegram01")
              ├─ get_session(chat_id, platform)   → resolves UUID via PlatformAccount(test_telegram01, 999001001)
              │                                     also returns is_new + loads User.tier
              ├─ run_conductor(...)               # REAL models from controls.py
              └─ save_session(session, platform)
                    │
                    ▼
        reply = send_telegram_message(chat_id, text)
          - chat_id starts "999" + api.telegram.org → MOCKED (logged, no real Telegram call)
          - real chat_id in a test                → sent to REAL api.telegram.org (you'd see it)
        db.log_chat(chat_id, "public", "bot", reply)   # ChatLog write (capture point)
```

---

## 4. Reply Capture — REPLACES fake Telegram polling

`[baziforecaster-only: TEST/GOLD/01_start/01_start.py not in kit download]` currently polls `http://127.0.0.1:9999/intercepted`
(a fake Telegram server). Under the real-Telegram test channel, `999` chat_ids are
**mocked** in `send_telegram_message` (reply is logged, never delivered to any intercept
server). So the test must capture the reply from the **database** instead:

- Add a helper in the test runner: `get_last_bot_reply(chat_id, platform)` that queries
  `chat_logs WHERE user_id = <uuid from PlatformAccount(test_telegram01, chat_id)>
  AND role = 'bot' ORDER BY created_at DESC LIMIT 1`.
- `db.log_chat(...)` already writes every bot reply to `chat_logs`, so the text is
  available immediately after processing.

This removes the dependency on `FAKE_TELEGRAM_URL` / `fake_telegram.py` for the test
channel entirely.

---

## 5. Exact Code Changes Required (setup only)

### A. `src2/interfaces/telegram/app.py`
1. New route mirroring `telegram_webhook`:
   ```python
   @app.post("/webhook/test")
   async def test_webhook(request, background_tasks):
       # same secret check + update_id dedupe
       background_tasks.add_task(process_webhook_logic, data, platform="test_telegram01")
       return {"status": "ok"}
   ```
2. `process_webhook_logic(data, platform="telegram")` → pass `platform` to
   `check_and_acquire_channel_lock(chat_id, platform)` and `_process_webhook_logic_inner`.
3. `_process_webhook_logic_inner(data, platform="telegram")` → pass `platform` to both
   `handle_intake(chat_id, text_val, platform=platform)` call sites.

### B. `src2/interfaces/telegram/db.py`
Add `platform="telegram"` (default, zero regression) to:
- `_get_or_create_uuid(self, chat_id, platform="telegram")` → use in the
  `filter_by(platform=platform, ...)` lookup and `PlatformAccount(platform=platform, ...)` create.
  **Also return `(uuid_val, is_new)`** so intake knows old vs new.
- `get_session(self, user_id, platform="telegram")`
- `update_session(self, user_id, ..., platform="telegram")`
- `get_semantic_id` / `ensure_semantic_id`
- (other ~40 internal callers keep default `"telegram"` → unchanged)

### C. `src2/interfaces/telegram/session.py`
- `get_session(chat_id, platform="telegram")` → `db.get_session(chat_id, platform)`
- `save_session(session, platform="telegram")` → `db.update_session(..., platform)`
- `delete_session(chat_id, platform="telegram")`
- Surface `is_new` + `User.tier` on the returned `Session` (new optional fields) so intake
  can read them.

### D. `src2/interfaces/telegram/intake/intake.py`
- `handle_intake(chat_id, text, platform="telegram")` → thread `platform` into
  `get_session` / `save_session`; read `is_new` + `User.tier` for branching.

### E. `[baziforecaster-only: TEST/GOLD/01_start/01_start.py not in kit download]` (the test)
1. `SERVER_URL` → `http://127.0.0.1:8445`.
2. `send_webhook(...)` → POST to `f"{SERVER_URL}/webhook/test"` (same secret header).
3. Replace `FAKE_TELEGRAM_URL` polling with `get_last_bot_reply(chat_id, "test_telegram01")`
   (reads `chat_logs` for that user).
4. `chat_id` default → `999001001` (a registered `test_telegram01` account).
5. Add assertions:
   - PlatformAccount exists with `platform="test_telegram01"`, `platform_user_id="999001001"`.
   - `User.tier == "FREE"` (free by default).
   - First run → `is_new == True`; second `/start` (or re-run) → `is_new == False` (old).
   - Welcome message contains expected text.

### F. `[baziforecaster-only: TEST/GOLD/run.py not in kit download]`
1. `send_webhook` → POST to `/webhook/test`.
2. `get_session_step(chat_id)` → query `platform="test_telegram01"` (not `"telegram"`).

### G. `[baziforecaster-only: TEST/GOLD/00_infra/start.sh not in kit download]`
Launch **one** production server only:
```
tmux new-session -d -s bazi-infra "uv run start2.py --skip-preflight"
```
(`test_start.py` / `test_control.py` retained on disk but no longer launched.)

---

## 6. What We Do NOT Change
- `admin/controls/controls.py` — sacrosanct; real models used as-is.
- `.env` — `TELEGRAM_API_BASE=https://api.telegram.org`, real token, real webhook URL.
- The production `/webhook` route and your live Telegram bot behavior.
- `send_telegram_message` — already mocks sends for `999` chat_ids on `api.telegram.org`.

---

## 7. Verification (when you say GO)
1. Start: `uv run start2.py` (or `./[baziforecaster-only: TEST/GOLD/00_infra/start.sh not in kit download]`).
2. You message the bot on Telegram → replies arrive in your Telegram app (real).
3. Terminal: `# baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'. --no-start-server --server-url http://127.0.0.1:8445`
   → drives `/webhook/test` concurrently.
4. `01_start` verifies: registered `test_telegram01` account, `tier=FREE`, old/new flag,
   welcome text captured from `chat_logs`.
5. Both run at once; your `telegram` session untouched; `logs/bot.log` shows interleaved
   processing for two platforms.
