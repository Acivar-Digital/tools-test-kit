"""
Unit tests for the markdown_to_tg_html converter in utils.py.
"""

import pytest
import respx
from httpx import Response

from src.bot.utils import edit_telegram_message, markdown_to_tg_html


def test_empty_string():
    assert markdown_to_tg_html("") == ""
    assert markdown_to_tg_html(None) == ""


def test_html_escape():
    # Brackets must be escaped to prevent Telegram crashes
    assert markdown_to_tg_html("A < B") == "A &lt; B"
    assert markdown_to_tg_html("X > Y") == "X &gt; Y"
    assert markdown_to_tg_html("A <blockquote expandable> B") == "A &lt;blockquote expandable&gt; B"


def test_bold_conversion():
    assert markdown_to_tg_html("Hello **World**") == "Hello <b>World</b>"
    assert markdown_to_tg_html("This is **bold** text.") == "This is <b>bold</b> text."


def test_italic_conversion():
    # Convert *italic* and _italic_ to <i>italic</i>
    assert markdown_to_tg_html("Hello *World*") == "Hello <i>World</i>"
    assert markdown_to_tg_html("Hello _World_") == "Hello <i>World</i>"


def test_combined_markdown():
    text = "This is **bold** and *italic* with < brackets."
    expected = "This is <b>bold</b> and <i>italic</i> with &lt; brackets."
    assert markdown_to_tg_html(text) == expected


def test_chronomancer_reply_concatenation():
    from src.bot.utils import ChronomancerReply
    reply = ChronomancerReply("Hello World", "HTML")
    assert reply.parse_mode == "HTML"

    # Concatenate right
    res1 = reply + "\nFooter"
    assert isinstance(res1, ChronomancerReply)
    assert res1.parse_mode == "HTML"
    assert res1 == "Hello World\nFooter"

    # Concatenate left
    res2 = "Header\n" + reply
    assert isinstance(res2, ChronomancerReply)
    assert res2.parse_mode == "HTML"
    assert res2 == "Header\nHello World"


@respx.mock
@pytest.mark.asyncio
async def test_edit_telegram_message_fallback():
    route1 = respx.post(url__regex=r".*/editMessageText")
    route1.side_effect = [
        Response(400, json={"ok": False, "description": "Bad Request: can't parse entities"}),
        Response(200, json={"ok": True})
    ]

    res = await edit_telegram_message("123", 456, "Hello *world*", parse_mode="HTML")
    assert res is True
    # Ensure it was called twice
    assert route1.call_count == 2
    # Verify the second payload had no parse_mode
    import json
    second_payload = json.loads(route1.calls[1].request.content)
    assert "parse_mode" not in second_payload


@respx.mock
@pytest.mark.asyncio
async def test_send_telegram_document_fallback(tmp_path):
    from src.bot.utils import send_telegram_document
    # Create a temporary dummy file to upload
    dummy_file = tmp_path / "chart.png"
    dummy_file.write_bytes(b"dummy image content")

    route1 = respx.post(url__regex=r".*/sendDocument")
    route1.side_effect = [
        Response(400, json={"ok": False, "description": "Bad Request: can't parse entities"}),
        Response(200, json={"ok": True})
    ]

    res = await send_telegram_document("123", str(dummy_file), "Hello *world*")
    assert res == {"ok": True}
    assert route1.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_reliability_send_telegram_message_fallback():
    from src.bot.reliability import send_telegram_message as reliability_send
    route1 = respx.post(url__regex=r".*/sendMessage")
    route1.side_effect = [
        Response(400, json={"ok": False, "description": "Bad Request: can't parse entities"}),
        Response(200, json={"ok": True})
    ]

    # Call with parse_mode=Markdown
    await reliability_send("123", "Hello *world*", "MY_TOKEN", parse_mode="Markdown")
    assert route1.call_count == 2


@respx.mock
@pytest.mark.asyncio
async def test_telegram_character_limit_truncation():
    from src.bot.utils import send_telegram_message
    route1 = respx.post(url__regex=r".*/sendMessage").respond(200, json={"ok": True})

    long_text = "A" * 5000
    await send_telegram_message("123", long_text)
    assert route1.call_count == 1

    # Check that it was truncated to 4090 + "..." (length 4093)
    import json
    payload = json.loads(route1.calls[0].request.content)
    assert len(payload["text"]) == 4093
    assert payload["text"].endswith("...")


@respx.mock
@pytest.mark.asyncio
async def test_answer_telegram_callback():
    from src.bot.utils import answer_telegram_callback
    route1 = respx.post(url__regex=r".*/answerCallbackQuery").respond(200, json={"ok": True})

    res = await answer_telegram_callback("query_123", text="Done")
    assert res is True
    assert route1.call_count == 1


def test_safe_html_truncate():
    from src.bot.utils import safe_html_truncate

    # 1. Short string under the limit should remain unchanged
    short_str = "<b>Hello</b>"
    assert safe_html_truncate(short_str, max_len=100) == short_str

    # 2. String over the limit should be truncated and open tags closed beautifully
    long_html = "<b>Hello <i>world</i> this is a <blockquote expandable>test of a very long message</blockquote></b>"
    res = safe_html_truncate(long_html, max_len=80)
    assert res == "<b>Hello <i>world</i> this is a <blockquote expandable>...</blockquote></b>"

