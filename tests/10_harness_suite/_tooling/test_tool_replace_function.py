import subprocess
from pathlib import Path

def test_replace_function_preserves_formatting():
    # Use a relative path inside the workspace
    source_rel = "tests/test_tmp_replace.py"
    source = Path(source_rel)
    source.write_text("""\
# Some file comment
import os

class Foo:
    # A comment before method
    def method(self):
        return 1

    def another(self):
        pass

# End comment
""")
    
    # Tool currently requires new_function_code to be valid top-level Python
    # meaning it cannot have leading indentation. 
    new_func = """\
def method(self):
    # new comment
    return 2
"""
    
    try:
        # Run the tool
        cmd = [
            "python", "factory/tools/replace_function.py",
            source_rel, "method", new_func, "--class-name", "Foo"
        ]
        subprocess.run(cmd, check=True)
        
        updated = source.read_text()
        assert "# Some file comment" in updated
        assert "# End comment" in updated
        assert "return 2" in updated
        assert "# new comment" in updated
        assert "return 1" not in updated
        
        # Verify the indentation was applied correctly!
        assert "    def method(self):" in updated
        
        # Also test top-level function
        source2_rel = "tests/test_tmp_replace2.py"
        source2 = Path(source2_rel)
        source2.write_text("""\
def top_level():
    pass

# footer
""")
        new_func2 = """\
def top_level():
    return True
"""
        cmd2 = [
            "python", "factory/tools/replace_function.py",
            source2_rel, "top_level", new_func2
        ]
        subprocess.run(cmd2, check=True)
        
        updated2 = source2.read_text()
        assert "# footer" in updated2
        assert "return True" in updated2
    finally:
        # Cleanup
        if source.exists():
            source.unlink()
        if Path("tests/test_tmp_replace2.py").exists():
            Path("tests/test_tmp_replace2.py").unlink()

