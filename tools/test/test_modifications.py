import json
import os
import shutil
import subprocess
from pathlib import Path

SCRATCH_DIR = "scratch"

def run_tool(args):
    result = subprocess.run(["uv", "run", "python", str(Path(__file__).parents[1] / f"{args[0]}.py")] + args[1:],
                            capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error running {args[0]}.py: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Failed to decode JSON from {args[0]}.py: {result.stdout}")
        return None

def setup():
    if os.path.exists(SCRATCH_DIR):
        shutil.rmtree(SCRATCH_DIR)
    os.makedirs(SCRATCH_DIR)

def test_write_file():
    print("Testing write_file...")
    path = f"{SCRATCH_DIR}/test.txt"
    content = "Hello World"
    res = run_tool(["write_file", path, content])
    return res is not None and os.path.exists(path) and open(path).read() == content

def test_replace_text():
    print("Testing replace_text...")
    path = f"{SCRATCH_DIR}/test.txt"
    if not os.path.exists(path):
        with open(path, "w") as f:
            f.write("Hello World")
    res = run_tool(["replace_text", path, "World", "Opencode"])
    return res is not None and open(path).read() == "Hello Opencode"

def test_replace_function():
    print("Testing replace_function...")
    path = f"{SCRATCH_DIR}/test_func.py"
    content = "def foo():\n    return 1"
    with open(path, "w") as f:
        f.write(content)
    new_code = "def foo():\n    return 2"
    res = run_tool(["replace_function", path, "foo", new_code])
    return res is not None and "return 2" in open(path).read()

def test_add_constant():
    print("Testing add_constant...")
    path = f"{SCRATCH_DIR}/test_const.py"
    with open(path, "w") as f:
        f.write("x = 1")
    res = run_tool(["add_constant", path, "MY_CONST", "100"])
    return res is not None and "MY_CONST = 100" in open(path).read()

def test_add_import():
    print("Testing add_import...")
    path = f"{SCRATCH_DIR}/test_import.py"
    with open(path, "w") as f:
        f.write("print(os.getcwd())")
    res = run_tool(["add_import", path, "import os"])
    return res is not None and "import os" in open(path).read()

def test_delete_file():
    print("Testing delete_file...")
    path = f"{SCRATCH_DIR}/delete_me.txt"
    with open(path, "w") as f:
        f.write("bye")
    res = run_tool(["delete_file", path])
    return res is not None and not os.path.exists(path)

def test_rename_file():
    print("Testing rename_file...")
    old_path = f"{SCRATCH_DIR}/old.txt"
    new_path = f"{SCRATCH_DIR}/new.txt"
    with open(old_path, "w") as f:
        f.write("hi")
    res = run_tool(["rename_file", old_path, new_path])
    return res is not None and not os.path.exists(old_path) and os.path.exists(new_path)

def test_move_symbol():
    print("Testing move_symbol...")
    src_path = f"{SCRATCH_DIR}/src.py"
    dst_path = f"{SCRATCH_DIR}/dst.py"
    with open(src_path, "w") as f:
        f.write("def move_me():\n    pass")
    with open(dst_path, "w") as f:
        f.write("")
    res = run_tool(["move_symbol", "move_me", src_path, dst_path])
    return res is not None and "def move_me" in open(dst_path).read()

def test_ast_clean_imports():
    print("Testing ast_clean_imports...")
    path = f"{SCRATCH_DIR}/clean.py"
    content = "import os\nimport sys\nprint(1)"
    with open(path, "w") as f:
        f.write(content)
    res = run_tool(["ast_clean_imports", path])
    # Since os and sys are unused, they should be removed by ruff
    return res is not None and "import os" not in open(path).read()

if __name__ == "__main__":
    setup()
    tests = [test_write_file, test_replace_text, test_replace_function, test_add_constant,
             test_add_import, test_delete_file, test_rename_file, test_move_symbol, test_ast_clean_imports]
    results = []
    for test in tests:
        results.append((test.__name__, test()))

    for name, res in results:
        print(f"{name}: {'PASS' if res else 'FAIL'}")
