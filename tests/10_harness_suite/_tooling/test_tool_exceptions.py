"""Tests to verify that IDE modification tools raise ModelRetry on errors/failures.
"""
import sys
import json
from pathlib import Path
import pytest
from pydantic_ai.exceptions import ModelRetry

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import factory.infra.tools as tools


def test_replace_text_raises_model_retry_on_error(monkeypatch):
    """Verify replace_text raises ModelRetry when the tool returns an error status."""
    # Mock _run_tool to return error JSON
    def mock_run_tool(tool_name, argv):
        return json.dumps({
            "status": "error",
            "message": "Pattern not found",
            "error": "Target pattern was not found in the source file."
        })
    
    # Mock _src_write_guard to allow write
    import factory.infra.tools_shell
    monkeypatch.setattr(factory.infra.tools_shell, "_src_write_guard", lambda *a: None)
    monkeypatch.setattr(factory.infra.tools_shell, "_run_tool", mock_run_tool)
    
    with pytest.raises(ModelRetry) as exc_info:
        tools.replace_text("src2/a.py", "old", "new")
    assert "Pattern not found" in str(exc_info.value)


def test_replace_text_raises_model_retry_on_no_change(monkeypatch):
    """Verify replace_text raises ModelRetry when status is success but changed is False."""
    def mock_run_tool(tool_name, argv):
        return json.dumps({
            "status": "success",
            "message": "No match found in the file",
            "data": {"changed": False}
        })
    
    import factory.infra.tools_shell
    monkeypatch.setattr(factory.infra.tools_shell, "_src_write_guard", lambda *a: None)
    monkeypatch.setattr(factory.infra.tools_shell, "_run_tool", mock_run_tool)
    
    with pytest.raises(ModelRetry) as exc_info:
        tools.replace_text("src2/a.py", "old", "new")
    assert "No match found in the file" in str(exc_info.value)
