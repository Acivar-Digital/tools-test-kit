# ruff: noqa: E402
import pytest

pytest.skip("Legacy alt_src module removed", allow_module_level=True)


import asyncio
import json

from alt_src.K3.k3_pipeline import generate_annual_summary

from src.bot.bridge import map_profile_to_k3
from src.bot.session import UserProfile
from src.engine.orchestrator import run_full_engine


async def test_francis_monthly_report():
    print("--- Simulating Monthly Forecast Engine Run for Test Profile ---")

    # 1. Setup Profile (Mirroring intake)
    profile = UserProfile(
        name="Test Profile",
        alias="Tester",
        gender="M",
        year_pillar={"stem": "Ding", "branch": "Si"},
        month_pillar={"stem": "Jia", "branch": "Chen"},
        day_pillar={"stem": "Yi", "branch": "Mao"},
        hour_pillar={"stem": "Ren", "branch": "Wu"},
        da_yun_pillar={"stem": "Ji", "branch": "Hai"},
        da_yun_start_year=2023,
        day_master_strength="Strong",
        favorable_elements=["Fire", "Earth"],
        unfavorable_elements=["Water", "Wood"],
        neutral_elements=["Metal"]
    )

    # Tailoring Concerns (4 questions, choose 1 for all)
    tailoring_concerns = {
        "career": "1. Growth: Is this a good year to seek a promotion or salary raise in my current role?",
        "relationships": "1. New Love: What are my prospects for meeting a new romantic partner this year?",
        "wealth": "1. High Growth: Is 2026 favorable for aggressive investments and new wealth creation?",
        "health": "1. Vitality: Which months should I prioritise rest and avoid over-exertion?",
        "health_concern": "1" # Sleep & energy levels
    }

    # 2. Map to K3 format
    k3_profile = map_profile_to_k3(profile, 999000001, dob="1990-01-01", tailoring_concerns=tailoring_concerns)

    print(f"Profile Mapped: {k3_profile['name']} ({k3_profile['dm_strength_type']})")

    # 3. Run Engine for 12 months
    print("Running 12-month engine simulation...")
    results = []
    for i in range(12):
        res = run_full_engine(k3_profile, i)
        results.append(res)
        m_name = res["month_metadata"]["month_name"]
        score = res["engine_outputs"]["module_8"]["composite_score"]
        rating = res["engine_outputs"]["module_8"]["rating"]
        print(f"  - {m_name}: Score {score} (Rating {rating})")

    # 4. Annual Summary
    print("\nGenerating Annual Summary...")
    try:
        summary = generate_annual_summary(results)
        print("Annual Summary Success!")

        # 5. Package Master JSON
        for m in results:
            m_name = m["month_metadata"]["month_name"]
            eng = m["engine_outputs"]
            score = eng["module_8"]
            stars = eng.get("module_12_stars", [])
            events = eng.get("activity_forecasts", {}).get("classified_events", [])

            # Build a technically dense narrative mock
            star_names = ", ".join([s["star"] for s in stars]) if stars else "None"
            event_alerts = "\n".join([f"  ⚠️ {e['type'].replace('_', ' ').title()}: {e['reason']} ({e['probability']}%)" for e in events[:2]])

            trace = score["calculation_trace"]
            tech_advisory = (
                f"### 🎯 {m_name} Technical Alignment\n"
                f"**Structural Rating: {score['rating']} ({score['composite_score']})**\n\n"
                f"**1. Core Dynamics:**\n"
                f"- **Climate Bias:** {m['month_metadata']['climate_bias']} (Impact on resource flow)\n"
                f"- **Medicine Contrib:** {trace.get('medicine_contrib', 0)} (Strength of favorable elements)\n"
                f"- **DM Life Phase:** {eng.get('dm_life_phase', 'N/A')} (Your vitality level)\n\n"
                f"**2. Active Triggers & Stars:**\n"
                f"- **Stars:** {star_names}\n"
                f"- **Key Interactions:** {trace.get('monthly_mod', 0)} friction impact.\n\n"
                f"**3. Automated Event Alerts:**\n{event_alerts or '  No critical alerts detected.'}\n\n"
                f"**4. Tailored Response ({tailoring_concerns['career'].split(':')[0]}):**\n"
                f"As a **Strong Yi Wood**, your focus on '{tailoring_concerns['career']}' is analyzed against the incoming {m_name} pillar. "
                f"The presence of favorable {', '.join(k3_profile['medicine'])} elements suggests this is a period for **{'Action' if score['composite_score'] > 60 else 'Observation'}**.\n\n"
                f"Regarding your **Wealth goal ({tailoring_concerns['wealth'].split(':')[0]})**, "
                f"the {trace.get('released_element_mod', 0)} release modifier indicates a {'positive' if trace.get('released_element_mod', 0) > 0 else 'neutral'} wealth window."
            )

            m["engine_outputs"]["module_6a"] = {
                "content": tech_advisory
            }

        master_json = {
            "profile_summary": k3_profile,
            "monthly_forecasts": results,
            "annual_summary": summary
        }

        json_path = "TEST/reports/francis_yap_monthly_master.json"
        md_path = "TEST/reports/francis_yap_monthly_report.md"

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(master_json, f, indent=2, ensure_ascii=False)

        print(f"Master JSON saved to {json_path}")

        # 6. Format Report
        from alt_src.K3.k3_report_formatter import format_k3_markdown
        format_k3_markdown(json_path, md_path)
        print(f"FINAL REPORT GENERATED: {md_path}")

    except Exception as e:
        print(f"FAILED to generate annual summary: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_francis_monthly_report())
