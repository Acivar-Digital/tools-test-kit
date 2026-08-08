# ruff: noqa: E402
import os
from unittest.mock import patch

import pytest
import sqlalchemy
import sqlalchemy.ext.asyncio

# 🔥 CRITICAL: Disable external services BEFORE any src2 import
os.environ["SENTRY_DSN"] = ""
os.environ["DISABLE_SENTRY"] = "1"
os.environ["LOGFIRE_NO_PLACEHOLDER"] = "true"
os.environ["LOGFIRE_IGNORE_MISSING_DATA_KEYS"] = "true"
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/baziforecaster")

# Redirect SQLAlchemy engine creation in test session to SQLite in-memory to prevent TCP connection hangs
_orig_create_engine = sqlalchemy.create_engine
_orig_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine


def _mock_create_engine(url, *args, **kwargs):
    if "postgresql" in str(url):
        eng = _orig_create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

        from src2.core.database.models import Base

        SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"
        SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(32)"
        Base.metadata.create_all(eng)
        return eng
    return _orig_create_engine(url, *args, **kwargs)


def _mock_create_async_engine(url, *args, **kwargs):
    if "postgresql" in str(url):
        return _orig_create_async_engine("sqlite+aiosqlite:///:memory:")
    return _orig_create_async_engine(url, *args, **kwargs)


sqlalchemy.create_engine = _mock_create_engine
sqlalchemy.ext.asyncio.create_async_engine = _mock_create_async_engine


# Module-level patch: stays active for entire pytest session, BEFORE
# memory_manager.py:26 triggers _db = Database("bot.db") at import time
patch(
    "src2.interfaces.telegram.db.Database._run_pg_migrations",
    lambda self: None,
).start()


@pytest.fixture(autouse=True)
def _block_db_init():
    """Redundant per-test guard. The module-level patch above breaks the
    import-time hang in memory_manager.py:26."""
    yield
