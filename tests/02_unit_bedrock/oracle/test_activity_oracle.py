"""
Unit tests for the Activity Oracle deterministic scoring engine.
"""

from src.engine.activity_oracle import ACTIVITIES, score_day


def _make_profile(
    dm_stem="Yi",
    dm_branch="Mao",
    fav=None,
    unfav=None,
    neutral=None,
    gender="M",
    day_stem_stream="Jia Mao",
):
    return {
        "gender": gender,
        "day_pillar": {"stem": dm_stem, "branch": dm_branch},
        "year_pillar": {"stem": "Bing", "branch": "Wu"},
        "month_pillar": {"stem": "Xin", "branch": "Mao"},
        "hour_pillar": {"stem": "Ren", "branch": "Chen"},
        "favorable_elements": fav or ["Fire", "Earth"],
        "unfavorable_elements": unfav or ["Water", "Wood"],
        "neutral_elements": neutral or ["Metal"],
        "day_stem_stream": day_stem_stream,
    }


class TestScoreDayStructure:
    def test_returns_all_activities(self):
        profile = _make_profile()
        result = score_day({"stem": "Wu", "branch": "Chen"}, profile)
        assert "activities" in result
        for act in ACTIVITIES:
            assert act in result["activities"]
            assert "score" in result["activities"][act]
            assert "reason" in result["activities"][act]
            assert "verdict" in result["activities"][act]

    def test_score_bounds(self):
        profile = _make_profile()
        result = score_day({"stem": "Wu", "branch": "Chen"}, profile)
        for act in ACTIVITIES:
            sc = result["activities"][act]["score"]
            assert -20 <= sc <= 20

    def test_verdict_categories(self):
        profile = _make_profile()
        result = score_day({"stem": "Wu", "branch": "Chen"}, profile)
        valid_verdicts = {"Peak", "Excellent", "Favorable", "Neutral", "Caution", "Avoid", "Strike"}
        for act in ACTIVITIES:
            assert result["activities"][act]["verdict"] in valid_verdicts


class TestTravelScoring:
    def test_traveling_star_bonus(self):
        # Shen is a traveling star
        profile = _make_profile(dm_stem="Jia", dm_branch="Zi")
        result = score_day({"stem": "Geng", "branch": "Shen"}, profile)
        travel = result["activities"]["travel"]
        assert travel["score"] > 0
        assert "Traveling Horse star" in travel["reason"]

    def test_clash_penalty(self):
        # Mao clashes with You
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao")
        result = score_day({"stem": "Xin", "branch": "You"}, profile)
        travel = result["activities"]["travel"]
        # Clash with natal day branch should reduce score
        assert travel["score"] < 5


class TestJobInterviewScoring:
    def test_officer_day(self):
        # For Yi DM, Geng = Direct Officer
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao")
        result = score_day({"stem": "Geng", "branch": "Chen"}, profile)
        iv = result["activities"]["job_interview"]
        assert iv["score"] >= 10
        assert "Direct Officer" in iv["reason"]

    def test_unfavorable_element_penalty(self):
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao", unfav=["Metal"], fav=["Fire"])
        result = score_day({"stem": "Geng", "branch": "Shen"}, profile)
        iv = result["activities"]["job_interview"]
        # Metal is unfavorable, should drag score down despite officer star
        assert "Unfavorable element" in iv["reason"]


class TestLoveScoring:
    def test_peach_blossom_day(self):
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao", gender="M")
        result = score_day({"stem": "Ding", "branch": "Wu"}, profile)
        love = result["activities"]["love"]
        assert "Peach blossom" in love["reason"]
        assert love["score"] > 0

    def test_gender_wealth_for_men(self):
        # For Yi DM, Wu = Direct Wealth
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao", gender="M")
        result = score_day({"stem": "Wu", "branch": "Chen"}, profile)
        love = result["activities"]["love"]
        assert "Direct Wealth" in love["reason"] or love["score"] >= 5

    def test_gender_officer_for_women(self):
        # For Yi DM, Geng = Direct Officer
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao", gender="F")
        result = score_day({"stem": "Geng", "branch": "Shen"}, profile)
        love = result["activities"]["love"]
        assert "Direct Officer" in love["reason"] or love["score"] >= 5


class TestSpeculationScoring:
    def test_indirect_wealth_day(self):
        # For Yi DM, Ji = Indirect Wealth
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao")
        result = score_day({"stem": "Ji", "branch": "Wei"}, profile)
        spec = result["activities"]["speculation"]
        assert spec["score"] >= 10
        assert "Indirect Wealth" in spec["reason"]


class TestStudyScoring:
    def test_resource_day(self):
        # For Yi DM, Ren = Direct Resource (Water produces Wood)
        profile = _make_profile(dm_stem="Yi", dm_branch="Mao")
        result = score_day({"stem": "Ren", "branch": "Zi"}, profile)
        study = result["activities"]["study"]
        assert study["score"] >= 6
        assert "Resource" in study["reason"]
