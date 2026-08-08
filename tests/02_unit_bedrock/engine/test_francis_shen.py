import unittest

from src.engine.shen_classifier import classify_shen


class TestTesterShen(unittest.TestCase):
    def setUp(self):
        # Test Profile's profile as provided by the user
        # 1) Year: Ding Si, 2) Month: Jia Chen, 3) Day: Yi Mao, 4) Hour: Ren Wu
        self.profile = {
            "name": "Test Profile",
            "gender": "M",
            "year_pillar": {"stem": "Ding", "branch": "Si"},
            "month_pillar": {"stem": "Jia", "branch": "Chen"},
            "day_pillar": {"stem": "Yi", "branch": "Mao"},
            "hour_pillar": {"stem": "Ren", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Ji", "branch": "Hai"},
            "favorable_elements": ["Fire", "Earth"],
            "unfavorable_elements": ["Water", "Wood"],
            "neutral_elements": ["Metal"],
            "spectrum_tier": "Strong"
        }

    def test_yong_shen_user_override(self):
        """Test Case 1: Uses manual inputs (Override Mode)"""
        dm_stem = self.profile["day_pillar"]["stem"]
        spectrum_tier = self.profile["spectrum_tier"]
        user_fav = self.profile.get("favorable_elements", [])
        user_unfav = self.profile.get("unfavorable_elements", [])

        shen_profile = classify_shen(
            dm_stem=dm_stem,
            spectrum_tier=spectrum_tier,
            user_fav=user_fav,
            user_unfav=user_unfav
        )

        self.assertEqual(shen_profile["source"], "user_override")
        self.assertEqual(shen_profile["yong_shen"], ["Fire"])
        print(f"\n[Test 1 - Override] Yong Shen: {shen_profile['yong_shen']}")

    def test_yong_shen_engine_derived(self):
        """Test Case 2: Uses only birth data (Autonomous Mode)"""
        dm_stem = self.profile["day_pillar"]["stem"]
        spectrum_tier = self.profile["spectrum_tier"]

        # Passing empty lists forces engine derivation
        shen_profile = classify_shen(
            dm_stem=dm_stem,
            spectrum_tier=spectrum_tier,
            user_fav=[],
            user_unfav=[]
        )

        self.assertEqual(shen_profile["source"], "engine_derived")
        # For a Strong Yi Wood, the engine picks Output (Fire) as primary medicine
        self.assertEqual(shen_profile["yong_shen"], ["Fire"])
        print(f"[Test 2 - Autonomous] Yong Shen: {shen_profile['yong_shen']}")
        print(f"Outcome: Both modes selected {shen_profile['yong_shen']} as Yong Shen. The system is consistent!")


if __name__ == "__main__":
    unittest.main()
