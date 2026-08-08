import asyncio
import logging
import sys
import traceback
from pathlib import Path

import pytest

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.engine.module3_interaction import calculate_interactions  # noqa: E402

# Setup logging (Mission Style)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("FanFuDiagnostic")

class FanFuDiagnostic:
    """
    MISSION: Hardened & Consistency-Aware Verification of Fan Yin (反吟) and Fu Yin (伏吟) logic.
    Location: TEST/integration/fanyin_fuyin_diagnostic.py

    Hardenings:
    - Schema-defensive access (safe .get() and key guards).
    - Consistency checking (detects contradictory scope signals).
    - Evidence extraction (returns matching entries for audit trails).
    - Scope tolerance (case-insensitive and alias-ready).
    """

    def __init__(self):
        pass

    async def run_verification_gate(self):
        """
        Runs the engine test suite gate.
        Failure here indicates a regression in core logic, aborting the swarm.
        """
        logger.info("🧪 RUNNING VERIFICATION GATE: uv run pytest...")
        proc = await asyncio.create_subprocess_exec(
            "uv", "run", "pytest", "TEST/unit/engine/", "-v",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode != 0:
            err_msg = stderr.decode() if stderr else stdout.decode()
            logger.error(f"❌ ENGINE TESTS FAILED:\n{err_msg}")
            return False

        logger.info("✅ ENGINE TESTS PASSED.")
        return True

    def _safe_verify(self, results: dict, target_type: str, target_scope: str, agent_name: str) -> dict:
        """
        Hardened consistency checker for interaction signals.

        Improvements:
        - Detects engine contradictions (multiple scopes for same type).
        - Returns the matching entry as evidence for logging.
        - Case-insensitive scope matching.
        """
        m3_res = results.get("module_3_results")
        if not isinstance(m3_res, dict):
            raise TypeError(f"[{agent_name}] Invalid engine output: 'module_3_results' is missing or not a dict.")

        specials = m3_res.get("active_disruptors")
        if not isinstance(specials, list):
            raise KeyError(f"[{agent_name}] Missing 'active_disruptors' list in engine output.")

        # 1. Filter for type matches
        matches = [
            e for e in specials
            if isinstance(e, dict) and e.get("type") == target_type
        ]

        if not matches:
            raise RuntimeError(f"[{agent_name}] {target_type} was NOT detected in test profile.")

        # 2. Consistency Check: Detect contradictory signals
        # If the engine emits the same Fan/Fu Yin type across multiple layers in a single check,
        # it suggests an internal logic leak (e.g., Natal logic firing during External check).
        scopes_detected = {str(e.get("layer")).lower() for e in matches if e.get("layer")}
        if len(scopes_detected) > 1:
            raise RuntimeError(f"[{agent_name}] CONTRADICTORY SCOPES: {target_type} found in multiple layers: {scopes_detected}")

        # 3. Targeted Scope Match (Case-Insensitive)
        target_scope_set = {target_scope.lower(), target_scope}
        evidence = next((e for e in matches if str(e.get("layer")).lower() in target_scope_set), None)

        if not evidence:
            raise RuntimeError(f"[{agent_name}] {target_type} found, but scope '{scopes_detected}' does not match expected '{target_scope}'.")

        return evidence

    async def agent_natal_fu_yin(self):
        """AGENT 1: Intent: Verify Natal-level identity (Repetition)."""
        logger.info("🎭 AGENT 1: Verifying Natal Fu Yin...")
        try:
            profile = {
                "year_pillar": {"stem": "Jia", "branch": "Zi"},
                "month_pillar": {"stem": "Jia", "branch": "Zi"},
                "day_pillar": {"stem": "Bing", "branch": "Wu"},
                "hour_pillar": {"stem": "Ding", "branch": "Wei"},
            }
            res = calculate_interactions(profile, {"branch": "Mao"}, {"branch": "Chen"})

            evidence = self._safe_verify(res, "Fu Yin", "Natal", "AGENT 1")
            logger.info(f"✅ AGENT 1 Verified. Evidence: {evidence}")
            return True
        except Exception:
            logger.error(f"❌ AGENT 1 FAILED:\n{traceback.format_exc()}")
            raise

    async def agent_natal_fan_yin(self):
        """AGENT 2: Intent: Verify Natal-level Tian Ke Di Chong (Shock)."""
        logger.info("🎭 AGENT 2: Verifying Natal Fan Yin...")
        try:
            profile = {
                "year_pillar": {"stem": "Jia", "branch": "Zi"},
                "month_pillar": {"stem": "Bing", "branch": "Yin"},
                "day_pillar": {"stem": "Geng", "branch": "Wu"},
                "hour_pillar": {"stem": "Ding", "branch": "Wei"},
            }
            res = calculate_interactions(profile, {"branch": "Mao"}, {"branch": "Chen"})

            evidence = self._safe_verify(res, "Fan Yin", "Natal", "AGENT 2")
            logger.info(f"✅ AGENT 2 Verified. Evidence: {evidence}")
            return True
        except Exception:
            logger.error(f"❌ AGENT 2 FAILED:\n{traceback.format_exc()}")
            raise

    async def agent_external_fan_yin(self):
        """AGENT 3: Intent: Verify temporal interaction with Luck/Annual pillars."""
        logger.info("🎭 AGENT 3: Verifying External Fan Yin...")
        try:
            profile = {
                "year_pillar": {"stem": "Xin", "branch": "You"},  # Non-clashing Year
                "month_pillar": {"stem": "Bing", "branch": "Yin"},
                "day_pillar": {"stem": "Geng", "branch": "Wu"},
                "hour_pillar": {"stem": "Ding", "branch": "Wei"},
            }
            # Annual pillar (Jia Zi) clashing with Day (Geng Wu)
            annual = {"stem": "Jia", "branch": "Zi"}
            res = calculate_interactions(profile, {"branch": "Mao"}, annual)

            evidence = self._safe_verify(res, "Fan Yin", "External", "AGENT 3")
            logger.info(f"✅ AGENT 3 Verified. Evidence: {evidence}")
            return True
        except Exception:
            logger.error(f"❌ AGENT 3 FAILED:\n{traceback.format_exc()}")
            raise

    async def execute_mission(self):
        """Orchestrates the consistency-aware swarm mission."""
        logger.info("🚀 MISSION LAUNCHED: Hardened & Consistency-Aware Audit")

        tasks = [
            self.agent_natal_fu_yin(),
            self.agent_natal_fan_yin(),
            self.agent_external_fan_yin()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        failures = [r for r in results if isinstance(r, Exception)]
        if failures:
            logger.error(f"🚨 MISSION ABORTED: {len(failures)} agents failed consistency or detection audit.")
            return False

        try:
            if not await self.run_verification_gate():
                return False
        except Exception as e:
            logger.error(f"❌ POST-MISSION GATE CRASHED: {e}")
            return False

        logger.info("✨ MISSION SUCCESS: Fan Yin / Fu Yin logic satisfies consistency and structural integrity criteria.")
        return True

@pytest.mark.asyncio
async def test_fanyin_fuyin_diagnostic_mission():
    """Pytest entry point for the Fan/Fu Yin diagnostic mission."""
    mission = FanFuDiagnostic()
    success = await mission.execute_mission()
    assert success is True

if __name__ == "__main__":
    mission = FanFuDiagnostic()
    try:
        success = asyncio.run(mission.execute_mission())
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Mission interrupted.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"UNHANDLED MISSION EXCEPTION: {e}")
        sys.exit(1)
