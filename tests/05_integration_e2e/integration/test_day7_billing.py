"""
Unit tests for Day 7: Billing Service
Tests promo code validation, tier management, and rate limiting.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import Base, PromoCode, User
from src.identity.service import create_user
from src.services.billing import (
    TIER_LIMITS,
    apply_promo_code,
    get_user_limits,
    set_user_tier,
    validate_promo_code,
)

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


class TestTierLimits:
    def test_free_tier_limits(self):
        limits = TIER_LIMITS["FREE"]
        assert limits["max_reports_per_day"] == 1
        assert limits["can_ask"] is False
        assert limits["rate_limit_per_minute"] == 5

    def test_pro_tier_limits(self):
        limits = TIER_LIMITS["PRO"]
        assert limits["max_reports_per_day"] == 5
        assert limits["can_ask"] is True
        assert limits["rate_limit_per_minute"] == 20

    def test_enterprise_tier_limits(self):
        limits = TIER_LIMITS["ENTERPRISE"]
        assert limits["max_reports_per_day"] == 999
        assert limits["can_ask"] is True
        assert limits["rate_limit_per_minute"] == 60


@pytest.mark.asyncio
class TestPromoCode:
    async def test_validate_valid_promo_code(self, async_session):
        promo = PromoCode(code="TEST2024", code_type="monthly", tier_granted="PRO", max_uses=10)
        async_session.add(promo)
        await async_session.flush()

        result = await validate_promo_code(async_session, "TEST2024")
        assert result is not None
        assert result.code == "TEST2024"

    async def test_validate_invalid_promo_code(self, async_session):
        result = await validate_promo_code(async_session, "INVALID")
        assert result is None

    async def test_apply_promo_code_success(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        promo = PromoCode(code="WELCOME", code_type="tier_upgrade", tier_granted="PRO", max_uses=100)
        async_session.add(promo)
        await async_session.flush()

        result = await apply_promo_code(async_session, user.id, "WELCOME")
        assert result is True

        from sqlalchemy import select
        user_result = await async_session.execute(select(User).where(User.id == user.id))
        updated_user = user_result.scalar_one()
        assert updated_user.tier == "PRO"
        await async_session.commit()

    async def test_apply_promo_code_idempotent(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        promo = PromoCode(code="UNIQUE", code_type="tier_upgrade", tier_granted="PRO", max_uses=100)
        async_session.add(promo)
        await async_session.flush()

        first = await apply_promo_code(async_session, user.id, "UNIQUE")
        second = await apply_promo_code(async_session, user.id, "UNIQUE")
        assert first is True
        assert second is False
        await async_session.commit()


@pytest.mark.asyncio
class TestSetUserTier:
    async def test_set_tier_success(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        await set_user_tier(async_session, user.id, "ENTERPRISE")
        await async_session.flush()

        from sqlalchemy import select
        result = await async_session.execute(select(User.tier).where(User.id == user.id))
        assert result.scalar_one() == "ENTERPRISE"
        await async_session.commit()

    async def test_set_invalid_tier_raises(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        with pytest.raises(ValueError, match="Invalid tier"):
            await set_user_tier(async_session, user.id, "INVALID")


@pytest.mark.asyncio
class TestGetUserLimits:
    async def test_free_user_limits(self, async_session):
        user = await create_user(async_session, tier="FREE")
        await async_session.flush()
        limits = await get_user_limits(async_session, user.id)
        assert limits["max_reports_per_day"] == 1

    async def test_pro_user_limits(self, async_session):
        user = await create_user(async_session, tier="PRO")
        await async_session.flush()
        limits = await get_user_limits(async_session, user.id)
        assert limits["max_reports_per_day"] == 5
