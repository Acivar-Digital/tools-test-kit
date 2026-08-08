"""TEST/math/conftest.py — Shared Pytest Fixtures & Validation Seams for Bazi Math Suite.

Provides standard fixtures for Heavenly Stems, Earthly Branches, Five Elements,
and 4-pillar natal charts. Enforces English CapitalCase key-format conventions
(e.g., 'Jia', 'Zi', 'Wood') and strictly forbids Chinese characters in key/value strings.
"""

import re
import sys
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest

# Add project root to sys.path for engine imports
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# CANONICAL BAZI DATASETS & CONSTANTS
# ============================================================================

HEAVENLY_STEMS_TUPLE: tuple[str, ...] = (
    "Jia", "Yi", "Bing", "Ding", "Wu",
    "Ji", "Geng", "Xin", "Ren", "Gui"
)

EARTHLY_BRANCHES_TUPLE: tuple[str, ...] = (
    "Zi", "Chou", "Yin", "Mao", "Chen", "Si",
    "Wu", "Wei", "Shen", "You", "Xu", "Hai"
)

FIVE_ELEMENTS_TUPLE: tuple[str, ...] = (
    "Wood", "Fire", "Earth", "Metal", "Water"
)

CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


# ============================================================================
# KEY-FORMAT VALIDATION SEAM
# ============================================================================

def assert_key_format_convention(data: Any) -> None:
    """Recursively inspect pytest function arguments/return values or data objects,

    ensuring NO Chinese characters (子, 丑, 甲, 木, etc.) are used for stems,
    branches, or elements, enforcing English CapitalCase (Zi, Chou, Jia, Wood).
    """
    if data is None:
        return

    if isinstance(data, str):
        if CHINESE_CHAR_RE.search(data):
            raise AssertionError(
                f"Key format convention violation: Chinese characters detected in '{data}'. "
                "Stems, branches, and elements must use English CapitalCase (e.g., 'Jia', 'Zi', 'Wood')."
            )
    elif isinstance(data, dict):
        for key, value in data.items():
            assert_key_format_convention(key)
            assert_key_format_convention(value)
    elif isinstance(data, (list, tuple, set)):
        for item in data:
            assert_key_format_convention(item)
    elif hasattr(data, "model_dump"):
        assert_key_format_convention(data.model_dump())
    elif hasattr(data, "__dict__"):
        assert_key_format_convention(data.__dict__)


@pytest.fixture(name="assert_key_format_convention")
def fixture_assert_key_format_convention() -> Callable[[Any], None]:
    """Fixture providing the key format validation assertion function."""
    return assert_key_format_convention


@pytest.fixture(autouse=True)
def enforce_key_format_convention(request: pytest.FixtureRequest) -> Generator[None, None, None]:
    """Automated Key-Format Validation Seam.

    Inspects pytest function arguments before test execution and validates
    that no Chinese characters are passed in stems, branches, elements, or fixture data.
    """
    for arg_name, arg_val in request.node.funcargs.items():
        if arg_name not in ("request", "monkeypatch", "tmp_path", "caplog", "capsys"):
            assert_key_format_convention(arg_val)
    yield


# ============================================================================
# HEAVENLY STEMS FIXTURES
# ============================================================================

@pytest.fixture
def heavenly_stems() -> tuple[str, ...]:
    """Fixture returning all 10 Heavenly Stems in English CapitalCase."""
    return HEAVENLY_STEMS_TUPLE


@pytest.fixture
def jia() -> str:
    return "Jia"


@pytest.fixture
def yi() -> str:
    return "Yi"


@pytest.fixture
def bing() -> str:
    return "Bing"


@pytest.fixture
def ding() -> str:
    return "Ding"


@pytest.fixture
def wu() -> str:
    return "Wu"


@pytest.fixture
def ji() -> str:
    return "Ji"


@pytest.fixture
def geng() -> str:
    return "Geng"


@pytest.fixture
def xin() -> str:
    return "Xin"


@pytest.fixture
def ren() -> str:
    return "Ren"


@pytest.fixture
def gui() -> str:
    return "Gui"


@pytest.fixture
def jia_stem() -> str:
    return "Jia"


@pytest.fixture
def yi_stem() -> str:
    return "Yi"


@pytest.fixture
def bing_stem() -> str:
    return "Bing"


@pytest.fixture
def ding_stem() -> str:
    return "Ding"


@pytest.fixture
def wu_stem() -> str:
    return "Wu"


@pytest.fixture
def ji_stem() -> str:
    return "Ji"


@pytest.fixture
def geng_stem() -> str:
    return "Geng"


@pytest.fixture
def xin_stem() -> str:
    return "Xin"


@pytest.fixture
def ren_stem() -> str:
    return "Ren"


@pytest.fixture
def gui_stem() -> str:
    return "Gui"


# ============================================================================
# EARTHLY BRANCHES FIXTURES
# ============================================================================

@pytest.fixture
def earthly_branches() -> tuple[str, ...]:
    """Fixture returning all 12 Earthly Branches in English CapitalCase."""
    return EARTHLY_BRANCHES_TUPLE


@pytest.fixture
def zi() -> str:
    return "Zi"


@pytest.fixture
def chou() -> str:
    return "Chou"


@pytest.fixture
def yin() -> str:
    return "Yin"


@pytest.fixture
def mao() -> str:
    return "Mao"


@pytest.fixture
def chen() -> str:
    return "Chen"


@pytest.fixture
def si() -> str:
    return "Si"


@pytest.fixture
def wu_branch() -> str:
    return "Wu"


@pytest.fixture
def wei() -> str:
    return "Wei"


@pytest.fixture
def shen() -> str:
    return "Shen"


@pytest.fixture
def you() -> str:
    return "You"


@pytest.fixture
def xu() -> str:
    return "Xu"


@pytest.fixture
def hai() -> str:
    return "Hai"


@pytest.fixture
def zi_branch() -> str:
    return "Zi"


@pytest.fixture
def chou_branch() -> str:
    return "Chou"


@pytest.fixture
def yin_branch() -> str:
    return "Yin"


@pytest.fixture
def mao_branch() -> str:
    return "Mao"


@pytest.fixture
def chen_branch() -> str:
    return "Chen"


@pytest.fixture
def si_branch() -> str:
    return "Si"


@pytest.fixture
def wei_branch() -> str:
    return "Wei"


@pytest.fixture
def shen_branch() -> str:
    return "Shen"


@pytest.fixture
def you_branch() -> str:
    return "You"


@pytest.fixture
def xu_branch() -> str:
    return "Xu"


@pytest.fixture
def hai_branch() -> str:
    return "Hai"


# ============================================================================
# FIVE ELEMENTS FIXTURES
# ============================================================================

@pytest.fixture
def five_elements() -> tuple[str, ...]:
    """Fixture returning all 5 Elements in English CapitalCase."""
    return FIVE_ELEMENTS_TUPLE


@pytest.fixture
def elements() -> tuple[str, ...]:
    """Alias fixture returning all 5 Elements in English CapitalCase."""
    return FIVE_ELEMENTS_TUPLE


@pytest.fixture
def wood() -> str:
    return "Wood"


@pytest.fixture
def fire() -> str:
    return "Fire"


@pytest.fixture
def earth() -> str:
    return "Earth"


@pytest.fixture
def metal() -> str:
    return "Metal"


@pytest.fixture
def water() -> str:
    return "Water"


@pytest.fixture
def wood_element() -> str:
    return "Wood"


@pytest.fixture
def fire_element() -> str:
    return "Fire"


@pytest.fixture
def earth_element() -> str:
    return "Earth"


@pytest.fixture
def metal_element() -> str:
    return "Metal"


@pytest.fixture
def water_element() -> str:
    return "Water"


# ============================================================================
# STANDARD 4-PILLAR NATAL CHART FIXTURES
# ============================================================================

@pytest.fixture
def sample_natal_chart() -> dict[str, dict[str, str]]:
    """Standard 4-pillar natal chart dictionary."""
    return {
        "year": {"stem": "Jia", "branch": "Zi"},
        "month": {"stem": "Bing", "branch": "Yin"},
        "day": {"stem": "Wu", "branch": "Chen"},
        "hour": {"stem": "Ren", "branch": "Shen"},
    }


@pytest.fixture
def sample_natal_stems() -> list[str]:
    """List of stems for the standard sample natal chart."""
    return ["Jia", "Bing", "Wu", "Ren"]


@pytest.fixture
def sample_natal_branches() -> list[str]:
    """List of branches for the standard sample natal chart."""
    return ["Zi", "Yin", "Chen", "Shen"]


@pytest.fixture
def sample_day_master() -> str:
    """Day Master stem for the standard sample natal chart."""
    return "Wu"


@pytest.fixture
def sample_four_pillars() -> tuple[dict[str, str], ...]:
    """Tuple of 4 pillar dicts for standard sample natal chart."""
    return (
        {"stem": "Jia", "branch": "Zi"},
        {"stem": "Bing", "branch": "Yin"},
        {"stem": "Wu", "branch": "Chen"},
        {"stem": "Ren", "branch": "Shen"},
    )


@pytest.fixture
def strong_dm_chart() -> dict[str, dict[str, str]]:
    """Sample natal chart with a Strong Day Master (Jia Wood born in Spring)."""
    return {
        "year": {"stem": "Jia", "branch": "Yin"},
        "month": {"stem": "Yi", "branch": "Mao"},
        "day": {"stem": "Jia", "branch": "Yin"},
        "hour": {"stem": "Bing", "branch": "Chen"},
    }


@pytest.fixture
def weak_dm_chart() -> dict[str, dict[str, str]]:
    """Sample natal chart with a Weak Day Master (Jia Wood born in Autumn under Heavy Metal)."""
    return {
        "year": {"stem": "Geng", "branch": "Shen"},
        "month": {"stem": "Xin", "branch": "You"},
        "day": {"stem": "Jia", "branch": "Xu"},
        "hour": {"stem": "Geng", "branch": "Shen"},
    }


@pytest.fixture
def clash_chart() -> dict[str, dict[str, str]]:
    """Sample natal chart containing Zi-Wu Branch Clash."""
    return {
        "year": {"stem": "Jia", "branch": "Zi"},
        "month": {"stem": "Bing", "branch": "Yin"},
        "day": {"stem": "Wu", "branch": "Wu"},
        "hour": {"stem": "Ren", "branch": "Shen"},
    }


# ============================================================================
# CONFTEST SELF-VERIFICATION TESTS
# ============================================================================

def test_conftest_fixtures(
    heavenly_stems: tuple[str, ...],
    earthly_branches: tuple[str, ...],
    five_elements: tuple[str, ...],
    sample_natal_chart: dict[str, dict[str, str]],
    sample_natal_stems: list[str],
    sample_natal_branches: list[str],
    sample_day_master: str,
) -> None:
    """Verify that all standard fixtures return valid English CapitalCase values."""
    assert len(heavenly_stems) == 10
    assert heavenly_stems[0] == "Jia"
    assert heavenly_stems[-1] == "Gui"

    assert len(earthly_branches) == 12
    assert earthly_branches[0] == "Zi"
    assert earthly_branches[-1] == "Hai"

    assert len(five_elements) == 5
    assert five_elements[0] == "Wood"
    assert five_elements[-1] == "Water"

    assert sample_natal_chart["day"]["stem"] == "Wu"
    assert sample_natal_stems == ["Jia", "Bing", "Wu", "Ren"]
    assert sample_natal_branches == ["Zi", "Yin", "Chen", "Shen"]
    assert sample_day_master == "Wu"


def test_key_format_validation_seam(
    sample_natal_chart: dict[str, dict[str, str]],
    assert_key_format_convention: Callable[[Any], None],
) -> None:
    """Verify that the key-format validation seam accepts valid data and rejects Chinese characters."""
    # Valid chart should pass without error
    assert_key_format_convention(sample_natal_chart)

    # Invalid string with Chinese stem character should raise AssertionError
    invalid_chart = {
        "year": {"stem": "甲", "branch": "Zi"},
    }
    with pytest.raises(AssertionError, match="Chinese characters detected"):
        assert_key_format_convention(invalid_chart)

