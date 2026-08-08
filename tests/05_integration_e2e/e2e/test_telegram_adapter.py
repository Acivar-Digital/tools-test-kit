"""
Unit tests for Day 4-5: Platform Abstraction Layer + TelegramAdapter
Tests ChannelAdapter ABC, message parsing, capabilities, and guardrails.
"""
import pytest

from src.platforms.base import (
    ChannelCapabilities,
    IncomingMessage,
    OutgoingMessage,
)
from src.platforms.telegram import TelegramAdapter


class TestIncomingMessage:
    def test_create_incoming_message(self):
        msg = IncomingMessage(
            platform_user_id="12345",
            message_type="text",
            text="Hello",
            raw={},
        )
        assert msg.platform_user_id == "12345"
        assert msg.text == "Hello"

    def test_incoming_message_defaults(self):
        msg = IncomingMessage(
            platform_user_id="12345",
            text="Hello",
            raw={},
        )
        assert msg.message_type == "text"


class TestOutgoingMessage:
    def test_create_outgoing_message(self):
        msg = OutgoingMessage(text="Response")
        assert msg.text == "Response"
        assert msg.media_path is None
        assert msg.document_path is None


class TestChannelCapabilities:
    def test_capabilities_model(self):
        caps = ChannelCapabilities(
            max_message_length=1500,
            supports_media=False,
            supports_buttons=True,
            supports_markdown=True,
            rate_limit_per_minute=20,
        )
        assert caps.max_message_length == 1500
        assert caps.supports_media is False
        assert caps.supports_buttons is True


class TestTelegramAdapter:
    def test_capabilities(self):
        adapter = TelegramAdapter()
        caps = adapter.capabilities
        assert caps.max_message_length == 1500
        assert caps.supports_media is False
        assert caps.supports_buttons is True
        assert caps.supports_markdown is True
        assert caps.rate_limit_per_minute == 20

    @pytest.mark.asyncio
    async def test_parse_text_message(self):
        adapter = TelegramAdapter()
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "Hello bot",
                "date": 1700000000,
            }
        }
        msg = await adapter.parse_incoming(payload)
        assert msg.platform_user_id == "12345"
        assert msg.text == "Hello bot"
        assert msg.message_type == "text"

    @pytest.mark.asyncio
    async def test_parse_callback_query(self):
        adapter = TelegramAdapter()
        payload = {
            "callback_query": {
                "id": "cq_123",
                "data": "/forecast",
                "message": {
                    "chat": {"id": 99999},
                    "date": 1700000000,
                },
            }
        }
        msg = await adapter.parse_incoming(payload)
        assert msg.platform_user_id == "99999"
        assert msg.text == "/forecast"
        assert msg.message_type == "callback"

    @pytest.mark.asyncio
    async def test_reject_media_attachments(self):
        adapter = TelegramAdapter()
        payload = {
            "message": {
                "chat": {"id": 12345},
                "photo": [{"file_id": "abc"}],
                "date": 1700000000,
            }
        }
        with pytest.raises(ValueError, match="Media attachments are not supported"):
            await adapter.parse_incoming(payload)

    @pytest.mark.asyncio
    async def test_reject_long_messages(self):
        adapter = TelegramAdapter()
        payload = {
            "message": {
                "chat": {"id": 12345},
                "text": "x" * 2000,
                "date": 1700000000,
            }
        }
        with pytest.raises(ValueError, match="Message too long"):
            await adapter.parse_incoming(payload)

    @pytest.mark.asyncio
    async def test_send_outgoing_without_token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        adapter = TelegramAdapter()
        msg = OutgoingMessage(text="Test")
        result = await adapter.send_outgoing("12345", msg)
        assert result is False
