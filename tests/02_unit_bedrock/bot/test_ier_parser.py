from datetime import date, timedelta

import pytest
from pydantic_ai.models.test import TestModel

from src2.interfaces.telegram.ier_parser import (
    generate_reference_calendar,
    ier_agent,
    parse_question,
)
from src2.interfaces.telegram.session import ChatMessage


def test_generate_reference_calendar():
    test_today = date(2026, 7, 31)
    calendar_text = generate_reference_calendar(test_today)

    assert "2026-07-31" in calendar_text
    assert "<-- TODAY" in calendar_text
    assert "2026-07-30" in calendar_text
    assert "<-- YESTERDAY" in calendar_text
    assert "2026-08-01" in calendar_text
    assert "<-- TOMORROW" in calendar_text
    assert "2026-07-24" in calendar_text
    assert "2026-08-07" in calendar_text


@pytest.mark.asyncio
async def test_ier_parser_returns_dict():
    """
    Verifies parse_question returns a dict with all expected keys when using the TestModel.
    """
    test_question = "When will I marry my boyfriend?"
    test_today = date(2026, 6, 24)
    test_model = TestModel()

    with ier_agent.override(model=test_model):
        result = await parse_question(
            question=test_question,
            today=test_today,
            chat_history=[],
            known_stakeholders=["John"],
        )

    assert isinstance(result, dict)
    assert "dates" in result
    assert "entity" in result
    assert "intent" in result
    assert "raw_question" in result
    assert "source" in result
    assert result["raw_question"] == test_question
    assert result["source"] == "llm"
    assert result.get("clarified_prompt") is not None


@pytest.mark.asyncio
async def test_ier_parser_chat_message_history():
    """
    Regression test: parse_question must accept ChatMessage objects in chat_history.
    Previously this raised AttributeError: 'ChatMessage' object has no attribute 'get'.
    """
    test_question = "When will I marry my boyfriend?"
    test_today = date(2026, 6, 24)
    test_model = TestModel()
    history = [
        ChatMessage(role="user", content="What is my career outlook?"),
        ChatMessage(role="assistant", content="Let me check your Day Master strength."),
    ]

    with ier_agent.override(model=test_model):
        result = await parse_question(
            question=test_question,
            today=test_today,
            chat_history=history,
            known_stakeholders=["John"],
        )

    assert isinstance(result, dict)
    assert "dates" in result
    assert "entity" in result
    assert "intent" in result
    assert "raw_question" in result
    assert result["raw_question"] == test_question
    assert result.get("clarified_prompt") is not None


def test_parse_question_dict_get_access():
    """
    Regression test: parse_question return payload must support dictionary .get() access
    (e.g. result.get("clarified_prompt")).
    """
    result = {
        "clarified_prompt": "I understand you want career advice.",
        "sentiment": "Hopeful",
        "mental_model": "Check Day Master strength",
        "rag_keywords": ["事业", "正财", "官星"],
        "dates": ["2026-08-15"],
        "entity": "boss",
        "intent": "career",
        "raw_question": "When will I get promoted?",
        "source": "llm",
    }
    assert result.get("clarified_prompt") == "I understand you want career advice."
    assert result.get("sentiment") == "Hopeful"
    assert result.get("mental_model") == "Check Day Master strength"
    assert result.get("rag_keywords") == ["事业", "正财", "官星"]
    assert result.get("dates") == ["2026-08-15"]
    assert result.get("entity") == "boss"
    assert result.get("intent") == "career"
    assert result.get("raw_question") == "When will I get promoted?"
    assert result.get("source") == "llm"


@pytest.mark.asyncio
async def test_parse_question_multilingual_relative_dates():
    """Verify live parse_question correctly maps English and Chinese relative dates using reference calendar."""
    test_today = date(2026, 7, 31)

    res_today = await parse_question("i am meeting my friends later today, what should i do?", today=test_today)
    assert res_today["dates"] == [test_today]

    res_cn = await parse_question("我今晚要跟朋友聚會，該注意什麼？", today=test_today)
    assert res_cn["dates"] == [test_today]

    res_yesterday = await parse_question("Yesterday I had an argument with my boss", today=test_today)
    assert res_yesterday["dates"] == [test_today - timedelta(days=1)]
