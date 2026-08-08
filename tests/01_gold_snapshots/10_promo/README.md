# Promo Code Tests (T18-T19)

Tests promo code commands for unlocking features.

## Commands
| File | Env Var | Unlocks |
|------|---------|---------|
| `snapshot_monthly.json` | `PROMO_MONTHLY` | `can_generate_report` |
| `snapshot_feature.json` | `PROMO_FEATURE` | `can_use_chronomancer` |

## Prerequisites
- Environment variable must be set before server start
- User must send exact promo code text

## Handler
```
app.py (line 157-164)
  → clean_text == promo_monthly → db.set_monthly_code(chat_id, True)
  → clean_text == promo_feature → db.set_feature_code(chat_id, True)
```

## Verification
- "Promo code accepted" in response
- No traceback in logs
- **Skipped in GOLD runs** — requires env var to be set
