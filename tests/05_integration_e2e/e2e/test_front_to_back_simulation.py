# ruff: noqa: E402
import pytest

pytest.skip("Legacy alt_src module removed", allow_module_level=True)


import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment
load_dotenv()

# Override for local endpoint and heartbeat
os.environ["LOCAL_LLM_MODEL"] = "gemini-3.1-flash-lite"
os.environ["K3_DISPATCH_INTERVAL"] = "30.0" # Ultra stable 30s gap
os.environ["PYTHONIOENCODING"] = "utf-8"

# Import system components
from src.bot.bridge import map_profile_to_k3  # noqa: E402
from src.bot.session import UserProfile  # noqa: E402
from src.engine import openrouter  # noqa: E402
from src.engine.rag_client import query_classical_text_async  # noqa: E402

# Monkeypatch to force preset-specific routing and handle serial dispatching
_orig_call_openrouter_async = openrouter.call_openrouter_async

async def forced_local_call_serial(prompt, system_prompt=None, model=None, temperature=0.1, tools=None, max_turns=6, preset=None):
    p = preset or "narrative"
    return await _orig_call_openrouter_async(
        prompt=prompt,
        system_prompt=system_prompt,
        model=model,
        temperature=temperature,
        tools=tools,
        max_turns=max_turns,
        preset=p
    )

# Apply monkeypatch
openrouter.call_openrouter_async = forced_local_call_serial

# We also need to monkeypatch the pipeline to avoid asyncio.gather
import alt_src.K3.k3_pipeline as k3p  # noqa: E402


async def sequential_phase_a(month_idx, profile, engine_res, cache_dir, phase_a_config, tailoring_context=""):
    """SEQUENTIAL version of Phase A with proper RAG."""
    m_name = engine_res["month_metadata"]["month_name"]
    month_cache_file = cache_dir / f"month_{month_idx}_rag_bundle.json"

    if month_cache_file.exists():
        with open(month_cache_file, encoding="utf-8") as f:
            return json.load(f)

    print(f"  [SERIAL] Phase A: Starting {m_name}...")
    results = {}
    for domain in k3p.PHASE_A_DOMAINS:
        structural_briefing = k3p.build_structural_briefing(profile, engine_res)
        domain_zh = k3p.DOMAIN_CHINESE.get(domain, domain)

        # 1. Get Search Queries
        print(f"    -> {domain}: Getting Queries...")
        user_prompt = phase_a_config["user_template"].format(
            domain=domain, domain_zh=domain_zh, structural_briefing=structural_briefing
        )
        if tailoring_context:
            user_prompt += f"\n\n{tailoring_context}"

        raw = await openrouter.call_openrouter_async(
            system_prompt=phase_a_config["system_instruction"],
            prompt=user_prompt,
            preset="narrative",
            temperature=0.3
        )
        extracted = k3p.extract_json(raw)

        # 2. RAG
        queries = extracted.get("search_queries", [])[:3] # Max 3 for speed/safety
        print(f"    -> {domain}: RAG for {len(queries)} queries...")
        citations = []
        for q in queries:
            try:
                res_text = await query_classical_text_async(query=q, top_k=3)
                citations.append({
                    "source_text": res_text,
                    "verbatim_excerpt": f"Query: {q}",
                    "english_translation": "Result from BaziRAG"
                })
            except Exception as e:
                print(f"      [RAG ERROR] {e}")

        extracted["classical_citations"] = citations
        results[domain] = extracted

        # Stagger between domains
        await asyncio.sleep(1.0)

    # Cache to disk
    month_cache_file.parent.mkdir(parents=True, exist_ok=True)
    with open(month_cache_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    return results

# Monkeypatch Phase A to be sequential
k3p.run_phase_a_month = sequential_phase_a

from alt_src.K3.k3_consolidator import stitch_and_convert  # noqa: E402
from alt_src.K3.k3_summarizer import run_summarizer  # noqa: E402


async def progress_logger(msg: str):
    print(f"  [PROGRESS] {msg}")

async def run_front_to_back():
    print("--- STARTING FRONT-TO-BACK SIMULATION (STRICT SERIAL + 2S HEARTBEAT) ---")

    chat_id = 999000001
    name = "Test Profile"

    # 1. SETUP DATA
    profile = UserProfile(
        name=name, alias="Tester", gender="M",
        year_pillar={"stem": "Ding", "branch": "Si"},
        month_pillar={"stem": "Jia", "branch": "Chen"},
        day_pillar={"stem": "Yi", "branch": "Mao"},
        hour_pillar={"stem": "Ren", "branch": "Wu"},
        da_yun_pillar={"stem": "Ji", "branch": "Hai"},
        da_yun_start_year=2023, day_master_strength="Strong",
        favorable_elements=["Fire", "Earth"], unfavorable_elements=["Water", "Wood"], neutral_elements=["Metal"]
    )
    tailoring_concerns = {
        "career": "Growth: Is this a good year to seek a promotion or salary raise in my current role?",
        "relationships": "New Love: What are my prospects for meeting a new romantic partner this year?",
        "wealth": "High Growth: Is 2026 favorable for aggressive investments and new wealth creation?",
        "health": "Vitality: Which months should I prioritise rest and avoid over-exertion?",
        "health_concern": "1"
    }

    output_dir = Path("_prd") / str(chat_id) / "front_to_back"
    output_dir.mkdir(parents=True, exist_ok=True)

    profile_path = output_dir / "profile.json"
    master_json_path = output_dir / "master.json"
    summary_md_path = output_dir / "executive_summary.md"
    summary_json_path = output_dir / "summary.json"
    final_html_path = output_dir / "final_report.html"

    k3_profile = map_profile_to_k3(profile, chat_id, dob="1990-01-01", tailoring_concerns=tailoring_concerns)
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(k3_profile, f, indent=2, ensure_ascii=False)

    # 3. RUN K3 PIPELINE (Strictly Sequential)
    print("[Step 2/4] Running 12-Month Pipeline (STRICT SERIAL)...")
    try:
        # The run_k3_pipeline has a semaphore(1) for months, so we just need to ensure months are processed in order
        # and not gathered in the background if possible.
        # Actually, the original code uses await asyncio.gather(*tasks) even with semaphore(1).
        # To be ultra safe, we monkeypatch the month loop too.

        # We'll just rely on the semaphore being 1 and our sequential Phase A.

        results, failed_months = await k3p.run_k3_pipeline(
            profile_path=str(profile_path),
            output_path=str(master_json_path),
            progress_callback=progress_logger
        )
        print(f"OK: Master JSON generated at {master_json_path}")
    except Exception as e:
        print(f"ERROR: Pipeline failed: {e}")

    # 4. RUN SUMMARIZER
    if master_json_path.exists():
        print("[Step 3/4] Running Annual Summarizer...")
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: run_summarizer(
                k3_json_path=str(master_json_path),
                output_md_path=str(summary_md_path),
                output_json_path=str(summary_json_path),
                live_api=True,
                progress_callback=progress_logger,
                loop=loop
            ))
            print(f"OK: Executive Summary generated at {summary_md_path}")
        except Exception as e:
            print(f"ERROR: Summarizer failed: {e}")

    # 5. CONSOLIDATE
    if summary_md_path.exists():
        print("[Step 4/4] Generating Final Report...")
        try:
            stitch_and_convert(str(summary_md_path), str(final_html_path))
            print(f"OK: FINAL REPORT READY: {final_html_path}")
        except Exception as e:
            print(f"ERROR: Consolidation failed: {e}")

    print("\n--- FRONT-TO-BACK RUN COMPLETE ---")

if __name__ == "__main__":
    asyncio.run(run_front_to_back())
