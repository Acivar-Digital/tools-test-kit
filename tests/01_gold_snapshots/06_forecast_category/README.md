# Forecast Category Tests (T07-T12)

Tests all Chronomancer forecast category subcommands.

## Commands
| File | Command | Handler |
|------|---------|---------|
| `snapshot_best.json` | `/best` | `handle_forecast_category(chat_id, 'best')` |
| `snapshot_career.json` | `/career` | `handle_forecast_category(chat_id, 'career')` |
| `snapshot_love.json` | `/love` | `handle_forecast_category(chat_id, 'love')` |
| `snapshot_wealth.json` | `/wealth` | `handle_forecast_category(chat_id, 'wealth')` |
| `snapshot_travel.json` | `/travel` | `handle_forecast_category(chat_id, 'travel')` |
| `snapshot_30.json` | `/30` | `handle_forecast(chat_id, 30)` |

## Prerequisites
- Report must exist (generate via `/auto` first)
- User must be admin or have feature code (`can_use_chronomancer`)
- Master JSON must be on disk

## Verification
- "Chronomancer is thinking" thinking message sent first
- Category-specific response with Top 3 / Worst 3 days
- Session step set to `CHRONOMANCER` after response
- No traceback in logs
