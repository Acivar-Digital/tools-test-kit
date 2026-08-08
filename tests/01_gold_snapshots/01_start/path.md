# Path Definition — /start Welcome and Session Initialization

This path documents the E2E path for welcoming the user when starting a new session with the Chronomancer Bot.

## 🗺️ E2E Test Path (2 Steps)

1. **User sends `/start`**: Bot resets session and greets user with the welcome greeting, outlining prerequisites, partner platform info, and presenting two options:
   * `/auto` — calculate pillars automatically from birth details.
   * `/input` — manually input pillars and elements.
2. **User selects a branch**:
   * **Branch A (User sends `/auto`)**: Bot initiates automated calculation and begins collecting birth details (alias, gender, date/time, location) via the LLM Conductor.
   * **Branch B (User sends `/input`)**: Bot initiates manual input and sends the copy-paste Bazi parameter template (`HELP_TEMPLATE`).
