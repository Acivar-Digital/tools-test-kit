"""
Unit tests for Day 8: Privacy & Compliance Service
Tests consent recording, data export, and forget_user cascading deletion.
"""
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import (
    Base,
    ChatLog,
    Session,
    User,
)
from src.identity.service import create_user, link_platform_account, record_consent
from src.services.compliance import export_user_data, forget_user
from src.services.memory import log_chat
from src.services.session import save_session

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
class TestRecordConsent:
    async def test_record_consent_creates_record(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        consent = await record_consent(async_session, user.id, "1.0", "127.0.0.1")
        assert consent.terms_accepted is True
        assert consent.privacy_policy_version == "1.0"
        assert consent.ip_address == "127.0.0.1"
        await async_session.commit()


@pytest.mark.asyncio
class TestExportUserData:
    async def test_export_returns_user_data(self, async_session):
        user = await create_user(async_session, tier="PRO")
        await async_session.flush()
        await link_platform_account(async_session, user.id, "telegram", "12345")
        await log_chat(async_session, user.id, "telegram", "user", "Hello")
        await save_session(async_session, user.id, {"step": "CHOOSING"})
        await async_session.flush()

        data = await export_user_data(async_session, user.id)
        assert data["user"]["tier"] == "PRO"
        assert len(data["platform_accounts"]) == 1
        assert data["reports"] == []

    async def test_export_nonexistent_user(self, async_session):
        data = await export_user_data(async_session, uuid.uuid4())
        assert "error" in data


@pytest.mark.asyncio
class TestForgetUser:
    async def test_forget_user_cascades_deletion(self, async_session):
        user = await create_user(async_session)
        await async_session.flush()
        await link_platform_account(async_session, user.id, "telegram", "99999")
        await log_chat(async_session, user.id, "telegram", "user", "Bye")
        await save_session(async_session, user.id, {"step": "CHOOSING"})
        await async_session.flush()

        user_id = user.id
        await forget_user(async_session, user_id)
        await async_session.flush()

        from sqlalchemy import select
        user_result = await async_session.execute(select(User).where(User.id == user_id))
        assert user_result.scalar_one_or_none() is None

        session_result = await async_session.execute(
            select(Session).where(Session.user_id == user_id)
        )
        assert session_result.scalar_one_or_none() is None

        chat_result = await async_session.execute(
            select(ChatLog).where(ChatLog.user_id == user_id)
        )
        assert chat_result.scalar_one_or_none() is None

    async def test_forget_user_does_not_affect_other_users(self, async_session):
        user1 = await create_user(async_session)
        user2 = await create_user(async_session)
        await async_session.flush()
        await log_chat(async_session, user1.id, "telegram", "user", "User1 msg")
        await log_chat(async_session, user2.id, "telegram", "user", "User2 msg")
        await async_session.flush()

        await forget_user(async_session, user1.id)
        await async_session.flush()

        from sqlalchemy import select
        chat_result = await async_session.execute(
            select(ChatLog).where(ChatLog.user_id == user2.id)
        )
        assert chat_result.scalar_one_or_none() is not None
