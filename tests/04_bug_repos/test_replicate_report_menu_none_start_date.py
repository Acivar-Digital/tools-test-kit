import json
import os
import tempfile

from src2.interfaces.telegram.report_utils import (
    _format_date_range,
    _format_english_month_header,
    get_report_menu_text,
)


def test_format_date_range_with_none_start_iso_returns_unknown(caplog):
    """
    After fix: _format_date_range(None) returns "Unknown date" instead of crashing.
    """
    caplog.set_level("ERROR", logger="src2.interfaces.telegram.report_utils")
    result = _format_date_range(None, None)
    assert result == "Unknown date"


def test_format_date_range_with_valid_start_iso(caplog):
    """
    Sanity check: _format_date_range works correctly with valid dates.
    """
    caplog.set_level("ERROR", logger="src2.interfaces.telegram.report_utils")
    result = _format_date_range("2026-02-04T04:02:00+08:00")
    assert result != "Unknown date"
    assert "Feb" in result or "04 Feb" in result


def test_get_report_menu_text_with_valid_month_metadata_works():
    """
    After fix: when month_metadata.start_date is present, the menu renders correctly.
    This replicates the /reports trigger point that the user experienced.
    """
    master = {
        "monthly_forecasts": [
            {
                "month_name": "Month 1",
                "month_title": "Geng Yin Month",
                "advisory": {},
                "month_metadata": {
                    "start_date": "2026-02-04T04:02:00+08:00",
                    "month_name": "Geng Yin",
                    "stem": "Geng",
                    "branch": "Yin",
                },
            }
        ] * 12
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(master, f)
        tmp = f.name

    try:
        menu = get_report_menu_text(tmp)
        assert "Your 2026 Monthly Forecasts" in menu
        assert "/1." in menu
        assert "/12." in menu
        assert "Geng Yin" in menu
    finally:
        os.unlink(tmp)


def test_get_report_menu_text_with_missing_month_metadata_returns_graceful_message():
    """
    After fix: when month_metadata is missing, the menu does not crash.
    It returns a graceful message or renders with "Unknown date".
    """
    master = {
        "monthly_forecasts": [
            {
                "month_name": "Geng Yin",
                "month_title": "Navigating Structural Governance",
                "advisory": {},
            }
        ] * 12
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(master, f)
        tmp = f.name

    try:
        menu = get_report_menu_text(tmp)
        assert "Failed to load report menu" not in menu
    finally:
        os.unlink(tmp)


def test_get_report_menu_text_with_empty_monthly_forecasts():
    """
    Edge case: empty monthly_forecasts returns a no-data message.
    """
    master = {"monthly_forecasts": []}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(master, f)
        tmp = f.name

    try:
        menu = get_report_menu_text(tmp)
        assert "No monthly data found" in menu
    finally:
        os.unlink(tmp)


def test_format_english_month_header_with_none_start_iso_returns_unknown():
    """
    After fix: _format_english_month_header(None) returns "Unknown Month" instead of crashing.
    This replicates the crash path when month_metadata.start_date is missing from JSON.
    """
    result = _format_english_month_header(None)
    assert result == "Unknown Month"


def test_format_english_month_header_with_none_next_start_iso():
    """
    _format_english_month_header works when next_start_iso is None (last month of the year).
    """
    result = _format_english_month_header("2026-12-06T00:00:00+08:00", None)
    assert "December" in result
    assert "2026" in result


def test_get_report_menu_text_with_stale_json_shows_month_names_not_numbers():
    """
    Stale JSON scenario: month_metadata is empty {} but month_name is at top level.
    After fix: menu should show "Geng Yin" not "Month 1".
    This matches the user's actual reported output.
    """
    master = {
        "monthly_forecasts": [
            {
                "month_name": "Geng Yin",
                "month_title": "Navigating Structural Governance",
                "advisory": {},
            }
        ] * 12
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(master, f)
        tmp = f.name

    try:
        menu = get_report_menu_text(tmp)
        assert "Failed to load report menu" not in menu
        assert "Geng Yin" in menu
        assert "Month 1" not in menu
    finally:
        os.unlink(tmp)


def test_format_date_range_shows_end_of_month_not_next_start():
    """
    After fix: _format_date_range shows the last day of the current month,
    not the next month's start date. e.g. Feb 4 – Mar 4 should become Feb 4 – Mar 3.
    """
    result = _format_date_range("2026-02-04T04:02:00+08:00", "2026-03-05T21:59:00+08:00")
    assert result != "Unknown date"
    assert "04 Feb" in result
    # End date should be one day before the next start (Mar 4, not Mar 5)
    assert "04 Mar" in result
