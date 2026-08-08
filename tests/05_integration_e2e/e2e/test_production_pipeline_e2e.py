# ruff: noqa: E402
import pytest

pytest.skip("Legacy alt_src module removed", allow_module_level=True)


import asyncio
import json
from pathlib import Path

from alt_src.K3.k3_consolidator import stitch_and_convert
from alt_src.K3.k3_pipeline import generate_annual_summary
from alt_src.K3.k3_report_formatter import format_k3_markdown
from alt_src.K3.k3_summarizer import format_markdown_summary

from src.bot.bridge import map_profile_to_k3
from src.bot.session import UserProfile

# Import engine components
from src.engine.orchestrator import run_full_engine


async def test_full_production_pipeline():
    print("🚀 --- SIMULATING FULL PRODUCTION PIPELINE (ENTRY TO HTML) ---")

    # 1. DATA COLLECTION (Intake simulation)
    chat_id = 999000001
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

    tailoring_concerns = {
        "career": "1. Growth: Is this a good year to seek a promotion or salary raise in my current role?",
        "relationships": "1. New Love: What are my prospects for meeting a new romantic partner this year?",
        "wealth": "1. High Growth: Is 2026 favorable for aggressive investments and new wealth creation?",
        "health": "1. Vitality: Which months should I prioritise rest and avoid over-exertion?",
        "health_concern": "1" # Sleep & energy levels
    }

    # 2. ENTRY POINT BRIDGE
    print("[1/6] Mapping profile to K3 Bridge format...")
    k3_profile = map_profile_to_k3(profile, chat_id, dob="1990-01-01", tailoring_concerns=tailoring_concerns)

    # Setup directories
    artifact_dir = Path("TEST/reports/production_test")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    profile_path = artifact_dir / "profile.json"
    master_json_path = artifact_dir / "master.json"
    summary_md_path = artifact_dir / "executive_summary.md"
    technical_md_path = artifact_dir / "technical_report.md"
    final_html_path = artifact_dir / "final_report.html"

    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(k3_profile, f, indent=2, ensure_ascii=False)

    # 3. ENGINE PROCESSING
    print("[2/6] Running 12-Month Zi Ping Engine...")
    results = [run_full_engine(k3_profile, i) for i in range(12)]

    # 4. ANNUAL SUMMARY GENERATION
    print("[3/6] Generating Annual Structural Summary...")
    annual_summary = generate_annual_summary(results)

    # Mock some Phase A/B narrative content into the results for the technical report
    for m in results:
        m_name = m["month_metadata"]["month_name"]
        score = m["engine_outputs"]["module_8"]["composite_score"]
        m["engine_outputs"]["module_6a"] = {
            "content": f"### Monthly Analysis for {m_name}\nStructural score is {score}. Focus on {tailoring_concerns['career']}."
        }

    master_report = {
        "profile_summary": k3_profile,
        "monthly_forecasts": results,
        "annual_summary": annual_summary
    }
    with open(master_json_path, "w", encoding="utf-8") as f:
        json.dump(master_report, f, indent=2, ensure_ascii=False)

    # 5. SUMMARIZER (MOCKING LLM)
    print("[4/6] Generating Deep-Dive Executive Summary (Mocked LLM)...")
    mock_summary_data = {
        "executive_overview": {
            "title": "A Year of Strategic Expansion and Fortification",
            "narrative": "For a Strong Yi Wood Day Master, 2026 (Bing Wu) presents a high-output environment. Your medicine elements (Fire/Earth) are active, allowing you to convert your natural intensity into tangible assets. The core challenge is managing the Hai-Mao-Wei wood formation in your chart to prevent over-extension.",
            "tldr": [
                "Prioritize Fire (Output) to release Wood pressure.",
                "Capture Earth (Wealth) during the Chen and Xu months.",
                "Maintain flexibility in relationships during the Si month."
            ]
        },
        "execution_directives": [
            {"rule_name": "Output Venting", "instruction": "You must channel your energy into creative or speaking roles to avoid stress-induced health issues."},
            {"rule_name": "Asset Consolidation", "instruction": "Move profits from aggressive growth into stable Earth assets (Property/Land) by Q3."},
            {"rule_name": "Emotional Guardrails", "instruction": "Do not let the Mao-Chen harm affect your decision-making in April."}
        ],
        "monthly_strategy_calendar": [
            {
                "month_name": m["month_metadata"]["month_name"],
                "career_summary": "Seek Growth",
                "relationships_summary": "New Connections",
                "health_summary": "Manage Energy",
                "wealth_summary": "High Activity",
                "overall_strategy": "Advance" if m["engine_outputs"]["module_8"]["composite_score"] > 60 else "Steady"
            } for m in results
        ],
        "monthly_strategic_analysis": [
            {
                "month_name": m["month_metadata"]["month_name"],
                "title": f"Strategic Focus: {m['month_metadata']['month_name']}",
                "career": {"theme": "Momentum", "action": "Ask for raise", "tldr_theme": ["High support"], "tldr_action": ["Do it"]},
                "marriage": {"theme": "Harmony", "action": "Date night", "tldr_theme": ["Stable"], "tldr_action": ["Connect"]},
                "health": {"theme": "Vibrant", "action": "Exercise", "tldr_theme": ["Good"], "tldr_action": ["Stay active"]},
                "wealth": {"theme": "Gain", "action": "Invest", "tldr_theme": ["Positive"], "tldr_action": ["Aggressive"]}
            } for m in results
        ]
    }

    # Render the summary MD directly using the formatter
    exec_md = format_markdown_summary(mock_summary_data, k3_profile, [m["month_metadata"] for m in results])
    with open(summary_md_path, "w", encoding="utf-8") as f:
        f.write(exec_md)

    # 6. FORMAT TECHNICAL REPORT
    print("[5/6] Formatting Technical Deep-Dive Report...")
    format_k3_markdown(str(master_json_path), str(technical_md_path))

    # 7. STITCH AND CONVERT TO PREMIUM HTML
    print("[6/6] Stitching and Converting to Premium HTML...")
    stitch_and_convert(str(summary_md_path), str(final_html_path))

    print("\n✅ FULL PRODUCTION PIPELINE TEST COMPLETE!")
    print(f"  - Profile: {profile_path}")
    print(f"  - Master JSON: {master_json_path}")
    print(f"  - Executive Summary (MD): {summary_md_path}")
    print(f"  - Technical Report (MD): {technical_md_path}")
    print(f"  - FINAL PREMIUM HTML: {final_html_path}")

    # Return absolute path for verification
    return str(final_html_path)

if __name__ == "__main__":
    asyncio.run(test_full_production_pipeline())
