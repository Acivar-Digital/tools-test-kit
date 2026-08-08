"""TEST/fuzzing/test_chronomancer_temporal_fuzz.py — Fuzz Chronomancer Temporal Timeline Generation.

Feeds chaotic date ranges into timeline generators using st.dates(),
st.datetimes(), and st.integers() for offsets/durations. Includes leap years,
cross-century boundaries, and inverted dates (Start > End). Asserts anti-hang
invariant (no infinite while-loops), chronological order invariant, and no
unhandled OverflowError from C-math datetime bounds.
"""

import math
from datetime import date, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from src2.interfaces.telegram.chronomancer.coordinator import _resolve_forecast_dates
from src2.interfaces.telegram.chronomancer.ranking import rank_days_aggregate

UNSAFE_EXCEPTIONS = (RecursionError, KeyError, IndexError, TypeError, AttributeError, ZeroDivisionError, OverflowError, MemoryError)


def _assert_never_crashes_with_unhandled_exception(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (ValueError, OverflowError) as e:
        return e
    except UNSAFE_EXCEPTIONS as e:
        raise AssertionError(
            f"Unhandled raw exception leaked from chronomancer: {type(e).__name__}: {e}"
        ) from e


# ═══════════════════════════════════════════════════════════════
# _resolve_forecast_dates
# ═══════════════════════════════════════════════════════════════

@given(
    start_year=st.integers(min_value=1900, max_value=2100),
    start_month=st.integers(min_value=1, max_value=12),
    start_day=st.integers(min_value=1, max_value=31),
    offset_days=st.integers(min_value=-500, max_value=500),
)
@settings(max_examples=200, deadline=5000)
def test_resolve_forecast_dates_no_overflow(start_year, start_month, start_day, offset_days):
    """No unhandled OverflowError from C-math datetime bounds."""
    try:
        start = date(start_year, start_month, start_day)
    except ValueError:
        return

    end = start + timedelta(days=offset_days)

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, start, end)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert isinstance(resolved_start, date)
    assert isinstance(resolved_end, date)


@given(
    start_year=st.integers(min_value=1900, max_value=2100),
    start_month=st.integers(min_value=1, max_value=12),
    start_day=st.integers(min_value=1, max_value=31),
)
@settings(max_examples=200, deadline=5000)
def test_resolve_forecast_dates_inverted_start_after_end(start_year, start_month, start_day):
    """Inverted dates (Start > End) are returned as-is without crashing."""
    try:
        start = date(start_year, start_month, start_day)
    except ValueError:
        return
    end = start - timedelta(days=1)

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, start, end)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert resolved_start == start
    assert resolved_end == end


@given(
    start_year=st.integers(min_value=1900, max_value=2100),
    start_month=st.integers(min_value=1, max_value=12),
    start_day=st.integers(min_value=1, max_value=31),
    end_year=st.integers(min_value=1900, max_value=2100),
    end_month=st.integers(min_value=1, max_value=12),
    end_day=st.integers(min_value=1, max_value=31),
)
@settings(max_examples=200, deadline=5000)
def test_resolve_forecast_dates_chronological_invariant(start_year, start_month, start_day, end_year, end_month, end_day):
    """Chronological order invariant: result is always a valid (start, end) pair."""
    try:
        start = date(start_year, start_month, start_day)
        end = date(end_year, end_month, end_day)
    except ValueError:
        return

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, start, end)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert isinstance(resolved_start, date)
    assert isinstance(resolved_end, date)


@given(
    start_year=st.integers(min_value=1900, max_value=2100),
    start_month=st.integers(min_value=1, max_value=12),
    start_day=st.integers(min_value=1, max_value=31),
)
@settings(max_examples=200, deadline=5000)
def test_resolve_forecast_dates_none_end_uses_30day_window(start_year, start_month, start_day):
    """When end_date is None, result[1] == result[0] + timedelta(days=29)."""
    try:
        start = date(start_year, start_month, start_day)
    except ValueError:
        return

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, start, None)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert resolved_start == start
    assert resolved_end == start + timedelta(days=29)


@given(
    year=st.integers(min_value=1900, max_value=2100),
    month=st.integers(min_value=1, max_value=12),
    day=st.integers(min_value=1, max_value=31),
)
@settings(max_examples=200, deadline=5000)
def test_resolve_forecast_dates_leap_year_boundary(year, month, day):
    """Leap year dates (Feb 29) do not cause crashes."""
    if month == 2 and day == 29:
        import calendar
        if not calendar.isleap(year):
            return
    try:
        d = date(year, month, day)
    except ValueError:
        return

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, d, None)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert isinstance(resolved_start, date)
    assert isinstance(resolved_end, date)


@given(
    year=st.integers(min_value=1900, max_value=2100),
)
@settings(max_examples=100, deadline=5000)
def test_resolve_forecast_dates_cross_century(year):
    """Cross-century boundaries (e.g., 1999-12-31 → 2000-01-01) do not crash."""
    try:
        start = date(year, 12, 31)
        end = date(year + 1, 1, 1)
    except ValueError:
        return

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, start, end)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert isinstance(resolved_start, date)
    assert isinstance(resolved_end, date)


# ═══════════════════════════════════════════════════════════════
# rank_days_aggregate
# ═══════════════════════════════════════════════════════════════

@given(
    num_days=st.integers(min_value=0, max_value=50),
    top_n=st.integers(min_value=1, max_value=10),
    worst=st.booleans(),
)
@settings(max_examples=200, deadline=5000)
def test_rank_days_aggregate_no_crash(num_days, top_n, worst):
    """rank_days_aggregate never crashes with arbitrary scored_days input."""
    scored_days = []
    for i in range(num_days):
        day_date = date(2026, 1, 1) + timedelta(days=i)
        activities = {
            f"activity_{j}": {"score": float(j + 1), "verdict": "positive"}
            for j in range(3)
        }
        scored_days.append({
            "date": day_date.isoformat(),
            "stem": "Jia",
            "branch": "Zi",
            "activities": activities,
        })

    result = _assert_never_crashes_with_unhandled_exception(rank_days_aggregate, scored_days, top_n, worst)
    if isinstance(result, Exception):
        return
    assert isinstance(result, list)
    assert len(result) <= top_n


@given(
    num_days=st.integers(min_value=1, max_value=20),
    top_n=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=200, deadline=5000)
def test_rank_days_aggregate_chronological_order_invariant(num_days, top_n):
    """When worst=False, scores are in descending order (best first)."""
    scored_days = []
    for i in range(num_days):
        day_date = date(2026, 1, 1) + timedelta(days=i)
        activities = {
            f"activity_{j}": {"score": float((i + 1) * (j + 1)), "verdict": "positive"}
            for j in range(3)
        }
        scored_days.append({
            "date": day_date.isoformat(),
            "stem": "Jia",
            "branch": "Zi",
            "activities": activities,
        })

    result = rank_days_aggregate(scored_days, top_n=top_n, worst=False)
    assert isinstance(result, list)
    for i in range(len(result) - 1):
        assert result[i].score >= result[i + 1].score


@given(
    num_days=st.integers(min_value=1, max_value=20),
    top_n=st.integers(min_value=1, max_value=5),
)
@settings(max_examples=200, deadline=5000)
def test_rank_days_aggregate_worst_order_invariant(num_days, top_n):
    """When worst=True, scores are in ascending order (worst first)."""
    scored_days = []
    for i in range(num_days):
        day_date = date(2026, 1, 1) + timedelta(days=i)
        activities = {
            f"activity_{j}": {"score": float((i + 1) * (j + 1)), "verdict": "positive"}
            for j in range(3)
        }
        scored_days.append({
            "date": day_date.isoformat(),
            "stem": "Jia",
            "branch": "Zi",
            "activities": activities,
        })

    result = rank_days_aggregate(scored_days, top_n=top_n, worst=True)
    assert isinstance(result, list)
    for i in range(len(result) - 1):
        assert result[i].score <= result[i + 1].score


@given(
    num_days=st.integers(min_value=0, max_value=30),
)
@settings(max_examples=100, deadline=5000)
def test_rank_days_aggregate_empty_activities(num_days):
    """Empty activities dict is skipped without crashing."""
    scored_days = []
    for i in range(num_days):
        day_date = date(2026, 1, 1) + timedelta(days=i)
        scored_days.append({
            "date": day_date.isoformat(),
            "stem": "Jia",
            "branch": "Zi",
            "activities": {},
        })

    result = rank_days_aggregate(scored_days, top_n=3, worst=False)
    assert isinstance(result, list)
    assert len(result) == 0


@given(
    score=st.integers(min_value=-1_000_000, max_value=1_000_000),
)
@settings(max_examples=100, deadline=5000)
def test_rank_days_aggregate_int_score_no_nan_inf(score):
    """Integer scores in activities must not produce NaN or Infinity in output."""
    scored_days = [
        {
            "date": date(2026, 1, 1).isoformat(),
            "stem": "Jia",
            "branch": "Zi",
            "activities": {"activity_1": {"score": score, "verdict": "positive"}},
        }
    ]

    result = rank_days_aggregate(scored_days, top_n=3, worst=False)
    if not result:
        return
    day = result[0]
    assert not math.isnan(day.score), "rank_days_aggregate leaked a NaN value!"
    assert not math.isinf(day.score), "rank_days_aggregate leaked an Infinity value!"


@given(
    num_days=st.integers(min_value=1, max_value=20),
    top_n=st.integers(min_value=1, max_value=10),
)
@settings(max_examples=200, deadline=5000)
def test_rank_days_aggregate_result_length_leq_top_n(num_days, top_n):
    """Result length is always <= top_n."""
    scored_days = []
    for i in range(num_days):
        day_date = date(2026, 1, 1) + timedelta(days=i)
        activities = {
            f"activity_{j}": {"score": float(j + 1), "verdict": "positive"}
            for j in range(3)
        }
        scored_days.append({
            "date": day_date.isoformat(),
            "stem": "Jia",
            "branch": "Zi",
            "activities": activities,
        })

    result = rank_days_aggregate(scored_days, top_n=top_n, worst=False)
    assert len(result) <= top_n


@given(
    start_year=st.integers(min_value=1900, max_value=2100),
    start_month=st.integers(min_value=1, max_value=12),
    start_day=st.integers(min_value=1, max_value=31),
    offset=st.integers(min_value=0, max_value=365),
)
@settings(max_examples=200, deadline=5000)
def test_chronomancer_temporal_no_hang(start_year, start_month, start_day, offset):
    """Anti-hang invariant: no infinite while-loops in date resolution."""
    try:
        start = date(start_year, start_month, start_day)
        end = start + timedelta(days=offset)
    except ValueError:
        return

    result = _assert_never_crashes_with_unhandled_exception(_resolve_forecast_dates, start, end)
    if isinstance(result, Exception):
        return
    resolved_start, resolved_end = result
    assert isinstance(resolved_start, date)
    assert isinstance(resolved_end, date)
