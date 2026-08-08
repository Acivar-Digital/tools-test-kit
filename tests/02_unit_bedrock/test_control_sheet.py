from pydantic import BaseModel

from admin.controls.controls import CONTROL_SHEET, ControlSheetSchema


def test_control_sheet_is_pydantic_model():
    """Verify CONTROL_SHEET is an instance of ControlSheetSchema and subclasses BaseModel."""
    assert isinstance(CONTROL_SHEET, ControlSheetSchema)
    assert issubclass(ControlSheetSchema, BaseModel)
    assert isinstance(CONTROL_SHEET, BaseModel)

def test_control_sheet_dot_access():
    """Verify attributes of CONTROL_SHEET can be accessed via dot notation."""
    # Test a few models using dot notation to ensure they exist and can be accessed
    assert CONTROL_SHEET.rag_model is not None
    assert CONTROL_SHEET.chrono_model is not None
    assert CONTROL_SHEET.subagent_model is not None

    # Check one that might be optional but allows dot access
    assert hasattr(CONTROL_SHEET, "intake_model")
