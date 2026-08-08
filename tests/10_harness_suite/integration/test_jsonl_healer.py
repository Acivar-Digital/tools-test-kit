from pydantic import BaseModel

from factory.infra import output_sanitizer as osan
from factory.infra.jsonl_compiler import compile_jsonl_to_draft_plan_dict


class DummyEvidence(BaseModel):
    file_path: str
    content: str


class DummySubTask(BaseModel):
    id: str
    file_paths: list[str] = []
    evidence: list[DummyEvidence] = []


class DummyPlan(BaseModel):
    epic: dict = {}
    subtasks: list[DummySubTask] = []


def test_jsonl_compiler_basic():
    raw_jsonl = """
    {"epic": {"title": "Test Epic"}}
    {"subtasks": [{"id": "intern01", "file_paths": ["src2/a.py"]}]}
    """
    res = compile_jsonl_to_draft_plan_dict(raw_jsonl)
    assert res["epic"]["title"] == "Test Epic"
    assert len(res["subtasks"]) == 1
    assert res["subtasks"][0]["id"] == "intern01"
    # Auto-healing should add evidence item for src2/a.py
    assert len(res["subtasks"][0]["evidence"]) == 1
    assert res["subtasks"][0]["evidence"][0]["file_path"] == "src2/a.py"
    assert "[Auto-Healed]" in res["subtasks"][0]["evidence"][0]["content"]


def test_is_jsonl():
    assert osan.is_jsonl('{"a": 1}\n{"b": 2}') is True
    assert osan.is_jsonl('{"a": 1}') is False
    assert osan.is_jsonl('just text') is False


class SimpleModel(BaseModel):
    name: str
    value: int


def test_healer_mode_fallback(monkeypatch):
    import pytest
    malformed = '{"name": "test"}'
    with pytest.raises((RuntimeError, Exception)):
        osan.clean_role_output(malformed, SimpleModel)

def test_registry_str_mapping():
    from factory.common.registry import OUTPUT_TYPE_REGISTRY
    assert "str" in OUTPUT_TYPE_REGISTRY
    assert OUTPUT_TYPE_REGISTRY["str"] is str


def test_generic_jsonl_compiler():
    from factory.infra.jsonl_compiler import compile_jsonl_to_dict
    raw_jsonl = '{"a": 1}\n{"b": 2}\n{"nested": {"x": "y"}}'
    compiled = compile_jsonl_to_dict(raw_jsonl)
    assert compiled["a"] == 1
    assert compiled["b"] == 2
    assert compiled["nested"]["x"] == "y"

