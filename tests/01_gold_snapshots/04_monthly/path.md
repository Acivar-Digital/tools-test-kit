# Path Definition: Monthly Forecast Report Generation

## Success Path
1. User selects `/auto` or `/input` to input Bazi details.
2. Bot validates the details and presents understanding.
3. Bot asks whether user wants customization (Career, Relationships, Wealth).
4. User replies `No` (or completes customization).
5. Bot initiates the annual report pipeline to generate 12 monthly forecast reports for 2026.
6. Upon successful completion, the bot:
   - Persists the master JSON to disk (`BaziForecast_2026_*_master.json`).
   - Updates the database metadata.
   - Sends a completion message to the user (`✨ Analysis Complete for Alias! ✨`).
   - Posts a success message to the Telegram progress channel (`@yapily_qimen`).

## Failure Path (Failing Loudly)
If any step in the report generation pipeline fails (e.g. LLM timeout, database connection error, or missing RAG cache):
1. **Pipeline Termination**: The async pipeline task is aborted immediately (fails fast).
2. **User Notification**: The bot sends a system error message to the user's chat:
   - `⚠️ *Temporary System Error*`
3. **Developer Telegram Alerts**:
   - **Personal Alert**: A message with the exact error details and the traceback is sent directly to the developer chat (`999000001`).
   - **Progress Channel Alert**: The failure status is posted to the progress channel (`@yapily_qimen`).
4. **Console & System Logging**:
   - The traceback is logged as `logger.error` in the system log (`logs/bot.log`) with the exact stack trace, ensuring it is highly auditable.
