import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load env variables BEFORE importing src2 modules
load_dotenv()

from src2.engine.openrouter import call_openrouter_async  # noqa: E402

from src2.engine.orchestrator import run_full_engine  # noqa: E402
from src2.engine.rag_client import query_classical_text_async  # noqa: E402
from src2.interfaces.telegram.chronomancer.rag import RAG_INSTRUCTIONS  # noqa: E402


async def main():
    print("=== STARTING RAG SEARCH DIAGNOSTIC FOR MONTH 1 ===")

    # 1. Load test profile (User 999)
    # Annot: baziforecaster-only profile; guarded by kit-existence check.
    _kit_path = os.getenv("KIT_PATH", "")
    profile_path = Path(_kit_path) / "_prd" / "users" / "999" / "profile.json" if _kit_path else None
    if not profile_path or not profile_path.exists():
        print(f"Skipping: User 999 profile not found (baziforecaster-only). Set KIT_PATH.")
        return
    if not profile_path.exists():
        print(f"Error: Profile not found at {profile_path}")
        return

    with open(profile_path, encoding="utf-8") as f:
        profile = json.load(f)

    dm_strength = profile.get("dm_strength_type") or profile.get("day_master_strength") or "Strong"
    ge_ju_type = profile.get("ge_ju_type") or profile.get("structure") or "普通格局"

    print(f"User Profile Loaded: {profile.get('name')} (Strength: {dm_strength})")

    # 2. Run Bazi mathematical engine for Month 1 (Index 0 = GengYin)
    from src2.core.schemas import ChartProfile
    engine_result = run_full_engine(ChartProfile.model_validate(profile), 0)
    month_name = "GengYin (庚寅)"
    print(f"Bazi Engine calculation complete for Month 1 ({month_name}).")

    # Extract calculations from the engine result
    eo = engine_result.get("engine_outputs", {})

    # Xun Kong / Void Audit
    m1 = eo.get("module_1", {})
    void_audit = m1.get("macro_environmental_scan", {}).get("void_audit", {})
    is_void_active = void_audit.get("is_void_active", False)
    void_branches = void_audit.get("void_branches", [])
    void_str = f"Yes (Branches: {', '.join(void_branches)})" if is_void_active else "No"

    # Interactions (Clashes & Combinations) from Module 3
    m3 = eo.get("module_3", {}).get("module_3_results", {})
    clash_details = m3.get("clash_details", {})
    destroyed_pillars = m3.get("destroyed_pillars", [])
    beneficial_combinations = m3.get("beneficial_combinations", [])
    stem_combos = m3.get("stem_combo_modifiers", [])

    interactions = []
    for pillar, type_name in clash_details.items():
        if type_name:
            interactions.append(f"- Clash: Transit month branch interacts with Natal {pillar.capitalize()} branch ({type_name})")
    for pillar in destroyed_pillars:
        interactions.append(f"- Pillar Destruct: Transit month disrupts Natal {pillar} pillar")
    for combo in beneficial_combinations:
        combo_type = combo.get("type", "Combination")
        element = combo.get("element", "")
        branches = combo.get("branches", [])
        interactions.append(f"- Combination ({combo_type}): Transit branch forms harmony with {', '.join(branches)} forming {element}")
    for mod in stem_combos:
        if mod.get("layer") == "Monthly":
            interactions.append(f"- Combination (Stem): Transit stem ({mod.get('ext_stem')}) combines with Natal {mod.get('pillar')} stem ({mod.get('natal_stem')})")

    interactions_str = "\n".join(interactions) if interactions else "None detected."

    # Extract all 4 pillars for output
    year_p = profile.get("year_pillar")
    month_p = profile.get("month_pillar")
    day_p = profile.get("day_pillar")
    hour_p = profile.get("hour_pillar")
    da_yun_p = profile.get("da_yun_pillar")

    # Define user's tailoring options and descriptions
    concern_mappings = {
        "overall": {
            "1": "General overview of the month's thematic energy, core transitions, and major highlights.",
        },
        "career": {
            "1": "Job change, promotion, career transition, and job seeking.",
            "2": "Career stability, workload management, and performance stress.",
        },
        "wealth": {
            "1": "Investments, wealth accumulation, trading, and financial growth.",
            "2": "Wealth preservation, debt repayment, and expense control.",
        },
        "relationships": {
            "1": "Romance, marriage, dating, and partner compatibility.",
            "2": "Family harmony, children, and relative dynamics.",
        }
    }

    user_concerns = profile.get("tailoring_concerns", {})
    categories = ["overall", "career", "wealth", "relationships"]

    # 3. Formulate prompts for all 4 categories
    prompts = {}
    for cat in categories:
        option_num = str(user_concerns.get(cat) or "1")
        question_text = concern_mappings[cat].get(option_num, "General inquiry.")

        context_data = f"""### Bazi Context
Natal Chart (4 Pillars):
- Year Pillar: {year_p}
- Month Pillar: {month_p}
- Day Pillar: {day_p}
- Hour Pillar: {hour_p}
- Da Yun (10Y) Pillar: {da_yun_p}
- Day Master Strength: {dm_strength}
- Structure (Ge Ju): {ge_ju_type}

Transit Month: 庚寅 (GengYin)
Void (Kong Wang) Active: {void_str}

Calculated Interactions with Transit Month:
{interactions_str}

### Target Topic
Focus Area: {cat.capitalize()}
Specific User Question/Concern: {question_text}

### Instruction
You are the direct lineage of Master Xu Ziping, the founder of Ziping Bazi. Right now, this person (see profile below) needs your help. Please do not spend time thinking as this person urgently requires your inputs. Generate a Simplified Chinese search query to retrieve target snippets from the Ziping classics (baziRag) that address this person's concerns regarding {cat.capitalize()}. Do note that the materials in the RAG are mostly in Simplified Chinese, hence you MUST query using Simplified Chinese. Your kindness is much appreciated.
"""
        prompts[cat] = f"{RAG_INSTRUCTIONS}\n\n=== INPUT DATA ===\n{context_data}"

    # 4. Generate RAG search keywords from user concerns
    from src2.engine.pydantic_prompt_engine import keyword_agent

    concern_career = concern_mappings["career"].get(str(user_concerns.get("career") or "1"), "General career guidance.")
    concern_wealth = concern_mappings["wealth"].get(str(user_concerns.get("wealth") or "1"), "General wealth guidance.")
    concern_relationship = concern_mappings["relationships"].get(str(user_concerns.get("relationships") or "1"), "General relationship guidance.")

    keyword_prompt = (
        f"Generate Chinese search keywords for these user concerns:\n"
        f"1. Career Concern: {concern_career}\n"
        f"2. Wealth Concern: {concern_wealth}\n"
        f"3. Relationship Concern: {concern_relationship}\n"
    )

    print("\n--- Generating Chinese Keywords using keyword_agent ---")
    keyword_res = await keyword_agent.run(keyword_prompt)
    keywords = keyword_res.output

    # Run 9 parallel vector searches
    career_queries = [keywords.career.keyword_1, keywords.career.keyword_2, keywords.career.keyword_3]
    wealth_queries = [keywords.wealth.keyword_1, keywords.wealth.keyword_2, keywords.wealth.keyword_3]
    rel_queries = [keywords.relationships.keyword_1, keywords.relationships.keyword_2, keywords.relationships.keyword_3]

    all_queries = [q for q in (career_queries + wealth_queries + rel_queries) if q.strip()]

    print("\n--- Executing 9 Classical RAG Searches Concurrently ---")
    search_tasks = [query_classical_text_async(q, top_k=3) for q in all_queries]
    search_results = await asyncio.gather(*search_tasks)

    mapped_results = {}
    for q, res in zip(all_queries, search_results):
        mapped_results[q] = res

    def build_domain_rag(queries):
        parts = []
        for q in queries:
            res = mapped_results.get(q, "")
            if res and res.strip():
                parts.append(f"--- Reference (Keyword: {q}) ---\n{res}")
        return "\n\n".join(parts) if parts else "No specific references found."

    career_rag_context = build_domain_rag(career_queries)
    wealth_rag_context = build_domain_rag(wealth_queries)
    relationship_rag_context = build_domain_rag(rel_queries)

    # Format grounding references for the narrative generator
    grounding_str = (
        f"\n=== CLASSICAL REFERENCES FOR CAREER ===\n{career_rag_context}\n"
        f"\n=== CLASSICAL REFERENCES FOR WEALTH ===\n{wealth_rag_context}\n"
        f"\n=== CLASSICAL REFERENCES FOR RELATIONSHIPS ===\n{relationship_rag_context}\n"
    )

    user_name = profile.get("name") or "User"

    # Define the 5th Gemma system prompt
    narrative_system_prompt = (
        f"You are the direct lineage of Master Xu Ziping, the founder of Ziping Bazi, and the senior narrative writer for Chronomancer. "
        f"You have done a thorough research based on the grounded truth offered by our ancestors (see attached RAG materials). "
        f"Your task is to synthesize your research and address {user_name}'s concerns (see questions). "
        f"To really be helpful, you must first understand what {user_name} is asking, then provide your assessment of the situation "
        f"based on {user_name}'s luck/transit pillar and area of concern. Always end off each section with actionable steps that {user_name} can take. "
        f"{user_name} is eagerly awaiting your insights and advice on what to do next."
    )

    # User prompt
    narrative_user_prompt = f"""
### Bazi Context
Natal Chart (4 Pillars):
- Year Pillar: {year_p}
- Month Pillar: {month_p}
- Day Pillar: {day_p}
- Hour Pillar: {hour_p}
- Da Yun (10Y) Pillar: {da_yun_p}
- Day Master Strength: {dm_strength}
- Structure (Ge Ju): {ge_ju_type}

Transit Month: 庚寅 (GengYin)
Void (Kong Wang) Active: {void_str}

Calculated Interactions with Transit Month:
{interactions_str}

### Grounding Passages (Authoritative References):
{grounding_str}

### Specific User Concerns & Questions
- Overall Concern: {concern_mappings["overall"].get(str(user_concerns.get("overall") or "1"), "General thematic energy overview.")}
- Career Concern: {concern_mappings["career"].get(str(user_concerns.get("career") or "1"), "Job change, career transition, or workload stability.")}
- Wealth Concern: {concern_mappings["wealth"].get(str(user_concerns.get("wealth") or "1"), "Investments, wealth accumulation, or preserve capital.")}
- Relationships Concern: {concern_mappings["relationships"].get(str(user_concerns.get("relationships") or "1"), "Romance, dating, partner compatibility, or family harmony.")}

### Instruction
Generate the final monthly forecast. For each section (Overall, Career, Wealth, Relationships), synthesize the calculated Bazi interactions and matching classical references to write a congruent narrative. Keep the tone scholarly yet accessible (Sifu Mode).

Return your response as a strict JSON object with the keys "overall", "career", "wealth", and "relationships". Do not include any thinking blocks or markdown formatting.
"""

    chrono_url = os.getenv("CHRONO_URL")
    chrono_model = os.getenv("CHRONO_MODEL1") or os.getenv("CHRONO_MODEL") or "gemma-4-26b-a4b-it"
    print(f"Using Chronomancer Narrative Model: {chrono_model}")

    print("\n--- Invoking 5th Gemma Narrative Generator ---")
    narrative = await call_openrouter_async(
        prompt=narrative_user_prompt,
        url=chrono_url,
        model=chrono_model,
        system_prompt=narrative_system_prompt,
        temperature=1.0,
    )
    print("\n=======================================================")
    print("✨ GENERATED MONTHLY REPORT NARRATIVE")
    print("=======================================================")
    print(narrative)

if __name__ == "__main__":
    asyncio.run(main())
