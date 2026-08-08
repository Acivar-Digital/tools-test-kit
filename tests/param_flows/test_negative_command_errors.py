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
    db.has_monthly_code.return_value = True
    return db


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.step = "CHRONOMANCER"
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
@pytest.mark.parametrize("invalid_cmd", [
    "/forecast_999",
    "/forecast_xyz",
    "/forecast_hack",
])
async def test_invalid_forecast_category_passes_category_through(mock_db, mock_session, invalid_cmd):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast_category", new_callable=AsyncMock) as mock_handle:

        mock_handle.return_value = "Invalid category handled gracefully"
        expected_category = invalid_cmd.replace("/forecast_", "")

        from src2.interfaces.telegram.app import _handle_forecast_command
        await _handle_forecast_command(invalid_cmd, chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id, expected_category, None, None)


@pytest.mark.asyncio
async def test_handle_forecast_raises_propagates(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_forecast", new_callable=AsyncMock) as mock_handle:

        mock_handle.side_effect = RuntimeError("Forecast engine OOM during /30")

        from src2.interfaces.telegram.app import _handle_forecast_command
        with pytest.raises(RuntimeError, match="Forecast engine OOM"):
            await _handle_forecast_command("/30", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id, 30)


@pytest.mark.asyncio
async def test_handle_daily_raises_propagates(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_daily", new_callable=AsyncMock) as mock_handle:

        mock_handle.side_effect = ValueError("No profile set for user during /daily")

        from src2.interfaces.telegram.app import _handle_daily_command
        with pytest.raises(ValueError, match="No profile set"):
            await _handle_daily_command("/daily", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id)


@pytest.mark.asyncio
async def test_month_number_command_db_prefs_none_raises(mock_db, mock_session):
    chat_id = 123456789
    text = "/6"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.security.can_generate_report", return_value=True):

        mock_db.get_user_prefs.return_value = None
        mock_db.get_all_reports_for_user.return_value = [{"master_json_path": "/fake/path.json"}]

        from src2.interfaces.telegram.app import _handle_month_number_command
        with pytest.raises(AttributeError):
            await _handle_month_number_command(chat_id, text)

        mock_db.get_user_prefs.assert_called_once_with(chat_id)


@pytest.mark.asyncio
@pytest.mark.parametrize("unknown_relation", [
    "dragon",
    "unicorn",
    "xyz123",
])
async def test_add_command_unknown_relation_shows_keyboard(mock_db, mock_session, unknown_relation):
    chat_id = 123456789
    text = f"/add {unknown_relation}"

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock) as mock_send, \
         patch("src2.interfaces.telegram.ui_components.get_stakeholder_category_keyboard") as mock_keyboard:

        mock_keyboard.return_value = {"inline_keyboard": []}

        from src2.interfaces.telegram.app import _handle_add_command
        await _handle_add_command(text, chat_id, mock_session, "telegram")

        mock_keyboard.assert_called_once()
        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert "reply_markup" in call_kwargs.kwargs


@pytest.mark.asyncio
async def test_week_chart_handle_raises_propagates(mock_db, mock_session):
    chat_id = 123456789

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.utils.send_telegram_photo", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.handle_week_chart", new_callable=AsyncMock) as mock_handle:

        mock_handle.side_effect = FileNotFoundError("Weekly chart data file corrupted")

        from src2.interfaces.telegram.app import _handle_week_chart_command
        with pytest.raises(FileNotFoundError, match="Weekly chart data file corrupted"):
            await _handle_week_chart_command("/week", chat_id, mock_session, "telegram")

        mock_handle.assert_called_once_with(chat_id)


@pytest.mark.asyncio
async def test_daily_rag_failure_propagates(mock_db, mock_session):
    """When the RAG client raises FileNotFoundError (e.g. broken TURBOVEC_INDEX_PATH
    in constants.py), the error propagates through get_daily_forecast → handle_daily
    → _handle_daily_command without being swallowed."""
    chat_id = 123456789

    mock_session.profile = MagicMock()
    mock_session.profile.day_pillar = MagicMock()

    with patch("src2.interfaces.telegram.app.db", mock_db), \
         patch("src2.interfaces.telegram.app.send_telegram_message", new_callable=AsyncMock), \
         patch("src2.interfaces.telegram.session.get_session", return_value=mock_session), \
         patch("src2.interfaces.telegram.session.save_session"), \
         patch("src2.interfaces.telegram.chronomancer.coordinator.db", mock_db), \
         patch("src2.interfaces.telegram.chronomancer.coordinator._handle_daily_ensure_profile", return_value=mock_session), \
         patch("src2.interfaces.telegram.chronomancer.coordinator._session_to_profile", return_value={"alias": "TestUser"}), \
         patch("src2.interfaces.telegram.chronomancer.coordinator.session_to_chart_profile", return_value=MagicMock()), \
         patch("src2.interfaces.telegram.chronomancer.forecast_store.db", mock_db), \
         patch("src2.interfaces.telegram.db.Database") as mock_db_class, \
         patch("src2.engine.bazi_cache.query_classical_text_async", new_callable=AsyncMock) as mock_qct, \
         patch("src2.interfaces.telegram.chronomancer.agents.compute_structural_map", return_value=""), \
         patch("src2.interfaces.telegram.chronomancer.agents.compute_shen_sha_context", return_value=""):

        mock_db_class.return_value.get_user_prefs.return_value = {"language": "English", "sifu_mode": 0}
        mock_db_class.return_value.get_daily_forecast.return_value = None
        mock_qct.side_effect = FileNotFoundError("TurboVec index not found at src2/infrastructure/rag/bazi_index.tv")

        from src2.interfaces.telegram.app import _handle_daily_command
        with pytest.raises(FileNotFoundError, match="TurboVec index not found"):
            await _handle_daily_command("/daily", chat_id, mock_session, "telegram")
