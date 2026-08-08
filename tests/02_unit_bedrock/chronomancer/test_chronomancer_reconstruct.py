from src.bot.chronomancer_handler import _parse_pillar_string


class TestChronomancerReconstruct:
    def test_parse_pillar_string_with_space(self):
        assert _parse_pillar_string("Ding Si") == {"stem": "Ding", "branch": "Si"}
        assert _parse_pillar_string("Jia Zi") == {"stem": "Jia", "branch": "Zi"}

    def test_parse_pillar_string_no_space(self):
        # Fallback for Chinese or concatenated strings
        assert _parse_pillar_string("甲子") == {"stem": "甲", "branch": "子"}
        assert _parse_pillar_string("丙寅") == {"stem": "丙", "branch": "寅"}

    def test_parse_pillar_string_dict(self):
        # Should return as is if already a dict
        d = {"stem": "Geng", "branch": "Shen"}
        assert _parse_pillar_string(d) == d

    def test_parse_pillar_string_invalid(self):
        assert _parse_pillar_string(None) is None
        assert _parse_pillar_string("Unknown") is None
        assert _parse_pillar_string("") is None
        assert _parse_pillar_string("A") is None
