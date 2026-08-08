# 05_forecast — `/forecast` Command

## Scenario

User sends `/forecast`. Bot returns a static menu with category options for forecast subcommands.

## Menu Options

| Command | Description |
|---------|-------------|
| `/best` | Overall Best & Low Days |
| `/career` | Career & Interviews |
| `/love` | Relationships & Social Energy |
| `/wealth` | Wealth & Speculation |
| `/travel` | Travel & Movement |
| `/30` | Highlights for next 30 days |

## Verification Points

| # | Check | Expected |
|---|-------|----------|
| 1 | HTTP response | 200 |
| 2 | Bot message contains | "Forecast Menu" |
| 3 | All 6 subcommands listed | /best, /career, /love, /wealth, /travel, /30 |
| 4 | No Traceback | ✅ |
