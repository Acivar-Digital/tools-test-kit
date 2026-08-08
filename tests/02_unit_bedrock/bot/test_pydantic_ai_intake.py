import os

os.environ["OPENAI_API_KEY"] = "dummy-test-key"

from unittest.mock import MagicMock, patch

import pytest
from pydantic_ai.models.test import TestModel

from src2.interfaces.telegram.conductor import _parse_manual_template, run_conductor
from src2.interfaces.telegram.session import Session, SessionMetadata


def test_parse_manual_template_success():
    """Test deterministic regex parser for manual templates."""
    text = """
    Alias: Tester
    Gender: M
    Year: Geng Chen
    Month: Xin Si
    Day: Ren Wu
    Hour: Gui Wei
    Strength: Strong
    Favorable: Water, Wood
    """
    extracted = _parse_manual_template(text)

    assert extracted is not None
    assert extracted["alias"] == "Tester"
    assert extracted["gender"] == "M"
    assert extracted["year_pillar"] == "Geng Chen"
    assert extracted["month_pillar"] == "Xin Si"
    assert extracted["day_pillar"] == "Ren Wu"
    assert extracted["hour_pillar"] == "Gui Wei"
    assert extracted["day_master_strength"] == "Strong"
    assert extracted["favorable_elements"] == ["Water", "Wood"]

def test_parse_manual_template_invalid():
    """Test parser fails gracefully when not a template."""
    text = "Hey, what's my Bazi for 1990?"
    extracted = _parse_manual_template(text)
    assert extracted is None

@pytest.mark.asyncio
@patch("src2.interfaces.telegram.conductor.Agent.run")
@patch("pydantic_ai.models.openai.OpenAIChatModel", return_value=TestModel())
@patch("pydantic_ai.providers.openai.OpenAIProvider")
async def test_conductor_agent_call(mock_provider, mock_model, mock_run):
    """Test run_conductor initiates Agent.run and updates session."""

    from src2.interfaces.telegram.intake.input_agent import InputResult

    # Setup mock session
    session = Session(chat_id=123)
    session.metadata = SessionMetadata(intake_mode="input", intake={})

    # Setup mock Pydantic AI return
    mock_result = MagicMock()
    res_data = InputResult(
        reply="Please provide your birth year.",
        next_prompt="What is your birth year?",
        all_collected=False,
        year_pillar="Geng Chen",
        gender="M"
    )
    mock_result.data = res_data
    mock_result.output = res_data
    mock_run.return_value = mock_result

    reply, updated_session = await run_conductor(session, "My year is Geng Chen and I am male.")

    assert reply == "Please provide your birth year."
    assert updated_session.metadata.intake.get("year_pillar") == "Geng Chen"
    assert updated_session.metadata.intake.get("gender") == "M"
    mock_run.assert_called_once()
