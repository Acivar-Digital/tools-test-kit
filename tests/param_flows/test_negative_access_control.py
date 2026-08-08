from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_db():
    db = MagicMock()
    db.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
    db.set_user_prefs.return_value = None
    db.log_chat.return_value = None
    db.is_admin.return_value = False
    db.get_all_reports_for_user.return_value = []
    db.has_monthly_code.return_value = False
    return db


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "START"
    session.profile = None
    session.metadata.tailoring = None
    session.metadata.tailoring_concerns = None
    session.metadata.relation_category = None
    session.metadata.stakeholder_relation = None
    session.metadata.stakeholder_collected = None
    session.metadata.intake_mode = None
    session.metadata.location = "SG"
    return session


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["telegram", "web"])
async def test_blacklisted_user_denied_access(mock_db, mock_session, platform):
    chat_id = 123456789
    text = "/daily"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.security.check_user_access", return_value=False), \
         patch("src2.interfaces.telegram.app.text_manager"):

        from src2.interfaces.telegram.app import _route_message_data
        await _route_message_data({"chat": {"id": chat_id}, "text": text}, platform)

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1] if mock_send.call_args[0] else ""
        assert "access" in sent_text.lower() or "denied" in sent_text.lower() or "lock" in sent_text.lower()


@pytest.mark.asyncio
async def test_non_chronomancer_user_shows_promo(mock_db, mock_session):
    chat_id = 123456789
    text = "/daily"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.security.check_user_access", return_value=True), \
         patch("src2.interfaces.telegram.security.can_use_chronomancer", return_value=False), \
         patch("src2.interfaces.telegram.app.text_manager"):

        from src2.interfaces.telegram.app import _route_message_data
        await _route_message_data({"chat": {"id": chat_id}, "text": text}, "telegram")

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1] if mock_send.call_args[0] else ""
        assert "promo" in sent_text.lower() or "lock" in sent_text.lower() or "unlock" in sent_text.lower()


@pytest.mark.asyncio
async def test_tailoring_proceed_locked_without_monthly_code(mock_db, mock_session):
    chat_id = 123456789
    platform = "telegram"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.security.can_generate_report", return_value=False):

        from src2.interfaces.telegram.app import _handle_tailoring_proceed
        await _handle_tailoring_proceed(chat_id, "Done", mock_session, platform)

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1] if mock_send.call_args[0] else ""
        assert "promo" in sent_text.lower() or "lock" in sent_text.lower()
        assert mock_session.step == "CONFIRM"


@pytest.mark.asyncio
@pytest.mark.parametrize("platform", ["telegram", "web"])
async def test_queue_rejects_job_shows_capacity_error(mock_db, mock_session, platform):
    chat_id = 123456789
    mock_session.step = "PROCESSING"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.security.can_generate_report", return_value=True), \
         patch("src2.interfaces.telegram.app.queue_manager") as mock_queue:

        mock_queue.add_job = AsyncMock(return_value=False)

        from src2.interfaces.telegram.app import _handle_tailoring_proceed
        await _handle_tailoring_proceed(chat_id, "Done", mock_session, platform)

        mock_queue.add_job.assert_called_once_with(chat_id)
        assert mock_session.step == "COMPLETE"
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1] if mock_send.call_args[0] else ""
        assert "cannot" in sent_text.lower() or "limit" in sent_text.lower() or "capacity" in sent_text.lower()


@pytest.mark.asyncio
async def test_unauthorized_user_with_non_promo_text(mock_db, mock_session):
    chat_id = 123456789
    text = "hello general question"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.security.check_user_access", return_value=True), \
         patch("src2.interfaces.telegram.security.can_use_chronomancer", return_value=False), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.app.text_manager"):

        from src2.interfaces.telegram.app import _dispatch_message_routing
        await _dispatch_message_routing(text, chat_id, mock_session, "telegram")

        mock_send.assert_called_once()
        sent_text = mock_send.call_args[0][1] if mock_send.call_args[0] else ""
        assert "promo" in sent_text.lower() or "lock" in sent_text.lower() or "unlock" in sent_text.lower()
