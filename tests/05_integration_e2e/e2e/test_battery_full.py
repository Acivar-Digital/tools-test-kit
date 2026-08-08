"""
tests/e2e_battery_test.py
==========================
Production-readiness battery test.
Simulates a complete user journey from profile → tailoring → pipeline → report.
No Telegram. No bot server. Runs locally in ~4-6 minutes.

Usage:
    uv run python tests/e2e_battery_test.py

Pass criteria (printed at end):
    [OK] PASS  — all checks green
    [FAIL] FAIL  — check the step that failed
"""

import io
import json
import logging
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Force UTF-8 for stdout and stderr to handle emojis on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("battery")

# ── Test subject: Test Profile's real profile ──────────────────────────────────
FRANCIS_PROFILE = {
    "alias": "Tester YCL",
    "gender": "M",
    "year_pillar": {"stem": "Bing", "branch": "Chen"},
    "month_pillar": {"stem": "Geng", "branch": "Xu"},
    "day_pillar": {"stem": "Yi", "branch": "Wei"},
    "hour_pillar": {"stem": "Ren", "branch": "Zi"},
    "da_yun_pillar": {"stem": "Wu", "branch": "Chen"},
    "day_master_strength": "Weak",
    "favorable_elements": ["Fire", "Earth"],
    "unfavorable_elements": ["Metal", "Water"],
    "neutral_elements": ["Wood"],
    "dm_strength_type": "Weak",
    "medicine": ["Fire", "Earth"],
    "taboo": ["Metal", "Water"],
}

# Bogus tailoring answers — realistic enough to test injection
BOGUS_TAILORING = {
    "career": "I am currently unemployed and looking for a suitable role in finance or AI.",
    "relationships": "I am happily attached and want to deepen my bond with my partner.",
    "wealth": "I want to preserve my existing assets while seeking moderate growth.",
}

RESULTS = {}  # step_name → {"pass": bool, "detail": str}


def check(name: str, condition: bool, detail: str = ""):
    icon = "[OK]" if condition else "[FAIL]"
    RESULTS[name] = {"pass": condition, "detail": detail}
    logger.info(f"  {icon} {name}: {detail}")
    return condition


# ─────────────────────────────────────────────────────────────────────────────
# STEP 1: Tailoring module — unit checks
# ─────────────────────────────────────────────────────────────────────────────


def step1_tailoring_unit():
    logger.info("\n══ STEP 1: Tailoring Unit Checks ══")
    from src.bot.session import UserProfile
    from src.bot.tailoring import (
        build_tailoring_context,
        get_tailoring_state,
        handle_tailor_callback,
        handle_tailor_input,
        init_tailoring,
    )

    class FakeSession:
        def __init__(self):
            self.state = "TAILORING"
            self.metadata = {}
            self.profile = UserProfile()
            self.conversation_history = []

    # 1a: No path
    s = FakeSession()
    s = init_tailoring(s)
    reply, s, proceed = handle_tailor_callback(s, "tailor_no")
    check("1a_no_proceed", proceed is True, "tailor_no fires pipeline immediately")
    check("1a_no_concerns_none", s.metadata.get("tailoring_concerns") is None, "concerns=None on no path")

    # 1b: Yes path full flow
    s = FakeSession()
    s = init_tailoring(s)
    reply, s, proceed = handle_tailor_callback(s, "tailor_yes")
    check("1b_yes_no_proceed", proceed is False, "tailor_yes does NOT fire pipeline yet")
    check("1b_career_step", get_tailoring_state(s)["step"] == "career", "step=career after yes")

    reply, s, proceed = handle_tailor_input(s, BOGUS_TAILORING["career"])
    check("1c_career_saved", get_tailoring_state(s)["career"] == BOGUS_TAILORING["career"], "career saved")
    check("1c_step_relationships", get_tailoring_state(s)["step"] == "relationships", "step=relationships")

    reply, s, proceed = handle_tailor_input(s, BOGUS_TAILORING["relationships"])
    check(
        "1d_rel_saved",
        get_tailoring_state(s)["relationships"] == BOGUS_TAILORING["relationships"],
        "relationships saved",
    )
    check("1d_step_wealth", get_tailoring_state(s)["step"] == "wealth", "step=wealth")

    reply, s, proceed = handle_tailor_input(s, BOGUS_TAILORING["wealth"])
    check("1e_wealth_saved", get_tailoring_state(s)["wealth"] == BOGUS_TAILORING["wealth"], "wealth saved")
    check("1e_proceed_true", proceed is True, "pipeline fires after wealth")
    check("1e_step_done", get_tailoring_state(s)["step"] == "done", "step=done")

    concerns = s.metadata.get("tailoring_concerns", {})
    check(
        "1f_concerns_complete",
        all(k in concerns for k in ["career", "relationships", "wealth"]),
        f"all 3 keys present: {list(concerns.keys())}",
    )

    # 1c: Context string injection
    ctx = build_tailoring_context(BOGUS_TAILORING)
    check("1g_context_nonempty", len(ctx) > 50, f"context length={len(ctx)}")
    check("1g_context_career", BOGUS_TAILORING["career"] in ctx, "career concern in context")
    check("1g_context_rel", BOGUS_TAILORING["relationships"] in ctx, "relationships in context")
    check("1g_context_wealth", BOGUS_TAILORING["wealth"] in ctx, "wealth in context")

    # 1d: None returns empty
    ctx_empty = build_tailoring_context(None)
    check("1h_none_empty", ctx_empty == "", "None concerns → empty string")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 2: Profile JSON written correctly
# ─────────────────────────────────────────────────────────────────────────────


def step2_profile_json(tmp_dir: Path) -> Path:
    logger.info("\n══ STEP 2: Profile JSON Assembly ══")

    profile = {**FRANCIS_PROFILE, "tailoring_concerns": BOGUS_TAILORING}
    profile_path = tmp_dir / "test_profile.json"
    with open(profile_path, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    loaded = json.loads(profile_path.read_text(encoding="utf-8"))
    check("2a_profile_written", profile_path.exists(), str(profile_path))
    check("2b_tailoring_in_profile", "tailoring_concerns" in loaded, "tailoring_concerns key present")
    check(
        "2c_all_pillars",
        all(k in loaded for k in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]),
        "all 4 pillars present",
    )
    return profile_path


# ─────────────────────────────────────────────────────────────────────────────
# STEP 3: Deterministic engine — all 12 months
# ─────────────────────────────────────────────────────────────────────────────


def step3_engine(profile_path: Path):
    logger.info("\n══ STEP 3: Deterministic Engine (12 months) ══")
    from src.engine.orchestrator import run_full_engine

    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile.pop("tailoring_concerns", None)

    months_computed = []
    for i in range(12):
        try:
            res = run_full_engine(profile, i)
            months_computed.append(res["month_metadata"]["month_name"])
        except Exception as e:
            check(f"3_month_{i}", False, f"CRASHED: {e}")
            return None

    check("3a_all_12_months", len(months_computed) == 12, f"computed: {months_computed}")
    check("3b_first_month_geng_yin", months_computed[0] == "Geng Yin", f"first={months_computed[0]}")
    check("3c_last_month_xin_chou", months_computed[-1] == "Xin Chou", f"last={months_computed[-1]}")

    return months_computed


# ─────────────────────────────────────────────────────────────────────────────
# STEP 4: Tailoring context injected into pipeline prompt
# ─────────────────────────────────────────────────────────────────────────────


def step4_context_injection():
    logger.info("\n══ STEP 4: Context Injection into Pipeline Prompt ══")
    from src.bot.tailoring import build_tailoring_context

    ctx = build_tailoring_context(BOGUS_TAILORING)
    with open("alt_src/K3/prompts/narrative.json", encoding="utf-8") as f:
        narrative_config = json.load(f)

    # Simulate what dispatch_all_batches does
    dummy_profile = json.dumps(FRANCIS_PROFILE)
    dummy_engine = json.dumps([{"month": "Geng Yin", "scores": {}}])
    user_template = narrative_config.get("user_template", "")
    try:
        base_prompt = user_template.format(profile=dummy_profile, engine_data=dummy_engine)
        full_prompt = ctx + "\n\n" + base_prompt
        check(
            "4a_ctx_before_profile",
            full_prompt.index("unemployed") < full_prompt.index(dummy_profile[:20]),
            "concerns appear before engine data",
        )
        check(
            "4b_prompt_contains_all_concerns",
            all(c in full_prompt for c in BOGUS_TAILORING.values()),
            "all 3 concerns in prompt",
        )
    except Exception as e:
        check("4_injection", False, f"CRASHED: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# STEP 5: FULL PIPELINE — end-to-end with real LLM (the big one)
# ─────────────────────────────────────────────────────────────────────────────


def step5_full_pipeline(profile_path: Path, tmp_dir: Path) -> Path:
    logger.info("\n══ STEP 5: FULL PIPELINE RUN (real LLM calls) ══")
    logger.info("  [WAIT] This takes ~60-90 seconds. Do not interrupt.")

    output_path = tmp_dir / "test_master_output.json"

    from alt_src.K3.K3_pipeline import run_k3_pipeline

    t0 = time.time()
    try:
        run_k3_pipeline(str(profile_path), str(output_path))
    except Exception as e:
        check("5_pipeline_run", False, f"CRASHED: {e}")
        return None
    elapsed = time.time() - t0

    check("5a_output_exists", output_path.exists(), str(output_path))
    if not output_path.exists():
        return None

    with open(output_path, encoding="utf-8") as f:
        data = json.load(f)

    monthly = data.get("monthly_forecasts", [])
    audit = data.get("audit_metadata", {})
    annual = data.get("annual_summary", {})

    check("5b_12_months", len(monthly) == 12, f"months in output: {len(monthly)}")
    check("5c_audit_score_exists", "final_score" in audit, f"audit_metadata: {list(audit.keys())}")
    check("5d_audit_score_ge_70", (audit.get("final_score") or 0) >= 70, f"score={audit.get('final_score')}")
    check("5e_annual_summary", "annual_score" in annual, f"annual keys: {list(annual.keys())}")
    check("5f_elapsed_under_300s", elapsed < 300, f"elapsed={elapsed:.1f}s")

    # Check tailoring concerns were injected (look in first month's narrative)
    first_month = monthly[0] if monthly else {}
    narrative = first_month.get("engine_outputs", {}).get("module_6a", {})
    narrative_text = json.dumps(narrative).lower()
    # At least one of the concern keywords should appear somewhere
    career_keywords = ["unemployed", "finance", "role", "job"]
    found = any(kw in narrative_text for kw in career_keywords)
    check("5g_tailoring_reflected_in_narrative", found, f"career keywords found in narrative: {found}")

    logger.info(f"  ⏱  Pipeline completed in {elapsed:.1f}s")
    return output_path


# ─────────────────────────────────────────────────────────────────────────────
# STEP 6: Summarizer — executive JSON + markdown report
# ─────────────────────────────────────────────────────────────────────────────


def step6_summarizer(master_path: Path, tmp_dir: Path):
    logger.info("\n══ STEP 6: Summarizer -> Executive JSON + Markdown ══")
    logger.info("  [WAIT] This takes ~3 minutes.")

    md_path = tmp_dir / "test_report.md"
    exec_json_path = tmp_dir / "test_executive.json"

    import alt_src.K3.K3_summarizer as summarizer_module

    original_cache = summarizer_module.CACHE_PATH
    summarizer_module.CACHE_PATH = str(exec_json_path)

    if exec_json_path.exists():
        exec_json_path.unlink()

    try:
        summarizer_module.run_summarizer(
            k3_json_path=str(master_path),
            output_md_path=str(md_path),
            live_api=True,
        )
    except Exception as e:
        check("6_summarizer_run", False, f"CRASHED: {e}")
        return
    finally:
        summarizer_module.CACHE_PATH = original_cache

    check("6a_exec_json_exists", exec_json_path.exists(), str(exec_json_path))
    check("6b_markdown_exists", md_path.exists(), str(md_path))

    if md_path.exists():
        content = md_path.read_text(encoding="utf-8")
        size_kb = len(content) / 1024
        check("6c_markdown_size_gt_10kb", size_kb > 10, f"size={size_kb:.1f}KB")
        check("6d_has_executive_overview", "Executive Overview" in content, "Executive Overview section present")
        check("6e_has_monthly_calendar", "Monthly Strategy Calendar" in content, "Monthly Strategy Calendar present")
        check("6f_has_monthly_analysis", "Monthly Strategic Analysis" in content, "Monthly Strategic Analysis present")
        check("6g_has_12_months_table", content.count("Feb") + content.count("Mar") >= 2, "Calendar rows present")
        check("6h_francis_in_report", "Tester" in content, "Subject name in report")
        logger.info(f"  📄 Report size: {size_kb:.1f} KB")

    if exec_json_path.exists():
        with open(exec_json_path) as f:
            exec_data = json.load(f)
        check("6i_exec_has_overview", "executive_overview" in exec_data, "executive_overview key")
        check("6j_exec_has_calendar", "monthly_strategy_calendar" in exec_data, "monthly_strategy_calendar key")
        check("6k_exec_has_analysis", "monthly_strategic_analysis" in exec_data, "monthly_strategic_analysis key")
        cal = exec_data.get("monthly_strategy_calendar", [])
        check("6l_calendar_12_entries", len(cal) == 12, f"calendar entries: {len(cal)}")


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main():
    tmp_dir = Path("tests/tmp_battery")
    tmp_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("  CHRONOMANCER — PRODUCTION BATTERY TEST")
    logger.info(f"  Subject: {FRANCIS_PROFILE['alias']}")
    logger.info(f"  Output : {tmp_dir.resolve()}")
    logger.info("=" * 60)

    # Steps 1-4: fast, no LLM
    step1_tailoring_unit()
    profile_path = step2_profile_json(tmp_dir)
    step3_engine(profile_path)
    step4_context_injection()

    # Step 5: full pipeline (~90s)
    master_path = step5_full_pipeline(profile_path, tmp_dir)

    # Step 6: summarizer (~180s) — only runs if pipeline succeeded
    if master_path and master_path.exists():
        step6_summarizer(master_path, tmp_dir)
    else:
        logger.warning("  [WARN] Skipping Step 6 — pipeline did not produce output.")

    # ── Final verdict ─────────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("  BATTERY TEST RESULTS")
    logger.info("=" * 60)

    passed = [k for k, v in RESULTS.items() if v["pass"]]
    failed = [k for k, v in RESULTS.items() if not v["pass"]]

    for k, v in RESULTS.items():
        icon = "[OK]" if v["pass"] else "[FAIL]"
        logger.info(f"  {icon} {k}: {v['detail']}")

    logger.info("")
    logger.info(f"  PASSED: {len(passed)}/{len(RESULTS)}")
    if failed:
        logger.info(f"  FAILED: {failed}")
        logger.info("\n  [FAIL] NOT PRODUCTION READY — fix failed checks above.")
        sys.exit(1)
    else:
        logger.info("\n  [OK] ALL CHECKS PASSED — PRODUCTION READY.")
        logger.info(f"  📁 Outputs in: {tmp_dir.resolve()}")


if __name__ == "__main__":
    main()
