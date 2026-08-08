# Subscribe Test (T22)

Tests `/subscribe` command for enabling scheduled daily reports.

## Prerequisites
- Report must exist
- Scheduler daemon must be running

## Verification
- Response contains subscribe/daily keywords
- **Skipped in GOLD** — requires scheduler daemon
