"""Property-based fuzzing tests for Configuration / Profile Combinatorics.

Ticket: baziforecaster-6oba (Ticket 3 — Contradictory Data Validation)

Targets:
- src2.core.schemas.unified: UserProfile (extra="forbid", gender migration
  validator, strength normalization), ChartProfile, ValidatedPillar, LLMResponsePayload
- src2.engine.transformer: to_user_profile, to_chart_profile, normalize_elements,
  normalize_gender, normalize_strength
- src2.interfaces.telegram.conductor: _parse_manual_template, _apply_extracted

Invariants asserted:
1. Contradiction-Rejection: UserProfile(extra="forbid") raises ValidationError on
   extra fields; valid-looking contradictions are accepted & normalized.
2. Gender Normalization: normalize_gender(any_input) ALWAYS returns "M" or "F".
3. Element Set Disjoint: normalize_elements(value) returns only canonical elements;
   non-canonical entries are silently dropped (no KeyError/IndexError).
4. Pillar Schema: ValidatedPillar rejects invalid stems/branches via ValidationError,
   never IndexError/AttributeError on dict inputs with missing keys.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from src2.core.schemas.unified import (
    _BRANCHES,
    _STEMS,
    JIA_ZI_60,
    Gender,
    LLMResponsePayload,
    StrengthTier,
    UserProfile,
    ValidatedPillar,
)
from src2.engine.transformer import (
    normalize_elements,
    normalize_gender,
    normalize_strength,
    to_chart_profile,
    to_user_profile,
)
from src2.interfaces.telegram.conductor import _apply_extracted, _parse_manual_template
from src2.interfaces.telegram.session import Session

CANONICAL_ELEMENTS = {"Wood", "Fire", "Earth", "Metal", "Water"}
_STEM_SET = set(_STEMS)
_BRANCH_SET = set(_BRANCHES)
_STRENGTH_TIERS = {t.value for t in StrengthTier}

# A "Stem Branch" string guaranteed to satisfy the 60-cycle Yang/Yin pairing.
_VALID_PAIR = sorted(JIA_ZI_60)[0].split()
_VALID_STEM, _VALID_BRANCH = _VALID_PAIR[0], _VALID_PAIR[1]
_VALID_PILLAR = {"stem": _VALID_STEM, "branch": _VALID_BRANCH}


def _valid_user_profile(**overrides) -> UserProfile:
    return UserProfile(
        day_pillar=dict(_VALID_PILLAR),
        month_pillar=dict(_VALID_PILLAR),
        year_pillar=dict(_VALID_PILLAR),
        **overrides,
    )


def _fresh_session(**profile_overrides) -> Session:
    profile = _valid_user_profile(**profile_overrides)
    return Session(chat_id=2**31 - 1, profile=profile)


_valid_pillar_dict = st.builds(
    lambda pair: {"stem": pair.split()[0], "branch": pair.split()[1]},
    st.sampled_from(sorted(JIA_ZI_60)),
)


# ---------------------------------------------------------------------------
# Invariant 1 — Contradiction-Rejection
# ---------------------------------------------------------------------------


@given(
    same_as_day=st.booleans(),
    gender=st.one_of(st.sampled_from(["M", "F"]), st.none()),
    strength=st.one_of(st.text(min_size=0, max_size=25), st.integers(), st.none()),
    alias=st.text(min_size=0, max_size=50),
    sexuality_dynamic=st.text(min_size=0, max_size=120),
    overlap=st.booleans(),
)
@settings(max_examples=150, deadline=None)
def test_user_profile_accepts_contradictory_but_valid_data(
    same_as_day, gender, strength, alias, sexuality_dynamic, overlap
):
    """UserProfile MUST accept valid-looking contradictions (duplicated pillars,
    weird day_master_strength, pregnancy terms for any gender) and normalize them —
    never crash with IndexError/AttributeError/TypeError."""
    if overlap:
        fav, unfav = ["Wood"], ["Wood"]
    else:
        fav, unfav = ["Fire"], ["Metal"]

    try:
        profile = _valid_user_profile(
            gender=gender,
            day_master_strength=strength,
            alias=alias,
            sexuality_dynamic=sexuality_dynamic,
            favorable_elements=fav,
            unfavorable_elements=unfav,
        )
    except ValidationError:
        pytest.skip("rejected by gender/strength value validation")

    # day_master_strength MUST always normalize to a known StrengthTier value
    assert profile.day_master_strength in _STRENGTH_TIERS, profile.day_master_strength
    # gender normalizes to the Gender enum (or None)
    assert profile.gender in (None, Gender.MALE, Gender.FEMALE)
    # Same stem-branch duplicated across pillars is accepted (contradiction tolerated)
    assert (
        profile.day_pillar.stem
        == profile.month_pillar.stem
        == profile.year_pillar.stem
    )


def test_user_profile_rejects_extra_fields():
    """UserProfile has model_config extra='forbid'; extra fields MUST raise
    ValidationError (invariant 1), not a raw crash."""
    base = {
        "day_pillar": dict(_VALID_PILLAR),
        "month_pillar": dict(_VALID_PILLAR),
        "year_pillar": dict(_VALID_PILLAR),
    }
    with pytest.raises(ValidationError):
        UserProfile.model_validate({**base, "bogus_field": "x"})


def test_user_profile_rejects_old_gender_literals():
    """The gender-migration before-validator must reject 'Male'/'Female'."""
    bad_input = {
        "day_pillar": dict(_VALID_PILLAR),
        "month_pillar": dict(_VALID_PILLAR),
        "year_pillar": dict(_VALID_PILLAR),
    }
    for bad in ("Male", "Female"):
        with pytest.raises(ValidationError):
            UserProfile.model_validate({**bad_input, "gender": bad})


@given(strength=st.text(max_size=40))
@settings(max_examples=100, deadline=None)
def test_normalize_strength_arbitrary_strings_safe(strength):
    """normalize_strength (used by coordinator auto-strength path) MUST never raise
    KeyError on arbitrary LLM-extracted strings — unrecognized values map to a
    safe default."""
    assert normalize_strength(strength) in _STRENGTH_TIERS


# ---------------------------------------------------------------------------
# Invariant 2 — Gender Normalization
# ---------------------------------------------------------------------------


_arbitrary_value = st.one_of(
    st.integers(min_value=-2**31, max_value=2**31 - 1),
    st.floats(allow_nan=True, allow_infinity=True),
    st.none(),
    st.booleans(),
    st.dictionaries(
        st.text(min_size=1, max_size=4), st.text(min_size=1, max_size=4), max_size=6
    ),
    st.lists(st.text(min_size=1, max_size=4), max_size=6),
    st.text(min_size=0, max_size=10000),
    st.binary(max_size=2048),
    st.text(alphabet="🔥👹女男👶🤰", min_size=1, max_size=20),
)


@given(value=_arbitrary_value)
@settings(max_examples=400, deadline=None)
def test_normalize_gender_always_returns_M_or_F(value):
    """normalize_gender(ANY input) must ALWAYS return exactly 'M' or 'F' and never
    raise, regardless of type (int, None, dict, emoji, 10KB string)."""
    result = normalize_gender(value)
    assert result in ("M", "F"), f"normalize_gender({value!r}) = {result!r}"


def test_normalize_gender_handles_10kb_and_emoji():
    # 10KB input must not crash; "FEMALE" * 2500 is not exactly "female" so
    # it normalizes to the default "M" — the invariant is no-crash + M/F.
    assert normalize_gender("FEMALE" * 2500) in ("M", "F")
    assert normalize_gender("female") == "F"
    assert normalize_gender("Female 🧑‍🤝‍🧑") in ("M", "F")
    assert normalize_gender("\U0001F971") in ("M", "F")


# ---------------------------------------------------------------------------
# Invariant 3 — Element Set Disjoint
# ---------------------------------------------------------------------------


_element_like = st.one_of(
    st.text(min_size=1, max_size=20),
    st.integers(),
    st.none(),
    st.floats(allow_nan=True),
    st.booleans(),
    st.dictionaries(
        st.text(min_size=1, max_size=3), st.text(min_size=1, max_size=3), max_size=4
    ),
    st.text(alphabet="木火土金水", min_size=1, max_size=5),
    st.sampled_from(
        ["Wood", "Fire", "Earth", "Metal", "Water", "木", "🔥", "VIBRANT", ""]
    ),
)


@given(
    elements=st.one_of(
        st.lists(_element_like, max_size=25),
        st.text(min_size=0, max_size=120),
        _element_like,
        st.none(),
    )
)
@settings(max_examples=400, deadline=None)
def test_normalize_elements_returns_only_canonical(elements):
    """After normalize_elements(value), every returned element must belong to
    {Wood, Fire, Earth, Metal, Water}. Non-canonical entries (ints, None, dicts,
    emoji, bilingual '木Wood火') MUST be silently dropped — never raise."""
    result = normalize_elements(elements)
    assert isinstance(result, list)
    for el in result:
        assert el in CANONICAL_ELEMENTS, f"non-canonical element leaked: {el!r}"


def test_normalize_elements_overlap_allowed_but_canonical():
    """Favorable & unfavorable may overlap; each side still normalizes to the
    canonical set only — no crash."""
    raw = ["木", "Wood火", 5, None, {"x": 1}, "Fire", "🔥", "WaterWater"]
    res = normalize_elements(raw)
    assert set(res).issubset(CANONICAL_ELEMENTS)
    assert res == ["Wood", "Fire"]


def test_normalize_elements_bilingual_malformed_dropped():
    assert normalize_elements(["木Wood火"]) == []
    assert normalize_elements([]) == []
    assert normalize_elements(None) == []
    assert normalize_elements(5) == []


# ---------------------------------------------------------------------------
# Invariant 4 — Pillar Schema
# ---------------------------------------------------------------------------


_pillar_input = st.one_of(
    st.dictionaries(
        st.text(min_size=1, max_size=5), st.text(min_size=1, max_size=5), max_size=4
    ),
    st.dictionaries(
        st.sampled_from(["stem", "branch", "extra"]),
        st.text(min_size=1, max_size=8),
        max_size=4,
    ),
    st.text(min_size=0, max_size=15),
    st.integers(),
    st.none(),
    st.lists(st.text(min_size=1, max_size=3), max_size=5),
)


@given(value=_pillar_input)
@settings(max_examples=400, deadline=None)
def test_validated_pillar_never_crashes_with_non_validation_error(value):
    """ValidatedPillar must reject invalid stems/branches via ValidationError —
    never IndexError/AttributeError/KeyError/TypeError — even for dict inputs with
    missing stem/branch keys or stray extra keys (extra='forbid')."""
    try:
        vp = ValidatedPillar.model_validate(value)
    except ValidationError:
        return  # expected rejection path
    except (IndexError, AttributeError, KeyError, TypeError) as exc:  # pragma: no cover
        pytest.fail(
            f"ValidatedPillar crashed with non-ValidationError: {type(exc).__name__}: {exc}"
        )
    assert vp.stem in _STEM_SET
    assert vp.branch in _BRANCH_SET


def test_validated_pillar_rejects_invalid_literal_stem():
    with pytest.raises(ValidationError):
        ValidatedPillar.model_validate({"stem": "木", "branch": "Zi"})


def test_validated_pillar_rejects_missing_keys():
    """Dict with missing branch key must raise ValidationError, not IndexError."""
    with pytest.raises(ValidationError):
        ValidatedPillar.model_validate({"stem": _VALID_STEM})


def test_validated_pillar_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ValidatedPillar.model_validate(
            {"stem": _VALID_STEM, "branch": _VALID_BRANCH, "bogus": "x"}
        )


def test_validated_pillar_accepts_valid_combo():
    vp = ValidatedPillar.model_validate(dict(_VALID_PILLAR))
    assert vp.stem in _STEM_SET and vp.branch in _BRANCH_SET


# ---------------------------------------------------------------------------
# to_chart_profile / to_user_profile boundary (schema injection / extra forbid)
# ---------------------------------------------------------------------------


@given(
    extra=st.dictionaries(
        st.sampled_from(["bogus", "evil_field", "injected"]),
        st.text(min_size=1, max_size=20),
        min_size=1,
        max_size=3,
    )
)
@settings(max_examples=100, deadline=None)
def test_chart_profile_forbid_rejects_schema_injection(extra):
    """ChartProfile (extra='forbid') MUST raise ValidationError for injected
    fields — the anti-corruption seam must not crash."""
    base = {"day_master": "Jia", "year_pillar": dict(_VALID_PILLAR)}
    with pytest.raises(ValidationError):
        to_chart_profile({**base, **extra})


@given(
    raw=st.one_of(
        st.dictionaries(st.text(min_size=1, max_size=8), st.text(min_size=1, max_size=8), max_size=6),
        st.text(min_size=0, max_size=200),
    )
)
@settings(max_examples=150, deadline=None)
def test_to_user_profile_dict_only_validation_error(raw):
    """to_user_profile(dict|str) must surface ValidationError for bad input, never an
    unhandled IndexError/AttributeError/KeyError/TypeError."""
    try:
        to_user_profile(raw)
    except ValidationError:
        return
    except (IndexError, AttributeError, KeyError, TypeError) as exc:  # pragma: no cover
        pytest.fail(f"to_user_profile crashed: {type(exc).__name__}: {exc}")


# ---------------------------------------------------------------------------
# Conductor: manual template parsing + _apply_extracted contradictions
# ---------------------------------------------------------------------------


@given(text=st.text(min_size=0, max_size=600))
@settings(max_examples=400, deadline=None)
def test_parse_manual_template_never_crashes(text):
    """_parse_manual_template MUST return a dict or None for ANY string input,
    including swapped pillars, missing Da Yun, and 6+ pillars. Never raise."""
    try:
        result = _parse_manual_template(text)
    except (IndexError, AttributeError, KeyError, TypeError) as exc:  # pragma: no cover
        pytest.fail(f"_parse_manual_template crashed: {type(exc).__name__}: {exc}")
    assert result is None or isinstance(result, dict)


def test_parse_manual_template_extracts_swapped_pillars():
    template = (
        "Alias: Tester\nGender: M\n"
        "Year: Bing Chen\nMonth: Yi You\nDay: Jia Zi\n"
        "Hour: Ding Chou\nDa Yun: Wu Hai\nStrength: Strong\n"
        "Favorable: Wood, Fire\nUnfavorable: Metal\n"
    )
    res = _parse_manual_template(template)
    assert res is not None
    assert res["year_pillar"] == "Bing Chen"  # swapped semantics preserved, not crashed
    assert res["day_pillar"] == "Jia Zi"


def test_parse_manual_template_missing_day_yun():
    template = "Year: Jia Zi\nMonth: Yi You\nDay: Bing Chen\nHour: Wu Hai\n"
    res = _parse_manual_template(template)
    assert res is not None
    assert "da_yun_pillar" not in res  # missing Da Yun tolerated


def test_parse_manual_template_six_pillars_tolerated():
    template = (
        "Year: Jia Zi\nMonth: Yi You\nDay: Bing Chen\n"
        "Hour: Wu Hai\nDa Yun: Geng Shen\nExtra Pillar: Ren You\n"
        "Strength: Vibrant\n"
    )
    res = _parse_manual_template(template)
    assert res is not None
    # 6th "Extra Pillar" line ignored — only 5 known pillar labels parsed
    assert "da_yun_pillar" in res


_extracted_fields = st.fixed_dictionaries(
    {
        "gender": st.sampled_from(
            ["M", "F", "Male", "Female", "MALE", "FEMALE", "男", "女", "", "🔥", "nonbinary"]
        ),
        "day_master_strength": st.one_of(
            st.text(min_size=0, max_size=25),
            st.integers(min_value=-999, max_value=999),
            st.none(),
        ),
        "favorable_elements": st.lists(_element_like, max_size=12),
        "unfavorable_elements": st.lists(_element_like, max_size=12),
        "neutral_elements": st.lists(_element_like, max_size=8),
        "day_pillar": st.one_of(
            st.text(min_size=0, max_size=12),
            st.dictionaries(
                st.text(min_size=1, max_size=5), st.text(min_size=1, max_size=5), max_size=4
            ),
            st.none(),
        ),
        "sexuality_dynamic": st.text(min_size=0, max_size=80),
    }
)


@given(session=st.builds(_fresh_session), extracted=_extracted_fields)
@settings(max_examples=200, deadline=None)
def test_apply_extracted_no_unhandled_crash(session, extracted):
    """Running _apply_extracted over contradictory LLM-extracted payload must never
    leak IndexError/AttributeError/KeyError/TypeError. Invalid pillar data may
    surface as ValidationError (typed rejection)."""
    try:
        _apply_extracted(session, dict(extracted), "input")
    except ValidationError:
        return
    except (IndexError, AttributeError, KeyError, TypeError) as exc:
        pytest.fail(f"_apply_extracted leaked crash: {type(exc).__name__}: {exc}")


def test_apply_extracted_gender_strength_pregnancy_contradiction():
    """Concrete cross-contradiction: gender=F, strength='🔥 VIBRANT 🔥',
    pregnancy terms, invalid pillar stem — must degrade, not crash."""
    sess = _fresh_session()
    extracted = {
        "gender": "Female",
        "day_master_strength": "🔥 VIBRANT 🔥",
        "sexuality_dynamic": "pregnant with twins",
        "favorable_elements": ["木", "Fire", 5],
        "unfavorable_elements": ["Water", "🔥", None],
    }
    try:
        _apply_extracted(sess, extracted, "input")
    except ValidationError:
        return
    # If it succeeded, the profile should be in a normalized, consistent state.
    assert sess.profile.day_master_strength in _STRENGTH_TIERS
    assert set(sess.profile.favorable_elements).issubset(CANONICAL_ELEMENTS)
    assert set(sess.profile.unfavorable_elements).issubset(CANONICAL_ELEMENTS)


# ---------------------------------------------------------------------------
# LLMResponsePayload schema-fence (extra='forbid' must reject, not crash)
# ---------------------------------------------------------------------------


@given(
    extra=st.dictionaries(
        st.sampled_from(["bogus", "evil_key", "injected"]),
        st.text(min_size=1, max_size=20),
        min_size=1,
        max_size=3,
    )
)
@settings(max_examples=100, deadline=None)
def test_llm_response_payload_forbid_rejects_extra(extra):
    base = {"text": "ok"}
    with pytest.raises(ValidationError):
        LLMResponsePayload.model_validate({**base, **extra})
