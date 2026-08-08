"""
Unit tests verifying the 4 metaphysical upgrades implemented from the engine audit.
"""

from src.engine.module0_geju import _check_vibrant_structure
from src.engine.module2_root import calculate_root
from src.engine.module3_interaction import calculate_interactions
from src.engine.module7_shen_sha import classify_star_activation


class TestAuditFixes:
    """Test suite for the 4 implemented audit upgrades."""

    def test_gap1_vibrant_structure_purity(self):
        """Gap 1: Vibrant Structure is suppressed by opposing stems or shattered by clashes."""
        # Pure Fire vibrant profile (Si-Wu-Wei Fire seasonal, Bing/Ding Fire stems)
        profile_pure = {
            "year_pillar": {"stem": "Bing", "branch": "Si"},
            "month_pillar": {"stem": "Ding", "branch": "Wu"},
            "day_pillar": {"stem": "Bing", "branch": "Wei"},
            "hour_pillar": {"stem": "Yi", "branch": "Mao"},
        }
        # Wu month (Fire is Wang/Prosperous)
        assert _check_vibrant_structure(profile_pure, "Wu") == "yan_shang_ge"

        # Harmony Fire vibrant profile (Yin-Wu-Xu Fire harmony, Bing/Ding stems)
        profile_harmony = {
            "year_pillar": {"stem": "Bing", "branch": "Yin"},
            "month_pillar": {"stem": "Ding", "branch": "Wu"},
            "day_pillar": {"stem": "Bing", "branch": "Xu"},
            "hour_pillar": {"stem": "Yi", "branch": "Mao"},
        }
        assert _check_vibrant_structure(profile_harmony, "Wu") == "yan_shang_ge"

        # Harmony Wood vibrant profile (Hai-Mao-Wei Wood harmony, Jia/Yi stems)
        profile_wood_harmony = {
            "year_pillar": {"stem": "Jia", "branch": "Hai"},
            "month_pillar": {"stem": "Yi", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Wei"},
            "hour_pillar": {"stem": "Ding", "branch": "Wu"},
        }
        assert _check_vibrant_structure(profile_wood_harmony, "Mao") == "qu_zhi_ge"

        # Suppressed by Water stem (Ren)
        profile_suppressed = {
            "year_pillar": {"stem": "Ren", "branch": "Si"}, # Ren is suppressive Water
            "month_pillar": {"stem": "Ding", "branch": "Wu"},
            "day_pillar": {"stem": "Bing", "branch": "Wei"},
            "hour_pillar": {"stem": "Yi", "branch": "Mao"},
        }
        assert _check_vibrant_structure(profile_suppressed, "Wu") is None

        # Shattered by clash (Zi clashing Wu)
        profile_shattered = {
            "year_pillar": {"stem": "Bing", "branch": "Si"},
            "month_pillar": {"stem": "Ding", "branch": "Wu"},
            "day_pillar": {"stem": "Bing", "branch": "Wei"},
            "hour_pillar": {"stem": "Yi", "branch": "Zi"}, # Zi shatters Wu anchor
        }
        assert _check_vibrant_structure(profile_shattered, "Wu") is None

    def test_gap2_peach_blossom_masking(self):
        """Gap 2: Peach Blossom is masked by Kong Wang, shattered by clash, or extinguished by both."""
        # Setup pure, masked, and shattered states
        # Peach Blossom for Zi day/year branch is You.
        # Xun Kong for Jia Zi day_stem_stream is "Xu", "Hai". No Kong Wang on You.
        natal_pure = {
            "day_stem_stream": "Jia Zi",
            "year_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Xin", "branch": "You"}, # You is Peach Blossom
            "day_pillar": {"stem": "Jia", "branch": "Zi"},
            "hour_pillar": {"stem": "Geng", "branch": "Chen"},
        }

        # Pure Peach Blossom
        res_pure = classify_star_activation(natal_pure, {}, {}, [])
        assert res_pure["activation_matrix"]["Tao Hua"]["state"] == "latent"

        # Masked Peach Blossom (sitting on Kong Wang)
        # Xun Kong for Jia Xu day_stem_stream is "Shen", "You". You is now in Kong Wang!
        natal_masked = {
            "day_stem_stream": "Jia Xu",
            "year_pillar": {"stem": "Jia", "branch": "Zi"},
            "month_pillar": {"stem": "Xin", "branch": "You"}, # You in Kong Wang
            "day_pillar": {"stem": "Jia", "branch": "Xu"},
            "hour_pillar": {"stem": "Geng", "branch": "Chen"},
        }
        res_masked = classify_star_activation(natal_masked, {}, {}, [])
        assert res_masked["activation_matrix"]["Tao Hua"]["state"] == "masked"

        # Shattered Peach Blossom (clashed by Mao)
        res_shattered = classify_star_activation(natal_pure, {}, {}, ["You"])
        assert res_shattered["activation_matrix"]["Tao Hua"]["state"] == "shattered"

        # Extinguished Peach Blossom (both masked and shattered)
        res_extinguished = classify_star_activation(natal_masked, {}, {}, ["You"])
        assert res_extinguished["activation_matrix"]["Tao Hua"]["state"] == "extinguished"

    def test_gap4_decade_annual_shadowing(self):
        """Gap 4: Annual clashes are blocked/shadowed by strong Decade combinations."""
        # Natal has Yin. Decade Luck brings Hai (forms Yin-Hai 6-combination).
        # Annual brings Shen (normally clashes Yin).
        profile = {
            "year_pillar": {"stem": "Jia", "branch": "Yin"},
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "day_pillar": {"stem": "Jia", "branch": "Chen"},
            "hour_pillar": {"stem": "Geng", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Ren", "branch": "Hai"}, # Decade combinations
        }
        month_data = {"branch": "Mao"}
        annual_pillar = {"stem": "Bing", "branch": "Shen"} # Annual clashing Shen

        res = calculate_interactions(profile, month_data, annual_pillar)
        m3_res = res["module_3_results"]

        # Find the clash between Annual Shen and Natal Yin
        clashes = [d for d in m3_res["active_disruptors"] if d["type"] == "Chong" and d["layer"] == "Annual"]
        assert len(clashes) > 0
        annual_clash = clashes[0]

        # Verify it is shadowed/protected, severity is 0, and not registered as clashed
        assert annual_clash["is_resolved"] is True
        assert annual_clash["severity"] == 0.0
        assert "Yin" not in m3_res["clashed_branches"]
        assert "Yin" in m3_res["locked_natal_branches"]

    def test_gap6_wet_dry_earth_rooting(self):
        """Gap 6: Earth Day Masters root differently in Wet vs Dry Earth."""
        # Earth DM (Wu) in Wet Earth (Chen)
        profile_wet = {
            "day_pillar": {"stem": "Wu", "branch": "Chen"}, # Wet Earth root
            "year_pillar": {"stem": "Wu", "branch": "Chen"},
            "month_pillar": {"stem": "Xin", "branch": "Mao"},
            "hour_pillar": {"stem": "Geng", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Gui", "branch": "Hai"},
            "medicine": ["Earth"],
            "taboo": ["Water"],
        }
        month_data = {"branch": "Mao"}
        annual_pillar = {"stem": "Bing", "branch": "Shen"}

        res_wet = calculate_root(profile_wet, month_data, annual_pillar)

        # Wu in Dry Earth (Xu)
        profile_dry = {
            "day_pillar": {"stem": "Wu", "branch": "Xu"}, # Dry Earth root
            "year_pillar": {"stem": "Wu", "branch": "Xu"},
            "month_pillar": {"stem": "Xin", "branch": "Mao"},
            "hour_pillar": {"stem": "Geng", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Gui", "branch": "Hai"},
            "medicine": ["Earth"],
            "taboo": ["Water"],
        }
        res_dry = calculate_root(profile_dry, month_data, annual_pillar)

        # Dry Earth provides positive root adjustment (+2 x 2 = +4), Wet Earth penalizes (-2 x 2 = -4)
        diff = res_dry["module_2_results"]["dm_root_impact"] - res_wet["module_2_results"]["dm_root_impact"]
        assert diff == 8  # +4 vs -4 is a difference of 8 (since both branches are processed)!

    def test_gap6_water_dm_multi_earth_balance(self):
        """Gap 6: Water Day Master is fortified by Wet Earth but weakened by Dry Earth, balancing correctly when both are present."""
        # Water DM (Ren) with Chen (Wet Earth) and Xu (Dry Earth)
        profile_balanced = {
            "day_pillar": {"stem": "Ren", "branch": "Chen"}, # Chen (Wet Earth, +2)
            "year_pillar": {"stem": "Ren", "branch": "Xu"},   # Xu (Dry Earth, -2)
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "hour_pillar": {"stem": "Geng", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Ren", "branch": "Zi"},
            "medicine": ["Water"],
            "taboo": ["Fire"],
        }
        month_data = {"branch": "Mao"}
        annual_pillar = {"stem": "Bing", "branch": "Shen"}

        res_balanced = calculate_root(profile_balanced, month_data, annual_pillar)

        # Since it has Chen (+2) and Xu (-2), the net adjustment from the two earth branches should be 0.
        # Let's compare with a profile that has only one Chen (Wet Earth, +2)
        profile_only_wet = {
            "day_pillar": {"stem": "Ren", "branch": "Chen"}, # Chen (+2)
            "year_pillar": {"stem": "Ren", "branch": "Mao"},  # Mao (Not Earth, 0)
            "month_pillar": {"stem": "Ji", "branch": "Mao"},
            "hour_pillar": {"stem": "Geng", "branch": "Wu"},
            "da_yun_pillar": {"stem": "Ren", "branch": "Zi"},
            "medicine": ["Water"],
            "taboo": ["Fire"],
        }
        res_only_wet = calculate_root(profile_only_wet, month_data, annual_pillar)

        # Balanced (+0) vs Only Wet (+2) difference is exactly 2.
        diff = res_only_wet["module_2_results"]["dm_root_impact"] - res_balanced["module_2_results"]["dm_root_impact"]
        assert diff == 2

    def test_gap6_weak_water_dm_fortification(self):
        """Gap 6: Weak Water Day Master is fortified by Wet Earth during annual/monthly transits."""
        # Weak Water DM (Ren) receiving Wet Earth transit (Chen)
        profile_weak_water = {
            "day_pillar": {"stem": "Ren", "branch": "Zi"},
            "year_pillar": {"stem": "Ren", "branch": "Zi"},
            "month_pillar": {"stem": "Ji", "branch": "Si"},
            "hour_pillar": {"stem": "Ji", "branch": "Si"},
            "da_yun_pillar": {"stem": "Wu", "branch": "Wu"},
            "medicine": ["Water"],
            "taboo": ["Fire"],
            "dm_strength_type": "Weak",
        }
        # Wet Earth Chen in annual transit
        annual_pillar = {"stem": "Jia", "branch": "Chen"}
        month_data = {"branch": "Si"}

        # Calculate root with a low continuous score to trigger weak-leaning path
        strength_profile = {"continuous_score": -50}
        res = calculate_root(
            profile_weak_water,
            month_data,
            annual_pillar,
            strength_profile=strength_profile
        )
        # Verify it got fortified (positive dm_root_impact from fortification)
        assert res["module_2_results"]["dm_root_impact"] > 0

