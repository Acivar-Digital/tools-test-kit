from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src2.core.schemas.unified import ChartProfile, OracleDeps, OracleQueryIntent
from src2.interfaces.telegram.chronomancer.oracle_coordinator import handle_oracle
from src2.interfaces.telegram.chronomancer.oracle_gatherer import gather_oracle_deps
from src2.interfaces.telegram.chronomancer.state_writer import UserState


@pytest.mark.asyncio
async def test_oracle_gatherer_transits_and_deps():
    profile = ChartProfile(
        day_master="Bing",
        dm_element="Fire",
        language="English",
    )
    user_state = UserState(recent_concerns="Career advancement")
    intent = OracleQueryIntent(
        clarified_prompt="What is my career forecast for 2028 and 2030?",
        intent_category="CAREER_TIMELINE",
        sentiment="OPTIMISTIC",
        mental_model="Seeking job transition timing",
        target_years=[2028, 2030],
        time_horizon="FUTURE",
        focus_domain="Career",
        rag_keywords=["官星受冲"],
    )

    deps = await gather_oracle_deps(
        user_id=12345,
        intent=intent,
        profile=profile,
        user_state=user_state,
    )

    assert isinstance(deps, OracleDeps)
    assert deps.user_id == 12345
    assert 2028 in deps.transits_by_year
    assert 2030 in deps.transits_by_year
    assert "2028" in deps.transits_by_year[2028]


@pytest.mark.asyncio
async def test_handle_oracle_coordinator_flow():
    mock_intent = OracleQueryIntent(
        clarified_prompt="What is my wealth outlook for 2029?",
        intent_category="CAREER_TIMELINE",
        sentiment="NEUTRAL",
        mental_model="Wealth evaluation",
        target_years=[2029],
        time_horizon="FUTURE",
        focus_domain="Wealth",
    )

    mock_rewriter_result = MagicMock()
    mock_rewriter_result.output = mock_intent
    mock_rewriter_result.data = mock_intent

    mock_narrator_result = MagicMock()
    mock_narrator_result.output = "In 2029, your Fire Day Master experiences major wealth growth."
    mock_narrator_result.data = "In 2029, your Fire Day Master experiences major wealth growth."

    mock_rewriter_agent = MagicMock()
    mock_rewriter_agent.run = AsyncMock(return_value=mock_rewriter_result)

    mock_narrator_agent = MagicMock()
    mock_narrator_agent.run = AsyncMock(return_value=mock_narrator_result)

    with (
        patch("src2.interfaces.telegram.chronomancer.oracle_coordinator.get_oracle_rewriter_agent", return_value=mock_rewriter_agent),
        patch("src2.interfaces.telegram.chronomancer.oracle_coordinator.get_oracle_narrator_agent", return_value=mock_narrator_agent),
    ):
        profile = ChartProfile(day_master="Bing", dm_element="Fire")
        user_state = UserState()

        response = await handle_oracle(
            user_id=99999,
            query="What is my wealth outlook for 2029?",
            profile=profile,
            user_state=user_state,
            sifu_mode=1,
        )

        assert "In 2029, your Fire Day Master experiences major wealth growth." in response
        assert "Mode: Oracle (Lifetime)" in response


@pytest.mark.asyncio
async def test_handle_oracle_conversation_history_formatting():
    mock_intent = OracleQueryIntent(
        clarified_prompt="How is my relationship timing?",
        intent_category="RELATIONSHIP_COMPAT",
        sentiment="NEUTRAL",
        mental_model="Relationship evaluation",
        target_years=[2026],
        time_horizon="FUTURE",
        focus_domain="Relationships",
    )

    mock_rewriter_result = MagicMock()
    mock_rewriter_result.output = mock_intent
    mock_rewriter_result.data = mock_intent

    mock_narrator_result = MagicMock()
    mock_narrator_result.output = "Relationship outlook for 2026 is stable."
    mock_narrator_result.data = "Relationship outlook for 2026 is stable."

    mock_rewriter_agent = MagicMock()
    mock_rewriter_agent.run = AsyncMock(return_value=mock_rewriter_result)

    mock_narrator_agent = MagicMock()
    mock_narrator_agent.run = AsyncMock(return_value=mock_narrator_result)

    mock_history_item_1 = MagicMock()
    mock_history_item_1.role = "user"
    mock_history_item_1.content = "Previous question"

    mock_history_item_2 = MagicMock()
    mock_history_item_2.role = "assistant"
    mock_history_item_2.content = "Previous answer"

    conversation_history = [mock_history_item_1, mock_history_item_2]

    with (
        patch("src2.interfaces.telegram.chronomancer.oracle_coordinator.get_oracle_rewriter_agent", return_value=mock_rewriter_agent),
        patch("src2.interfaces.telegram.chronomancer.oracle_coordinator.get_oracle_narrator_agent", return_value=mock_narrator_agent),
    ):
        profile = ChartProfile(day_master="Bing", dm_element="Fire")
        user_state = UserState()

        response = await handle_oracle(
            user_id=88888,
            query="How is my relationship timing?",
            profile=profile,
            user_state=user_state,
            sifu_mode=1,
            conversation_history=conversation_history,
        )

        assert "Relationship outlook for 2026 is stable." in response
        assert mock_narrator_agent.run.called
        call_kwargs = mock_narrator_agent.run.call_args.kwargs
        assert "message_history" in call_kwargs
        msg_history = call_kwargs["message_history"]
        assert len(msg_history) == 2
