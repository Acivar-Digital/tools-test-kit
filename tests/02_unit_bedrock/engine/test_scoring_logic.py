import logging
import unittest

from src.engine.module8_scoring import calculate_composite_score

# Disable logging during tests
logging.basicConfig(level=logging.CRITICAL)

class TestV29Scoring(unittest.TestCase):
    def setUp(self):
        self.mock_profile = {
            "name": "Test User",
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Bing", "branch": "Yin"},
            "year_pillar": {"stem": "Yi", "branch": "Hai"},
            "hour_pillar": {"stem": "Ding", "branch": "Mao"},
            "da_yun_pillar": {"stem": "Gui", "branch": "Hai"},
            "medicine": ["Wood", "Water"],
            "taboo": ["Metal", "Earth"],
            "spectrum_tier": "Strong"
        }
        self.mock_root = {"dm_root_impact": 5, "generative_root_impact": 5, "elemental_root_impact": 0}
        self.mock_interactions = {"total_friction": -2, "released_elements": [], "stem_combo_modifiers": []}
        self.mock_medicine = {"average_potency": 8.0}
        self.mock_risk = {"total_risk_penalty": 0}
        self.mock_geju = {"ge_ju": {"tier": "Common"}, "structural_bonus": 0}
        self.mock_month = {"branch": "Yin", "ge_ju_alignment_mod": 0, "month_name": "Tiger"}
        self.mock_macro = {
            "macro_environmental_scan": {
                "decade_data": {"stem_impact": 0, "branch_impact": 0},
                "annual_data": {"tai_sui_impact": 0, "stem_impact": 0},
                "void_audit": {"is_void_active": False}
            }
        }
        self.mock_annual = {"stem": "Bing", "branch": "Wu"}

    def test_scoring_with_spectrum(self):
        """Verify scoring works with V29 spectrum tier logic."""
        strength_profile = {
            "tier": "Strong",
            "continuous_score": 65.0,
            "dsi_tier_scalar": 1.0
        }
        inputs = {"strength_profile": strength_profile, "domain_focus": "career"}

        results = calculate_composite_score(
            self.mock_profile,
            root_results=self.mock_root,
            interaction_results=self.mock_interactions,
            medicine_results=self.mock_medicine,
            risk_results=self.mock_risk,
            ge_ju_results=self.mock_geju,
            month_data=self.mock_month,
            macro_results=self.mock_macro,
            annual_pillar=self.mock_annual,
            inputs=inputs,
        )

        self.assertIn("composite_score", results)
        self.assertEqual(results["strength_profile_used"], "Strong")

    def test_enforce_v29_requirements(self):
        """Verify that calling without strength_profile now raises a hard ValueError (V29 Enforcement)."""
        with self.assertRaisesRegex(ValueError, "V29 Error"):
            calculate_composite_score(
                self.mock_profile,
                root_results=self.mock_root,
                interaction_results=self.mock_interactions,
                medicine_results=self.mock_medicine,
                risk_results=self.mock_risk,
                ge_ju_results=self.mock_geju,
                month_data=self.mock_month,
                macro_results=self.mock_macro,
                annual_pillar=self.mock_annual,
                inputs={},
            )

if __name__ == "__main__":
    unittest.main()
