
def format_engine_profile_markdown(k3_profile: dict) -> str:
    """Convert the mapped engine profile JSON/dict into a clean markdown table."""
    lines = []
    lines.append("### 📊 Engine Profile Sent to Chronomancer\n")
    lines.append("| Parameter | Value |")
    lines.append("| :--- | :--- |")

    # 1. Profile ID
    lines.append(f"| **Profile ID** | `{k3_profile.get('profile_id', '?')}` |")

    # 2. Name & Gender
    gender_map = {"M": "Male", "F": "Female"}
    gender = gender_map.get(k3_profile.get("gender"), "?")
    lines.append(f"| **Name / Alias** | `{k3_profile.get('name', '?')}` ({gender}) |")

    # 3. Pillars
    pillars = (
        f"Year: `{k3_profile.get('year_pillar', '?')}`, "
        f"Month: `{k3_profile.get('month_pillar', '?')}`, "
        f"Day: `{k3_profile.get('day_pillar', '?')}`, "
        f"Hour: `{k3_profile.get('hour_pillar', '?')}`"
    )
    lines.append(f"| **Pillars** | {pillars} |")

    # 4. Da Yun
    lines.append(f"| **Da Yun** | `{k3_profile.get('da_yun_pillar', '?')}` |")

    # 5. DM Strength
    sp = k3_profile.get("strength_profile", {})
    score = sp.get("continuous_score", "?")
    lines.append(f"| **DM Strength** | `{k3_profile.get('dm_strength_type', '?')}` (continuous score: `{score}`) |")

    # 6. Elements
    med = ", ".join(k3_profile.get("medicine", []))
    taboo = ", ".join(k3_profile.get("taboo", []))
    neut = ", ".join(k3_profile.get("neutral_elements", []))
    lines.append(f"| **Favorable Elements (Medicine)** | `{med or 'None'}` |")
    lines.append(f"| **Unfavorable Elements (Taboo)** | `{taboo or 'None'}` |")
    lines.append(f"| **Neutral Elements** | `{neut or 'None'}` |")

    # 7. DOB
    lines.append(f"| **Birth Date & Time** | `{k3_profile.get('dob', '?')}` |")

    # 8. Language
    lines.append(f"| **Language** | `{k3_profile.get('language', '?')}` |")

    # 9. Tailoring
    tc = k3_profile.get("tailoring_concerns", {})
    concerns = (
        f"Career: `{tc.get('career', 'None')}`, "
        f"Relationships: `{tc.get('relationships', 'None')}`, "
        f"Wealth: `{tc.get('wealth', 'None')}`"
    )
    lines.append(f"| **Tailoring Concerns** | {concerns} |")

    return "\n".join(lines) + "\n"
