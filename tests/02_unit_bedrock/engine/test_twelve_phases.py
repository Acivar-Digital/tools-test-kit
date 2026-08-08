from src.engine.twelve_phases import get_dm_phase, get_phase_modifier


class TestTwelvePhases:
    def test_yang_stem_forward(self):
        # Jia starts at Hai
        assert get_dm_phase("Jia", "Hai") == "Chang Sheng"
        assert get_dm_phase("Jia", "Zi") == "Mu Yu"
        assert get_dm_phase("Jia", "Mao") == "Di Wang"

    def test_yin_stem_reverse(self):
        # Yi starts at Wu
        assert get_dm_phase("Yi", "Wu") == "Chang Sheng"
        assert get_dm_phase("Yi", "Si") == "Mu Yu"  # Reverse from Wu
        assert (
            get_dm_phase("Yi", "Yin") == "Di Wang"
        )  # Reverse from Wu: Wu(0), Si(1), Chen(2), Mao(3), Yin(4) -> Di Wang(4)

    def test_special_stems(self):
        # Wu follows Bing
        assert get_dm_phase("Wu", "Yin") == "Chang Sheng"
        # Ji follows Ding
        assert get_dm_phase("Ji", "You") == "Chang Sheng"

    def test_phase_modifiers(self):
        assert get_phase_modifier("Di Wang") == 5
        assert get_phase_modifier("Si") == -3
        assert get_phase_modifier("Unknown") == 0

    def test_unknown_stem(self):
        assert get_dm_phase("Invalid", "Zi") == "Unknown"
