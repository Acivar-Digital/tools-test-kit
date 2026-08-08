"""
Unit tests for Day 3: Session + Memory Services
Tests UUID-based session management with optimistic locking, and memory/chat log operations.
Requires PostgreSQL running.
"""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.database.models import Base
from src.identity.service import create_user
from src.services.memory import delete_memory, get_memory_context, log_chat
from src.services.session import delete_session, get_session, save_session

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
class TestSessionService:
    async def test_get_session_returns_empty_dict_for_new_user(self, async_session, test_user):
        state = await get_session(async_session, test_user.id)
        assert state == {}

    async def test_save_and_get_session(self, async_session, test_user):
        state = {"step": "CHOOSING", "data": {"name": "Alice"}}
        await save_session(async_session, test_user.id, state)
        await async_session.flush()

        loaded = await get_session(async_session, test_user.id)
        assert loaded["step"] == "CHOOSING"
        assert loaded["data"]["name"] == "Alice"

    async def test_save_session_with_optimistic_lock(self, async_session, test_user):
        state_v1 = {"step": "CHOOSING", "version": 1}
        await save_session(async_session, test_user.id, state_v1)
        await async_session.flush()

        state_v2 = {"step": "COLLECTING", "version": 2}
        await save_session(async_session, test_user.id, state_v2, current_version=1)
        await async_session.flush()

        loaded = await get_session(async_session, test_user.id)
        assert loaded["step"] == "COLLECTING"

    async def test_optimistic_lock_failure_raises(self, async_session, test_user):
        state = {"step": "CHOOSING"}
        await save_session(async_session, test_user.id, state)
        await async_session.flush()

        with pytest.raises(RuntimeError, match="Optimistic lock failure"):
            await save_session(async_session, test_user.id, {"step": "X"}, current_version=99)

    async def test_delete_session(self, async_session, test_user):
        await save_session(async_session, test_user.id, {"step": "CHOOSING"})
        await async_session.flush()
        await delete_session(async_session, test_user.id)
        await async_session.flush()

        loaded = await get_session(async_session, test_user.id)
        assert loaded == {}


@pytest.mark.asyncio
class TestMemoryService:
    async def test_log_chat(self, async_session, test_user):
        log = await log_chat(async_session, test_user.id, "telegram", "user", "Hello!")
        assert log.role == "user"
        assert log.message_text == "Hello!"
        assert log.platform == "telegram"
        await async_session.commit()

    async def test_get_memory_context_returns_recent_messages(self, async_session, test_user):
        await log_chat(async_session, test_user.id, "telegram", "user", "Msg 1")
        await log_chat(async_session, test_user.id, "telegram", "assistant", "Reply 1")
        await log_chat(async_session, test_user.id, "telegram", "user", "Msg 2")
        await async_session.flush()

        context = await get_memory_context(async_session, test_user.id, limit=10)
        assert len(context) == 3
        assert context[0]["role"] == "user"
        assert context[0]["content"] == "Msg 2"

    async def test_get_memory_context_respects_limit(self, async_session, test_user):
        for i in range(10):
            await log_chat(async_session, test_user.id, "telegram", "user", f"Msg {i}")
        await async_session.flush()

        context = await get_memory_context(async_session, test_user.id, limit=3)
        assert len(context) == 3

    async def test_delete_memory(self, async_session, test_user):
        await log_chat(async_session, test_user.id, "telegram", "user", "Hello!")
        await async_session.flush()
        await delete_memory(async_session, test_user.id)
        await async_session.flush()

        context = await get_memory_context(async_session, test_user.id)
        assert context == []
