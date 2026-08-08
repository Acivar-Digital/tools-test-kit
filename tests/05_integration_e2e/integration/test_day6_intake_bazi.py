"""
Unit tests for Day 6: Intake + Bazi Services
Tests the platform-agnostic conversation engine and Bazi service stubs.
"""
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import Base
from src.identity.service import create_user
from src.services.bazi import ask_chronomancer, generate_report, get_daily_forecast
from src.services.intake import handle_message

DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/baziforecaster"


@pytest_asyncio.fixture
async def async_session():
    engine = create_async_engine(DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    async with session_factory() as session:
        yield session
        await session.rollback()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def test_user(async_session):
    user = await create_user(async_session)
    await async_session.flush()
    return user


@pytest.mark.asyncio
class TestIntakeService:
    async def test_start_command(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/start")
        assert "Welcome" in response
        assert "/forecast" in response

    async def test_help_command(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/help")
        assert "/forecast" in response
        assert "/daily" in response

    async def test_reset_command(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/reset")
        assert "reset" in response.lower()

    async def test_forecast_flow_initiates_collection(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/forecast")
        assert "birth date" in response.lower()

    async def test_daily_flow_initiates_collection(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/daily")
        assert "date" in response.lower()

    async def test_ask_with_question(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/ask Will I get rich?")
        assert "Chronomancer" in response

    async def test_ask_without_question_returns_usage(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "/ask")
        assert "usage" in response.lower() or "provide" in response.lower()

    async def test_unknown_command_returns_help_prompt(self, async_session, test_user):
        response = await handle_message(async_session, test_user.id, "random text")
        assert "/help" in response

    async def test_confirm_yes_moves_to_processing(self, async_session, test_user):
        await handle_message(async_session, test_user.id, "/forecast")
        await handle_message(async_session, test_user.id, "1990-01-01")
        response = await handle_message(async_session, test_user.id, "yes")
        assert "processing" in response.lower() or "queued" in response.lower()

    async def test_confirm_no_resets(self, async_session, test_user):
        await handle_message(async_session, test_user.id, "/forecast")
        await handle_message(async_session, test_user.id, "1990-01-01")
        response = await handle_message(async_session, test_user.id, "no")
        assert "cancelled" in response.lower() or "start" in response.lower()


@pytest.mark.asyncio
class TestBaziService:
    async def test_generate_report_returns_pending(self, async_session, test_user):
        result = await generate_report(async_session, test_user.id)
        assert result["status"] == "pending"
        assert "user_id" in result

    async def test_get_daily_forecast_default_date(self, async_session, test_user):
        result = await get_daily_forecast(async_session, test_user.id)
        assert result["status"] == "pending"
        assert "date" in result

    async def test_get_daily_forecast_custom_date(self, async_session, test_user):
        target = date(2024, 6, 15)
        result = await get_daily_forecast(async_session, test_user.id, target)
        assert result["date"] == "2024-06-15"

    async def test_ask_chronomancer_returns_response(self, async_session, test_user):
        response = await ask_chronomancer(async_session, test_user.id, "Will I succeed?")
        assert "Chronomancer" in response
        assert "Will I succeed?" in response
