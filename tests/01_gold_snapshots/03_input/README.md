# 03_input — `/input` Manual Pillar Entry Flow

Tests `/input` manual pillar entry flow.

## Prerequisites
- None (standalone)

## Verification
- Response requests details in specific format
- Conductor-driven flow
- **Skipped in GOLD** — use `/auto` for report generation testing

---

## 🗺️ E2E Test Path (10 Steps)

The script (`03_input.py`) runs the following sequential steps against the mock Telegram server, testing negative validations before proceeding with correct details:

| Step | User Input | Expected Bot Response / Action |
| :--- | :--- | :--- |
| **1** | `/start` | Welcome greeting showing `/auto` and `/input` options. |
| **2** | `/input` | 🔑 **Report Locked.** Asks for a promo code to proceed. |
| **3** | `frenfren` | ✅ **Promo code accepted!** Confirms whitelisting. |
| **4** | `/input` | Formatted manual template request listing alias, gender, and the 9 Bazi fields. |
| **5** | *(Template: Ding Zi)* | ⚠️ **Validation failed:** Rejects Yin-Yang polarity mismatch in Year pillar. |
| **6** | *(Template: Jia Chou)* | ⚠️ **Validation failed:** Rejects Yang-Yin polarity mismatch in Month pillar. |
| **7** | *(Template: Water Overlap)* | ⚠️ **Validation failed:** Rejects element overlap between Favorable/Unfavorable. |
| **8** | *(Template: Element Air)* | ⚠️ **Validation failed:** Rejects invalid element name 'Air'. |
| **9** | *(Template: Correct)* | 📋 **Here is what I understood:** Lists the Bazi parameters and asks for verification. |
| **10** | `Yes` | ✨ Offer for a highly customized report (questions about Career, Relationships, Wealth). |
## 💬 Conversational Path

```markdown
User: /start
Bot:  "🔮 Welcome to BaziForecast Bot..."

User: /input
Bot:  "🔑 *Report Locked.* Please enter your promo code to generate your monthly forecast report."

User: frenfren
Bot:  "✅ *Promo code accepted!* You can now generate your monthly forecast report."

User: /input
Bot:  "Please share your details in this format:
       Name: Test Profile
       🏷️ Alias: TEST
       👤 Gender: Male
       1️⃣ Year: Ding Si
       ..."

User: Name: Test Profile
      🏷️ Alias: TEST
      👤 Gender: Male
      1️⃣ Year: Ding Si
      2️⃣ Month: Yi Si
      3️⃣ Day: Geng Chen
      4️⃣ Hour: Ding Chou
      5️⃣ Da Yun: Geng Zi
      6️⃣ Strength: Weak
      7️⃣ Favorable: Metal, Water
      8️⃣ Unfavorable: Fire
      9️⃣ Neutral: Earth, Wood

Bot:  "📋 *Here is what I understood:*
       🎂 Age: 49 yrs 2 mths
       🏷️ Name/Alias: TEST
       👤 Gender: Male
       1️⃣ Year: Ding Si
       2️⃣ Month: Yi Si
       3️⃣ Day: Geng Chen
       4️⃣ Hour: Ding Chou
       5️⃣ Da Yun: Geng Zi
       6️⃣ Strength: Weak
       7️⃣ Favorable: Metal, Water
       8️⃣ Unfavorable: Fire
       9️⃣ Neutral: Earth, Wood

       ⚠️ *Please verify this is correct.*
       Reply Yes to proceed, or tell me what to fix."

User: Yes
Bot:  "✨ *Before I generate your 2026 report...* Would you like a customised report?"
```
