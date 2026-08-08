#!/usr/bin/env python3
"""
smoke_test.py — HARNESS-SIDE per-file type-construction smoke gate.

This is a harness-owned validation tool run by runner.py (or manually by the
operator). It is NOT exposed to any agent's tool_allow_list — the coder never
sees or calls it.

For one staged `.py` file it:
  1. imports the module (with `src2` importable so the edited file's
     cross-module type annotations resolve);
  2. for every pydantic ``BaseModel`` subclass *defined in that file*, probes
     its typed containers (``DictMap[X]`` / ``dict[..., X]`` with ``X`` a
     BaseModel): it builds a real ``X`` instance (via ``construct``, no
     validation) and assigns it into the container, then validates the parent
     model;
  3. if the container rejects the model instance (e.g. ``ExternalPillarTriggerMap
     (DictMap[str])`` given an ``ExternalPillarTrigger``), prints the error and
     exits 1 — this is BUG 2 in docs/01_fix.md (wrong container value type).

This is a *type-construction* check, not an execution test. It does NOT fail
on ordinary Literal/enum field mismatches (those are caught by ruff/pyright);
it targets only the class of bug where a typed container's value type cannot
actually hold the instances the code puts into it.

CLI:
    smoke_test.py <file>   -> prints a single JSON line and exits 0/1.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path
from typing import Any

from pydantic import BaseModel

SCRIPT_DIR = Path(__file__).resolve().parent  # kit-tools/
PROJECT_ROOT = SCRIPT_DIR.parent.parent  # target repo root

# Environmental import failures (DB/network at import time) must NOT block a
# coder — they are the architect's runtime concern, not a type bug (00_fix Fix H).
_ENV_ERRORS: tuple[type[BaseException], ...] = (ConnectionError, OSError)
try:
    import psycopg2

    _ENV_ERRORS = _ENV_ERRORS + (psycopg2.OperationalError,)
except Exception:
    pass
try:
    from sqlalchemy.exc import OperationalError as _SQLOperationalError

    _ENV_ERRORS = _ENV_ERRORS + (_SQLOperationalError,)
except Exception:
    pass


def _sample_base_model(ann: type) -> Any:
    """Build a real (validated) instance of a BaseModel for container probing."""
    data: dict = {}
    for name, field in ann.model_fields.items():
        data[name] = _permissive_value(field.annotation)
    try:
        return ann.model_validate(data)
    except Exception:
        # Fall back to construct (un-validated) if validation fails on strict
        # Literal/enum fields — still a real instance for container-type checks.
        return ann.model_construct(**data)


def _permissive_value(ann: Any) -> Any:
    """A value that satisfies most annotations without raising during sampling."""
    from pydantic import BaseModel

    origin = getattr(ann, "__origin__", None)
    if origin in (dict,):
        args = getattr(ann, "__args__", (str, str))
        v_sample = _permissive_value(args[1]) if len(args) == 2 else "x"
        return {"k": v_sample}
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        return _sample_base_model(ann)
    if ann is bool:
        return True
    if ann in (int, float):
        return 0
    return "x"


def _container_value_type(ann: Any) -> Any | None:
    """If ``ann`` is ``DictMap[X]`` / ``dict[..., X]`` (X a BaseModel), return X."""
    from pydantic import BaseModel

    # RootModel[dict[str, X]] (DictMap[X])
    if isinstance(ann, type) and issubclass(ann, BaseModel):
        fields = list(ann.model_fields.items())
        if len(fields) == 1 and fields[0][0] in ("root", "__root__"):
            inner = fields[0][1].annotation
            return _container_value_type(inner)
    # dict[K, V] / Dict[K, V]
    origin = getattr(ann, "__origin__", None)
    if origin in (dict,):
        args = getattr(ann, "__args__", (str, str))
        if len(args) == 2:
            v = args[1]
            if isinstance(v, type) and issubclass(v, BaseModel):
                return v
    return None


def _root_model_flavor(ann: type) -> bool:
    return "root" in ann.model_fields or "__root__" in ann.model_fields


def _container_is_wide(ann: Any) -> bool:
    """True if the container's declared value type is str / Any / object.

    Handles plain ``dict[str, str]`` and ``DictMap[str]`` (a RootModel whose
    single ``root`` field is ``dict[str, str]``).
    """
    if ann is str or ann is object or ann is None:
        return True
    if isinstance(ann, type) and issubclass(ann, BaseModel) and _root_model_flavor(ann):
        root_field = ann.model_fields.get("root") or ann.model_fields.get("__root__")
        if root_field is not None:
            return _container_is_wide(root_field.annotation)
        return False
    origin = getattr(ann, "__origin__", None)
    if origin in (dict,):
        args = getattr(ann, "__args__", (str, str))
        return len(args) == 2 and args[1] in (str, object, None)
    return False


def _narrow_container_intent(
    ann: Any, field_name: str, file_models: dict[str, type]
) -> type | None:
    """BUG 2 heuristic: if the container's *type* name is ``<X>Map`` and a
    same-file model ``X`` exists, and the container's declared value type is
    wide (str/Any), return ``X`` as the *intended* value type so the caller can
    check whether the container actually accepts an ``X`` instance.
    """
    if not _container_is_wide(ann):
        return None
    type_name = getattr(ann, "__name__", "") or ""
    if not type_name.endswith("Map"):
        return None
    candidate = type_name[: -len("Map")]
    return file_models.get(candidate)


def _module_dotted(path: Path) -> str | None:
    """If ``path`` lives under a package root (``src2/`` or ``src/``), return its
    dotted module name (e.g. ``src2.interfaces.telegram.session``). Returns
    ``None`` when no such marker is present.
    """
    s = str(path.as_posix())
    source_root = os.getenv("KIT_SOURCE_ROOT", "src")
    for marker in (f"/{source_root}/", "/src/"):
        idx = s.find(marker)
        if idx != -1:
            rel = s[idx + 1 :]
            if rel.endswith(".py"):
                rel = rel[:-3]
            return rel.replace("/", ".")
    return None


def _load_module_dotted(path: Path) -> tuple[types.ModuleType | None, str | None]:
    """Import ``path`` by its dotted package name (so cross-module relative
    imports resolve — 00_fix Fix A'/H). Returns (module, error_message).

    On an environmental import error (DB/network at import time) we return
    ``(None, None)`` with ok=True semantics handled by the caller. On a genuine
    import failure we return ``(None, message)`` so the caller can surface it.
    """
    dotted = _module_dotted(path)
    if dotted is None:
        return (None, None)
    # Package root = the dir that contains the source root segment.
    s = str(path.as_posix())
    source_root = os.getenv("KIT_SOURCE_ROOT", "src")
    root = None
    for marker in (f"/{source_root}/", "/src/"):
        idx = s.find(marker)
        if idx != -1:
            root = Path(s[:idx])
            break
    if root is None:
        return (None, None)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    try:
        return (importlib.import_module(dotted), None)
    except _ENV_ERRORS as e:
        # Environmental: do not block the coder.
        return (None, f"__ENV_SKIP__:{e}")
    except Exception as e:  # genuine import failure -> caller falls back
        return (None, f"Import failed: {type(e).__name__}: {e}")


def smoke_module(file_path: str) -> tuple[bool, str]:
    """Probe every BaseModel subclass defined in the file for container value-type bugs.

    Returns (ok, message). On any container value-type mismatch, ok=False.
    """
    from pydantic import BaseModel, ValidationError

    path = Path(file_path).resolve()
    if not path.exists():
        return (False, f"File not found: {path}")

    for p in (str(PROJECT_ROOT), str(PROJECT_ROOT / os.getenv("KIT_SOURCE_ROOT", "src"))):
        if p not in sys.path:
            sys.path.insert(0, p)

    module: types.ModuleType | None = None
    mod_name: str | None = None
    # Preferred: dotted import (resolves relative imports inside the package).
    loaded, err = _load_module_dotted(path)
    if loaded is not None:
        module = loaded
        mod_name = loaded.__name__
    elif err is not None and err.startswith("__ENV_SKIP__"):
        return (True, f"smoke skipped (environmental import error): {err[len('__ENV_SKIP__:'):]}")
    else:
        # Fallback: flat load (no package context) — legacy behaviour.
        mod_name = f"_smoke_{path.stem}"
        spec = importlib.util.spec_from_file_location(mod_name, str(path))
        if spec is None or spec.loader is None:
            return (False, f"Cannot load module from {path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        try:
            spec.loader.exec_module(module)
        except _ENV_ERRORS as e:
            return (True, f"smoke skipped (environmental import error): {e}")
        except Exception as e:
            return (False, f"Import failed: {type(e).__name__}: {e}")

    if module is None or mod_name is None:
        return (False, f"Cannot load module from {path}")

    defined_here = [
        attr
        for attr in vars(module).values()
        if isinstance(attr, type)
        and issubclass(attr, BaseModel)
        and getattr(attr, "__module__", None) == mod_name
    ]
    if not defined_here:
        return (True, f"no pydantic models defined in {path.name}")

    # Index same-file models by name, for the DictMap[X] intent heuristic.
    file_models = {m.__name__: m for m in defined_here}

    errors: list[str] = []
    for cls in defined_here:
        # Build the parent with permissive (string) values for non-container fields.
        base: dict = {}
        for name, field in cls.model_fields.items():
            base[name] = _permissive_value(field.annotation)
        try:
            # Verify the parent builds permissively; if not, skip container
            # probing (pyright/ruff own that class of error).
            cls.model_validate(base)
        except Exception:
            # Parent can't be built even permissively (e.g. strict Literal
            # unions) — skip container probing for this model; pyright/ruff own
            # that class of error.
            continue

        # Probe each typed container field for value-type acceptability.
        for name, field in cls.model_fields.items():
            vtype = _container_value_type(field.annotation)
            if vtype is not None:
                # Declared value type is a BaseModel — the container MUST be able
                # to hold a real instance of it.
                sample = _sample_base_model(vtype)
                try:
                    cls.model_validate({**base, name: {"k": sample}})
                except ValidationError as e:
                    errors.append(
                        f"{cls.__name__}.{name}: container rejects {vtype.__name__} instance — {e}"
                    )
                except Exception as e:
                    errors.append(f"{cls.__name__}.{name}: probe error {type(e).__name__}: {e}")
                continue

            # BUG 2 heuristic: a DictMap/container whose declared value type is
            # str/Any/object but whose name is ``<X>Map`` (e.g.
            # ExternalPillarTriggerMap) and a same-file model ``X`` exists
            # (ExternalPillarTrigger) is very likely meant to hold ``X``
            # instances. If the container rejects an ``X`` instance, the value
            # type is wrongly narrowed (the doc's DictMap[str] bug) — fail.
            heuristic = _narrow_container_intent(field.annotation, name, file_models)
            if heuristic is not None:
                x_cls = heuristic
                sample = _sample_base_model(x_cls)
                try:
                    cls.model_validate({**base, name: {"k": sample}})
                except ValidationError as e:
                    errors.append(
                        f"{cls.__name__}.{name}: declared container rejects "
                        f"{x_cls.__name__} instance (likely wrong value type: "
                        f"should be DictMap[{x_cls.__name__}]) — {e}"
                    )
                except Exception as e:
                    errors.append(f"{cls.__name__}.{name}: probe error {type(e).__name__}: {e}")

    if errors:
        return (False, "\n".join(errors))
    return (True, f"ok: {len(defined_here)} model(s) probed, no container value-type bugs")


def main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"success": False, "error": "usage: smoke_test.py <file>"}))
        return 2
    ok, msg = smoke_module(sys.argv[1])
    print(json.dumps({"success": ok, "message": msg}))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
