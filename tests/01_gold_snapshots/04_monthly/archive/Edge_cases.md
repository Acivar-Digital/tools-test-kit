# Bazi Special Structures (Vibrant / Follower) Edge Cases Verification

## 1. The Bug & Fix Context
Previously, the core Bazi engine's element classifier in [shen_classifier.py](file:///home/yapilwsl/arthityap/baziforecaster/src2/engine/shen_classifier.py) grouped special structures with normal structures: (baziforeporter-only: not in standalone kit download)
*   **Vibrant (从强)** was grouped with normal **Strong** structures, incorrectly assigning draining/controlling elements (`Output`, `Wealth`, `Officer`) as its medicine.
*   **Follower (从弱)** was grouped with normal **Weak** structures, incorrectly assigning supporting elements (`Friend`, `Resource`) as its medicine.

This was fixed by introducing explicit edge-case routing in the engine's `derive_engine_logic()` function.

---

## 2. Test Edge Cases to Create

To verify that the bug is really fixed, we need to test the engine and bot using two specific edge case charts:

### Case A: Vibrant Wood Structure (曲直格 - Bending-Straight)
*   **Day Master**: Yi Wood (乙木) or Jia Wood (甲木)
*   **Natal Pillars Example**:
    *   **Year**: `Gui Hai` (癸亥) — Water / Water
    *   **Month**: `Jia Yin` (甲寅) — Wood / Wood
    *   **Day**: `Yi Mao` (乙卯) — Wood / Wood
    *   **Hour**: `Ren Zuo` (壬子) — Water / Water
*   **Bazi Characteristics**: Extreme Wood and Water presence with zero Metal (Control) or heavy Fire (Output) to break the flow.
*   **Expected Classification**: **Vibrant** (从强)
*   **Expected Medicines (Yong Shen / Xi Shen)**: **Wood** (Friend) and **Water** (Resource)
*   **Expected Taboos (Ji Shen / Chou Shen)**: **Metal** (Officer) and **Earth** (Wealth)

### Case B: Follow Wealth / Follow Officer Structure (从财格 / 从杀格)
*   **Day Master**: Xin Metal (辛金)
*   **Natal Pillars Example**:
    *   **Year**: `Bing Wu` (丙午) — Fire / Fire (Officer)
    *   **Month**: `Bing Wu` (丙午) — Fire / Fire (Officer)
    *   **Day**: `Xin Si` (辛巳) — Metal / Fire (Officer)
    *   **Hour**: `Bing Wu` (丙午) — Fire / Fire (Officer)
*   **Bazi Characteristics**: Extremely weak Day Master with no roots (no Shen, You, or Earthly support) surrounded entirely by Fire (Officer).
*   **Expected Classification**: **Follower** (从弱)
*   **Expected Medicines (Yong Shen / Xi Shen)**: **Fire** (Officer), **Earth/Wood** (Wealth/Output)
*   **Expected Taboos (Ji Shen / Chou Shen)**: **Metal** (Friend) and **Water** (Resource) — because they would try to root/support the Day Master, breaking the follower pattern.

---

## 3. Verification Steps

1.  **Engine-Level Unit Test**:
    Create a temporary test script in `scratch/test_special_structures.py` to run these two profiles through the engine's `classify_shen` and verify the output.
2.  **Bot-Level Integration Test**:
    Verify that the daily forecast and month readings generated for these profiles correctly reflect these medicines and taboos in the LLM-generated narrative (e.g. the Vibrant Wood profile should be told to seek Water/Wood and avoid Metal, and the Follower profile should be told the opposite).
