#!/usr/bin/env python3
"""Generator script that writes the refactored utils.py."""

AR = chr(8594)   # right arrow →
AL = chr(8592)   # left arrow ←
AD = chr(8658)   # right double arrow ⇒
BR = chr(9888)   # warning ⚠
XM = chr(10060)  # cross mark ❌

content = f"""import asyncio
import html
import json
import logging
import os
import re
import time

import httpx

logger = logging.getLogger(__name__)

_client: httpx.AsyncClient | None = None


class ChronomancerReply(str):
    def __new__(cls, content: str, parse_mode: str = "Markdown", reply_markup: dict = None):
        obj = super().__new__(cls, content)
        obj.parse_mode = parse_mode
        obj.reply_markup = reply_markup
        return obj

    def __add__(self, other):
        if isinstance(other, str):
            return ChronomancerReply(super().__add__(other), self.parse_mode)
        return NotImplemented

    def __radd__(self, other):
        if isinstance(other, str):
            return ChronomancerReply(other + super().__str__(), self.parse_mode)
        return NotImplemented


def get_async_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(limits=httpx.Limits(max_connections=20, max_keepalive_connections=5), timeout=10.0)
    return _client


async def close_async_client():
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()


def markdown_to_tg_html(text: str) -> str:
    \"\"\"Converts LLM markdown to Telegram-safe HTML.\"\"\"
    if not text:
        return ""
    text = html.escape(text, quote=False)
    text = re.sub(r"\\*\\*(.+?)\\*\\*", r"<b>\\1</b>", text)
    text = re.sub(r"(?<![A-Za-z0-9])\\*([^\\*\\n]+)\\*(?![A-Za-z0-9])", r"<i>\\1</i>", text)
    text = re.sub(r"(?<![A-Za-z0-9])_([^\\_\\n]+)_(?![A-Za-z0-9])", r"<i>\\1</i>", text)
    text = re.sub(r"`([^`\\n]+)`", r"<code>\\1</code>", text)
    return text


def safe_html_truncate(text: str, max_len: int = 4096, suffix: str = "...") -> str:
    if not text or len(text) <= max_len:
        return text
    limit = max_len - len(suffix) - 150
    if limit < 0:
        limit = max_len // 2
    open_tags: list[str] = []
    accumulated: list[str] = []
    i = 0
    n = len(text)
    while i < n and len("".join(accumulated)) < limit:
        i = _accumulate_char(text, i, open_tags, accumulated)
    return "".join(accumulated) + suffix + _close_remaining_tags(open_tags)


def _accumulate_char(text: str, i: int, open_tags: list, accumulated: list) -> int:
    c = text[i]
    if c == "<":
        return _process_tag(text, i, open_tags, accumulated)
    if c == "&":
        return _process_entity(text, i, accumulated)
    accumulated.append(c)
    return i + 1


def _process_tag(text: str, i: int, open_tags: list, accumulated: list) -> int:
    j = text.find(">", i)
    if j == -1:
        return len(text)
    tag_content = text[i : j + 1]
    tag_inside = tag_content[1:-1].strip()
    if tag_inside.startswith("/"):
        tag_name = tag_inside[1:].strip().split()[0].lower()
        if tag_name in open_tags:
            _close_matching_tag(open_tags, tag_name, accumulated)
    else:
        parts = tag_inside.split()
        if parts:
            tag_name = parts[0].lower()
            if tag_name in ("b", "i", "code", "blockquote", "a", "pre"):
                open_tags.append(tag_name)
        accumulated.append(tag_content)
    return j + 1


def _close_matching_tag(open_tags: list, tag_name: str, accumulated: list) -> None:
    while open_tags:
        popped = open_tags.pop()
        accumulated.append(f"</{{popped}}>")
        if popped == tag_name:
            break


def _process_entity(text: str, i: int, accumulated: list) -> int:
    j = text.find(";", i)
    if j == -1 or j - i > 8:
        accumulated.append(text[i])
        return i + 1
    accumulated.append(text[i : j + 1])
    return j + 1


def _close_remaining_tags(open_tags: list) -> str:
    return "".join(f"</{{tag}}>" for tag in reversed(open_tags))


def sanitize_surrogates(text: str) -> str:
    if not text:
        return text
    try:
        text = text.encode("utf-16", "surrogatepass").decode("utf-16")
    except Exception:
        pass
    return text.encode("utf-8", "replace").decode("utf-8")


def split_text_into_chunks(text: str, max_chars: int = 4000) -> list[str]:
    if not text:
        return []
    if len(text) <= max_chars:
        return [text]
    chunks = []
    remaining = text
    while len(remaining) > max_chars:
        split_idx, split_len = _find_best_split(remaining[:max_chars], max_chars)
        chunk = remaining[:split_idx].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_idx + split_len :].lstrip("\\n")
    if remaining.strip():
        chunks.append(remaining.strip())
    return chunks


def _find_best_split(candidate: str, max_chars: int) -> tuple[int, int]:
    for sep, slen in (("\\n\\n", 2), ("\\n", 1), (" ", 1)):
        idx = candidate.rfind(sep)
        if idx > 0:
            return idx, slen
    return max_chars, 0


def _preprocess_telegram_text(text: str) -> str:
    if not text:
        return text
    text = sanitize_surrogates(text)
    text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL).strip()
    text = text.replace("${AR}$", "{AR}").replace("\\rightarrow", "{AR}")
    text = text.replace("${AL}$", "{AL}").replace("\\leftarrow", "{AL}")
    text = text.replace("${AD}$", "{AD}").replace("\\implies", "{AD}")
    text = text.replace("{{AR}}", "{AR}").replace("{{AL}}", "{AL}").replace("{{AD}}", "{AD}")
    return text


async def send_telegram_message(
    chat_id: int | str,
    text: str,
    token: str = None,
    retries: int = 3,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
) -> dict | None:
    text = _preprocess_telegram_text(text)
    result = await _try_resolve_split(chat_id, text, token, retries, reply_markup, parse_mode)
    if result is not None:
        return result
    result = await _try_resolve_long_text(chat_id, text, token, retries, reply_markup, parse_mode)
    if result is not None:
        return result
    return await _deliver_message(chat_id, text, token, retries, reply_markup, parse_mode)


async def _try_resolve_split(
    chat_id: int | str,
    text: str,
    token: str = None,
    retries: int = 3,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
) -> dict | None:
    if not text or "<MESSAGE_SPLIT>" not in text:
        return None
    parts = text.split("<MESSAGE_SPLIT>")
    last_resp = None
    for p in parts:
        if p.strip():
            last_resp = await send_telegram_message(chat_id, p.strip(), token, retries, reply_markup, parse_mode)
    return last_resp


async def _try_resolve_long_text(
    chat_id: int | str,
    text: str,
    token: str = None,
    retries: int = 3,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
) -> dict | None:
    if not text or len(text) <= 4000:
        return None
    chunks = split_text_into_chunks(text, max_chars=4000)
    last_resp = None
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        last_resp = await send_telegram_message(chat_id, chunk, token, retries, markup, parse_mode)
    return last_resp


def _is_test_user(chat_id: int | str, api_base: str) -> bool:
    return str(chat_id).startswith("999") and "api.telegram.org" in api_base


def _create_mock_response(chat_id: int | str, text: str) -> dict:
    return {{
        "ok": True,
        "result": {{
            "message_id": 123456,
            "from": {{"id": 1234567, "is_bot": True, "first_name": "TestBot", "username": "test_bot"}},
            "chat": {{"id": int(chat_id) if str(chat_id).isdigit() else 999, "first_name": "Test", "type": "private"}},
            "date": int(time.time()),
            "text": text,
        }},
    }}


async def _deliver_message(
    chat_id: int | str,
    text: str,
    token: str = None,
    retries: int = 3,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
) -> dict | None:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    api_base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
    if _is_test_user(chat_id, api_base):
        return _create_mock_response(chat_id, text)
    return await _send_via_api(chat_id, text, token, retries, reply_markup, parse_mode, api_base)


async def _send_via_api(
    chat_id: int | str,
    text: str,
    token: str = None,
    retries: int = 3,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
    api_base: str = None,
) -> dict | None:
    url = f"{{api_base}}/bot{{token}}/sendMessage"
    payload: dict = {{"chat_id": chat_id, "text": text}}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    if reply_markup:
        payload["reply_markup"] = reply_markup
    client = get_async_client()
    for attempt in range(retries):
        try:
            resp = await client.post(url, json=payload, timeout=10.0)
            if resp.status_code == 400 and "parse_mode" in payload:
                logger.warning("Markdown/HTML parsing failed, falling back to plain text.")
                payload.pop("parse_mode")
                resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
            logger.info(f"Successfully sent Telegram message to {{chat_id}}")
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to send Telegram message (attempt {{attempt + 1}}/{{retries}}): {{e}}")
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                raise


async def send_telegram_photo(
    chat_id: int | str,
    photo_path: str,
    caption: str = None,
    token: str = None,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
    retries: int = 3,
) -> dict | None:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    api_base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
    if caption:
        caption = sanitize_surrogates(caption)
    if _is_test_user(chat_id, api_base):
        return _create_photo_mock_response(chat_id, caption)
    return await _send_photo_via_api(chat_id, photo_path, caption, token, reply_markup, parse_mode, retries, api_base)


def _create_photo_mock_response(chat_id: int | str, caption: str = None) -> dict:
    return {{
        "ok": True,
        "result": {{
            "message_id": 123457,
            "chat": {{"id": int(chat_id) if str(chat_id).isdigit() else 999, "type": "private"}},
            "date": int(time.time()),
            "caption": caption,
        }},
    }}


def _build_photo_payload(chat_id: int | str, caption: str, parse_mode: str, reply_markup: dict, token: str) -> dict:
    data: dict = {{"chat_id": chat_id}}
    if caption:
        data["caption"] = caption
    if parse_mode:
        data["parse_mode"] = parse_mode
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    return data


async def _send_photo_via_api(
    chat_id: int | str,
    photo_path: str,
    caption: str = None,
    token: str = None,
    reply_markup: dict = None,
    parse_mode: str = "Markdown",
    retries: int = 3,
    api_base: str = None,
) -> dict | None:
    url = f"{{api_base}}/bot{{token}}/sendPhoto"
    payload = _build_photo_payload(chat_id, caption, parse_mode, reply_markup, token)
    client = get_async_client()
    for attempt in range(retries):
        try:
            with open(photo_path, "rb") as f:
                files = {{"photo": (os.path.basename(photo_path), f, "image/png")}}
                resp = await client.post(url, data=payload, files=files, timeout=20.0)
            resp.raise_for_status()
            logger.info(f"Successfully sent Telegram photo to {{chat_id}}")
            return resp.json()
        except Exception as e:
            logger.error(f"Failed to send Telegram photo (attempt {{attempt + 1}}/{{retries}}): {{e}}")
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                raise


async def answer_telegram_callback(
    callback_query_id: str, text: str = None, token: str = None, retries: int = 2
) -> bool:
    token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
    api_base = os.environ.get("TELEGRAM_API_BASE", "https://api.telegram.org")
    url = f"{{api_base}}/bot{{token}}/answerCallbackQuery"
    payload = {{"callback_query_id": callback_query_id}}
    if text:
        payload["text"] = sanitize_surrogates(text)
    return await _post_with_retry(url, payload, retries, timeout=10.0, logger_msg="callback query")


async def _post_with_retry(
    url: str, payload: dict, retries: int, timeout: float = 10.0, logger_msg: str = "request"
) -> bool:
    client = get_async_client()
    for attempt in range(retries):
        try:
            resp = await client.post(url, json=payload, timeout=timeout)
            resp.raise_for_status()
            return True
        except Exception as e:
            if logger_msg == "callback query":
                logger.error(f"Failed to answer Telegram callback query (attempt {{attempt + 1}}/{{retries}}): {{e}}")
            else:
                logger.error(f"Failed to send Telegram message (attempt {{attempt + 1}}/{{retries}}): {{e}}")
            if attempt < retries - 1:
                await asyncio.sleep(1 if logger_msg == "callback query" else 2)
            else:
                raise
    return False


async def send_developer_message(text: str, token: str = None):
    admin_channel_id = os.getenv("KIT_REPORT_CHANNEL_ID")
    if admin_channel_id:
        await send_telegram_message(admin_channel_id, text, token)

    dev_chat_id = os.getenv("KIT_DEV_CHAT_ID")
    if dev_chat_id and str(dev_chat_id).strip() != str(admin_channel_id).strip():
        is_critical = any(marker in text for marker in ["{XM}", "{BR}", "Interrupted", "failed", "Error"])
        if is_critical and str(dev_chat_id).strip().startswith("-"):
            await send_telegram_message(dev_chat_id, text, token)


async def check_and_acquire_channel_lock(user_id: int, channel: str) -> tuple[bool, str | None]:
    try:
        valkey = await _get_valkey_client()
        if valkey is None:
            return True, None
        return await _check_or_set_channel_lock(valkey, user_id, channel)
    except Exception as e:
        logger.error(f"Error checking channel lock for user {{user_id}}: {{e}}")
        return True, None


async def _get_valkey_client() -> Any | None:
    try:
        from src2.core.valkey import get_valkey_client
    except ImportError:
        return None

    valkey = get_valkey_client()
    return valkey if valkey else None


async def _check_or_set_channel_lock(valkey, user_id: int, channel: str) -> tuple[bool, str | None]:
    lock_key = f"session:active_channel:{{user_id}}"
    active = await valkey.get(lock_key)
    if active and active != channel:
        ttl = await valkey.ttl(lock_key)
        if ttl > 0:
            mins_left = max(1, int(ttl / 60))
            return (
                False,
                f"{BR} Active session running on {{active.capitalize()}}. Please finish your conversation there or wait {{mins_left}} minutes.",
            )
    await valkey.set(lock_key, channel, ex=900)
    return True, None
"""

# Now replace the f-string placeholders with actual Unicode characters
# But wait - we used {{ and }} to escape braces in f-strings, but _ also used {AR}, {AL}, etc.
# The problem is that {AR} was treated as an f-string variable reference...
# Let me use a different approach: use .format() or replace at the end

# Actually wait - the f-string approach won't work because {AR} would be evaluated as a Python variable.
# Let me go back to a non-f-string approach.

print("ERROR: f-string approach has issues, need to use different method")
