# ruff: noqa: E402
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy
import sqlalchemy.ext.asyncio

# Add project root to Python path for test imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure required test env vars are set before any src2 import
os.environ.setdefault("SENTRY_DSN", "")
os.environ.setdefault("DISABLE_SENTRY", "1")
os.environ.setdefault("LOGFIRE_NO_PLACEHOLDER", "true")
os.environ.setdefault("LOGFIRE_IGNORE_MISSING_DATA_KEYS", "true")
# Kit config: fail-loud at import when KIT_LIVE=true. Source the kit-facing
# vars HERE so a downloading user only fills kit-tests/.env (never hardcode creds).
from config import load_config  # noqa: E402
_path, _base_url, _api_key, _model, _mem0_model = load_config()
os.environ.setdefault("KIT_PATH", _path or str(Path(__file__).parent.parent))
os.environ.setdefault("LLM_BASE_URL", _base_url)
os.environ.setdefault("LLM_API_KEY", _api_key)
os.environ.setdefault("MEM0_MODEL", _mem0_model)
os.environ.setdefault("CHRONO_MODEL", _model)
os.environ.setdefault("CHRONO_URL", _base_url)
os.environ.setdefault("TELEGRAM_API_BASE", "https://api.telegram.org")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/baziforecaster")

# Redirect SQLAlchemy engine creation in test session to SQLite in-memory to prevent TCP connection hangs
_orig_create_engine = sqlalchemy.create_engine
_orig_create_async_engine = sqlalchemy.ext.asyncio.create_async_engine


def _mock_create_engine(url, *args, **kwargs):
    if "postgresql" in str(url):
        eng = _orig_create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

        from src2.core.database.models import Base

        SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"  # type: ignore[attr-defined]
        SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(32)"  # type: ignore[attr-defined]
        Base.metadata.create_all(eng)
        try:
            from src.database.models import Base as LegacyBase
            LegacyBase.metadata.create_all(eng)
        except Exception:
            pass
        return eng
    return _orig_create_engine(url, *args, **kwargs)


def _mock_create_async_engine(url, *args, **kwargs):
    if "postgresql" in str(url):
        return _orig_create_async_engine("sqlite+aiosqlite:///:memory:")
    return _orig_create_async_engine(url, *args, **kwargs)


sqlalchemy.create_engine = _mock_create_engine
sqlalchemy.ext.asyncio.create_async_engine = _mock_create_async_engine

# Patch Database migrations for import-time database calls
patch(
    "src2.interfaces.telegram.db.Database._run_pg_migrations",
    lambda self: None,
).start()

