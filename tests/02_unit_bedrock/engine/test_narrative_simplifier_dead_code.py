"""Regression tests: verify Phase 1.2 dead symbols are removed from narrative_simplifier.py.

These symbols were removed in commit 2b8eed37 (LazyAgentProxy class + instances)
and must remain absent to prevent dead-code regression:
  - get_month_simplifier_agent()
  - get_advisory_simplifier_agent()
  - _month_simplifier_agent (module-level global)
  - _advisory_simplifier_agent (module-level global)

See _docs/Upgrade/00_Improvements.md Phase 1.2.
"""
import os

os.environ.setdefault("BGEM3_URL", "http://mock")
os.environ.setdefault("BGEM3_TOKEN", "mock")
os.environ.setdefault("QDRANT_URL", "http://mock")

import inspect  # noqa: E402

from src2.engine import narrative_simplifier  # noqa: E402


def test_get_month_simplifier_agent_removed():
    """get_month_simplifier_agent getter must not exist — zero callers, dead code."""
    assert not hasattr(narrative_simplifier, "get_month_simplifier_agent"), (
        "get_month_simplifier_agent() is dead code with zero callers and must be removed"
    )


def test_get_advisory_simplifier_agent_removed():
    """get_advisory_simplifier_agent getter must not exist — zero callers, dead code."""
    assert not hasattr(narrative_simplifier, "get_advisory_simplifier_agent"), (
        "get_advisory_simplifier_agent() is dead code with zero callers and must be removed"
    )


def test_lazy_globals_removed():
    """Backing globals _month_simplifier_agent / _advisory_simplifier_agent must not exist."""
    assert not hasattr(narrative_simplifier, "_month_simplifier_agent"), (
        "_month_simplifier_agent global must be removed"
    )
    assert not hasattr(narrative_simplifier, "_advisory_simplifier_agent"), (
        "_advisory_simplifier_agent global must be removed"
    )


def test_live_api_functions_preserved():
    """Public API functions simplify_advisory and simplify_month_narrative must still exist."""
    assert callable(narrative_simplifier.simplify_advisory)
    assert callable(narrative_simplifier.simplify_month_narrative)


def test_lazyagentproxy_absent_from_source():
    """LazyAgentProxy class must not appear anywhere in the module source."""
    source = inspect.getsource(narrative_simplifier)
    assert "LazyAgentProxy" not in source, (
        "LazyAgentProxy class must be fully removed from narrative_simplifier.py"
    )
