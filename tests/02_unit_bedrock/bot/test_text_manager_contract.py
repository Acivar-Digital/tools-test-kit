"""
test_text_manager_contract.py — Contract verification suite for TextManager (V31 remediation).

Verifies export boundary hardening, symbol resolution against messages.yaml,
and fail-safe runtime error handling for invalid keys and formatting exceptions.
"""

from pydantic import BaseModel

from src2.interfaces.telegram.text_manager import (
    TextManager,
    text,
    text_manager,
)


def test_text_manager_export_alias():
    """Verify that both text and text_manager are exported and reference the same singleton instance."""
    assert text is text_manager
    assert isinstance(text_manager, TextManager)


def test_all_yaml_keys_accessible():
    """
    Systematically inspect all categories and keys in messages.yaml and assert that
    text.get(category, key) resolves cleanly without raising exceptions or returning fallback error strings.
    """
    app_messages = text._messages
    for category_name in type(app_messages).model_fields.keys():
        category_obj = getattr(app_messages, category_name)
        assert isinstance(category_obj, BaseModel), f"Category {category_name} should be a BaseModel"
        for key_name in type(category_obj).model_fields.keys():
            res = text.get(category_name, key_name)
            assert isinstance(res, str), f"Result for {category_name}.{key_name} should be string"
            assert res, f"Result for {category_name}.{key_name} should not be empty"
            assert "⚠️ System message unavailable" not in res, (
                f"Failed symbol resolution for {category_name}.{key_name}"
            )


def test_get_invalid_category_or_key():
    """Verify that requesting a non-existent category or key returns a graceful fallback instead of raising AttributeError."""
    res = text.get("non_existent_category", "missing_key")
    assert res == "⚠️ System message unavailable (Key: non_existent_category.missing_key)"

    res_key = text.get("status", "non_existent_key")
    assert res_key == "⚠️ System message unavailable (Key: status.non_existent_key)"


def test_get_formatting_error():
    """Verify that formatting exceptions are caught and return the unformatted template."""
    res = text.get("status", "thinking", invalid_format_arg="value")
    assert isinstance(res, str)
    assert res == text._messages.status.thinking
