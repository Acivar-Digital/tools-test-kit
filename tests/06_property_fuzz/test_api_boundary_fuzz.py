"""Property-based fuzzing tests for Pydantic API boundary ingestion models.

Throws massive, malformed, and edge-case data at the Pydantic ingestion models
in src2/core/schemas/ to prove the ingestion layer never crashes with unhandled
raw exceptions.

Rules enforced:
- NaN/Infinity guard checks on all float outputs
- Native Hypothesis strategies (st.builds, st.fixed_dictionaries, st.floats)
- No try/except escapes to skip bad data
- Property-based assertions (invariants, not specific outputs)
"""

import math
from datetime import date

from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src2.core.schemas import (
    ChartProfile,
    CongGeValidationResult,
    DailyForecastRecord,
    DaYunCycleItem,
    DaYunOutput,
    DMScoreWithOutput,
    GatedScoreResult,
    LLMRequestPayload,
    LLMResponsePayload,
    Pillar,
    ScoringOutput,
    SerializedGeJuContext,
    SerializedProfileContext,
    SessionState,
    SolarMonthAnchor,
    TailoringState,
    TaiSuiConditionCheck,
    TraceEntry,
    TracePayload,
    UserProfile,
    ValidatedPillar,
)
from src2.core.schemas.unified import PeriodFavorability

YANG_STEMS = ["Jia", "Bing", "Wu", "Geng", "Ren"]
YIN_STEMS = ["Yi", "Ding", "Ji", "Xin", "Gui"]
YANG_BRANCHES = ["Zi", "Yin", "Chen", "Shen", "Xu"]
YIN_BRANCHES = ["Chou", "Mao", "Si", "Wei", "Hai"]
VALID_STEMS = YANG_STEMS + YIN_STEMS
VALID_BRANCHES = YANG_BRANCHES + YIN_BRANCHES
TAILORING_STEP = ["offer", "career", "relationships", "wealth", "health", "done"]
SESSION_STEP = [
    "START", "CHOOSING", "COLLECTING", "CONFIRM", "TAILORING",
    "PROCESSING", "COMPLETE", "CHRONOMANCER", "STAKEHOLDER_COLLECTING", "CONFIRM_DELETE",
]

UNSAFE_EXCEPTIONS = (RecursionError, KeyError, IndexError, TypeError, AttributeError, ZeroDivisionError, OverflowError, MemoryError)


def _assert_never_crashes_with_unhandled_exception(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except (ValidationError, ValueError) as e:
        return e
    except UNSAFE_EXCEPTIONS as e:
        raise AssertionError(
            f"Unhandled raw exception leaked from ingestion layer: {type(e).__name__}: {e}"
        ) from e


# ═══════════════════════════════════════════════════════════════
# LLMRequestPayload
# ═══════════════════════════════════════════════════════════════

@given(
    model=st.sampled_from(["gpt-4", "claude-3", "gemini-pro"]),
    messages=st.lists(
        st.dictionaries(st.text(min_size=1), st.text()),
        min_size=1,
        max_size=5,
    ),
    temperature=st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=2.0),
)
@settings(max_examples=50)
def test_llm_request_payload_valid_data_succeeds(model, messages, temperature):
    result = LLMRequestPayload(model=model, messages=messages, temperature=temperature)
    assert isinstance(result, LLMRequestPayload)
    assert isinstance(result.model, str)
    assert isinstance(result.messages, list)
    assert isinstance(result.temperature, float)
    assert not math.isnan(result.temperature), "temperature leaked NaN!"
    assert not math.isinf(result.temperature), "temperature leaked Infinity!"


@given(data=st.fixed_dictionaries({
    "model": st.one_of(st.just(None), st.just(123), st.just([]), st.just({})),
    "messages": st.one_of(st.just(None), st.just("not a list"), st.just(42), st.just(True)),
    "temperature": st.one_of(st.just(None), st.just("hot"), st.just([])),
}))
@settings(max_examples=50)
def test_llm_request_payload_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(LLMRequestPayload.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed LLMRequestPayload, got {type(result).__name__}"
    )


@given(temperature=st.floats(allow_nan=True, allow_infinity=True))
@settings(max_examples=50)
def test_llm_request_payload_nan_infinity_never_crashes(temperature):
    """NaN/Infinity temperature must raise ValidationError, not crash."""
    if math.isnan(temperature) or math.isinf(temperature):
        result = _assert_never_crashes_with_unhandled_exception(
            LLMRequestPayload.model_validate,
            {"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}], "temperature": temperature},
        )
        assert isinstance(result, (ValidationError, ValueError)), (
            f"Expected ValidationError/ValueError for NaN/Infinity temperature, got {type(result).__name__}"
        )
    else:
        result = LLMRequestPayload.model_validate(
            {"model": "gpt-4", "messages": [{"role": "user", "content": "hello"}], "temperature": temperature},
        )
        assert isinstance(result, LLMRequestPayload)


# ═══════════════════════════════════════════════════════════════
# LLMResponsePayload
# ═══════════════════════════════════════════════════════════════

@given(
    text=st.text(min_size=1, max_size=200),
)
@settings(max_examples=50)
def test_llm_response_payload_valid_data_succeeds(text):
    result = LLMResponsePayload(text=text)
    assert isinstance(result, LLMResponsePayload)
    assert isinstance(result.text, str)


@given(data=st.fixed_dictionaries({
    "text": st.one_of(st.just(None), st.just(123), st.just([]), st.just({})),
    "raw_response": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "usage": st.one_of(st.just(None), st.just("not a dict"), st.just([])),
}))
@settings(max_examples=50)
def test_llm_response_payload_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(LLMResponsePayload.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed LLMResponsePayload, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# SerializedProfileContext
# ═══════════════════════════════════════════════════════════════

@given(
    day_master=st.sampled_from(VALID_STEMS),
    element=st.sampled_from(["Wood", "Fire", "Earth", "Metal", "Water"]),
    strength=st.sampled_from(["Vibrant", "Strong", "Mild Strong", "Mild Weak", "Weak", "Follower"]),
)
@settings(max_examples=50)
def test_serialized_profile_context_valid_data_succeeds(day_master, element, strength):
    result = SerializedProfileContext(
        day_master=day_master,
        element=element,
        strength=strength,
        favorable=["Wood", "Fire"],
        unfavorable=["Earth", "Metal"],
    )
    assert isinstance(result, SerializedProfileContext)
    assert isinstance(result.day_master, str)
    assert isinstance(result.element, str)
    assert isinstance(result.strength, str)
    assert isinstance(result.favorable, list)
    assert isinstance(result.unfavorable, list)
    assert isinstance(result.raw_details, dict)


@given(data=st.fixed_dictionaries({
    "day_master": st.one_of(st.just(None), st.just(123), st.just([])),
    "element": st.one_of(st.just(None), st.just(42), st.just(True)),
    "strength": st.one_of(st.just(None), st.just(3.14), st.just([])),
    "favorable": st.one_of(st.just(None), st.just("not a list"), st.just(42)),
    "unfavorable": st.one_of(st.just(None), st.just("not a list"), st.just(42)),
    "raw_details": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
}))
@settings(max_examples=50)
def test_serialized_profile_context_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(SerializedProfileContext.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed SerializedProfileContext, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# SerializedGeJuContext
# ═══════════════════════════════════════════════════════════════

@given(
    pattern_name=st.text(min_size=1, max_size=50),
    is_special=st.booleans(),
    alignment_modifier=st.floats(allow_nan=False, allow_infinity=False, min_value=-10.0, max_value=10.0),
)
@settings(max_examples=50)
def test_serialized_geju_context_valid_data_succeeds(pattern_name, is_special, alignment_modifier):
    result = SerializedGeJuContext(
        pattern_name=pattern_name,
        is_special=is_special,
        alignment_modifier=alignment_modifier,
        validation_reason="test",
    )
    assert isinstance(result, SerializedGeJuContext)
    assert isinstance(result.pattern_name, str)
    assert isinstance(result.is_special, bool)
    assert isinstance(result.alignment_modifier, float)
    assert not math.isnan(result.alignment_modifier), "alignment_modifier leaked NaN!"
    assert not math.isinf(result.alignment_modifier), "alignment_modifier leaked Infinity!"
    assert isinstance(result.validation_reason, str)


@given(data=st.fixed_dictionaries({
    "pattern_name": st.one_of(st.just(None), st.just(123), st.just([])),
    "is_special": st.one_of(st.just(None), st.just("not a bool"), st.just(42), st.just([])),
    "alignment_modifier": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
    "validation_reason": st.one_of(st.just(None), st.just(123), st.just([])),
}))
@settings(max_examples=50)
def test_serialized_geju_context_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(SerializedGeJuContext.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed SerializedGeJuContext, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# ChartProfile
# ═══════════════════════════════════════════════════════════════

@given(extra_key=st.text(min_size=1, max_size=20))
@settings(max_examples=50)
def test_chart_profile_valid_data_succeeds(extra_key):
    data = {
        "day_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "gender": "M",
        "day_master_strength": "Weak",
        extra_key: "extra",
    }
    result = ChartProfile(**data)
    assert isinstance(result, ChartProfile)
    assert isinstance(result.day_pillar, Pillar)
    assert isinstance(result.month_pillar, Pillar)
    assert isinstance(result.year_pillar, Pillar)


@given(data=st.fixed_dictionaries({
    "day_pillar": st.one_of(st.just(None), st.just("not a pillar"), st.just(42), st.just([])),
    "month_pillar": st.one_of(st.just(None), st.just("not a pillar"), st.just(42)),
    "year_pillar": st.one_of(st.just(None), st.just("not a pillar"), st.just(42)),
    "hour_pillar": st.one_of(st.just("not a pillar"), st.just(42), st.just([])),
    "gender": st.one_of(st.just(None), st.just(123), st.just([])),
    "day_master_strength": st.one_of(st.just(None), st.just(42), st.just([]), st.just(True)),
    "favorable_elements": st.one_of(st.just(None), st.just("not a list"), st.just(42)),
    "unfavorable_elements": st.one_of(st.just(None), st.just("not a list"), st.just(42)),
    "target_year": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "monthly_composite_score": st.one_of(st.just(None), st.just("not a float"), st.just([])),
}))
@settings(max_examples=50)
def test_chart_profile_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(ChartProfile.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed ChartProfile, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# UserProfile
# ═══════════════════════════════════════════════════════════════

@given(extra_key=st.text(min_size=1, max_size=20))
@settings(max_examples=50)
def test_user_profile_valid_data_succeeds(extra_key):
    data = {
        "day_pillar": {"stem": "Jia", "branch": "Zi"},
        "month_pillar": {"stem": "Bing", "branch": "Yin"},
        "year_pillar": {"stem": "Wu", "branch": "Chen"},
        "gender": "M",
        "day_master_strength": "Weak",
        extra_key: "extra",
    }
    result = UserProfile(**data)
    assert isinstance(result, UserProfile)
    assert isinstance(result.day_pillar, ValidatedPillar)
    assert isinstance(result.gender, str)


@given(data=st.fixed_dictionaries({
    "day_pillar": st.one_of(st.just(None), st.just("not a pillar"), st.just(42)),
    "month_pillar": st.one_of(st.just(None), st.just("not a pillar"), st.just(42)),
    "year_pillar": st.one_of(st.just(None), st.just("not a pillar"), st.just(42)),
    "gender": st.one_of(st.just(None), st.just(123), st.just([])),
    "day_master_strength": st.one_of(st.just(None), st.just(42), st.just([]), st.just(True)),
}))
@settings(max_examples=50)
def test_user_profile_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(UserProfile.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed UserProfile, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# ValidatedPillar
# ═══════════════════════════════════════════════════════════════

@given(
    stem_branch=st.sampled_from([
        ("Jia", "Zi"), ("Jia", "Yin"), ("Jia", "Chen"), ("Jia", "Shen"), ("Jia", "Xu"),
        ("Bing", "Zi"), ("Bing", "Yin"), ("Bing", "Chen"), ("Bing", "Shen"), ("Bing", "Xu"),
        ("Wu", "Zi"), ("Wu", "Yin"), ("Wu", "Chen"), ("Wu", "Shen"), ("Wu", "Xu"),
        ("Geng", "Zi"), ("Geng", "Yin"), ("Geng", "Chen"), ("Geng", "Shen"), ("Geng", "Xu"),
        ("Ren", "Zi"), ("Ren", "Yin"), ("Ren", "Chen"), ("Ren", "Shen"), ("Ren", "Xu"),
        ("Yi", "Chou"), ("Yi", "Mao"), ("Yi", "Si"), ("Yi", "Wei"), ("Yi", "Hai"),
        ("Ding", "Chou"), ("Ding", "Mao"), ("Ding", "Si"), ("Ding", "Wei"), ("Ding", "Hai"),
        ("Ji", "Chou"), ("Ji", "Mao"), ("Ji", "Si"), ("Ji", "Wei"), ("Ji", "Hai"),
        ("Xin", "Chou"), ("Xin", "Mao"), ("Xin", "Si"), ("Xin", "Wei"), ("Xin", "Hai"),
        ("Gui", "Chou"), ("Gui", "Mao"), ("Gui", "Si"), ("Gui", "Wei"), ("Gui", "Hai"),
    ]),
)
@settings(max_examples=50)
def test_validated_pillar_valid_data_succeeds(stem_branch):
    stem, branch = stem_branch
    result = ValidatedPillar(stem=stem, branch=branch)
    assert isinstance(result, ValidatedPillar)
    assert isinstance(result.stem, str)
    assert isinstance(result.branch, str)


@given(data=st.fixed_dictionaries({
    "stem": st.one_of(st.just(None), st.just(123), st.just([]), st.just({})),
    "branch": st.one_of(st.just(None), st.just(42), st.just([]), st.just({})),
}))
@settings(max_examples=50)
def test_validated_pillar_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(ValidatedPillar.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed ValidatedPillar, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# DailyForecastRecord
# ═══════════════════════════════════════════════════════════════

@given(
    user_id=st.integers(min_value=1, max_value=999999),
    profile_hash=st.text(min_size=1, max_size=64),
)
@settings(max_examples=50)
def test_daily_forecast_record_valid_data_succeeds(user_id, profile_hash):
    result = DailyForecastRecord(
        user_id=user_id,
        profile_hash=profile_hash,
        date=date(2026, 1, 15),
        stem="Jia",
        branch="Zi",
    )
    assert isinstance(result, DailyForecastRecord)
    assert isinstance(result.user_id, int)
    assert isinstance(result.stem, str)
    assert isinstance(result.branch, str)


@given(data=st.fixed_dictionaries({
    "user_id": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "profile_hash": st.one_of(st.just(None), st.just(123), st.just([])),
    "date": st.one_of(st.just(None), st.just("not a date"), st.just(42), st.just([])),
    "stem": st.one_of(st.just(None), st.just(123), st.just([])),
    "branch": st.one_of(st.just(None), st.just(42), st.just([])),
    "activities": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "events": st.one_of(st.just(None), st.just("not a list"), st.just(42)),
    "hourly_scores": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "is_permanent": st.one_of(st.just(None), st.just("not a bool"), st.just(42)),
}))
@settings(max_examples=50)
def test_daily_forecast_record_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(DailyForecastRecord.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed DailyForecastRecord, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# TraceEntry
# ═══════════════════════════════════════════════════════════════

@given(
    step=st.sampled_from(SESSION_STEP),
    status=st.sampled_from(["ok", "error", "pending"]),
    reasoning=st.text(min_size=1, max_size=200),
)
@settings(max_examples=50)
def test_trace_entry_valid_data_succeeds(step, status, reasoning):
    result = TraceEntry(step=step, status=status, reasoning=reasoning)
    assert isinstance(result, TraceEntry)
    assert isinstance(result.step, str)
    assert isinstance(result.status, str)
    assert isinstance(result.reasoning, str)


@given(data=st.fixed_dictionaries({
    "step": st.one_of(st.just(None), st.just(123), st.just([])),
    "status": st.one_of(st.just(None), st.just(42), st.just([])),
    "inputs": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "outputs": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "reasoning": st.one_of(st.just(None), st.just(123), st.just([])),
}))
@settings(max_examples=50)
def test_trace_entry_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(TraceEntry.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed TraceEntry, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# TracePayload
# ═══════════════════════════════════════════════════════════════

@given(data=st.builds(dict))
@settings(max_examples=50)
def test_trace_payload_valid_data_succeeds(data):
    result = TracePayload(data=data)
    assert isinstance(result, TracePayload)


# ═══════════════════════════════════════════════════════════════
# GatedScoreResult
# ═══════════════════════════════════════════════════════════════

@given(
    composite_score=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    raw_score=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    era_ceiling=st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6),
)
@settings(max_examples=50)
def test_gated_score_result_valid_data_succeeds(composite_score, raw_score, era_ceiling):
    result = GatedScoreResult(
        composite_score=composite_score,
        raw_score=raw_score,
        da_yun_envelope=PeriodFavorability(center=0.0, range=1.0),
        year_envelope=PeriodFavorability(center=0.0, range=1.0),
        month_envelope=PeriodFavorability(center=0.0, range=1.0),
        era_ceiling=era_ceiling,
    )
    assert isinstance(result, GatedScoreResult)
    assert isinstance(result.composite_score, float)
    assert not math.isnan(result.composite_score), "composite_score leaked NaN!"
    assert not math.isinf(result.composite_score), "composite_score leaked Infinity!"
    assert isinstance(result.raw_score, float)
    assert not math.isnan(result.raw_score), "raw_score leaked NaN!"
    assert not math.isinf(result.raw_score), "raw_score leaked Infinity!"


@given(data=st.fixed_dictionaries({
    "composite_score": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
    "raw_score": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
    "da_yun_envelope": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "year_envelope": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "month_envelope": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "era_ceiling": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
}))
@settings(max_examples=50)
def test_gated_score_result_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(GatedScoreResult.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed GatedScoreResult, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# ScoringOutput
# ═══════════════════════════════════════════════════════════════

@given(
    composite_score=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
    raw_score=st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
)
@settings(max_examples=50)
def test_scoring_output_valid_data_succeeds(composite_score, raw_score):
    result = ScoringOutput(composite_score=composite_score, raw_score=raw_score, luck_dm_interaction="neutral")
    assert isinstance(result, ScoringOutput)
    assert isinstance(result.composite_score, float)
    assert not math.isnan(result.composite_score), "composite_score leaked NaN!"
    assert not math.isinf(result.composite_score), "composite_score leaked Infinity!"
    assert isinstance(result.raw_score, float)
    assert not math.isnan(result.raw_score), "raw_score leaked NaN!"
    assert not math.isinf(result.raw_score), "raw_score leaked Infinity!"


@given(data=st.fixed_dictionaries({
    "composite_score": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
    "raw_score": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
    "luck_dm_interaction": st.one_of(st.just(None), st.just(123), st.just([])),
}))
@settings(max_examples=50)
def test_scoring_output_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(ScoringOutput.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed ScoringOutput, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# TaiSuiConditionCheck
# ═══════════════════════════════════════════════════════════════

@given(
    severity=st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=10.0),
)
@settings(max_examples=50)
def test_tai_sui_condition_check_valid_data_succeeds(severity):
    result = TaiSuiConditionCheck(
        condition="clash",
        annual_branch="Zi",
        birth_year_branch="Chou",
        detected=True,
        severity=severity,
    )
    assert isinstance(result, TaiSuiConditionCheck)
    assert isinstance(result.severity, float)
    assert not math.isnan(result.severity), "severity leaked NaN!"
    assert not math.isinf(result.severity), "severity leaked Infinity!"
    assert result.severity >= 0.0, "severity must be non-negative"


@given(data=st.fixed_dictionaries({
    "condition": st.one_of(st.just(None), st.just(123), st.just([])),
    "annual_branch": st.one_of(st.just(None), st.just(42), st.just([])),
    "birth_year_branch": st.one_of(st.just(None), st.just(42), st.just([])),
    "detected": st.one_of(st.just(None), st.just("not a bool"), st.just(42), st.just([])),
    "severity": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
}))
@settings(max_examples=50)
def test_tai_sui_condition_check_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(TaiSuiConditionCheck.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed TaiSuiConditionCheck, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# CongGeValidationResult
# ═══════════════════════════════════════════════════════════════

@given(
    dominance=st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=1.0),
)
@settings(max_examples=50)
def test_cong_ge_validation_result_valid_data_succeeds(dominance):
    result = CongGeValidationResult(
        is_valid=True,
        has_counters=False,
        season_supported=True,
        dominance=dominance,
    )
    assert isinstance(result, CongGeValidationResult)
    assert isinstance(result.dominance, float)
    assert not math.isnan(result.dominance), "dominance leaked NaN!"
    assert not math.isinf(result.dominance), "dominance leaked Infinity!"
    assert 0.0 <= result.dominance <= 1.0, "dominance must be in [0, 1]"


@given(data=st.fixed_dictionaries({
    "is_valid": st.one_of(st.just(None), st.just("not a bool"), st.just(42), st.just([])),
    "has_counters": st.one_of(st.just(None), st.just("not a bool"), st.just(42), st.just([])),
    "season_supported": st.one_of(st.just(None), st.just("not a bool"), st.just(42), st.just([])),
    "dominance": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
}))
@settings(max_examples=50)
def test_cong_ge_validation_result_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(CongGeValidationResult.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed CongGeValidationResult, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# DMScoreWithOutput
# ═══════════════════════════════════════════════════════════════

@given(
    dm_strength=st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=100.0),
    output_dm=st.floats(allow_nan=False, allow_infinity=False, min_value=0.0, max_value=100.0),
    clash_adjustment=st.floats(allow_nan=False, allow_infinity=False, min_value=-50.0, max_value=50.0),
)
@settings(max_examples=50)
def test_dm_score_with_output_valid_data_succeeds(dm_strength, output_dm, clash_adjustment):
    result = DMScoreWithOutput(
        dm_strength=dm_strength,
        output_dm=output_dm,
        clash_adjustment=clash_adjustment,
    )
    assert isinstance(result, DMScoreWithOutput)
    assert isinstance(result.dm_strength, float)
    assert not math.isnan(result.dm_strength), "dm_strength leaked NaN!"
    assert not math.isinf(result.dm_strength), "dm_strength leaked Infinity!"
    assert isinstance(result.output_dm, float)
    assert not math.isnan(result.output_dm), "output_dm leaked NaN!"
    assert not math.isinf(result.output_dm), "output_dm leaked Infinity!"
    assert isinstance(result.final_score, float)
    assert not math.isnan(result.final_score), "final_score leaked NaN!"
    assert not math.isinf(result.final_score), "final_score leaked Infinity!"


@given(data=st.fixed_dictionaries({
    "dm_strength": st.one_of(st.just("not a float"), st.just([]), st.just({})),
    "output_dm": st.one_of(st.just("not a float"), st.just([]), st.just({})),
    "clash_adjustment": st.one_of(st.just("not a float"), st.just([]), st.just({})),
    "final_score": st.one_of(st.just("not a float"), st.just([]), st.just({})),
}))
@settings(max_examples=50)
def test_dm_score_with_output_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(DMScoreWithOutput.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed DMScoreWithOutput, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# Pillar
# ═══════════════════════════════════════════════════════════════

@given(
    stem=st.one_of(st.sampled_from(VALID_STEMS), st.just(None)),
    branch=st.one_of(st.sampled_from(VALID_BRANCHES), st.just(None)),
)
@settings(max_examples=50)
def test_pillar_valid_data_succeeds(stem, branch):
    result = Pillar(stem=stem, branch=branch)
    assert isinstance(result, Pillar)


@given(data=st.fixed_dictionaries({
    "stem": st.one_of(st.just(123), st.just([]), st.just({})),
    "branch": st.one_of(st.just(42), st.just([]), st.just({})),
    "date": st.one_of(st.just(123), st.just([]), st.just({})),
}))
@settings(max_examples=50)
def test_pillar_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(Pillar.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed Pillar, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# TailoringState
# ═══════════════════════════════════════════════════════════════

@given(
    step=st.sampled_from(TAILORING_STEP),
    skipped=st.booleans(),
)
@settings(max_examples=50)
def test_tailoring_state_valid_data_succeeds(step, skipped):
    result = TailoringState(step=step, skipped=skipped)
    assert isinstance(result, TailoringState)
    assert isinstance(result.step, str)
    assert isinstance(result.skipped, bool)


@given(data=st.fixed_dictionaries({
    "step": st.one_of(st.just(None), st.just(123), st.just([])),
    "career": st.one_of(st.just(None), st.just(42), st.just([])),
    "relationships": st.one_of(st.just(None), st.just(42), st.just([])),
    "wealth": st.one_of(st.just(None), st.just(42), st.just([])),
    "health": st.one_of(st.just(None), st.just(42), st.just([])),
    "skipped": st.one_of(st.just(None), st.just("not a bool"), st.just(42), st.just([])),
}))
@settings(max_examples=50)
def test_tailoring_state_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(TailoringState.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed TailoringState, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# SessionState
# ═══════════════════════════════════════════════════════════════

@given(
    step=st.sampled_from(SESSION_STEP),
)
@settings(max_examples=50)
def test_session_state_valid_data_succeeds(step):
    result = SessionState(step=step)
    assert isinstance(result, SessionState)
    assert isinstance(result.step, str)
    assert isinstance(result.profile_data, dict)


@given(data=st.fixed_dictionaries({
    "step": st.one_of(st.just(None), st.just(123), st.just([])),
    "profile_data": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
    "tailoring": st.one_of(st.just(None), st.just("not a dict"), st.just(42)),
}))
@settings(max_examples=50)
def test_session_state_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(SessionState.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed SessionState, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# DaYunOutput
# ═══════════════════════════════════════════════════════════════

@given(
    start_age=st.integers(min_value=1, max_value=120),
    start_year=st.integers(min_value=1900, max_value=2100),
    direction=st.sampled_from(["forward", "backward"]),
)
@settings(max_examples=50)
def test_da_yun_output_valid_data_succeeds(start_age, start_year, direction):
    result = DaYunOutput(start_age=start_age, start_year=start_year, direction=direction)
    assert isinstance(result, DaYunOutput)
    assert isinstance(result.start_age, int)
    assert isinstance(result.start_year, int)
    assert isinstance(result.direction, str)


@given(data=st.fixed_dictionaries({
    "start_age": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "start_year": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "start_date": st.one_of(st.just(None), st.just("not a date"), st.just(42)),
    "direction": st.one_of(st.just(None), st.just(123), st.just([])),
    "cycles": st.one_of(st.just(None), st.just("not a list"), st.just(42)),
}))
@settings(max_examples=50)
def test_da_yun_output_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(DaYunOutput.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed DaYunOutput, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# DaYunCycleItem
# ═══════════════════════════════════════════════════════════════

@given(
    start_age=st.integers(min_value=1, max_value=120),
    start_year=st.integers(min_value=1900, max_value=2100),
    end_year=st.integers(min_value=1900, max_value=2100),
)
@settings(max_examples=50)
def test_da_yun_cycle_item_valid_data_succeeds(start_age, start_year, end_year):
    result = DaYunCycleItem(
        start_age=start_age,
        start_year=start_year,
        end_year=end_year,
        stem="Jia",
        branch="Zi",
        element="Wood",
        ten_god="Bi Jian",
        phase_label="Chang Sheng",
    )
    assert isinstance(result, DaYunCycleItem)
    assert isinstance(result.start_age, int)
    assert isinstance(result.start_year, int)
    assert isinstance(result.end_year, int)


@given(data=st.fixed_dictionaries({
    "start_age": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "start_year": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "end_year": st.one_of(st.just(None), st.just("not an int"), st.just([]), st.just(True)),
    "stem": st.one_of(st.just(None), st.just(123), st.just([])),
    "branch": st.one_of(st.just(None), st.just(42), st.just([])),
    "element": st.one_of(st.just(None), st.just(123), st.just([])),
    "ten_god": st.one_of(st.just(None), st.just(42), st.just([])),
    "phase_label": st.one_of(st.just(None), st.just(123), st.just([])),
}))
@settings(max_examples=50)
def test_da_yun_cycle_item_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(DaYunCycleItem.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed DaYunCycleItem, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# SolarMonthAnchor
# ═══════════════════════════════════════════════════════════════

@given(
    climate_bias=st.floats(allow_nan=False, allow_infinity=False, min_value=-10.0, max_value=10.0),
)
@settings(max_examples=50)
def test_solar_month_anchor_valid_data_succeeds(climate_bias):
    result = SolarMonthAnchor(
        month_name="January",
        stem="Jia",
        branch="Zi",
        climate_bias=climate_bias,
    )
    assert isinstance(result, SolarMonthAnchor)
    assert isinstance(result.climate_bias, float)
    assert not math.isnan(result.climate_bias), "climate_bias leaked NaN!"
    assert not math.isinf(result.climate_bias), "climate_bias leaked Infinity!"


@given(data=st.fixed_dictionaries({
    "month_name": st.one_of(st.just(None), st.just(123), st.just([])),
    "stem": st.one_of(st.just(None), st.just(42), st.just([])),
    "branch": st.one_of(st.just(None), st.just(42), st.just([])),
    "start_date": st.one_of(st.just(None), st.just("not a date"), st.just(42)),
    "daily_anchor": st.one_of(st.just(None), st.just(123), st.just([])),
    "climate_bias": st.one_of(st.just(None), st.just("not a float"), st.just([]), st.just(True)),
}))
@settings(max_examples=50)
def test_solar_month_anchor_malformed_data_raises_validation_error(data):
    result = _assert_never_crashes_with_unhandled_exception(SolarMonthAnchor.model_validate, data)
    assert isinstance(result, (ValidationError, ValueError)), (
        f"Expected ValidationError/ValueError for malformed SolarMonthAnchor, got {type(result).__name__}"
    )


# ═══════════════════════════════════════════════════════════════
# Extreme float values never crash ingestion
# ═══════════════════════════════════════════════════════════════

@given(
    float_val=st.floats(allow_nan=True, allow_infinity=True),
)
@settings(max_examples=50)
def test_all_float_ingestion_models_never_crash_with_nan_or_infinity(float_val):
    """Any float field in any ingestion model must either raise ValidationError or produce a non-NaN, non-Infinity value."""
    models_to_test = [
        (SolarMonthAnchor, {"month_name": "January", "stem": "Jia", "branch": "Zi", "climate_bias": float_val}),
        (TaiSuiConditionCheck, {"condition": "clash", "annual_branch": "Zi", "birth_year_branch": "Chou", "detected": True, "severity": float_val}),
        (CongGeValidationResult, {"is_valid": True, "has_counters": False, "season_supported": True, "dominance": float_val}),
        (DMScoreWithOutput, {"dm_strength": float_val, "output_dm": float_val, "clash_adjustment": float_val}),
        (ScoringOutput, {"composite_score": float_val, "raw_score": float_val, "luck_dm_interaction": "neutral"}),
        (GatedScoreResult, {"composite_score": float_val, "raw_score": float_val, "da_yun_envelope": PeriodFavorability(center=0.0, range=1.0), "year_envelope": PeriodFavorability(center=0.0, range=1.0), "month_envelope": PeriodFavorability(center=0.0, range=1.0), "era_ceiling": float_val}),
    ]

    for model_cls, kwargs in models_to_test:
        result = _assert_never_crashes_with_unhandled_exception(model_cls.model_validate, kwargs)
        if isinstance(result, (ValidationError, ValueError)):
            continue
        if isinstance(result, model_cls):
            for field_name in result.model_fields_set:
                val = getattr(result, field_name, None)
                if isinstance(val, float):
                    assert not math.isnan(val), f"{model_cls.__name__}.{field_name} leaked NaN for input {float_val!r}"
                    assert not math.isinf(val), f"{model_cls.__name__}.{field_name} leaked Infinity for input {float_val!r}"
            continue
        assert False, f"Unexpected return type {type(result).__name__} from {model_cls.__name__}.model_validate"
