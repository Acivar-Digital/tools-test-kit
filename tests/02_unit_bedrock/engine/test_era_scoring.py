"""
V30 Stage 2+3 Tests — Era Block + Primary/Noise signal hierarchy.

Tests:
1. Ji Shen era returns era_ceiling = 71
2. Yong Shen era returns era_ceiling = 80
3. Ji Shen era score cannot exceed 71 regardless of medicine month input
4. medicine_contrib is the dominant monthly signal — structural noise
   alone cannot move score by more than 5
"""

import logging
import unittest

from src.engine.module1_macro import _get_era_block
from src.engine.module8_scoring import calculate_composite_score

logging.basicConfig(level=logging.CRITICAL)


class TestV30EraBlock(unittest.TestCase):
    """Stage 2: Era block classification tests."""

    def _make_profile(self, dy_branch: str, medicine: list, taboo: list):
        """Minimal profile for era block testing."""
        return {
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Yi", "branch": "Hai"},
            "hour_pillar": {"stem": "Ding", "branch": "Mao"},
            "da_yun_pillar": {"stem": "Gui", "branch": dy_branch},
            "medicine": medicine,
            "taboo": taboo,
            "favorable_elements": medicine,
            "unfavorable_elements": taboo,
            "neutral_elements": [],
            "day_stem_stream": "Jia Zi",
        }

    def test_ji_shen_era_ceiling_71(self):
        """Test 1: Ji Shen era returns era_ceiling = 71."""
        # Medicine = Wood, Taboo = Metal
        # Da Yun branch = Shen (in Shen-You-Xu = Metal era = Ji Shen)
        profile = self._make_profile("Shen", medicine=["Wood"], taboo=["Metal"])
        era = _get_era_block("Shen", profile)

        self.assertEqual(era["era_element"], "Metal")
        self.assertEqual(era["era_label"], "Hostile Era")
        self.assertEqual(era["era_ceiling"], 71)

    def test_yong_shen_era_ceiling_80(self):
        """Test 2: Yong Shen era returns era_ceiling = 80."""
        # Medicine = Wood, Taboo = Metal
        # Da Yun branch = Mao (in Yin-Mao-Chen = Wood era = Medicine)
        profile = self._make_profile("Mao", medicine=["Wood"], taboo=["Metal"])
        era = _get_era_block("Mao", profile)

        self.assertEqual(era["era_element"], "Wood")
        self.assertEqual(era["era_label"], "Medicine Era")
        self.assertEqual(era["era_ceiling"], 80)


class TestV30ScoringHierarchy(unittest.TestCase):
    """Stage 3: Scoring signal hierarchy tests."""

    def setUp(self):
        """Set up mock data for scoring tests."""
        self.mock_profile = {
            "name": "Test User",
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Yi", "branch": "Hai"},
            "hour_pillar": {"stem": "Ding", "branch": "Mao"},
            "da_yun_pillar": {"stem": "Gui", "branch": "Shen"},
            "medicine": ["Wood", "Water"],
            "taboo": ["Metal", "Earth"],
            "favorable_elements": ["Wood", "Water"],
            "unfavorable_elements": ["Metal", "Earth"],
            "neutral_elements": [],
            "spectrum_tier": "Strong",
        }
        self.mock_root = {"dm_root_impact": 5, "generative_root_impact": 5, "elemental_root_impact": 0}
        self.mock_interactions = {"total_friction": -2, "released_elements": [], "stem_combo_modifiers": []}
        self.mock_medicine = {"average_potency": 8.0}
        self.mock_risk = {"total_risk_penalty": 0}
        self.mock_geju = {"ge_ju": {"tier": "Common"}, "structural_bonus": 0}
        self.mock_month = {"branch": "Yin", "ge_ju_alignment_mod": 0, "month_name": "Tiger"}
        self.mock_annual = {"stem": "Bing", "branch": "Wu"}
        self.strength_profile = {"tier": "Strong", "continuous_score": 65.0, "dsi_tier_scalar": 1.0}
        self.inputs = {"strength_profile": self.strength_profile, "domain_focus": "career"}

    def _make_macro(self, era_ceiling=80.0, era_label="Neutral Era"):
        """Create macro results with configurable era ceiling."""
        return {
            "macro_environmental_scan": {
                "decade_data": {"stem_impact": 0, "branch_impact": 0},
                "annual_data": {"tai_sui_impact": 0, "stem_impact": 0},
                "void_audit": {"is_void_active": False},
                "era_block": {
                    "era_element": "Metal",
                    "era_label": era_label,
                    "era_ceiling": era_ceiling,
                    "era_medicine_ratio": 0.0,
                },
            }
        }

    def test_ji_shen_era_caps_score_at_71(self):
        """Test 3: Ji Shen era score cannot exceed 71 regardless of
        medicine month input."""
        macro = self._make_macro(era_ceiling=71.0, era_label="Hostile Era")

        # Pump medicine potency to max
        medicine_max = {"average_potency": 100.0}

        results = calculate_composite_score(
            self.mock_profile,
            root_results=self.mock_root,
            interaction_results=self.mock_interactions,
            medicine_results=medicine_max,
            risk_results=self.mock_risk,
            ge_ju_results=self.mock_geju,
            month_data=self.mock_month,
            macro_results=macro,
            annual_pillar=self.mock_annual,
            inputs=self.inputs,
        )

        self.assertLessEqual(
            results["composite_score"], 71.0,
            f"Ji Shen era score {results['composite_score']} exceeds ceiling 71"
        )

    def test_structural_noise_capped_at_5(self):
        """Test 4: structural noise alone cannot move score by more than 5."""
        macro = self._make_macro(era_ceiling=80.0)

        # Extreme structural noise scenario: max friction, root, phase
        extreme_root = {"dm_root_impact": 10, "generative_root_impact": 10, "elemental_root_impact": 10}
        extreme_interactions = {
            "total_friction": 10,
            "released_elements": [],
            "stem_combo_modifiers": [
                {"type": "Combine"}, {"type": "Combine"}, {"type": "Combine"},
            ],
        }
        # Zero medicine so primary signal doesn't contribute
        zero_medicine = {"average_potency": 0.0}

        results = calculate_composite_score(
            self.mock_profile,
            root_results=extreme_root,
            interaction_results=extreme_interactions,
            medicine_results=zero_medicine,
            risk_results=self.mock_risk,
            ge_ju_results=self.mock_geju,
            month_data=self.mock_month,
            macro_results=macro,
            annual_pillar=self.mock_annual,
            inputs=self.inputs,
        )

        # At neutral climate (dy=0, ann=0):
        # primary_signal = (12.5 + 0) * 1.0 * 1.0 = 12.5
        # noise_clamped = max +5
        # raw = 30 + 15 + 12.5 + 5 = 62.5
        # So structural noise adds at most 5 from neutral 57.5
        trace = results["calculation_trace"]
        self.assertLessEqual(abs(trace.get("structural_noise_raw", 0)), 100,
                             "Raw noise can be large")
        # But the actual score impact is bounded
        self.assertLessEqual(results["composite_score"], 62.5,
                             f"Score {results['composite_score']} exceeds neutral+5 from noise alone")


if __name__ == "__main__":
    unittest.main()
