"""
redis_cache.py — Redis-backed caching layer for BaziRAG.

Provides sync + async dual support. Async variants use redis.asyncio.
Gracefully degrades when Redis is unavailable.
"""

import hashlib
import json
import logging
import os
from typing import Any, Optional

import redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "127.0.0.1")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "1"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")
REDIS_TTL_EMBEDDING = int(os.getenv("REDIS_TTL_EMBEDDING", "86400"))
REDIS_TTL_QUERY = int(os.getenv("REDIS_TTL_QUERY", "3600"))

_PREFIX_EMBED = "bazi:embed:"
_PREFIX_QUERY = "bazi:query:"

_sync_client: Optional["redis.Redis"] = None
_async_client: Optional["redis.asyncio.Redis"] = None


# ── Sync client ────────────────────────────────────────────────────────────────

def _get_sync_client():
    global _sync_client
    if _sync_client is not None:
        return _sync_client
    import redis
    try:
        _sync_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        _sync_client.ping()
    except Exception as exc:
        logger.warning(f"Redis sync unavailable ({exc}) — cache disabled")
        _sync_client = None
    return _sync_client


# ── Async client ───────────────────────────────────────────────────────────────

async def _get_async_client():
    global _async_client
    if _async_client is not None:
        return _async_client
    import redis.asyncio as redis_async
    try:
        _async_client = redis_async.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            password=REDIS_PASSWORD or None,
            decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        await _async_client.ping()
    except Exception as exc:
        logger.warning(f"Redis async unavailable ({exc}) — cache disabled")
        _async_client = None
    return _async_client


def _key_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── Embedding cache (sync) ─────────────────────────────────────────────────────

def cache_embedding(text: str, vector: list[float]) -> None:
    client = _get_sync_client()
    if client is None:
        return
    try:
        key = _PREFIX_EMBED + _key_hash(text)
        val = json.dumps(vector, ensure_ascii=False)
        client.setex(key, REDIS_TTL_EMBEDDING, val)
    except Exception:
        logger.debug("Failed to cache embedding", exc_info=True)


def get_cached_embedding(text: str) -> list[float] | None:
    client = _get_sync_client()
    if client is None:
        return None
    try:
        raw = client.get(_PREFIX_EMBED + _key_hash(text))
        return json.loads(raw) if raw is not None else None
    except Exception:
        logger.debug("Failed to read cached embedding", exc_info=True)
        return None


# ── Embedding cache (async) ────────────────────────────────────────────────────

async def async_cache_embedding(text: str, vector: list[float]) -> None:
    client = await _get_async_client()
    if client is None:
        return
    try:
        key = _PREFIX_EMBED + _key_hash(text)
        val = json.dumps(vector, ensure_ascii=False)
        await client.setex(key, REDIS_TTL_EMBEDDING, val)
    except Exception:
        logger.debug("Failed to cache embedding", exc_info=True)


async def async_get_cached_embedding(text: str) -> list[float] | None:
    client = await _get_async_client()
    if client is None:
        return None
    try:
        raw = await client.get(_PREFIX_EMBED + _key_hash(text))
        return json.loads(raw) if raw is not None else None
    except Exception:
        logger.debug("Failed to read cached embedding", exc_info=True)
        return None


# ── Query result cache (sync) ──────────────────────────────────────────────────

def cache_query_result(query: str, result: list[dict]) -> None:
    client = _get_sync_client()
    if client is None:
        return
    try:
        key = _PREFIX_QUERY + _key_hash(query)
        val = json.dumps(result, ensure_ascii=False)
        client.setex(key, REDIS_TTL_QUERY, val)
    except Exception:
        logger.debug("Failed to cache query result", exc_info=True)


def get_cached_query_result(query: str) -> list[dict] | None:
    client = _get_sync_client()
    if client is None:
        return None
    try:
        raw = client.get(_PREFIX_QUERY + _key_hash(query))
        return json.loads(raw) if raw is not None else None
    except Exception:
        logger.debug("Failed to read cached query result", exc_info=True)
        return None


# ── Query result cache (async) ─────────────────────────────────────────────────

async def async_cache_query_result(query: str, result: list[dict]) -> None:
    client = await _get_async_client()
    if client is None:
        return
    try:
        key = _PREFIX_QUERY + _key_hash(query)
        val = json.dumps(result, ensure_ascii=False)
        await client.setex(key, REDIS_TTL_QUERY, val)
    except Exception:
        logger.debug("Failed to cache query result", exc_info=True)


async def async_get_cached_query_result(query: str) -> list[dict] | None:
    client = await _get_async_client()
    if client is None:
        return None
    try:
        raw = await client.get(_PREFIX_QUERY + _key_hash(query))
        return json.loads(raw) if raw is not None else None
    except Exception:
        logger.debug("Failed to read cached query result", exc_info=True)
        return None


# ── Cache stats (sync + async) ─────────────────────────────────────────────────

def cache_stats() -> dict[str, Any]:
    client = _get_sync_client()
    if client is None:
        return {"status": "disconnected", "embedding_keys": 0, "query_keys": 0}
    try:
        embed_count = len(client.keys(_PREFIX_EMBED + "*"))
        query_count = len(client.keys(_PREFIX_QUERY + "*"))
        return {"status": "connected", "embedding_keys": embed_count, "query_keys": query_count}
    except Exception as exc:
        return {"status": f"error: {exc}", "embedding_keys": 0, "query_keys": 0}


async def async_cache_stats() -> dict[str, Any]:
    client = await _get_async_client()
    if client is None:
        return {"status": "disconnected", "embedding_keys": 0, "query_keys": 0}
    try:
        embed_keys = await client.keys(_PREFIX_EMBED + "*")
        query_keys = await client.keys(_PREFIX_QUERY + "*")
        return {
            "status": "connected",
            "embedding_keys": len(embed_keys),
            "query_keys": len(query_keys),
        }
    except Exception as exc:
        return {"status": f"error: {exc}", "embedding_keys": 0, "query_keys": 0}


def clear_cache() -> None:
    client = _get_sync_client()
    if client is None:
        return
    try:
        for key in client.scan_iter(match=_PREFIX_EMBED + "*"):
            client.delete(key)
        for key in client.scan_iter(match=_PREFIX_QUERY + "*"):
            client.delete(key)
    except Exception:
        logger.debug("Failed to clear cache", exc_info=True)


async def async_clear_cache() -> None:
    client = await _get_async_client()
    if client is None:
        return
    try:
        async for key in client.scan_iter(match=_PREFIX_EMBED + "*"):
            await client.delete(key)
        async for key in client.scan_iter(match=_PREFIX_QUERY + "*"):
            await client.delete(key)
    except Exception:
        logger.debug("Failed to clear cache", exc_info=True)
