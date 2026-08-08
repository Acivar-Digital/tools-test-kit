import logging
import unittest

from src.engine.orchestrator import run_full_engine

# Disable logging during tests
logging.basicConfig(level=logging.CRITICAL)

class TestV29Orchestrator(unittest.TestCase):
    def setUp(self):
        self.profile = {
            "name": "V29 Test User",
            "gender": "M",
            "age": 35,
            "year_pillar": {"stem": "Bing", "branch": "Wu"},
            "month_pillar": {"stem": "Geng", "branch": "Zi"},
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "hour_pillar": {"stem": "Ding", "branch": "Mao"},
            "da_yun_pillar": {"stem": "Xin", "branch": "Chou"},
            "medicine": ["Wood", "Water"],
            "taboo": ["Metal", "Earth"],
            "domain_focus": "Career",
            "spectrum_tier": "Neutral",
            "strength_profile": {"tier": "Neutral", "continuous_score": 0.0}
        }

    def test_orchestrator_v29_payload(self):
        """Verify the full engine run returns the V29 deterministic keys."""
        # Run for Month 0 (Feb)
        results = run_full_engine(self.profile, 0)

        module_8 = results["engine_outputs"]["module_8"]
        module_11 = results["engine_outputs"]["module_11"]

        # Check for Log-Odds keys in module 11
        self.assertIn("event_probabilities", module_11)
        self.assertIn("is_transition_period", module_11)

        # Check for Gate keys in module 8
        self.assertIn("composite_score", module_8)
        self.assertIn("calculation_trace", module_8)
        self.assertIn("components", module_8)

        # Verify retirement of legacy keys
        self.assertNotIn("monthly_probability_percent", module_8)
        self.assertNotIn("expected_utility", module_8)

if __name__ == "__main__":
    unittest.main()
