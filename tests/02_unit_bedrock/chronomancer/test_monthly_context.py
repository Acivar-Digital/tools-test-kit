"""
Unit tests for _get_monthly_context in chronomancer_handler.
Verifies correct parsing of V31 modular keys, legacy keys, and loud ValueError propagation on missing data.
"""
# ruff: noqa: E402

import json
import os
import sys
import tempfile
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# Ensure the project root is in the path
sys.path.append(os.getcwd())

from src.bot.chronomancer_handler import _get_monthly_context


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.mark.asyncio
async def test_get_monthly_context_no_reports(mock_db):
    mock_db.get_reports_for_alias.return_value = []
    with patch("src.bot.chronomancer_handler.db", mock_db):
        res = await _get_monthly_context(user_id=123, target_date=date(2026, 5, 22), alias="Tester")
        assert res is None


@pytest.mark.asyncio
async def test_get_monthly_context_modern_happy_path(mock_db):
    # Prepare a temp master.json file
    with tempfile.NamedTemporaryFile(suffix="_master.json", mode="w", delete=False, encoding="utf-8") as f:
        master_data = {
            "monthly_forecasts": [
                {
                    "month_name": "Gui Si",
                    "assembled_narrative": "A modern narrative content here...",
                    "month_metadata": {
                        "month_name": "Gui Si",
                        "start_date": "2026-05-05T00:00:00+08:00"
                    },
                    "module8": {
                        "composite_score": 68
                    }
                }
            ]
        }
        json.dump(master_data, f)
        temp_path = f.name

    try:
        mock_db.get_reports_for_alias.return_value = [
            {"master_json_path": temp_path, "summary_path": "/dummy/summary.md"}
        ]
        with patch("src.bot.chronomancer_handler.db", mock_db):
            res = await _get_monthly_context(user_id=123, target_date=date(2026, 5, 22), alias="Tester")
            assert res is not None
            assert res["month_name"] == "Gui Si"
            assert res["score"] == 68
            assert res["narrative"] == "A modern narrative content here..."
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.mark.asyncio
async def test_get_monthly_context_legacy_happy_path(mock_db):
    # Prepare a temp master.json file with legacy keys
    with tempfile.NamedTemporaryFile(suffix="_master.json", mode="w", delete=False, encoding="utf-8") as f:
        master_data = {
            "months": [
                {
                    "month_name": "Gui Si",
                    "narrative": "A legacy narrative content...",
                    "month_metadata": {
                        "month_name": "Gui Si",
                        "start_date": "2026-05-05T00:00:00+08:00"
                    },
                    "score": 75
                }
            ]
        }
        json.dump(master_data, f)
        temp_path = f.name

    try:
        mock_db.get_reports_for_alias.return_value = [
            {"master_json_path": temp_path, "summary_path": "/dummy/summary.md"}
        ]
        with patch("src.bot.chronomancer_handler.db", mock_db):
            res = await _get_monthly_context(user_id=123, target_date=date(2026, 5, 22), alias="Tester")
            assert res is not None
            assert res["month_name"] == "Gui Si"
            assert res["score"] == 75
            assert res["narrative"] == "A legacy narrative content..."
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.mark.asyncio
async def test_get_monthly_context_missing_narrative_fails_loudly(mock_db):
    with tempfile.NamedTemporaryFile(suffix="_master.json", mode="w", delete=False, encoding="utf-8") as f:
        # narrative/assembled_narrative is empty
        master_data = {
            "monthly_forecasts": [
                {
                    "month_name": "Gui Si",
                    "month_metadata": {
                        "month_name": "Gui Si",
                        "start_date": "2026-05-05T00:00:00+08:00"
                    },
                    "module8": {
                        "composite_score": 68
                    }
                }
            ]
        }
        json.dump(master_data, f)
        temp_path = f.name

    try:
        mock_db.get_reports_for_alias.return_value = [
            {"master_json_path": temp_path, "summary_path": "/dummy/summary.md"}
        ]
        with patch("src.bot.chronomancer_handler.db", mock_db):
            with pytest.raises(ValueError) as excinfo:
                await _get_monthly_context(user_id=123, target_date=date(2026, 5, 22), alias="Tester")
            assert "Monthly narrative for 'Gui Si' is empty or missing" in str(excinfo.value)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.mark.asyncio
async def test_get_monthly_context_missing_score_fails_loudly(mock_db):
    with tempfile.NamedTemporaryFile(suffix="_master.json", mode="w", delete=False, encoding="utf-8") as f:
        # composite_score/score is missing
        master_data = {
            "monthly_forecasts": [
                {
                    "month_name": "Gui Si",
                    "assembled_narrative": "Valid narrative",
                    "month_metadata": {
                        "month_name": "Gui Si",
                        "start_date": "2026-05-05T00:00:00+08:00"
                    }
                }
            ]
        }
        json.dump(master_data, f)
        temp_path = f.name

    try:
        mock_db.get_reports_for_alias.return_value = [
            {"master_json_path": temp_path, "summary_path": "/dummy/summary.md"}
        ]
        with patch("src.bot.chronomancer_handler.db", mock_db):
            with pytest.raises(ValueError) as excinfo:
                await _get_monthly_context(user_id=123, target_date=date(2026, 5, 22), alias="Tester")
            assert "Monthly structural score for 'Gui Si' is missing" in str(excinfo.value)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
