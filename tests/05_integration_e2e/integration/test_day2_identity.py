"""
Unit tests for Day 2: Identity Service
Tests UUID-based user creation, platform account linking, and lookups.
Requires PostgreSQL running.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import Base
from src.identity.service import (
    create_user,
    get_user_by_platform,
    get_user_by_uuid,
    link_platform_account,
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


@pytest.mark.asyncio
class TestCreateUser:
    async def test_create_user_returns_user_with_uuid(self, async_session):
        user = await create_user(async_session)
        assert user is not None
        assert isinstance(user.id, uuid.UUID)
        assert user.tier == "FREE"
        assert user.region == "SG"
        await async_session.commit()

    async def test_create_user_with_custom_tier(self, async_session):
        user = await create_user(async_session, tier="PRO", region="EU")
        assert user.tier == "PRO"
        assert user.region == "EU"
        await async_session.commit()

    async def test_create_multiple_users_get_unique_uuids(self, async_session):
        user1 = await create_user(async_session)
        user2 = await create_user(async_session)
        assert user1.id != user2.id
        await async_session.commit()


@pytest.mark.asyncio
class TestGetUserByUuid:
    async def test_get_existing_user(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        found = await get_user_by_uuid(async_session, user.id)
        assert found is not None
        assert found.id == user.id
        await async_session.commit()

    async def test_get_nonexistent_user_returns_none(self, async_session):
        fake_id = uuid.uuid4()
        found = await get_user_by_uuid(async_session, fake_id)
        assert found is None


@pytest.mark.asyncio
class TestGetUserByPlatform:
    async def test_get_user_by_telegram_platform(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        await link_platform_account(
            async_session, user.id, "telegram", "123456789"
        )
        await async_session.flush()

        found = await get_user_by_platform(async_session, "telegram", "123456789")
        assert found is not None
        assert found.id == user.id
        await async_session.commit()

    async def test_get_user_by_nonexistent_platform_returns_none(self, async_session):
        found = await get_user_by_platform(async_session, "telegram", "nonexistent")
        assert found is None


@pytest.mark.asyncio
class TestLinkPlatformAccount:
    async def test_link_telegram_account(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        account = await link_platform_account(
            async_session, user.id, "telegram", "999888777"
        )
        assert account.platform == "telegram"
        assert account.platform_user_id == "999888777"
        assert account.user_id == user.id
        await async_session.commit()

    async def test_link_multiple_platforms_to_same_user(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        await link_platform_account(async_session, user.id, "telegram", "111")
        await link_platform_account(async_session, user.id, "whatsapp", "222")
        await async_session.flush()

        tg_user = await get_user_by_platform(async_session, "telegram", "111")
        wa_user = await get_user_by_platform(async_session, "whatsapp", "222")
        assert tg_user.id == wa_user.id
        await async_session.commit()
