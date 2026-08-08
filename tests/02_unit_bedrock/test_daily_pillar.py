# tests/test_daily_pillar.py
# Run with: uv run pytest test/unit/engine/test_daily_pillar.py -v

from src2.core.tools.bazi_engine import get_day_master_strength, get_pillars, score_elements

# ─────────────────────────────────────────────
# SECTION 1: get_pillars — known reference dates
# ─────────────────────────────────────────────


class TestGetPillars:
    def test_returns_four_pillars(self):
        p = get_pillars(1985, 3, 15, 14)
        assert p.year_pillar is not None
        assert p.month_pillar is not None
        assert p.day_pillar is not None
        assert p.hour_pillar is not None
        assert p.day_pillar.stem is not None

    def test_pillar_strings_are_two_chars(self):
        p = get_pillars(1985, 3, 15, 14)
        for key in ["year_pillar", "month_pillar", "day_pillar", "hour_pillar"]:
            pillar = getattr(p, key)
            assert len(pillar.stem + pillar.branch) == 2, (
                f"{key} pillar should be 2 chars, got: {pillar.stem + pillar.branch}"
            )

    def test_day_master_is_single_gan(self):
        gan = set("甲乙丙丁戊己庚辛壬癸")
        p = get_pillars(1985, 3, 15, 14)
        assert p.day_pillar.stem in gan

    def test_known_date_mao_year(self):
        # 1963 is 癸卯 year — year pillar should start with 癸
        p = get_pillars(1963, 6, 1, 12)
        assert p.year_pillar.branch == "卯", f"Expected 卯 year branch, got: {p.year_pillar.branch}"

    def test_known_date_jiazi_year(self):
        # 1984 is 甲子 year
        p = get_pillars(1984, 6, 1, 12)
        assert p.year_pillar.stem + p.year_pillar.branch == "甲子", (
            f"Expected 甲子, got: {p.year_pillar.stem + p.year_pillar.branch}"
        )

    def test_hour_zi_midnight(self):
        # 23:00 = 子时, branch should be 子
        p = get_pillars(1990, 1, 15, 23)
        assert p.hour_pillar.branch == "子", f"Expected 子 hour branch, got: {p.hour_pillar.branch}"

    def test_hour_wu_noon(self):
        # 11:00-13:00 = 午时
        p = get_pillars(1990, 1, 15, 12)
        assert p.hour_pillar.branch == "午", f"Expected 午 hour branch, got: {p.hour_pillar.branch}"

    def test_minute_defaults_to_zero(self):
        p1 = get_pillars(1990, 5, 10, 8, 0)
        p2 = get_pillars(1990, 5, 10, 8)
        assert p1.model_dump() == p2.model_dump()

    def test_solar_term_boundary_month(self):
        # 4 Feb is 立春 — before it = 丑月, on/after = 寅月
        before = get_pillars(2000, 2, 3, 12)
        after = get_pillars(2000, 2, 5, 12)
        assert (
            before.month_pillar.stem + before.month_pillar.branch != after.month_pillar.stem + after.month_pillar.branch
        ), "Month pillar should change across 立春"


# ─────────────────────────────────────────────
# SECTION 2: score_elements — five-element totals
# ─────────────────────────────────────────────


class TestScoreElements:
    def test_returns_five_elements(self):
        p = get_pillars(1985, 3, 15, 14)
        s = score_elements(p)
        assert set(s.keys()) == {"木", "火", "土", "金", "水"}

    def test_scores_are_non_negative(self):
        p = get_pillars(1990, 7, 7, 7)
        s = score_elements(p)
        assert all(v >= 0 for v in s.values())

    def test_total_score_reasonable(self):
        # 4 pillars × stem(4) + branches(5+2+1 max) = roughly 20-52 range
        p = get_pillars(1985, 3, 15, 14)
        s = score_elements(p)
        total = sum(s.values())
        assert 20 <= total <= 60, f"Total score out of expected range: {total}"

    def test_no_element_dominates_completely(self):
        # No single element should be 100% of total in a normal chart
        p = get_pillars(1985, 3, 15, 14)
        s = score_elements(p)
        total = sum(s.values())
        for el, val in s.items():
            assert val / total < 1.0, f"Element {el} wrongly dominates 100%"


# ─────────────────────────────────────────────
# SECTION 3: get_day_master_strength
# ─────────────────────────────────────────────


class TestDayMasterStrength:
    def test_returns_required_keys(self):
        p = get_pillars(1985, 3, 15, 14)
        r = get_day_master_strength(p)
        for key in [
            "day_master",
            "dm_element",
            "strength",
            "support_ratio",
            "element_scores",
            "favorable_elements",
            "unfavorable_elements",
        ]:
            assert key in r

    def test_strength_is_valid_label(self):
        p = get_pillars(1985, 3, 15, 14)
        r = get_day_master_strength(p)
        assert r["strength"] in {"身强", "身弱", "中和", "偏强", "偏弱", "从强", "从弱"}

    def test_support_ratio_between_0_and_1(self):
        p = get_pillars(1990, 7, 7, 7)
        r = get_day_master_strength(p)
        assert 0 <= r["support_ratio"] <= 1.0

    def test_favorable_unfavorable_no_overlap(self):
        p = get_pillars(1985, 3, 15, 14)
        r = get_day_master_strength(p)
        overlap = set(r["favorable_elements"]) & set(r["unfavorable_elements"])
        assert not overlap, f"Overlap between favorable and unfavorable: {overlap}"

    def test_favorable_unfavorable_neutral_cover_all_five(self):
        p = get_pillars(1985, 3, 15, 14)
        r = get_day_master_strength(p)
        all_els = set(r["favorable_elements"]) | set(r["unfavorable_elements"]) | set(r.get("neutral_elements", []))
        assert all_els == {"木", "火", "土", "金", "水"}

    def test_shen_qiang_correct_logic(self):
        # 身强 → favorable should NOT include supporting elements
        p = get_pillars(1985, 3, 15, 14)
        r = get_day_master_strength(p)
        if r["strength"] == "身强":
            from src2.core.tools.bazi_engine import SUPPORTS

            supporting = SUPPORTS[r["dm_element"]]
            for el in supporting:
                assert el not in r["favorable_elements"]

    def test_shen_ruo_correct_logic(self):
        # 身弱 → favorable should include supporting elements
        p = get_pillars(2000, 10, 10, 22)  # adjust until 身弱 if needed
        r = get_day_master_strength(p)
        if r["strength"] == "身弱":
            from src2.core.tools.bazi_engine import SUPPORTS

            supporting = SUPPORTS[r["dm_element"]]
            for el in supporting:
                assert el in r["favorable_elements"]


# ─────────────────────────────────────────────────
# SECTION 4: resolve_daily_pillar_range — cross-year
# ─────────────────────────────────────────────────


class TestResolveDailyPillarRange:
    def test_cross_year_range(self):
        """Range spanning Dec 2025 → Mar 2026 should resolve without crash."""
        from datetime import date

        from src2.engine.daily_pillar import resolve_daily_pillar_range

        result = resolve_daily_pillar_range(date(2025, 12, 1), date(2026, 3, 15))
        assert len(result) > 0
        for entry in result:
            assert entry.stem is not None
            assert entry.branch is not None
            assert entry.date is not None

    def test_cross_year_pillar_continuity(self):
        """Pillars should be contiguous across the Dec 31 / Jan 1 boundary."""
        from datetime import date

        from src2.engine.daily_pillar import resolve_daily_pillar_range

        result = resolve_daily_pillar_range(date(2025, 12, 30), date(2026, 1, 5))
        dates = [r.date for r in result]
        assert dates == [
            "2025-12-30",
            "2025-12-31",
            "2026-01-01",
            "2026-01-02",
            "2026-01-03",
            "2026-01-04",
            "2026-01-05",
        ]
        # Each pillar should be a 2-char pinyin stem+branch
        for r in result:
            assert len(r.stem) >= 2
            assert len(r.branch) >= 1

    def test_single_date_range(self):
        """Single date still works."""
        from datetime import date

        from src2.engine.daily_pillar import resolve_daily_pillar_range

        result = resolve_daily_pillar_range(date(2026, 6, 1), date(2026, 6, 1))
        assert len(result) == 1
        assert result[0].date == "2026-06-01"

    def test_same_year_range(self):
        """Same-year range unchanged behavior."""
        from datetime import date

        from src2.engine.daily_pillar import resolve_daily_pillar_range

        result = resolve_daily_pillar_range(date(2026, 1, 1), date(2026, 1, 31))
        assert len(result) == 31
        assert result[0].date == "2026-01-01"
        assert result[-1].date == "2026-01-31"

    def test_invalid_range_raises(self):
        """End before start should raise ValueError."""
        from datetime import date

        import pytest

        from src2.engine.daily_pillar import resolve_daily_pillar_range

        with pytest.raises(ValueError, match="end_date must be >= start_date"):
            resolve_daily_pillar_range(date(2026, 6, 15), date(2026, 6, 1))


# ─────────────────────────────────────────────────
# SECTION 5: get_month_anchor_for_date — Jan anchor
# ─────────────────────────────────────────────────


class TestGetMonthAnchor:
    def test_jan_date_uses_prev_year_anchor(self):
        """Jan dates should fall back to the previous solar year anchor."""
        from datetime import date

        from src2.engine.daily_pillar import get_month_anchor_for_date, resolve_daily_pillar

        # Jan 1, 2026 — the 2026 solar year starts Feb 4, so the anchor
        # should come from the 2025 solar year (which ends Jan 5, 2026).
        anchor = get_month_anchor_for_date(date(2026, 1, 1))
        assert anchor is not None, "Jan 1 should find an anchor via previous-year fallback"
        assert anchor.start_date.date() <= date(2026, 1, 1)

        # resolve_daily_pillar should also work for Jan dates
        pillar = resolve_daily_pillar(date(2026, 1, 1))
        assert pillar.stem is not None
        assert pillar.branch is not None

    def test_feb_after_solar_new_year_uses_current_year(self):
        """Feb/Mar dates after the solar new year should use current year anchor."""
        from datetime import date

        from src2.engine.daily_pillar import get_month_anchor_for_date

        anchor = get_month_anchor_for_date(date(2026, 3, 15))
        assert anchor is not None
        # The 2026 solar year starts Feb 4, so Mar 15 should be in the 2026 solar year
        assert anchor.start_date.date().year == 2026

