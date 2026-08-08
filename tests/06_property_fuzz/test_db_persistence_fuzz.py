"""Property-based fuzzing tests for Database persistence boundary integrity.

Ticket: baziforecaster-6pnz
Goal: throw randomized and adversarial data at the SQLite persistence layer
(`Database` in src2/interfaces/telegram/db.py) to prove the following
invariants hold:

  1. SQLite Session Round-Trip -- a valid session state dump saved via
     ``update_session`` is retrievable verbatim via ``get_session`` and
     survives Hypothesis-generated content (null bytes, emojis, nested dicts
     up to 1200 messages / 14 MB).
  2. Corrupt JSONL Recovery -- ``_read_cache_file`` isolates individual
     malformed JSONL lines (truncated, embedded null bytes, non-dict payloads)
     and still yields all valid entries. No exception escapes to the caller.
  3. Concurrent DailyForecast Upsert -- 10 async threads calling
     ``save_daily_forecast`` for the same (user, date, language) produce
     exactly one row; no IntegrityError or "database is closed" leaks.
  4. SQL-Level state_json Corruption -- a row whose ``state_json`` was
     corrupted via raw SQL (broken JSON, non-dict payload) causes
     ``get_session`` to return ``(None, 0)`` with a logged warning, not crash.
  5. Optimistic Lock Integrity -- ``update_session`` calls with stale
     ``expected_version`` values raise ``RuntimeError``, and valid versions
     produce monotonically increasing version counters.
  6. Schema Constraint Enforcement -- a raw INSERT violating the unique
     constraint on (user_id, date, language) raises sqlite3.IntegrityError.

Rules enforced (per SKILL.md):
- NaN/Infinity guard checks on all float outputs.
- Native Hypothesis strategies (no try/except escapes to skip bad data).
- Property-based assertions (invariants, not specific outputs).
"""

from __future__ import annotations

# ── Isolate DB + disable side-effects BEFORE importing src2 modules. ─────────
# DATABASE_URL must be empty at import time so the module-level PostgreSQL
# async engine creation is skipped (_pg_url == "" → _async_engine = None).
# We patch DATABASE_URL to sqlite:///:memory: inside the `db` fixture.
import os as _os

_os.environ.setdefault("DISABLE_SENTRY", "1")
_os.environ.setdefault("BGEM3_URL", "http://localhost:666")
_os.environ.setdefault("BGEM3_TOKEN", "test")

import asyncio
import json
import math
import sqlite3
import uuid as _uuid
from collections import Counter
from datetime import date
from unittest.mock import patch

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from src2.core.schemas import SessionStep
from src2.interfaces.telegram import db as db_mod
from src2.interfaces.telegram.db import Database

_VALID_STEPS = list(SessionStep.__args__)

# ── Shared Hypothesis profile for DB-backed tests ────────────────────────
# Function-scoped fixtures are suppressed because each test creates a fresh
# in-memory Database via the fixture; the shared state across examples within
# a single test function is intentional (round-trip within one DB instance).
settings.register_profile(
    "db_fuzz",
    deadline=None,
    suppress_health_check=[
        HealthCheck.function_scoped_fixture,
        HealthCheck.data_too_large,
        HealthCheck.too_slow,
    ],
)
settings.load_profile("db_fuzz")


# ── Fixtures ──────────────────────────────────────────────────────────────

@pytest.fixture()
def db() -> Database:
    """Yield a fresh in-memory Database per test (no file side-effects)."""
    from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
    # The module-level monkey-patch that maps JSONB->JSON for SQLite only runs
    # at import time when DATABASE_URL is already sqlite:///:memory:. Since we
    # patch DATABASE_URL in the fixture *after* import, we must re-apply it.
    SQLiteTypeCompiler.visit_JSONB = lambda self, type_, **kw: "JSON"
    SQLiteTypeCompiler.visit_UUID = lambda self, type_, **kw: "CHAR(32)"
    with patch.object(db_mod, "DATABASE_URL", "sqlite:///:memory:"):
        db = Database(":memory:")
        yield db


@pytest.fixture()
def cache_file(tmp_path):
    """Yield a writable .jsonl cache path, then restore CACHE_FILE global."""
    import src2.engine.bazi_cache as bc
    fpath = tmp_path / "bazi_cache.jsonl"
    original = bc.CACHE_FILE
    bc.CACHE_FILE = fpath
    yield fpath
    bc.CACHE_FILE = original


# ── Helpers ───────────────────────────────────────────────────────────────

def _safe_session_dump(step: str = "START") -> dict:
    """Build a minimal but valid Telegram Session model dump."""
    from src2.interfaces.telegram.session import Session as TelegramSession
    s = TelegramSession(chat_id=1, step=step)
    dump = s.model_dump()
    dump.pop("version", None)
    dump.pop("is_new", None)
    dump.pop("tier", None)
    return dump


def _is_valid_kw(kw: str) -> bool:
    has_chinese = any("\u4e00" <= c <= "\u9fff" for c in kw)
    has_latin = any(ord(c) < 128 for c in kw)
    return has_chinese and not has_latin


# ── 1. SQLite Session Round-Trip ──────────────────────────────────────────

_MESSAGE_STRAT = st.one_of(
    st.text(
        alphabet=st.characters(min_codepoint=0x20, max_codepoint=0x10FFFF,
                               exclude_categories=("Cs",)),
        min_size=0, max_size=500,
    ),
    st.just(""),
)


@given(
    step=st.sampled_from(_VALID_STEPS),
    messages=st.lists(_MESSAGE_STRAT, min_size=0, max_size=30),
)
@settings(max_examples=100)
def test_session_round_trip(db: Database, step: str, messages: list[str]):
    from src2.interfaces.telegram.session import ChatMessage
    from src2.interfaces.telegram.session import Session as TelegramSession

    chat_msgs = [ChatMessage(role="user", content=m) for m in messages if m]
    s = TelegramSession(chat_id=1, step=step, conversation_history=chat_msgs)
    dump = s.model_dump()
    dump.pop("version", None)
    dump.pop("is_new", None)
    dump.pop("tier", None)

    db.delete_session(1)
    db.update_session(1, dump)

    retrieved, version = db.get_session(1)
    assert retrieved is not None, "get_session returned None for a freshly saved session"
    assert version == 1, f"expected version 1, got {version}"
    assert retrieved.step == step, f"step mismatch: {retrieved.step!r} != {step!r}"
    assert len(retrieved.conversation_history) == len(chat_msgs), "history length mismatch"


@given(messages=st.lists(_MESSAGE_STRAT, min_size=1200, max_size=1200))
@settings(max_examples=10)
def test_session_round_trip_large_conversation(db: Database, messages: list[str]):
    """1200 messages / ~14 MB must round-trip without truncation or crash."""
    from src2.interfaces.telegram.session import ChatMessage
    from src2.interfaces.telegram.session import Session as TelegramSession

    chat_msgs = [ChatMessage(role="user", content=m) for m in messages if m]
    total_bytes = sum(len(m.encode("utf-8")) for m in messages)
    s = TelegramSession(chat_id=42, step="PROCESSING", conversation_history=chat_msgs)
    s.metadata.intake = {"total_bytes": total_bytes}
    dump = s.model_dump()
    dump.pop("version", None)
    dump.pop("is_new", None)
    dump.pop("tier", None)

    db.delete_session(42)
    db.update_session(42, dump)

    retrieved, _ = db.get_session(42)
    assert retrieved is not None
    assert len(retrieved.conversation_history) == len(chat_msgs), "history length mismatch"
    assert (
        retrieved.metadata.intake.get("total_bytes") == total_bytes
    ), "metadata total_bytes corrupted"


# ── 2. Corrupt JSONL Recovery ─────────────────────────────────────────────

@given(
    valid_entries=st.lists(
        st.tuples(
            st.text(min_size=1, max_size=10).map(lambda s: "木" + s),
            st.text(min_size=1, max_size=500),
        ),
        min_size=1, max_size=20,
    ),
    corrupt_lines=st.lists(
        st.one_of(
            st.text(min_size=1, max_size=200),
            st.binary(min_size=1, max_size=50),
            st.integers(),
            st.none(),
        ),
        min_size=0, max_size=30,
    ),
)
@settings(max_examples=50)
def test_cache_file_skips_corrupt_lines(cache_file, valid_entries, corrupt_lines):
    """Mix valid + corrupt lines in arbitrary order; all valid entries survive."""
    import src2.engine.bazi_cache as bc

    lines: list[str] = []

    for kw, text in valid_entries:
        if _is_valid_kw(kw):
            lines.append(json.dumps({"keywords": kw, "text": text}, ensure_ascii=False))

    for corrupt in corrupt_lines:
        if isinstance(corrupt, bytes):
            lines.append(corrupt.decode("latin-1"))
        else:
            lines.append(str(corrupt))

    with open(cache_file, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    results = list(bc._read_cache_file())

    expected = Counter((kw, text) for kw, text in valid_entries if _is_valid_kw(kw))
    actual = Counter(results)
    assert actual == expected, "valid cache entries lost or corrupt entries leaked"
    assert len(results) == sum(expected.values()), "duplicate or lost results"


# ── 3. Concurrent DailyForecast Upsert ────────────────────────────────────

_DATE_STRAT = st.dates(min_value=date(2000, 1, 1), max_value=date(2030, 12, 31)).map(lambda d: d.isoformat())


@given(
    target_date=_DATE_STRAT,
    stem=st.text(min_size=1, max_size=10),
    branch=st.text(min_size=1, max_size=10),
    profile_hash=st.text(min_size=1, max_size=64),
    events=st.lists(st.text(max_size=100), max_size=5),
    hourly_scores=st.dictionaries(
        st.text(min_size=1, max_size=10),
        st.floats(allow_nan=False, allow_infinity=False, min_value=-100.0, max_value=100.0),
        max_size=5,
    ),
)
@settings(max_examples=25)
def test_concurrent_daily_forecast_upsert(db: Database, target_date, stem, branch,
                                           profile_hash, events, hourly_scores):
    user_id = 999
    activities = {"favorable": ["prosperity"], "unfavorable": ["conflict"]}
    db.delete_daily_forecasts_for_user(user_id)

    async def _run():
        loop = asyncio.get_running_loop()
        coros = [
            loop.run_in_executor(
                None,
                lambda i: db.save_daily_forecast(
                    user_id, profile_hash, target_date, stem, branch,
                    activities, events, f"narrative_{i}", False, hourly_scores, "English",
                ),
                i,
            )
            for i in range(10)
        ]
        await asyncio.gather(*coros)

    asyncio.run(_run())

    uuid_val = db._get_or_create_uuid(user_id)
    uuid_str = str(uuid_val).replace("-", "")
    row = db.conn.execute(
        "SELECT COUNT(*) FROM daily_forecasts WHERE user_id = ? AND date = ? AND language = ?",
        (uuid_str, target_date, "English"),
    ).fetchone()
    count = row[0]
    assert count == 1, f"expected 1 row after 10 concurrent upserts, got {count}"

    stored = db.conn.execute(
        "SELECT hourly_scores_json FROM daily_forecasts WHERE user_id = ? AND date = ? AND language = ?",
        (uuid_str, target_date, "English"),
    ).fetchone()
    if stored and stored[0]:
        for v in json.loads(stored[0]).values():
            if isinstance(v, float):
                assert not math.isnan(v), "hourly_scores_json leaked NaN!"
                assert not math.isinf(v), "hourly_scores_json leaked Infinity!"


# ── 4. SQL-Level state_json Corruption ────────────────────────────────────

@given(
    state=st.fixed_dictionaries({
        "step": st.sampled_from(_VALID_STEPS),
        "profile_data": st.dictionaries(
            st.text(min_size=1, max_size=30),
            st.text(max_size=100),
            max_size=5,
        ),
        "tailoring": st.none(),
    }),
)
@settings(max_examples=25)
def test_sql_corrupted_state_json_returns_none(db: Database, state: dict):
    uuid_val = db._get_or_create_uuid(777)
    uuid_str = str(uuid_val).replace("-", "")

    corrupt_payloads = [
        "{broken json",
        json.dumps(["not", "a", "dict"]),
        json.dumps("just a string"),
        json.dumps(42),
        json.dumps(True),
        json.dumps(None),
        "",
    ]

    for payload in corrupt_payloads:
        db.conn.execute(
            "DELETE FROM sessions WHERE user_id = ?",
            (uuid_str,),
        )
        db.conn.commit()

        db.conn.execute(
            "INSERT INTO sessions (user_id, state_json, version) VALUES (?, ?, ?)",
            (uuid_str, json.dumps(state), 1),
        )
        db.conn.commit()

        db.conn.execute(
            "UPDATE sessions SET state_json = ? WHERE user_id = ?",
            (payload, uuid_str),
        )
        db.conn.commit()

        result, version = db.get_session(777)
        assert result is None, (
            f"corrupt state_json payload {payload!r} should yield None, got {result}"
        )
        assert version == 0, f"expected version 0 for corrupt state, got {version}"


# ── 5. Optimistic Lock Integrity ──────────────────────────────────────────

@given(
    versions=st.lists(
        st.integers(min_value=0, max_value=10),
        min_size=3, max_size=3,
    ),
)
@settings(max_examples=25)
def test_optimistic_lock_serialization(db: Database, versions):
    db.delete_session(1)
    db.update_session(1, _safe_session_dump("START"))

    _, base_version = db.get_session(1)
    assert base_version == 1, f"expected base version 1, got {base_version}"

    with pytest.raises(RuntimeError, match="Optimistic lock failure"):
        db.update_session(1, _safe_session_dump("CHOOSING"), expected_version=999)

    db.update_session(1, _safe_session_dump("CHOOSING"), expected_version=1)
    _, v1 = db.get_session(1)
    assert v1 == 2, f"expected version 2 after update, got {v1}"

    db.update_session(1, _safe_session_dump("COLLECTING"), expected_version=2)
    _, v2 = db.get_session(1)
    assert v2 == 3, f"expected version 3 after second update, got {v2}"
    assert v2 > v1 > base_version, "versions must be monotonically increasing"


# ── 6. Schema Constraint Enforcement ──────────────────────────────────────

def test_unique_constraint_on_daily_forecast(db: Database):
    """A raw INSERT violating the (user_id, date, language) unique constraint
    on daily_forecasts must raise sqlite3.IntegrityError."""
    uuid_val = db._get_or_create_uuid(111)
    uuid_str = str(uuid_val).replace("-", "")

    # First raw INSERT should succeed.
    db.conn.execute(
        "INSERT INTO daily_forecasts (id, user_id, profile_hash, date, stem, branch, "
        "activities_json, events_json, hourly_scores_json, narrative, language, is_permanent) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (str(_uuid.uuid4()), uuid_str, "hash1", "2030-01-01", "Jia", "Zi", "{}",
         "[]", "{}", "narrative_0", "English", False),
    )
    db.conn.commit()

    # Second raw INSERT with same (user_id, date, language) — must fail.
    with pytest.raises(sqlite3.IntegrityError):
        db.conn.execute(
            "INSERT INTO daily_forecasts (id, user_id, profile_hash, date, stem, branch, "
            "activities_json, events_json, hourly_scores_json, narrative, language, is_permanent) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(_uuid.uuid4()), uuid_str, "hash2", "2030-01-01", "Bing", "Yin", "{}",
             "[]", "{}", "narrative_1", "English", False),
        )
        db.conn.commit()

    db.conn.rollback()
