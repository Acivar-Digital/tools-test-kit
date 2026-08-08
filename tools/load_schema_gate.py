import argparse
import importlib.util
import os
import sys
from pathlib import Path

from pydantic import BaseModel

from control import REPO_ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file_path", help="Path to the staged python file")
    args = parser.parse_args()

    repo_root = REPO_ROOT
    temp_dir = repo_root / os.getenv("KIT_TEMP_DIR", "temp")

    # Prepend temp dir to sys.path so staged modules shadow live ones
    sys.path.insert(0, str(temp_dir))
    if str(repo_root) not in sys.path:
        sys.path.insert(1, str(repo_root))

    fp = Path(args.file_path).resolve()
    try:
        rel = fp.relative_to(temp_dir)
    except ValueError:
        try:
            rel = fp.relative_to(repo_root)
        except ValueError:
            print(f"File {fp} is not in repo.")
            sys.exit(1)

    # Load the staged file directly by path (no package __init__.py required).
    # A synthetic dot-free name avoids importlib's package-discovery requirement
    # while keeping internal `from src2...` imports resolvable via sys.path above.
    module_name = "schema_gate_" + str(rel.with_suffix("")).replace(os.sep, "_").replace(".", "_")

    try:
        spec = importlib.util.spec_from_file_location(module_name, str(fp))
        if spec is None or spec.loader is None:
            print(f"Failed to load {fp}: could not build import spec")
            sys.exit(1)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Failed to import {module_name}: {type(e).__name__}: {e}")
        sys.exit(1)

    for name in dir(module):
        obj = getattr(module, name)
        if isinstance(obj, type) and issubclass(obj, BaseModel) and obj is not BaseModel:
            try:
                obj.model_json_schema()
            except Exception as e:
                print(f"Failed schema validation for {name}: {type(e).__name__}: {e}")
                sys.exit(1)

    print("Schema load successful.")
    sys.exit(0)


if __name__ == "__main__":
    main()
