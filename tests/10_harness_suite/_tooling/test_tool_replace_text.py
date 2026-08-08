import os
import tempfile
import subprocess
import json

def test_replace_text_ignore_whitespace():
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", dir=".", suffix=".txt", delete=False) as f:
        f.write("def foo():\n    return 'bar'\n")
        f.flush()
        file_path = f.name
        
    try:
        rel_path = os.path.relpath(file_path, start=".")
        
        # We want to replace "return 'bar'" but we provide different whitespaces
        target_text = "def foo():\n\n\n\n  return 'bar'"
        replacement_text = "def foo():\n    return 'baz'"
        
        cmd = ["uv", "run", "python", "factory/tools/replace_text.py", rel_path, target_text, replacement_text, "--ignore-whitespace"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        output = result.stdout
        # print("stdout:", output)
        # print("stderr:", result.stderr)
        
        assert result.returncode == 0
        try:
            parsed = json.loads(output)
            assert parsed.get("success") is True
            assert parsed["data"]["changed"] is True
            assert parsed["data"]["count"] == 1
        except json.JSONDecodeError:
            assert False, f"Output was not valid JSON: {output}"
            
        with open(file_path, "r", encoding="utf-8") as rf:
            content = rf.read()
            assert "return 'baz'" in content
            assert "return 'bar'" not in content
    finally:
        os.remove(file_path)

def test_replace_text_ignore_whitespace_case_insensitive():
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", dir=".", suffix=".txt", delete=False) as f:
        f.write("hello   WORLD\n")
        f.flush()
        file_path = f.name
        
    try:
        rel_path = os.path.relpath(file_path, start=".")
        
        target_text = "HELLO world"
        replacement_text = "goodbye world"
        
        cmd = ["uv", "run", "python", "factory/tools/replace_text.py", rel_path, target_text, replacement_text, "--ignore-whitespace", "--case-insensitive"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        output = result.stdout
        
        assert result.returncode == 0
        try:
            parsed = json.loads(output)
            assert parsed.get("success") is True
            assert parsed["data"]["changed"] is True
            assert parsed["data"]["count"] == 1
        except json.JSONDecodeError:
            assert False, f"Output was not valid JSON: {output}"
            
        with open(file_path, "r", encoding="utf-8") as rf:
            content = rf.read()
            assert "goodbye world" in content
    finally:
        os.remove(file_path)
