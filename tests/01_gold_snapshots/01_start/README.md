# GOLD E2E Test — 01_start

## Domain Model (4 files)

| File | Role |
|------|------|
| `path.md` | **Design** — the expected `/start` flow (welcome + offer `/auto` / `/input`). |
| `01_start.py` | **Implementation** — makes the path happen; data-driven from `snapshot.json`. |
| `UI.md` | **Live capture** — the actual script↔engine interaction, written every run for troubleshooting. |
| `snapshot.json` | **Data contract** — drives the python's inputs and captures the engine's answers. |

## What This Test Does

Simulates a Telegram user sending `/start` to the BaziForecaster bot over the
isolated `test_telegram01` test channel and verifies the bot returns the welcome
greeting with mode-selection prompt. It covers two scenarios:

1. **Existing / paying customer** (`999001001`, seeded `PAID` by `00_infra/[baziforecaster-only: seed_test_users.py not in kit download]`).
2. **New / free customer** (`999001002`, auto-created `FREE` on first contact).

## How To Run

```bash
# 1. Start the infra in a tmux session we can watch together (separate terminal)
cd kit-tests
# baziforecaster-only: TEST/GOLD/00_infra/start.sh not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.
#    -> tmux session "bazi-infra", window "services", runs start2.py on :8445

# 2. Seed the test user (PAID) — run once per fresh DB
# baziforecaster-only: TEST/GOLD/00_infra/seed_test_users.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.

# 3. Run the test against the LIVE tmux server (no embedded server start)
# [baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.]
uv run python -c "import sys; sys.path.insert(0,'.'); \
import TEST.GOLD.run as R; \
R.SERVER_URL='http://127.0.0.1:8445'; R.HEALTH_ENDPOINT=R.SERVER_URL+'/health'; \
import json; print(json.dumps(R.run_test_folder('01_start'), indent=2, default=str))"
```

Or manually with curl (note the test channel header):

```bash
curl -s -X POST http://127.0.0.1:8445/webhook/test \
  -H "Content-Type: application/json" \
  -H "X-Telegram-Bot-Api-Secret-Token: 00000000000000000000000000000000" \
  -H "X-Test-Channel: test_telegram01" \
  -d '{"update_id": 9001, "message": {"message_id": 1, "from": {"id": 999001001, "is_bot": false, "first_name": "GoldTest"}, "chat": {"id": 999001001, "type": "private"}, "date": 1717545600, "text": "/start"}}'
```

## Test Flow

```
Test                          Bot (test_telegram01)
 │                             │
 ├─ POST /webhook/test ──────→ │
 │   (+ X-Test-Channel hdr)    ├─ Validate webhook secret
 │                             ├─ Deduplicate update_id
 │                             ├─ Offload to background task
 │←── {"status": "ok"} ────────┤
 │                             ├─ process_webhook_logic()
 │                             ├─ check_user_access() → auto-whitelist
 │                             ├─ handle_intake("/start")
 │                             │   ├─ step=START → CHOOSING
 │                             │   └─ return GREETING message
 │                             ├─ send to chat_logs (test channel)
 │←── captured via get_last ───┤  (reply read from chat_logs, NOT a live Telegram send)
 │                             └─ Done (no crash)
```

## Expected Results

| Check | Expected | Status |
|-------|----------|--------|
| Server starts | Port 8445 listening (tmux `bazi-infra`) | — |
| `/health` | `200` | — |
| Webhook response | HTTP 200, `{"status":"ok"}` | — |
| Scenario 1 reply | contains "Welcome to BaziForcast" + `/auto`/`/input` | — |
| Scenario 2 reply | contains "Welcome to BaziForcast" + `/auto`/`/input` | — |
| Captured JSON cleared | `snapshot.json` `actual_response`/`last_updated` reset at session start | — |
| No crashes | No Traceback in logs | — |

## Artifacts

| File | What It Is |
|------|-----------|
| `snapshot.json` | Data contract: inputs + expected assertions, and the captured `actual_response` per step after a run. |
| `UI.md` | Live dump of the captured bot replies for both scenarios (troubleshooting view). |
| `results.json` | `run.py` summary written at the repo level when run via `run.py`. |

## Notes

- The webhook returns `{"status":"ok"}` immediately because bot logic runs in a background task.
- Replies are captured from `chat_logs` via `get_last_bot_reply(chat_id, "test_telegram01")` — there is **no** live Telegram API send and therefore no 400 on the fake chat_id (unlike the legacy `/webhook` flow).
- The test user `999001001` is seeded `PAID`; `999001002` is created `FREE` on first contact.
- `01_start.py` clears captured values in `snapshot.json` at the start of every session.
