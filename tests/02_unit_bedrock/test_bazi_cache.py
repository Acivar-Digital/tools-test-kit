import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("BGEM3_URL", "http://test/v1/embeddings")
os.environ.setdefault("BGEM3_TOKEN", "test-token")
os.environ.setdefault("QDRANT_URL", "http://test")

from src2.engine.bazi_cache import (
    _is_valid_keyword,
    _load_cache,
    _sanitize_keywords,
    _save_to_cache,
    get_or_fetch_classical_text,
)


@pytest.fixture
def temp_cache_file(tmp_path: Path):
    return tmp_path / "bazi_cache.jsonl"


class TestIsValidKeyword:
    def test_valid_chinese_keyword(self):
        assert _is_valid_keyword("乙木") is True

    def test_valid_multi_char_chinese_keyword(self):
        assert _is_valid_keyword("五行偏枯") is True

    def test_rejects_ascii_only_keyword(self):
        assert _is_valid_keyword("shensha") is False

    def test_rejects_garbage_mixed_latin_chinese(self):
        assert _is_valid_keyword("G庚|Stem|Xin辛") is False

    def test_rejects_single_ascii_char(self):
        assert _is_valid_keyword("a") is False

    def test_rejects_empty_string(self):
        assert _is_valid_keyword("") is False


class TestSanitizeKeywords:
    def test_sanitize_removes_chinese_commas(self):
        result = _sanitize_keywords(["事业，晋升"])
        assert "事业" in result
        assert "晋升" in result

    def test_sanitize_removes_semicolons(self):
        result = _sanitize_keywords(["七杀；正官"])
        assert "七杀" in result
        assert "正官" in result

    def test_sanitize_removes_english_commas(self):
        result = _sanitize_keywords(["七杀, 正官"])
        assert "七杀" in result
        assert "正官" in result

    def test_sanitize_strips_whitespace(self):
        result = _sanitize_keywords(["  乙木  ", "劫财"])
        assert "乙木" in result
        assert "劫财" in result

    def test_sanitize_filters_non_strings(self):
        result = _sanitize_keywords(["乙木", 123, None, "劫财"])  # type: ignore[list-item]
        assert "乙木" in result
        assert "劫财" in result
        assert len(result) == 2


class TestLoadCache:
    def test_load_cache_reads_single_keyword_entries(self, temp_cache_file: Path):
        temp_cache_file.write_text(
            json.dumps({"keywords": "乙木", "text": "Wood element"}) + "\n"
            + json.dumps({"keywords": "劫财", "text": "Rob wealth"}) + "\n",
            encoding="utf-8",
        )
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file):
            cache = _load_cache()
        assert cache["乙木"] == "Wood element"
        assert cache["劫财"] == "Rob wealth"

    def test_load_cache_excludes_garbage_mixed_language_keywords(self, temp_cache_file: Path):
        temp_cache_file.write_text(
            json.dumps({"keywords": "G庚|Stem|Xin辛", "text": "Garbage"}) + "\n",
            encoding="utf-8",
        )
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file):
            cache = _load_cache()
        assert "G庚" not in cache
        assert "Stem" not in cache

    def test_load_cache_missing_file_returns_empty(self, temp_cache_file: Path):
        missing = temp_cache_file.parent / "missing.jsonl"
        with patch("src2.engine.bazi_cache.CACHE_FILE", missing):
            cache = _load_cache()
        assert cache == {}


class TestSaveToCache:
    def test_save_writes_single_keywords_per_line(self, temp_cache_file: Path):
        import asyncio
        async def run():
            with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file):
                await _save_to_cache(["乙木", "劫财"], "Combined wood and rob wealth text")
        asyncio.run(run())

        lines = temp_cache_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        entries = [json.loads(entry) for entry in lines]
        keywords = [e["keywords"] for e in entries]
        assert "乙木" in keywords
        assert "劫财" in keywords
        assert "|" not in str(keywords)

    def test_save_writes_separate_text_per_keyword(self, temp_cache_file: Path):
        import asyncio
        async def run():
            with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file):
                await _save_to_cache(["乙木", "劫财"], "Some text")
        asyncio.run(run())

        entries = [json.loads(entry) for entry in temp_cache_file.read_text(encoding="utf-8").strip().split("\n")]
        keyword_to_text = {e["keywords"]: e["text"] for e in entries}
        assert keyword_to_text["乙木"] == "Some text"
        assert keyword_to_text["劫财"] == "Some text"

    def test_save_filters_all_non_chinese_keywords(self, temp_cache_file: Path):
        import asyncio
        async def run():
            with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file):
                await _save_to_cache(["乙木", "G庚", "Stem", "劫财"], "Text")
        asyncio.run(run())

        entries = [json.loads(entry) for entry in temp_cache_file.read_text(encoding="utf-8").strip().split("\n")]
        keywords = [e["keywords"] for e in entries]
        assert "乙木" in keywords
        assert "劫财" in keywords
        assert "G庚" not in keywords
        assert "Stem" not in keywords


class TestGetOrFetchClassicalText:
    @pytest.mark.asyncio
    async def test_returns_cached_text_when_keyword_found(self):
        temp = Path("/tmp/test_bazi_cache_hit.jsonl")
        temp.write_text(
            json.dumps({"keywords": "乙木", "text": "Cached wood text"}) + "\n",
            encoding="utf-8",
        )
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp), \
             patch("src2.engine.bazi_cache.query_classical_text_async") as mock_qdrant:
            result = await get_or_fetch_classical_text(["乙木"])
        assert "Cached wood text" in result
        mock_qdrant.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_qdrant_when_no_cache_hit(self):
        temp = Path("/tmp/test_bazi_cache_miss.jsonl")
        temp.write_text("", encoding="utf-8")
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp), \
             patch("src2.engine.bazi_cache.query_classical_text_async", new_callable=AsyncMock) as mock_qdrant:
            mock_qdrant.return_value = "Qdrant result for 乙木"
            result = await get_or_fetch_classical_text(["乙木"])
        assert "Qdrant result" in result
        mock_qdrant.assert_awaited_once_with("乙木", top_k=2)

    @pytest.mark.asyncio
    async def test_combines_multiple_cache_hits(self):
        temp = Path("/tmp/test_bazi_cache_multi.jsonl")
        temp.write_text(
            json.dumps({"keywords": "乙木", "text": "Wood text"}) + "\n"
            + json.dumps({"keywords": "劫财", "text": "Rob wealth text"}) + "\n",
            encoding="utf-8",
        )
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp), \
             patch("src2.engine.bazi_cache.query_classical_text_async") as mock_qdrant:
            result = await get_or_fetch_classical_text(["乙木", "劫财"])
        assert "Wood text" in result
        assert "Rob wealth text" in result
        mock_qdrant.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_empty_for_empty_keywords(self):
        result = await get_or_fetch_classical_text([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_partial_cache_hit_fetches_only_misses(self, temp_cache_file: Path):
        temp_cache_file.write_text(
            json.dumps({"keywords": "乙木", "text": "Cached wood text"}) + "\n",
            encoding="utf-8",
        )
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file), \
             patch("src2.engine.bazi_cache.query_classical_text_async", new_callable=AsyncMock) as mock_qdrant:
            mock_qdrant.return_value = "Qdrant result for 劫财"
            result = await get_or_fetch_classical_text(["乙木", "劫财"])
        assert "Cached wood text" in result
        assert "Qdrant result" in result
        mock_qdrant.assert_awaited_once_with("劫财", top_k=2)

    @pytest.mark.asyncio
    async def test_no_cache_contamination_after_multi_keyword_miss(self, temp_cache_file: Path):
        temp_cache_file.write_text("", encoding="utf-8")
        with patch("src2.engine.bazi_cache.CACHE_FILE", temp_cache_file), \
             patch("src2.engine.bazi_cache.query_classical_text_async", new_callable=AsyncMock) as mock_qdrant:
            mock_qdrant.side_effect = ["Wood result for 乙木", "Rob wealth result for 劫财"]
            result = await get_or_fetch_classical_text(["乙木", "劫财"])

            assert "Wood result for 乙木" in result
            assert "Rob wealth result for 劫财" in result

            cache = _load_cache()
            assert cache["乙木"] == "Wood result for 乙木"
            assert cache["劫财"] == "Rob wealth result for 劫财"
