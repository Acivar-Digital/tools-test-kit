import os
from unittest.mock import AsyncMock, patch

import pytest

from src2.interfaces.telegram.utils import send_developer_message


@pytest.mark.asyncio
async def test_send_developer_message_skips_user_dm():
    with patch.dict(os.environ, {
        "REPORT_PROGRESS_CHANNEL_ID": "-1003630017817",
        "DEVELOPER_CHAT_ID": "999000001"
    }):
        with patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock) as mock_send:
            await send_developer_message("❌ *CRITICAL: Forecast Webhook Failed*\nStack Trace: ...")

            # Must send to progress channel (-1003630017817)
            # Must NOT send to personal user DM (999000001)
            mock_send.assert_called_once()
            args, _ = mock_send.call_args
            assert args[0] == "-1003630017817"


@pytest.mark.asyncio
async def test_send_developer_message_allows_dev_channel():
    with patch.dict(os.environ, {
        "REPORT_PROGRESS_CHANNEL_ID": "-1003630017817",
        "DEVELOPER_CHAT_ID": "-100999999999"
    }):
        with patch("src2.interfaces.telegram.utils.send_telegram_message", new_callable=AsyncMock) as mock_send:
            await send_developer_message("❌ *CRITICAL: Forecast Webhook Failed*")

            assert mock_send.call_count == 2
            called_ids = [call[0][0] for call in mock_send.call_args_list]
            assert "-1003630017817" in called_ids
            assert "-100999999999" in called_ids
