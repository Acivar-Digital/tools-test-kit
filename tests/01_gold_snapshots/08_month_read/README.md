# Month Reading Tests (T13-T15)

Tests month narrative reading commands `/1` through `/12`.

## Commands
| File | Month | Name | Range |
|------|-------|------|-------|
| `snapshot_01.json` | `/1` | Geng Yin | 04 Feb – 05 Mar |
| `snapshot_06.json` | `/6` | Jia Wu | 05 Jun – 07 Jul |
| `snapshot_12.json` | `/12` | Xin Chou | 05 Jan onwards |

## Prerequisites
- Report must exist in DB (`Reports` table)
- Master JSON path must be valid on disk

## Handler Chain
```
/1 → app.py (line 197)
  → db.get_all_reports_for_user(chat_id)
  → get_month_narrative(master_json_path, month_idx=0, chat_id)
    → reads month_01.json or generates via narrative_simplifier
```

## Verification
- Response contains month name and date range
- Read-only (session step unchanged)
- No traceback in logs
