# Path Definition — /input Manual Pillar Entry

This path validates the complete manual intake flow, asserting early lock protection, promotion code redemption, structured pillar parsing, and sequential tailoring.

## 🗺️ E2E Test Path (10 Steps)

1. **User sends `/start`**: Bot resets session and greets user with `/auto` and `/input` options.
2. **User sends `/input`**: Bot checks whitelisting status, finds user is locked, and prompts:
   `🔑 *Report Locked.* Please enter your promo code to generate your monthly forecast report.`
3. **User sends `frenfren`**: Bot verifies promo code, whitelists the user, and sends:
   `✅ *Promo code accepted!* You can now generate your monthly forecast report.`
4. **User sends `/input`**: Bot prompts the user with the formatted copy-paste manual parameter template.
5. **User sends invalid template (Polarity violation `Ding Zi` for Year)**: Bot detects Yin-Yang mismatch and rejects:
   `⚠️ *Validation failed for manual entry:* ... impossible pillar`
6. **User sends invalid template (Polarity violation `Jia Chou` for Month)**: Bot detects Yang-Yin mismatch and rejects:
   `⚠️ *Validation failed for manual entry:* ... impossible pillar`
7. **User sends invalid template (Overlap `Water` in both Favorable and Unfavorable)**: Bot rejects overlapping lists:
   `⚠️ *Validation failed for manual entry:* ... cannot be both favorable and unfavorable`
8. **User sends invalid template (Invalid Element name `Air`)**: Bot rejects non-metaphysical element names:
   `⚠️ *Validation failed for manual entry:* ... Missing element`
9. **User sends correct template with minor spelling typos (e.g. `Dingg Sii`, `Metall, Watr`)**: Bot fuzzy-corrects all typos, stores pillars, and outputs the verification block:
   `📋 *Here is what I understood:* ... (Year, Month, Day, Hour, Da Yun, Strength, Favorable, Unfavorable, Neutral)`
10. **User sends `Yes`**: Bot accepts verification and offers tailoring:
    `✨ *Before I generate your 2026 report...* Would you like a customised report?`
