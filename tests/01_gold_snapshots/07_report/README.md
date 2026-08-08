# 07_report — `/report` Command

## Scenario

User sends `/report`. Bot reads the latest report's master JSON and displays a numbered menu of 2026 monthly forecasts. User can then type `/1` through `/12` to read specific months.

## Prerequisites

- Report must exist in DB (generated via `/auto` intake flow)
- Master JSON file must exist on disk at `_prd/users/{id}/reports/{index}/_master.json`

## Flow

1. Bot queries `db.get_all_reports_for_user(chat_id)`
2. If no reports → "📋 No reports found. Please run /start to generate your 2026 forecast."
3. If reports exist → reads master JSON → generates numbered menu
4. Each month shown as `/{n}. *Month Name*\n   _date range_`
5. User types `/1` to `/12` to read specific month

## Month Names (2026)

| Command | Month | Date Range |
|---------|-------|------------|
| `/1` | Geng Yin | 04 Feb – 05 Mar |
| `/2` | Xin Mao | 05 Mar – 05 Apr |
| `/3` | Ren Chen | 05 Apr – 05 May |
| `/4` | Gui Si | 05 May – 05 Jun |
| `/5` | Jia Wu | 05 Jun – 07 Jul |
| `/6` | Yi Wei | 07 Jul – 07 Aug |
| `/7` | Bing Shen | 07 Aug – 07 Sep |
| `/8` | Ding You | 07 Sep – 08 Oct |
| `/9` | Wu Xu | 08 Oct – 07 Nov |
| `/10` | Ji Hai | 07 Nov – 07 Dec |
| `/11` | Geng Zi | 07 Dec – 05 Jan |
| `/12` | Xin Chou | 05 Jan onwards |

## Verification Points

| # | Check | Expected |
|---|-------|----------|
| 1 | HTTP response | 200 |
| 2 | Bot message contains | "Your 2026 Monthly Forecasts" |
| 3 | All 12 months listed | /1 through /12 |
| 4 | Month names correct | Stems + Branches from Bazi engine |
| 5 | No Traceback | ✅ |

## Notes

- If no reports exist, returns "No reports found" instead of menu
- Bot response is NOT logged in ChatLogs (code quirk at app.py line 183-194)
- Telegram sendMessage will 400 for fake chat_id — expected
