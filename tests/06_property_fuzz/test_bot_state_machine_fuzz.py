"""Stateful sequence fuzzing for the Telegram bot state machine.

Ticket: baziforecaster-fpo6
Goal: drive the bot's conversational state machine through random sequences of
``send_date`` / ``click_menu`` / ``send_garbage_text`` actions and assert:
  1. Anti-Deadlock Invariant: the bot never silently no-ops on a user message
     (it must emit a reply or advance state) and ``session.step`` never
     degrades to an invalid value.
  2. KeyError Safety: no ``KeyError`` raised from missing / corrupt session
     data escapes the routing layer to the webhook boundary.

The bot's LLM-dependent nodes (conductor, calendar engine, chronomancer asks)
are mocked so the fuzzer exercises the *routing/state-machine* layer
deterministically. Persistence uses the real SQLite ``bot.db`` (via
``BOT_DB_PATH``) so the DB layer is exercised too.
"""

from __future__ import annotations

import asyncio
import os
from contextlib import ExitStack
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

# --- Isolate DB + disable side-effects BEFORE importing src2 modules. ----------
_DB_PATH = os.path.join(os.path.dirname(__file__), ".fuzz_bot_state.db")
os.environ.setdefault("DISABLE_SENTRY", "1")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token")
os.environ.setdefault("TELEGRAM_API_BASE", "https://api.telegram.org")
os.environ.setdefault("TELEGRAM_ADMIN_ID", "999999999")
os.environ.setdefault("BOT_DB_PATH", _DB_PATH)
os.environ.setdefault("TELEGRAM_WEBHOOK_SECRET", "")

# ruff: noqa: E402  (env vars must be set before importing src2 modules)
from typing import get_args as _get_args

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

import src2.interfaces.telegram.app as app_mod
import src2.interfaces.telegram.chronomancer.coordinator as coordinator_mod
import src2.interfaces.telegram.conductor as conductor_mod
import src2.interfaces.telegram.intake.intake as intake_mod
import src2.interfaces.telegram.pipeline as pipeline_mod
import src2.interfaces.telegram.report_utils as report_utils
import src2.interfaces.telegram.security as security_mod
import src2.interfaces.telegram.session as session_mod
import src2.interfaces.telegram.stakeholder_intake as stakeholder_intake_mod
import src2.interfaces.telegram.ui_components as ui_components_mod
import src2.interfaces.telegram.utils as utils_mod
from src2.core.schemas import Pillar, SessionStep, UserProfile
from src2.interfaces.telegram.app import _route_callback_query, _route_message_data
from src2.interfaces.telegram.db import Database
from src2.interfaces.telegram.session import delete_session, get_session
from src2.interfaces.telegram.utils import ChronomancerReply

CHAT_ID = 999999999
PLATFORM = "telegram"
VALID_STEPS = set(_get_args(SessionStep))
# One shared Database instance so every module hits a single SQLite connection
# (avoids cross-instance file-lock contention / spurious "database is locked").
_DB = Database(_DB_PATH)

_DATE_STRAT = st.dates(min_value=date(1940, 1, 1), max_value=date(2010, 12, 31)).map(lambda d: d.isoformat())

_CONFIRM_WORDS = ["yes", "y", "ok", "confirm", "correct", "proceed", "go", "Yes", "OK", "✅"]
_GARBAGE_TEXTS = ["", "asdf", "123", "🎉", "random words", "/unknowncommand", "blah blah", "???", "x" * 200]
_SYSTEM_TEXTS = [
    "/start",
    "/help",
    "/info",
    "/reset",
    "/lang",
    "/sifu",
    "/subscribe",
    "/tips",
    "/daily",
    "/ask something",
    "/oracle is it good",
    "/week",
    "/7day",
    "/forecast_daily",
    "/stakeholders",
    "/manage",
    "/forecast",
]

_MENU_CALLBACKS = [
    "lang_English",
    "lang_Chinese",
    "lang_Indonesian",
    "lang_Malaysian",
    "start_auto",
    "start_manual",
    "confirm_yes",
    "confirm_no",
    "chart_7day",
    "tailor_choice_career",
    "tailor_choice_relationships",
    "tailor_choice_wealth",
    "tailor_choice_health",
    "tailor_choice_skip",
    "add_rel_Spouse",
    "add_rel_Partner",
    "del_stake_1",
    "cancel_del_stake",
    "garbage_cb_xyz",
]


def _action_strategy():
    return st.one_of(
        st.builds(lambda t: ("msg", t), st.sampled_from(_SYSTEM_TEXTS)),
        st.builds(lambda d: ("msg", d), _DATE_STRAT),
        st.builds(lambda w: ("msg", w), st.sampled_from(_CONFIRM_WORDS)),
        st.builds(lambda g: ("msg", g), st.sampled_from(_GARBAGE_TEXTS)),
        st.builds(lambda d: ("cb", d), st.sampled_from(_MENU_CALLBACKS)),
    )


_SEQUENCES = st.lists(_action_strategy(), min_size=2, max_size=20)


def _fresh_db():
    """Reset the fuzzed user to a fresh START session.

    Schema is created once at import time (Database("bot.db") honours BOT_DB_PATH),
    so we avoid the expensive per-example file deletion / table rebuild. Only the
    session row is cleared: ``get_user_prefs`` always returns complete defaults, so
    lingering prefs from a prior example cannot trigger KeyError.
    """
    try:
        delete_session(CHAT_ID, PLATFORM)
    except Exception:
        pass


def _patch_llm(stack: ExitStack):
    async def _fake_conductor(session, user_text):
        return (None, session)

    async def _fake_calendar(session):
        if session.profile is None:
            session.profile = UserProfile(
                gender="M",
                alias="Tester",
                year_pillar=Pillar(stem="Jia", branch="Zi"),
                month_pillar=Pillar(stem="Yi", branch="Chou"),
                day_pillar=Pillar(stem="Bing", branch="Yin"),
                hour_pillar=Pillar(stem="Ding", branch="Mao"),
                da_yun_pillar=Pillar(stem="Wu", branch="Chen"),
                day_master_strength="Weak",
                favorable_elements=["Wood"],
                unfavorable_elements=["Fire"],
                neutral_elements=["Earth", "Metal", "Water"],
                structure="Other",
                domain_focus="General",
            )
        return session

    canned = ChronomancerReply("canned reply", parse_mode="Markdown")
    stack.enter_context(patch.object(conductor_mod, "run_conductor", new=AsyncMock(side_effect=_fake_conductor)))
    stack.enter_context(patch.object(intake_mod, "run_calendar_node", new=AsyncMock(side_effect=_fake_calendar)))
    stack.enter_context(patch("src2.interfaces.telegram.chronomancer.handle_ask", new=AsyncMock(return_value=canned)))
    stack.enter_context(
        patch("src2.interfaces.telegram.chronomancer.handle_daily", new=AsyncMock(return_value="canned daily"))
    )
    stack.enter_context(
        patch(
            "src2.interfaces.telegram.chronomancer.handle_week_chart",
            new=AsyncMock(return_value=("", "canned 7day sparkline")),
        )
    )
    stack.enter_context(
        patch("src2.interfaces.telegram.chronomancer.handle_forecast", new=AsyncMock(return_value=canned))
    )
    stack.enter_context(
        patch("src2.interfaces.telegram.chronomancer.handle_forecast_menu", new=MagicMock(return_value="canned menu"))
    )
    stack.enter_context(
        patch(
            "src2.interfaces.telegram.chronomancer.handle_forecast_category",
            new=AsyncMock(return_value="canned category"),
        )
    )
    stack.enter_context(
        patch(
            "src2.interfaces.telegram.chronomancer.oracle_coordinator.handle_oracle", new=AsyncMock(return_value=canned)
        )
    )
    stack.enter_context(
        patch.object(report_utils, "get_month_narrative", new=AsyncMock(return_value="canned narrative"))
    )

    # Redirect every module's module-level `db` to the shared instance so all
    # SQLite traffic funnels through one connection (no cross-instance locks).
    _db_targets = [session_mod, app_mod, intake_mod, coordinator_mod, security_mod, stakeholder_intake_mod]
    for _mod in _db_targets:
        if hasattr(_mod, "db"):
            stack.enter_context(patch.object(_mod, "db", new=_DB))

    # Patch every Telegram-IO sink on BOTH the `utils` module (covers
    # in-function `from .utils import ...` lazy bindings) and on every module
    # that captured a top-level binding at import time. Otherwise the real
    # no-op "999" mock-path runs silently and defeats the reply-detection
    # anti-deadlock invariant.
    _io_targets = [utils_mod, app_mod, ui_components_mod, stakeholder_intake_mod, pipeline_mod]
    _io_fns = ("send_telegram_message", "answer_telegram_callback", "send_telegram_photo", "send_developer_message")
    send_mocks: list = []
    cb_mocks: list = []
    for _mod in _io_targets:
        for _fn in _io_fns:
            if hasattr(_mod, _fn):
                _m = AsyncMock()
                stack.enter_context(patch.object(_mod, _fn, new=_m))
                if _fn == "send_telegram_message":
                    send_mocks.append(_m)
                elif _fn == "answer_telegram_callback":
                    cb_mocks.append(_m)
    return {"send": send_mocks, "cb": cb_mocks}


def _step_of():
    try:
        return get_session(CHAT_ID, PLATFORM).step
    except Exception:
        return None


def _send_total(mocks):
    return sum(m.call_count for m in mocks["send"])


def _run_sequence(actions):
    _fresh_db()
    with ExitStack() as stack:
        mocks = _patch_llm(stack)
        # Ensure a session row exists for this user before fuzzing.
        try:
            get_session(CHAT_ID, PLATFORM)
        except Exception:
            pass
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        seed = [("msg", "/start")]
        all_actions = seed + list(actions)
        recorded_keyerrors = []
        recorded_other = []
        try:
            prev_step = _step_of()
            for i, (kind, payload) in enumerate(all_actions):
                sends_before = _send_total(mocks)
                exc = None
                try:
                    if kind == "msg":
                        loop.run_until_complete(
                            _route_message_data({"chat": {"id": CHAT_ID}, "text": payload}, PLATFORM)
                        )
                    else:
                        cb = {
                            "id": f"cb_{i}",
                            "data": payload,
                            "message": {"chat": {"id": CHAT_ID}, "message_id": i + 1},
                        }
                        loop.run_until_complete(_route_callback_query(cb, PLATFORM))
                except Exception as e:
                    exc = e
                    if isinstance(e, KeyError):
                        recorded_keyerrors.append((i, kind, payload, repr(e)))
                    else:
                        recorded_other.append((i, kind, payload, repr(e)))

                cur_step = _step_of()
                if cur_step is not None:
                    assert cur_step in VALID_STEPS, (
                        f"step corrupted to {cur_step!r} after action {i} {(kind, payload)!r}"
                    )

                if kind == "msg" and exc is None:
                    sends_delta = _send_total(mocks) - sends_before
                    step_changed = cur_step != prev_step
                    assert sends_delta > 0 or step_changed, (
                        f"DEADLOCK: user text {payload!r} (action {i}) produced no reply "
                        f"and no state change (step={cur_step})"
                    )
                prev_step = cur_step
        finally:
            loop.close()

    assert not recorded_keyerrors, (
        "KeyError(s) escaped routing — missing session data reached top level:\n"
        + "\n".join(f"  action {i} {kind}={payload!r}: {err}" for i, kind, payload, err in recorded_keyerrors)
        + f"\nother escaped exceptions: {recorded_other}"
    )
    return recorded_other


@given(actions=_SEQUENCES)
@settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.function_scoped_fixture],
)
def test_bot_state_machine_sequence(actions):
    """Random send_date / click_menu / send_garbage_text sequences must not
    deadlock or leak KeyError to the webhook boundary."""
    _run_sequence(actions)


def test_format_subscription_status_with_missing_prefs():
    """Targeted guard for the direct-subscript pattern in
    ``_format_subscription_status``: a corrupted / partial prefs dict (missing
    ``chronomancer_push_enabled`` / ``push_time`` / ``push_timezone``) must not
    raise KeyError; the bot must return a graceful status message instead."""
    _fresh_db()
    get_session(CHAT_ID, PLATFORM)
    with patch.object(Database, "get_user_prefs", return_value={"user_id": CHAT_ID}):
        err = None
        with ExitStack() as stack:
            mocks = _patch_llm(stack)
            sends_before = _send_total(mocks)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(_route_message_data({"chat": {"id": CHAT_ID}, "text": "/subscribe"}, PLATFORM))
            except Exception as e:
                err = e
            finally:
                loop.close()
        assert err is None, f"unhandled {type(err).__name__} escaped for /subscribe: {err!r}"
        assert _send_total(mocks) - sends_before > 0, "bot produced no reply for /subscribe under corrupted prefs"
