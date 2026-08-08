# Path Definition — /auto Automated Report Calculations

This documents the E2E paths for hitting the early lock check, unlocking with the promo code, and generating either a standard report (Path A) or a customised report (Path B) via the automated (`/auto`) flow.

---

## 🗺️ Path A: Early Lock & Declining Customisation (Standard Report)

1. **User sends `/auto`**: Bot checks whitelisting status, finds user is locked, and prompts:
   `🔑 *Report Locked.* Please enter your promo code to generate your monthly forecast report.`
2. **User sends `frenfren`**: Bot verifies promo code, whitelists the user, and sends:
   `✅ *Promo code accepted!* You can now generate your monthly forecast report.`
3. **User sends `/auto`**: Bot initiates automated calculation, asking for the user's name/alias, gender, birth date/time, and birth location.
4. **User sends name details (e.g., `Name: Test Profile, Alias: TEST, Gender: Male`)**: Bot records details and prompts for date of birth, time of birth, and birth location.
5. **User sends birth details (e.g., `DOB: 1977-04-28 11:51, Location: Singapore`)**: Bot runs the Bazi engine to calculate pillars/elements, outputs the reconstructed profile verification block, and prompts for confirmation:
   `⚠️ *Please verify this is correct.* Reply Yes to proceed, or tell me what to fix.`
6. **User sends `Yes`**: Bot accepts verification and prompts for report customisation:
   `Would you like a customised report?`
7. **User sends `No`**: Bot declines customisation, skips the tailoring questions, triggers the standard report generation pipeline, and outputs:
   `🧠 *Chronomancer* initialised...`

---

## 🗺️ Path B: Early Lock & Accepting Customisation (Personalised Report)

*Note: Database is reset before starting Path B to simulate a fresh user from the start.*

1. **User sends `/auto`**: Bot checks whitelisting status, finds user is locked, and prompts:
   `🔑 *Report Locked.* Please enter your promo code to generate your monthly forecast report.`
2. **User sends `frenfren`**: Bot verifies promo code, whitelists the user, and sends:
   `✅ *Promo code accepted!* You can now generate your monthly forecast report.`
3. **User sends `/auto`**: Bot initiates automated calculation, asking for the user's name/alias, gender, birth date/time, and birth location.
4. **User sends name details (e.g., `Name: Test Profile, Alias: TEST, Gender: Male`)**: Bot records details and prompts for date of birth, time of birth, and birth location.
5. **User sends birth details (e.g., `DOB: 1977-04-28 11:51, Location: Singapore`)**: Bot runs the Bazi engine to calculate pillars/elements, outputs the reconstructed profile verification block, and prompts for confirmation:
   `⚠️ *Please verify this is correct.* Reply Yes to proceed, or tell me what to fix.`
6. **User sends `Yes`**: Bot accepts verification and prompts for report customisation:
   `Would you like a customised report?`
7. **User sends `Yes`**: Bot accepts customisation and presents the first tailoring question (Career concerns).
8. **User sends Career choice (e.g., `1` for Career growth)**: Bot records answer and presents the second tailoring question (Relationship concerns).
9. **User sends Relationships choice (e.g., `1` for New Love)**: Bot records answer and presents the third tailoring question (Wealth concerns).
10. **User sends Wealth choice (e.g., `1` for High Growth)**: Bot records answer, triggers the customised report pipeline, and outputs:
    `🧠 *Chronomancer* initialised... (with your three concerns)`
