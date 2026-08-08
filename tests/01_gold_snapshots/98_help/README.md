# 98_help — `/help` Command

## Scenario

User sends `/help` at any point. Bot returns the `HELP_TEMPLATE` — a static message showing the manual input format with example data.

## Key Facts

- **Deterministic**: Always returns the exact same `HELP_TEMPLATE` string
- **No LLM involved**: Pure static response
- **No state change**: Session step remains unchanged
- **Telegram 400 expected**: Fake chat_id 999 will get 400 on sendMessage

## Verification Points

| # | Check | Expected |
|---|-------|----------|
| 1 | HTTP response | 200, `{"status":"ok"}` |
| 2 | Bot message contains | "Please share your details in this format" |
| 3 | Bot message contains | All 9 input fields (Name, Alias, Gender, Year, Month, Day, Hour, Da Yun, Strength, Favorable, Unfavorable, Neutral) |
| 4 | No Traceback in logs | ✅ |
| 5 | Telegram sendMessage | Fails with 400 (expected for fake chat_id) |

## Artifacts

- `snapshot.json` — Expected response + verification points
