"""
Unit tests for Module 10: Event Classification (module10_classification.py) - V29
"""

import pytest

from src.engine.module10_classification import classify_events

# ─────────────────────────────────────────────
# Test Data Fixtures
# ─────────────────────────────────────────────


@pytest.fixture
def male_profile():
    """Create a male profile for testing."""
    return {
        "gender": "M",
        "strength_profile": {"tier": "Weak", "continuous_score": 35.0},
        "medicine": ["Fire", "Earth"],
        "taboo": ["Metal"],
        "domain_focus": "General",
        "age": 35
    }


@pytest.fixture
def female_profile():
    """Create a female profile for testing."""
    return {
        "gender": "F",
        "strength_profile": {"tier": "Weak", "continuous_score": 35.0},
        "medicine": ["Fire", "Earth"],
        "taboo": ["Metal"],
        "domain_focus": "General",
        "age": 35
    }


@pytest.fixture
def career_focused_profile():
    """Create a career-focused profile."""
    return {
        "gender": "M",
        "strength_profile": {"tier": "Weak", "continuous_score": 35.0},
        "medicine": ["Fire", "Earth"],
        "taboo": ["Metal"],
        "domain_focus": "Career",
        "age": 40
    }


# ─────────────────────────────────────────────
# Test: Physical Injury Events
# ─────────────────────────────────────────────


class TestPhysicalInjuryEvents:
    """Test physical injury and accident classification."""

    def test_car_accident_with_yang_ren_and_clash(self, male_profile):
        """Test car accident classification with Yang Ren + Day clash."""
        triggers = {
            "clash_triggers": {
                "day": {"active": True, "type": "Chong"},
            },
            "star_triggers": [{"star": "Yang Ren"}],
            "raw_friction": -10,
        }

        events = classify_events(triggers, male_profile)

        # Should have physical injury event
        injury_events = [e for e in events if e["type"] == "physical_injury"]
        assert len(injury_events) > 0

        injury = injury_events[0]
        assert injury["severity"] == "critical"
        assert injury["base_weight"] >= 40
        assert "accident" in injury["subtype"]

    def test_health_disruption_with_clash_only(self, male_profile):
        """Test health disruption with Day clash but no Yang Ren."""
        triggers = {
            "clash_triggers": {
                "day": {"active": True, "type": "Chong"},
            },
            "star_triggers": [],
            "raw_friction": -5,
        }

        events = classify_events(triggers, male_profile)

        health_events = [e for e in events if e["type"] == "health_disruption"]
        assert len(health_events) > 0

        health = health_events[0]
        assert health["severity"] == "high"
        assert health["base_weight"] >= 25

# ─────────────────────────────────────────────
# Test: Career Events
# ─────────────────────────────────────────────


class TestCareerEvents:
    """Test career-related event classification."""

    def test_career_change_with_month_clash(self, male_profile):
        """Test career change with Month pillar clash."""
        triggers = {
            "clash_triggers": {
                "month": {"active": True, "type": "Chong"},
            },
            "star_triggers": [],
            "raw_friction": -8,
        }

        events = classify_events(triggers, male_profile)

        career_events = [e for e in events if e["type"] == "career_change"]
        assert len(career_events) > 0

        career = career_events[0]
        assert career["severity"] == "high"
        assert career["base_weight"] >= 30

    def test_career_collapse_with_lu_clash(self, male_profile):
        """Test career collapse with Lu (Salary) clash."""
        triggers = {
            "clash_triggers": {},
            "star_triggers": [{"star": "Lu Clash"}],
            "raw_friction": -12,
        }

        events = classify_events(triggers, male_profile)

        collapse_events = [e for e in events if e["type"] == "career_collapse"]
        assert len(collapse_events) > 0

        collapse = collapse_events[0]
        assert collapse["severity"] == "critical"
        assert collapse["base_weight"] >= 50


# ─────────────────────────────────────────────
# Test: Event Sorting and Priority
# ─────────────────────────────────────────────


class TestEventSorting:
    """Test event sorting by priority."""

    def test_events_sorted_by_weight(self, male_profile):
        """Test that events are sorted by base_weight descending."""
        triggers = {
            "clash_triggers": {
                "day": {"active": True, "type": "Chong"},
                "month": {"active": True, "type": "Chong"},
            },
            "star_triggers": [{"star": "Yang Ren"}],
            "raw_friction": -10,
        }

        events = classify_events(triggers, male_profile)

        # Events should be sorted by base_weight descending
        weights = [e["base_weight"] for e in events]
        assert weights == sorted(weights, reverse=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
