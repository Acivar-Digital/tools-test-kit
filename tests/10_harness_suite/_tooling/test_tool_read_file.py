import os
import tempfile
import subprocess

def test_read_file_line_numbers():
    with tempfile.NamedTemporaryFile("w+", encoding="utf-8", dir=".", suffix=".txt", delete=False) as f:
        f.write("alpha\nbeta\ngamma\ndelta\n")
        f.flush()
        file_path = f.name
        
    try:
        # Ensure path is relative to repo root (where this is run from)
        rel_path = os.path.relpath(file_path, start=".")
        
        # Call the script using uv run python
        env = os.environ.copy()
        # Unset CWD and TARGET_REPO so resolve_secure_path falls back to PROJECT_ROOT
        env.pop("CWD", None)
        env.pop("TARGET_REPO", None)
        cmd = ["uv", "run", "python", "factory/tools/read_file.py", rel_path, "--start-line", "2", "--end-line", "3"]
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        output = result.stdout
        
        assert "2: beta" in output
        assert "3: gamma" in output
        assert "1: alpha" not in output
        assert "4: delta" not in output
        assert "=== File read" in output
        assert result.returncode == 0
    finally:
        os.remove(file_path)

def test_read_file_missing_file():
    cmd = ["uv", "run", "python", "factory/tools/read_file.py", "nonexistent_file_12345.txt"]
    result = subprocess.run(cmd, capture_output=True, text=True)
        
    output = result.stdout
    assert "ERROR: File not found" in output
    # Check that returncode is 0, since it just prints ERROR and returns
    assert result.returncode == 0
