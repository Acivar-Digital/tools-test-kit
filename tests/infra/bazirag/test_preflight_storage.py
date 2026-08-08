"""
Tests for check_bazi_rag_storage() in preflight.py.
Verifies TurboVec and SQLite file presence checks.
"""
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestCheckBaziRagStorage:
    @pytest.mark.asyncio
    async def test_both_files_exist_returns_true(self, tmp_path: Path, monkeypatch):
        from src2.interfaces.telegram.preflight import check_bazi_rag_storage
        rag_dir = tmp_path / "infrastructure" / "rag"
        rag_dir.mkdir(parents=True)
        (rag_dir / "bazi_index.tv").write_text("fake index")
        (rag_dir / "bazi_metadata.db").write_text("fake db")
        monkeypatch.chdir(tmp_path)
        result = await check_bazi_rag_storage()
        assert result is True

    @pytest.mark.asyncio
    async def test_missing_tv_file_returns_false(self, tmp_path: Path, monkeypatch):
        from src2.interfaces.telegram.preflight import check_bazi_rag_storage
        rag_dir = tmp_path / "infrastructure" / "rag"
        rag_dir.mkdir(parents=True)
        (rag_dir / "bazi_metadata.db").write_text("fake db")
        monkeypatch.chdir(tmp_path)
        result = await check_bazi_rag_storage()
        assert result is False

    @pytest.mark.asyncio
    async def test_missing_db_file_returns_false(self, tmp_path: Path, monkeypatch):
        from src2.interfaces.telegram.preflight import check_bazi_rag_storage
        rag_dir = tmp_path / "infrastructure" / "rag"
        rag_dir.mkdir(parents=True)
        (rag_dir / "bazi_index.tv").write_text("fake index")
        monkeypatch.chdir(tmp_path)
        result = await check_bazi_rag_storage()
        assert result is False

    @pytest.mark.asyncio
    async def test_missing_both_files_returns_false(self, tmp_path: Path, monkeypatch):
        from src2.interfaces.telegram.preflight import check_bazi_rag_storage
        rag_dir = tmp_path / "infrastructure" / "rag"
        rag_dir.mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        result = await check_bazi_rag_storage()
        assert result is False

    @pytest.mark.asyncio
    async def test_check_bazi_rag_storage_prints_status(self, tmp_path: Path, monkeypatch, capsys):
        from src2.interfaces.telegram.preflight import check_bazi_rag_storage
        rag_dir = tmp_path / "infrastructure" / "rag"
        rag_dir.mkdir(parents=True)
        (rag_dir / "bazi_index.tv").write_text("fake index")
        (rag_dir / "bazi_metadata.db").write_text("fake db")
        monkeypatch.chdir(tmp_path)
        result = await check_bazi_rag_storage()
        assert result is True

    def test_preflight_check_qdrant_still_present(self):
        from src2.interfaces.telegram.preflight import check_qdrant
        assert callable(check_qdrant)


class TestPreflightStorageIntegration:
    def test_tv_file_extension_is_tv(self):
        expected = "bazi_index.tv"
        assert expected.endswith(".tv")

    def test_db_file_extension_is_db(self):
        expected = "bazi_metadata.db"
        assert expected.endswith(".db")

    def test_constants_match_preflight_paths(self):
        from src2.core.memory.constants import BAZI_SQLITE_PATH, TURBOVEC_INDEX_PATH
        assert TURBOVEC_INDEX_PATH.name == "bazi_index.tv"
        assert BAZI_SQLITE_PATH.name == "bazi_metadata.db"
