"""Metamorphic fuzzing tests for timezone & absolute-time invariance.

Target: src2/engine/daily_pillar.py — ``resolve_daily_pillar_from_datetime``

Strategy:
  1. ``st.datetimes()`` generates an absolute UTC moment.
  2. That moment is converted to UTC+14 and UTC-12 (~26 h apart).
  3. Both localized datetimes are fed into the chart calculator.
  4. Properties asserted:
    (a) **Absolute Time Invariant** — chart_A MUST strictly equal chart_B.
    (b) **No OverflowError / unhandled crash** on timezone boundary math.

Reference timezone: GMT+8 (China Standard Time / Singapore Time), which is
the Bazi day-boundary standard.  ``resolve_daily_pillar_from_datetime``
normalizes every timezone-aware input to SGT before extracting the
calendar date, guaranteeing that the same absolute moment always maps
to the same daily pillar.
"""

from datetime import UTC, datetime, timedelta, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src2.engine.daily_pillar import (
    BRANCH_ORDER,
    STEM_ORDER,
    Pillar,
    resolve_daily_pillar,
    resolve_daily_pillar_from_datetime,
)

# ── Timezone constants ────────────────────────────────────────────────
# UTC is imported from datetime (Python 3.11+ alias).
SGT = timezone(timedelta(hours=8))            # Bazi reference (GMT+8)
TZ_PLUS_14 = timezone(timedelta(hours=14))    # Line Islands (Kiritimati)
TZ_MINUS_12 = timezone(timedelta(hours=-12))  # Baker / Howland Islands

# ── Strategies ────────────────────────────────────────────────────────
# Safe range: years with loaded solar-month data (2025–2027).
# The first Jieqi of 2025 is Feb 3, so the earliest supported SGT
# date is 2025-02-03.  The last solar month of 2027 starts Jan 6 2028,
# covering dates through 2028-01-07.  1-day margin on each end
# prevents boundary-crossing dates from landing outside the anchor data.
_SAFE_MIN = datetime(2025, 2, 4)
_SAFE_MAX = datetime(2027, 12, 30, 23, 59, 59)

safe_utc = st.datetimes(
    min_value=_SAFE_MIN,
    max_value=_SAFE_MAX,
).map(lambda dt: dt.replace(tzinfo=UTC))

# Full range: tests OverflowError handling at Python's datetime boundaries
# (year 1 / year 9999).
full_utc = st.datetimes(
    min_value=datetime(1, 1, 1),
    max_value=datetime(9999, 12, 31, 23, 59, 59, 999999),
).map(lambda dt: dt.replace(tzinfo=UTC))

# Exceptions considered recoverable — they signal *out-of-scope input*
# (unsupported year, impossible conversion), not an engine bug.
_RECOVERABLE = (ValueError, OverflowError)

# Exceptions that indicate a genuine engine bug and must never leak.
_UNSAFE = (
    RecursionError,
    KeyError,
    IndexError,
    TypeError,
    AttributeError,
    ZeroDivisionError,
    MemoryError,
)


def _invoke(func, *args):
    """Run *func*; return its result, or return the caught exception if
    recoverable.  Re-raise unsafe exceptions as AssertionError so the
    fuzzer fails loudly on genuine bugs.
    """
    try:
        return func(*args)
    except _RECOVERABLE as exc:
        return exc
    except _UNSAFE as exc:
        raise AssertionError(
            f"Unhandled {type(exc).__name__} leaked from engine: {exc!r}"
        ) from exc


# ═══════════════════════════════════════════════════════════════
# Property 1 — Absolute Time Invariant
# ═══════════════════════════════════════════════════════════════


@given(utc_dt=safe_utc)
@settings(
    max_examples=500,
    deadline=20_000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_absolute_time_invariant(utc_dt):
    """Same absolute moment → identical daily pillar (UTC+14 vs UTC-12).

    This is the core metamorphic property: regardless of which timezone
    representation is used to describe the *same instant*, the Bazi chart
    calculator must return the same result.
    """
    dt_plus_14 = utc_dt.astimezone(TZ_PLUS_14)
    dt_minus_12 = utc_dt.astimezone(TZ_MINUS_12)

    chart_a = _invoke(resolve_daily_pillar_from_datetime, dt_plus_14)
    chart_b = _invoke(resolve_daily_pillar_from_datetime, dt_minus_12)

    if isinstance(chart_a, Exception) or isinstance(chart_b, Exception):
        # Out-of-scope input (unsupported year) — both must agree
        assert isinstance(chart_a, Exception) and isinstance(chart_b, Exception)
        return

    assert chart_a == chart_b, (
        f"TIMEZONE MISMATCH — same absolute moment produced different pillars:\n"
        f"  UTC moment : {utc_dt.isoformat()}\n"
        f"  UTC+14     : {dt_plus_14.isoformat()} → {chart_a}\n"
        f"  UTC-12     : {dt_minus_12.isoformat()} → {chart_b}"
    )


@given(utc_dt=safe_utc)
@settings(
    max_examples=500,
    deadline=20_000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_sgt_normalization_matches_direct_resolution(utc_dt):
    """SGT-normalized date is identical regardless of input timezone.

    Verifies that UTC+14, UTC-12, UTC, and SGT inputs all collapse to
    the same canonical SGT date and therefore the same pillar.
    """
    canonical_date = utc_dt.astimezone(SGT).date()
    canonical_pillar = resolve_daily_pillar(canonical_date)

    for tz in (TZ_PLUS_14, TZ_MINUS_12, UTC, SGT):
        localized = utc_dt.astimezone(tz)
        result = _invoke(resolve_daily_pillar_from_datetime, localized)
        if isinstance(result, Exception):
            return  # out-of-scope — skip
        assert result == canonical_pillar, (
            f"TZ {tz.tzname(None)} ({localized.isoformat()}) → {result} "
            f"but canonical SGT → {canonical_pillar}"
        )


# ═══════════════════════════════════════════════════════════════
# Property 2 — No OverflowError on timezone boundary math
# ═══════════════════════════════════════════════════════════════


@given(utc_dt=safe_utc)
@settings(
    max_examples=500,
    deadline=20_000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_no_crash_valid_output_structure(utc_dt):
    """On valid input, engine returns a well-structured Pillar — no crash,
    no NaN, no OverflowError, stems/branches are valid."""
    dt_plus_14 = utc_dt.astimezone(TZ_PLUS_14)
    dt_minus_12 = utc_dt.astimezone(TZ_MINUS_12)

    for label, dt_label in [("A", dt_plus_14), ("B", dt_minus_12)]:
        chart = _invoke(resolve_daily_pillar_from_datetime, dt_label)
        if isinstance(chart, Exception):
            assert isinstance(chart, ValueError), (
                f"Unexpected {type(chart).__name__} for chart_{label}"
            )
            continue

        assert isinstance(chart, Pillar), f"chart_{label} is not a Pillar"
        assert chart.stem in STEM_ORDER, (
            f"chart_{label}.stem={chart.stem!r} not in STEM_ORDER"
        )
        assert chart.branch in BRANCH_ORDER, (
            f"chart_{label}.branch={chart.branch!r} not in BRANCH_ORDER"
        )
        assert chart.date is not None, f"chart_{label}.date is None"


@given(utc_dt=full_utc)
@settings(
    max_examples=300,
    deadline=20_000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_no_overflow_error_leak(utc_dt):
    """Engine must not leak OverflowError from timezone boundary math.

    Uses the full datetime range (year 1 – 9999) so that ``astimezone``
    can hit Python's boundary limits.  An OverflowError raised by
    ``datetime.astimezone`` *in the test setup* (UTC → UTC±14/±12) is a
    Python datetime limitation, not an engine bug — we skip it.  But an
    OverflowError raised by the *engine* (UTC±14/±12 → SGT) must be
    caught and converted to ValueError.
    """
    # Conversion in test setup — may OverflowError at Python boundaries
    try:
        dt_plus_14 = utc_dt.astimezone(TZ_PLUS_14)
    except OverflowError:
        return
    try:
        dt_minus_12 = utc_dt.astimezone(TZ_MINUS_12)
    except OverflowError:
        return

    result_a = _invoke(resolve_daily_pillar_from_datetime, dt_plus_14)
    result_b = _invoke(resolve_daily_pillar_from_datetime, dt_minus_12)

    # OverflowError must NEVER leak from the engine's internal conversion
    assert not isinstance(result_a, OverflowError), (
        f"Engine leaked OverflowError for {dt_plus_14.isoformat()}"
    )
    assert not isinstance(result_b, OverflowError), (
        f"Engine leaked OverflowError for {dt_minus_12.isoformat()}"
    )


@given(utc_dt=full_utc)
@settings(
    max_examples=300,
    deadline=20_000,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_no_unhandled_exceptions(utc_dt):
    """No unhandled (unsafe) exception of any kind may leak from the engine."""
    try:
        dt_plus_14 = utc_dt.astimezone(TZ_PLUS_14)
    except OverflowError:
        return
    try:
        dt_minus_12 = utc_dt.astimezone(TZ_MINUS_12)
    except OverflowError:
        return

    # _invoke already re-raises unsafe exceptions as AssertionError
    _invoke(resolve_daily_pillar_from_datetime, dt_plus_14)
    _invoke(resolve_daily_pillar_from_datetime, dt_minus_12)


def test_extreme_datetime_overflow_converted_to_value_error():
    """Datetime at Python's max boundary must not leak OverflowError.

    ``datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)`` converted
    to SGT (UTC+8) attempts to represent year 10000, which overflows.
    The engine must catch this and raise ValueError instead.
    """
    extreme = datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC)

    result = _invoke(resolve_daily_pillar_from_datetime, extreme)

    assert not isinstance(result, OverflowError), (
        "resolve_daily_pillar_from_datetime leaked OverflowError "
        f"for extreme datetime {extreme.isoformat()}"
    )
    assert isinstance(result, (ValueError, Pillar)), (
        f"Unexpected result type: {type(result).__name__}: {result!r}"
    )
