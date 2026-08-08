"""
Test runner: executes the K3 pipeline end-to-end using the local Gemini proxy.
All presets are pointed at LOCAL_LLM_URL so zero OpenRouter traffic is generated.
Output is saved to TEST/reports/.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from alt_src.K3.K3_pipeline import run_k3_pipeline
from alt_src.K3.K3_summarizer import run_summarizer


async def main():
    print("=" * 60)
    print("  K3 Pipeline Test Run  –  Local Gemini Proxy Only")
    print("=" * 60)

    project_root = Path(__file__).parent.parent.parent
    profile_path = project_root / "alt_src/K2/K2_profile.json"
    output_dir = project_root / "TEST" / "reports"
    os.makedirs(output_dir, exist_ok=True)

    master_json = output_dir / "K3_master_output.json"
    summary_md = output_dir / "K3_executive_summary.md"

    # ── 1. Run the K3 pipeline (engine + 2-phase LLM per month) ────────
    print("\n>> Phase 1: K3 Pipeline")
    await run_k3_pipeline(str(profile_path), str(master_json))

    # ── 2. Run the Summarizer (executive summary) ──────────────────────
    print("\n>> Phase 2: Executive Summary")
    run_summarizer(str(master_json), str(summary_md), live_api=True)

    print("\n" + "=" * 60)
    print("  [OK] Test Complete - reports saved to", output_dir)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
