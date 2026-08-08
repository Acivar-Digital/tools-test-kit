#!/usr/bin/env python3
"""
Kill-Tries Scanner & Refactorer: Flat Control Flow & Anti-Pattern Eliminator.
Scans Python files in src2/ for:
1. Priority 1: Try Pyramids / Try-Else-If Anti-Patterns.
2. Priority 2: Deep Nesting (Depth > 3).
3. Priority 3: Cyclomatic Complexity (CC > 5).

Uses AST pre-filtering first, Pydantic AI 2.0 (CONTROL_SHEET.scanner_model) for refactoring,
VirtualASTBuffer for in-memory AST verification, and AST validation before committing code changes.

Emits kit-hygiene/reports/kill_tries.json
"""

import ast
import asyncio
import functools
import json
import logging
import os
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import logfire
import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import ModelRetry
from pydantic_ai.messages import ModelRequest, UserPromptPart

# Ensure repo root in sys.path
from _bootstrap import pkg_root  # noqa: F401,E402

REQUEST_TIMEOUT = 300  # seconds — max subprocess/LLM request timeout
MAX_RETRIES = 10  # max retries for LLM refactoring attempts

from virtual_ast_buffer import (  # noqa: E402
    VirtualASTBuffer,
    ensure_pydantic_imports,
)
from control import CONTROL_SHEET  # noqa: E402

_KNOWN_TEMPLATE_KEYS = re.compile(
    r"\{("
    + r"|".join(re.escape(k) for k in (
        "file_path", "function_name", "narrative_context", "anti_patterns",
        "samples", "attempts_left", "upstream_callers", "module_context",
        "anti_patterns_list", "conditions", "rules", "line", "violations",
        "what_worked_text", "what_to_fix_text", "violation_count", "attempt",
        "violations_text", "what_worked", "what_to_fix",
        "imported_modules_text", "imported_symbols_text", "top_level_symbols_text",
        "global_constants_text", "header_symbol_contract",
    ))
    + r")\}"
)


def fill_template(template_str: str, **kwargs: str) -> str:
    def _replacer(match: re.Match) -> str:
        val = kwargs.get(match.group(1))
        return val if val is not None else match.group(0)

    return _KNOWN_TEMPLATE_KEYS.sub(_replacer, template_str)

# Initialize Logfire instrumentation once globally
try:
    logfire.configure(send_to_logfire=False)
    logfire.instrument_pydantic_ai()
except Exception as err:
    logging.warning("Logfire instrumentation failed: %s", err)

CHECKPOINT_FILE = pkg_root / "reports" / "kill_tries_checkpoint.jsonl"
REPORT_FILE = pkg_root / "reports" / "kill_tries.json"
SRC2_DIR = pkg_root.parent / "src2"
PROMPT_TEMPLATE_PATH = pkg_root / "scanners" / "kill_tries_prompt.yaml"
PROMPT_RETRY_PATH = pkg_root / "scanners" / "kill_tries_prompt_retry.yaml"
LIST_FILE = pkg_root / "scanners" / "kill_tries_list.txt"


def get_timestamp() -> str:
    now = datetime.now()
    return now.strftime("%m-%d-%H:%M:%S") + f":{int(now.microsecond / 1000):03d}"


def get_model_provider_name(model: Any) -> str:
    provider = getattr(model, "provider", None)
    from control import PROVIDERS

    for name, prov in PROVIDERS.items():
        if provider is prov:
            return name
    base_url = getattr(provider, "base_url", "")
    return base_url.split("/")[2] if "/" in base_url else "unknown"


# Configure logging with ANSI colors
class ColoredFormatter(logging.Formatter):
    COLORS = {
        "INFO": "\033[94m",
        "WARNING": "\033[93m",
        "ERROR": "\033[91m",
        "CRITICAL": "\033[91m\033[1m",
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"
    GREEN = "\033[92m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)
        msg = record.getMessage()
        if msg.startswith("[") and "]" in msg:
            end_idx = msg.find("]") + 1
            msg = f"{self.BOLD}{self.GREEN}{msg[:end_idx]}{self.RESET} {msg[end_idx:].strip()}"
        return f"{color}[{record.levelname}]{self.RESET} {msg}"


handler = logging.StreamHandler()
handler.setFormatter(ColoredFormatter())
logger = logging.getLogger("KillTriesScanner")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False


def _normalize_pyright_error(line: str) -> str:
    line = line.strip()
    if " - " in line:
        return line.split(" - ", 1)[-1].strip()
    return line


def _get_normalized_pyright_errors(file_content: str) -> set[str]:
    if not file_content:
        return set()
    scratch_dir = pkg_root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = scratch_dir / f"temp_pyright_{uuid.uuid4().hex}.py"
    try:
        tmp_path.write_text(file_content, encoding="utf-8")
        res = subprocess.run(
            ["uv", "run", "pyright", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=REQUEST_TIMEOUT,
            cwd=str(pkg_root),
            env={**os.environ, "PYTHONPATH": "."},
        )
        errors = set()
        for line in res.stdout.splitlines():
            if "error:" in line.lower():
                norm = _normalize_pyright_error(line)
                if norm:
                    errors.add(norm)
        return errors
    except Exception:
        return set()
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def _get_ruff_errors(file_content: str) -> set[str]:
    if not file_content:
        return set()
    scratch_dir = pkg_root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = scratch_dir / f"temp_pyright_{uuid.uuid4().hex}.py"
    try:
        tmp_path.write_text(file_content, encoding="utf-8")
        res = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "F821,E9,F63,F7", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=REQUEST_TIMEOUT,
            cwd=str(pkg_root),
            env={**os.environ, "PYTHONPATH": "."},
        )
        errors = set()
        for line in res.stdout.splitlines():
            if ":" in line:
                norm = line.split(":", 1)[-1].strip()
                if norm:
                    errors.add(norm)
        return errors
    except Exception:
        return set()
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


@functools.lru_cache(maxsize=128)
def get_file_baseline_errors(file_path_str: str, root_dir: Path) -> set[str]:
    full_path = root_dir / file_path_str
    if not full_path.exists():
        return set()
    source = full_path.read_text(encoding="utf-8")
    return _get_normalized_pyright_errors(source)


# =====================================================================
# PYDANTIC 2.0 DOMAIN SCHEMAS
# =====================================================================


class HeaderSymbolContract(BaseModel):
    """Structured contract of imported modules, symbols, top-level definitions, and global constants."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    imported_modules: list[str] = Field(default_factory=list)
    imported_symbols: list[str] = Field(default_factory=list)
    top_level_symbols: list[str] = Field(default_factory=list)
    global_constants: list[str] = Field(default_factory=list)

    def to_prompt_section(self) -> str:
        all_symbols = sorted(set(self.imported_symbols + self.top_level_symbols + self.global_constants))
        symbols_str = ", ".join(all_symbols) if all_symbols else "None"
        modules_str = ", ".join(sorted(set(self.imported_modules))) if self.imported_modules else "None"
        return (
            f"AVAILABLE IMPORTED MODULES IN THIS FILE HEADER: [{modules_str}]\n"
            f"AVAILABLE IMPORTED MODELS AND SYMBOLS IN THIS FILE HEADER: [{symbols_str}]\n"
            f"STRICT RULE: You must ONLY use standard primitives (int, str, float, bool, dict, list, tuple, set, Any, Optional, Union) OR the imported symbols listed above. DO NOT invent or reference unimported class names."
        )


def extract_header_symbol_contract(source: str) -> HeaderSymbolContract:
    """Parse full file AST to extract all imported module names, imported symbols, top-level functions/classes, and global constants."""
    if not source:
        return HeaderSymbolContract()
    try:
        tree = ast.parse(source)
    except Exception:
        return HeaderSymbolContract()

    imported_modules: set[str] = set()
    imported_symbols: set[str] = set()
    top_level_symbols: set[str] = set()
    global_constants: set[str] = set()

    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)
                bound_name = alias.asname or alias.name.split(".")[0]
                imported_symbols.add(bound_name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_modules.add(node.module)
            for alias in node.names:
                if alias.name != "*":
                    bound_name = alias.asname or alias.name
                    imported_symbols.add(bound_name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            top_level_symbols.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    global_constants.add(target.id)

    return HeaderSymbolContract(
        imported_modules=sorted(imported_modules),
        imported_symbols=sorted(imported_symbols),
        top_level_symbols=sorted(top_level_symbols),
        global_constants=sorted(global_constants),
    )


class FunctionCandidate(BaseModel):
    """Pydantic 2.0 schema representing candidate functions violating control flow standards."""

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)

    file_path: str
    function_name: str
    line: int
    end_line: int
    cc: int
    max_depth: int
    priority: int
    try_issues: list[tuple[int, str]] = Field(default_factory=list)
    source_code: str
    full_file_source: str = ""
    upstream_callers: str = ""
    module_context: str = ""
    header_contract: HeaderSymbolContract = Field(default_factory=HeaderSymbolContract)
    phase: int = 1
    parent_function: str = ""
    line_count: int = 0
    requires_decomposition: bool = False


class DecompositionPlan(BaseModel):
    """Result of deterministic pre-decomposition of an extremely complex function."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    phase_number: int = 1
    main_function_name: str = ""
    helper_functions: list[str] = Field(default_factory=list)
    helper_candidates: list[FunctionCandidate] = Field(default_factory=list)
    residual_cc: int = 0
    original_cc: int = 0


class RefactoringVerdict(BaseModel):
    """Pydantic 2.0 schema for LLM structured refactoring output with strict constraints."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    reasoning_and_plan: str = Field(
        ...,
        description="Step-by-step reasoning and plan for refactoring, verifying imports, symbols, and helper function scope",
    )
    function_name: str = Field(..., description="Name of the target function being refactored")
    refactored_code: str = Field(
        ...,
        description="Complete refactored python code starting at column 0 (no leading indentation), using flat control flow",
    )
    helper_functions: list[str] = Field(
        default_factory=list,
        description="Extracted private helper functions starting at column 0 (no leading indentation)",
    )
    explanation: str = Field(..., description="Summary of how anti-patterns and deep nesting were eliminated")

    @field_validator("reasoning_and_plan", "refactored_code", "helper_functions", mode="before")
    @classmethod
    def strip_markdown_backticks(cls, v: Any) -> Any:
        def _clean(s: str) -> str:
            s = s.strip()
            if s.startswith("```python"):
                s = s[9:]
            elif s.startswith("```"):
                s = s[3:]
            if s.endswith("```"):
                s = s[:-3]
            return s.strip()

        if isinstance(v, str):
            return _clean(v)
        elif isinstance(v, list):
            return [_clean(item) if isinstance(item, str) else item for item in v]
        return v

    @model_validator(mode="after")
    def validate_structural_constraints(self) -> "RefactoringVerdict":
        combined = self.refactored_code + "\n" + "\n".join(self.helper_functions)
        lines = combined.splitlines()

        safe_modules = {"typing", "collections", "enum", "dataclasses", "itertools", "re"}
        unauthorized_imports: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                parts = stripped.split()
                mod = parts[1].split(".")[0] if len(parts) > 1 else ""
                if mod not in safe_modules and not mod.startswith("src2"):
                    unauthorized_imports.append(stripped)

        if unauthorized_imports:
            raise ModelRetry(
                f"CRITICAL: Unauthorized imports included: {unauthorized_imports}. "
                f"You may ONLY import from {safe_modules} or internal `src2` modules."
            )

        class_lines = [line for line in lines if line.strip().startswith("class ")]
        if class_lines:
            raise ModelRetry(
                f"CRITICAL: You created a class: {class_lines}. Do NOT create classes to pass state. "
                f"Use flat dictionaries, tuples, or standard function arguments."
            )

        # Closure Ban: Prevent nested function definitions inside main refactored code
        try:
            main_tree = ast.parse(self.refactored_code)
            for node in ast.walk(main_tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name != self.function_name:
                        raise ModelRetry(
                            f"CRITICAL: Nested function `{node.name}` defined inside `refactored_code`. "
                            f"Move `{node.name}` into `helper_functions` and ensure it starts with `_{self.function_name}_`."
                        )
        except SyntaxError as e:
            logger.warning(f"[validate_structural_constraints] SyntaxError in refactored code: {e}")

        # Helper Naming Constraint: Ensure helper functions start with an underscore
        for helper_code in self.helper_functions:
            try:
                helper_tree = ast.parse(helper_code)
                for node in helper_tree.body:
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not node.name.startswith("_"):
                            raise ModelRetry(
                                f"CRITICAL: Helper function `{node.name}` MUST start with an underscore (e.g., `_{node.name}`)."
                            )
            except SyntaxError as e:
                logger.warning(f"[validate_structural_constraints] SyntaxError in helper code: {e}")

        return self


class RefactorDeps(BaseModel):
    """Pydantic 2.0 schema for agent dependencies."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    orig_code: str = ""
    full_file_source: str = ""
    file_path: str = ""
    line: int = 0
    end_line: int = 0
    func_name: str = ""
    baseline_errors: set[str] = Field(default_factory=set)
    header_contract: HeaderSymbolContract = Field(default_factory=HeaderSymbolContract)


class RefactorResult(BaseModel):
    """Pydantic 2.0 schema for checkpoint and report items."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_path: str
    function_name: str
    line: int
    status: str  # "APPROVED", "FAILED_VERIFICATION", "LLM_ERROR", "FAILED_RUNTIME"
    attempts: int
    original_cc: int
    refactored_cc: int
    original_depth: int
    refactored_depth: int
    refactored_code: str
    helper_functions: list[str] = Field(default_factory=list)
    explanation: str
    verification_msg: str
    reasoning_and_plan: str = ""


refactor_result_adapter = TypeAdapter(RefactorResult)


# =====================================================================
# PYDANTIC-AI AGENT & OUTPUT VALIDATION
# =====================================================================

_refactor_agent = Agent(
    model=CONTROL_SHEET.scanner_model,
    deps_type=RefactorDeps,
    output_type=RefactoringVerdict,
    instructions="You are a principal Python architect strictly enforcing Flat Control Flow.",
    retries=MAX_RETRIES,
    model_settings={"temperature": 0.0, "timeout": REQUEST_TIMEOUT},
)


class ComplexityVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        self.complexity += 1
        for case in node.cases:
            self.complexity += 1
        self.generic_visit(node)

    def _count_comprehension_ifs(self, node: Any) -> None:
        for gen in node.generators:
            self.complexity += len(gen.ifs)
        self.generic_visit(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._count_comprehension_ifs(node)

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._count_comprehension_ifs(node)

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._count_comprehension_ifs(node)

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._count_comprehension_ifs(node)


class ReturnVisitor(ast.NodeVisitor):
    """Scans AST to record top-level return expressions."""

    def __init__(self) -> None:
        self.return_types: set[str] = set()

    def visit_Return(self, node: ast.Return) -> None:
        if node.value:
            if isinstance(node.value, ast.Dict):
                self.return_types.add("dict")
            elif isinstance(node.value, ast.Call):
                self.return_types.add("call")
            elif isinstance(node.value, (ast.Tuple, ast.List)):
                self.return_types.add("sequence")
            elif isinstance(node.value, ast.Name):
                self.return_types.add("var")
        self.generic_visit(node)


class AttributeVisitor(ast.NodeVisitor):
    """Scans AST to record attribute access names on existing objects."""

    def __init__(self) -> None:
        self.attributes: set[str] = set()

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.attributes.add(node.attr)
        self.generic_visit(node)


class CallVisitor(ast.NodeVisitor):
    """Scans AST to record function calls and the variable names passed as arguments."""

    def __init__(self) -> None:
        self.calls: set[tuple[str, tuple[str, ...]]] = set()
        self.calls_with_keywords: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        func_name: str | None = None
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            func_name = node.func.attr

        if func_name:
            args = tuple(arg.id for arg in node.args if isinstance(arg, ast.Name))
            self.calls.add((func_name, args))
            if node.keywords:
                self.calls_with_keywords.add(func_name)
        self.generic_visit(node)


STANDARD_BUILTINS_AND_TYPING: set[str] = {
    # Standard Python builtins
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes", "callable",
    "chr", "classmethod", "compile", "complex", "delattr", "dict", "dir", "divmod",
    "enumerate", "eval", "exec", "filter", "float", "format", "frozenset", "getattr",
    "globals", "hasattr", "hash", "help", "hex", "id", "input", "int", "isinstance",
    "issubclass", "iter", "len", "list", "locals", "map", "max", "memoryview",
    "min", "next", "object", "oct", "open", "ord", "pow", "print", "property",
    "range", "repr", "reversed", "round", "set", "setattr", "slice", "sorted",
    "staticmethod", "str", "sum", "super", "tuple", "type", "vars", "zip",
    "__import__",
    "Exception", "BaseException", "ValueError", "TypeError", "KeyError",
    "AttributeError", "IndexError", "RuntimeError", "SyntaxError", "ImportError",
    "ModuleNotFoundError", "StopIteration", "FileNotFoundError", "PermissionError",
    "TimeoutError", "OSError", "AssertionError", "NotImplementedError", "OverflowError",
    "ZeroDivisionError", "UnboundLocalError", "UnicodeDecodeError", "UnicodeEncodeError",
    "True", "False", "None", "Ellipsis", "NotImplemented",
    # Common typing primitives & types
    "Any", "Optional", "Union", "Callable", "Dict", "List", "Tuple", "Set", "Type",
    "Cast", "Literal", "TypeVar", "Generic", "Overload", "Final", "ClassVar", "Self",
    "Sequence", "Mapping", "Iterable", "Iterator", "Generator", "Coroutine", "AsyncGenerator",
    "AsyncIterable", "AsyncIterator", "ContextManager", "AsyncContextManager", "NamedTuple",
    "TypedDict", "Protocol", "runtime_checkable", "type_check_only", "cast", "Pattern", "Match",
    # Common safe stdlib modules and built-in names
    "typing", "collections", "enum", "dataclasses", "itertools", "re", "math",
    "datetime", "asyncio", "sys", "os", "json", "logging", "pathlib", "Path", "uuid", "time",
    "__name__", "__file__", "__doc__", "__all__", "__annotations__",
}


class SymbolScopeVisitor(ast.NodeVisitor):
    """AST NodeVisitor that inspects refactored functions and extracted helper ASTs for loaded names

    (ast.Name in ast.Load context) and function calls (ast.Call), validating them against local definitions,
    Python builtins/primitives, function parameter/local variables, and the HeaderSymbolContract.
    """

    def __init__(self, header_contract: HeaderSymbolContract | None = None, code_str: str = "") -> None:
        self.header_contract = header_contract or HeaderSymbolContract()
        self.code_str = code_str
        self.code_lines = code_str.splitlines() if code_str else []
        self.unimported_symbols: list[dict[str, Any]] = []

        self.allowed_symbols: set[str] = set(STANDARD_BUILTINS_AND_TYPING)
        self.allowed_symbols.update(self.header_contract.imported_symbols)
        self.allowed_symbols.update(self.header_contract.top_level_symbols)
        self.allowed_symbols.update(self.header_contract.global_constants)
        for mod in self.header_contract.imported_modules:
            self.allowed_symbols.add(mod)
            self.allowed_symbols.add(mod.split(".")[0])

        self.scope_stack: list[set[str]] = [set()]
        self._in_annotation: bool = False

    def is_symbol_defined(self, name: str) -> bool:
        if name in self.allowed_symbols:
            return True
        for scope in reversed(self.scope_stack):
            if name in scope:
                return True
        return False

    def _get_line_context(self, lineno: int) -> str:
        if 1 <= lineno <= len(self.code_lines):
            return self.code_lines[lineno - 1].strip()
        return ""

    def _record_violation(self, name: str, lineno: int, category: str = "unimported_symbol") -> None:
        line_context = self._get_line_context(lineno)
        if not any(item["name"] == name and item["line"] == lineno for item in self.unimported_symbols):
            self.unimported_symbols.append({
                "name": name,
                "line": lineno,
                "context": line_context,
                "category": category,
            })

    def collect_top_level_defs(self, tree: ast.AST) -> None:
        """Pre-pass to collect all top-level defined functions, classes, imports, and assignments into root scope."""
        root_scope = self.scope_stack[0]
        if isinstance(tree, ast.Module):
            body_nodes = tree.body
        elif isinstance(tree, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body_nodes = [tree]
        else:
            body_nodes = []

        for node in body_nodes:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                root_scope.add(node.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        root_scope.add(target.id)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    root_scope.add(bound)

    def _collect_function_locals(self, fn_node: ast.FunctionDef | ast.AsyncFunctionDef, scope: set[str]) -> None:
        """Collect all parameters and local assigned variables for a function definition."""
        args_node = fn_node.args
        for arg in args_node.posonlyargs + args_node.args + args_node.kwonlyargs:
            scope.add(arg.arg)
        if args_node.vararg:
            scope.add(args_node.vararg.arg)
        if args_node.kwarg:
            scope.add(args_node.kwarg.arg)

        for node in ast.walk(fn_node):
            if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Param)):
                scope.add(node.id)
            elif isinstance(node, ast.ExceptHandler) and node.name:
                scope.add(node.name)
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound = alias.asname or alias.name.split(".")[0]
                    scope.add(bound)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node is not fn_node:
                scope.add(node.name)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for decorator in node.decorator_list:
            self.visit(decorator)

        args_node = node.args
        for default in args_node.defaults + [d for d in args_node.kw_defaults if d]:
            self.visit(default)

        for arg in args_node.posonlyargs + args_node.args + args_node.kwonlyargs:
            if arg.annotation:
                prev = self._in_annotation
                self._in_annotation = True
                self.visit(arg.annotation)
                self._in_annotation = prev
        if args_node.vararg and args_node.vararg.annotation:
            prev = self._in_annotation
            self._in_annotation = True
            self.visit(args_node.vararg.annotation)
            self._in_annotation = prev
        if args_node.kwarg and args_node.kwarg.annotation:
            prev = self._in_annotation
            self._in_annotation = True
            self.visit(args_node.kwarg.annotation)
            self._in_annotation = prev

        if node.returns:
            prev = self._in_annotation
            self._in_annotation = True
            self.visit(node.returns)
            self._in_annotation = prev

        fn_scope: set[str] = set()
        self._collect_function_locals(node, fn_scope)
        self.scope_stack.append(fn_scope)

        for stmt in node.body:
            self.visit(stmt)

        self.scope_stack.pop()

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        prev = self._in_annotation
        self._in_annotation = True
        self.visit(node.annotation)
        self._in_annotation = prev

        if node.value:
            self.visit(node.value)
        self.visit(node.target)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            name = node.id
            if not self.is_symbol_defined(name):
                lineno = getattr(node, "lineno", 0)
                category = "unimported_type_annotation" if self._in_annotation else "unimported_symbol"
                self._record_violation(name, lineno, category)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name):
            func_name = node.func.id
            if not self.is_symbol_defined(func_name):
                lineno = getattr(node, "lineno", 0)
                self._record_violation(func_name, lineno, "unimported_function_call")
        self.generic_visit(node)

    def inspect(self, tree: ast.AST) -> list[dict[str, Any]]:
        self.unimported_symbols.clear()
        self.scope_stack = [set()]
        self._in_annotation = False
        self.collect_top_level_defs(tree)
        self.visit(tree)
        return self.unimported_symbols


VIOLATION_SUGGESTIONS: dict[str, str] = {
    "cc_exceeds": (
        "Extract into a private helper function. "
        "Use a tuple-of-tuples data table for lookups, a match/case dispatch for routing, "
        "or split into guard clauses with early returns. "
        "Each helper must have CC <= 5."
    ),
    "nesting_exceeds": (
        "Flatten with guard clauses and early returns. "
        "Replace nested if/else with `if not condition: return result` at the top. "
        "Extract inner logic into a helper function."
    ),
    "try_pyramid": (
        "Move orelse statements out of the try block. "
        "Use guard clauses before the try/except. "
        "Extract the try body into a helper function if cleanup is needed."
    ),
    "signature_missing_param": (
        "Add the missing parameter back with its original default value to preserve the caller contract."
    ),
    "signature_extra_param": ("Remove the extra parameter — callers don't expect it."),
    "signature_wrong_default": ("Restore the original default value for this parameter."),
    "cleanup_missing": (
        "Add the required cleanup call before the return statement. "
        "This is a hard contract requirement from upstream callers."
    ),
    "missing_function": (
        "The target function was removed or renamed. Restore it with the original name and signature."
    ),
    "hallucinated_fields": (
        "You invented attributes that do not exist on the original objects. "
        "You MUST use ONLY the attributes present in the original code. "
        "Route logic using dot notation on existing fields only."
    ),
    "argument_swap": (
        "You changed the arguments passed to this function. "
        "You MUST preserve the exact variable arguments for existing function calls."
    ),
    "namespace_collision": (
        "Helper name shadows an existing import, function, class, or global variable. "
        "Pick a unique _-prefixed name for this helper."
    ),
}


def _get_module_context(src_path: str, root_dir: Path) -> str:
    """Extract module-level imports, public constants, and header symbol contract."""
    file_path = root_dir / src_path
    if not file_path.exists():
        return "Module source not found."
    try:
        source = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except Exception:
        return "Could not parse module."

    contract = extract_header_symbol_contract(source)
    contract_text = contract.to_prompt_section()

    lines: list[str] = [contract_text, "", "=== MODULE IMPORTS & CONSTANTS ==="]

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            lines.append(ast.unparse(node))

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(
                    node.value, (ast.Constant, ast.Tuple, ast.List, ast.Dict)
                ):
                    try:
                        lines.append(f"{target.id} = {ast.unparse(node.value)}")
                    except (ValueError, TypeError):
                        pass

    return "\n".join(lines)


def extract_function_signature(fn_node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    args_node = fn_node.args
    posonly = [a.arg for a in args_node.posonlyargs]
    pos_args = [a.arg for a in args_node.args]
    vararg = args_node.vararg.arg if args_node.vararg else None
    kwonly = [a.arg for a in args_node.kwonlyargs]
    kwarg = args_node.kwarg.arg if args_node.kwarg else None
    defaults_count = len(args_node.defaults)
    kw_defaults_count = sum(1 for d in args_node.kw_defaults if d is not None)
    return {
        "posonly": posonly,
        "args": pos_args,
        "vararg": vararg,
        "kwonly": kwonly,
        "kwarg": kwarg,
        "defaults_count": defaults_count,
        "kw_defaults_count": kw_defaults_count,
    }


@_refactor_agent.output_validator
def enforce_return_shape(ctx: RunContext[RefactorDeps], result: RefactoringVerdict) -> RefactoringVerdict:
    if not ctx.deps or not ctx.deps.orig_code:
        return result

    # 1. Helper Function Complexity Cap (Extracted helpers MUST be CC <= 5)
    for helper_code in result.helper_functions:
        try:
            helper_tree = ast.parse(helper_code)
            for node in helper_tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    comp_vis = ComplexityVisitor()
                    comp_vis.visit(node)
                    if comp_vis.complexity > 5:
                        msg = (
                            f"CRITICAL: Extracted helper function `{node.name}` has Cyclomatic Complexity {comp_vis.complexity} (must be <= 5). "
                            f"ALL helper functions MUST have CC <= 5. Break `{node.name}` down into simpler steps."
                        )
                        logger.warning(f"[ModelRetry] Helper CC > 5: {msg}")
                        raise ModelRetry(msg)
        except SyntaxError as e:
            logger.warning(f"[ModelRetry] SyntaxError in helper function code from LLM: {e}")

    # 2. Return Shape Preserving Check (Prevents dict -> BaseModel mutation)
    try:
        orig_tree = ast.parse(ctx.deps.orig_code)
        new_tree = ast.parse(result.refactored_code)

        orig_ret_vis = ReturnVisitor()
        orig_ret_vis.visit(orig_tree)

        new_ret_vis = ReturnVisitor()
        new_ret_vis.visit(new_tree)

        if "dict" in orig_ret_vis.return_types and "call" in new_ret_vis.return_types:
            msg = (
                "CRITICAL: Return type mutation detected. The original function returned a raw dictionary (ast.Dict), "
                "but your refactored code returns a class/model instantiation. Preserve the exact dictionary return structure."
            )
            logger.warning(f"[ModelRetry] Return shape mutation: {msg}")
            raise ModelRetry(msg)
    except SyntaxError as e:
        logger.warning(f"[ModelRetry] SyntaxError in refactored code during return shape check: {e}")

    # 3. Refactored AST Verification & Symbol Scope Check
    full_code = result.refactored_code + (
        "\n\n" + "\n\n".join(result.helper_functions) if result.helper_functions else ""
    )
    header_contract = (
        extract_header_symbol_contract(ctx.deps.full_file_source)
        if ctx.deps.full_file_source
        else extract_header_symbol_contract(ctx.deps.orig_code)
    )

    comp_vis = ComplexityVisitor()
    try:
        orig_tree = ast.parse(ctx.deps.orig_code)
        comp_vis.visit(orig_tree)
        orig_cc = comp_vis.complexity
    except Exception:
        orig_cc = 0

    passed_ast, _, _, ast_msg = verify_refactored_ast(
        code=full_code,
        candidate_name=ctx.deps.func_name,
        orig_code=ctx.deps.orig_code,
        orig_cc=orig_cc,
        baseline_errors=ctx.deps.baseline_errors if hasattr(ctx.deps, "baseline_errors") else set(),
        header_contract=header_contract,
    )
    if not passed_ast:
        allowed_opts = (
            header_contract.imported_symbols
            if (header_contract and header_contract.imported_symbols)
            else (sorted(set(header_contract.top_level_symbols + header_contract.global_constants)) if header_contract else [])
        )
        scope_violations = [
            line for line in ast_msg.splitlines()
            if any(cat in line for cat in ("unimported_symbol", "unimported_type_annotation", "unimported_function_call"))
        ]
        if scope_violations:
            scope_details = "\n".join(scope_violations)
            retry_msg = (
                f"CRITICAL AST SYMBOL SCOPE FAILURE for `{ctx.deps.func_name}` in `{ctx.deps.file_path}` "
                f"(lines {ctx.deps.line}-{ctx.deps.end_line}):\n\n"
                f"SCOPE VIOLATIONS DETECTED:\n{scope_details}\n\n"
                f"AVAILABLE IMPORTED SYMBOLS IN HEADER CONTRACT:\n{allowed_opts}\n\n"
                f"ACTIONABLE FIX INSTRUCTIONS:\n"
                f"1. Remove or replace hallucinated / unimported symbols or type names with standard primitives "
                f"(e.g., dict, list, str, int, float, bool, Any, Optional, Union) or symbols explicitly listed in header contract above.\n"
                f"2. Ensure all function calls inside helper functions or refactored code refer to imported functions or "
                f"extracted helpers starting with `_{ctx.deps.func_name}_` defined in `helper_functions`.\n"
                f"3. Do NOT invent new class models or reference unimported symbols."
            )
        else:
            retry_msg = (
                f"CRITICAL REFACTORING AST VERIFICATION FAILURE for `{ctx.deps.func_name}` in `{ctx.deps.file_path}` "
                f"(lines {ctx.deps.line}-{ctx.deps.end_line}):\n"
                f"{ast_msg}\n"
                f"Available imported symbols in header contract: {allowed_opts}"
            )
        logger.warning(f"[ModelRetry] verify_refactored_ast failed: {ast_msg}")
        raise ModelRetry(retry_msg)

    # 4. Live Compiler Sandbox (extracted to verify_live_compiler_sandbox)
    if ctx.deps.full_file_source and ctx.deps.func_name:
        passed_sandbox, sandbox_msg = verify_live_compiler_sandbox(
            full_file_source=ctx.deps.full_file_source,
            file_path=ctx.deps.file_path,
            func_name=ctx.deps.func_name,
            refactored_code=result.refactored_code,
            helper_functions=result.helper_functions,
            baseline_errors=ctx.deps.baseline_errors if hasattr(ctx.deps, "baseline_errors") else set(),
            orig_code=ctx.deps.orig_code,
        )
        if not passed_sandbox:
            allowed_opts = (
                header_contract.imported_symbols
                if (header_contract and header_contract.imported_symbols)
                else (sorted(set(header_contract.top_level_symbols + header_contract.global_constants)) if header_contract else [])
            )
            retry_msg = (
                f"CRITICAL LIVE COMPILER SANDBOX FAILURE for `{ctx.deps.func_name}` in `{ctx.deps.file_path}` "
                f"(lines {ctx.deps.line}-{ctx.deps.end_line}):\n"
                f"{sandbox_msg}\n"
                f"Available imported symbols in header contract: {allowed_opts}"
            )
            logger.warning(f"[ModelRetry] verify_live_compiler_sandbox failed: {sandbox_msg}")
            raise ModelRetry(retry_msg)

    return result


def verify_live_compiler_sandbox(
    full_file_source: str,
    file_path: str,
    func_name: str,
    refactored_code: str,
    helper_functions: list[str],
    baseline_errors: set[str],
    orig_code: str,
) -> tuple[bool, str]:
    """Run refactored code through VirtualASTBuffer, ruff format, ruff check, and pyright.

    Returns (passed: bool, error_message: str).
    """
    try:
        buf = VirtualASTBuffer(full_file_source, file_path)
        temp_source = buf.replace_function(func_name, refactored_code, helper_functions)
        try:
            temp_source = ensure_pydantic_imports(
                temp_source,
                refactored_code
                + (
                    "\n\n" + "\n\n".join(h.rstrip() for h in helper_functions)
                    if helper_functions
                    else ""
                ),
            )
        except Exception as e:
            msg = f"CRITICAL: AST replacement failed in VirtualASTBuffer: {e}"
            logger.warning(f"[ModelRetry] VirtualASTBuffer Replace Error: {msg}")
            return False, msg
    except Exception as e:
        msg = f"CRITICAL: Refactored code AST replacement failed in VirtualASTBuffer: {e}"
        logger.warning(f"[ModelRetry] VirtualASTBuffer Replace Error: {msg}")
        return False, msg

    scratch_dir = pkg_root / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = scratch_dir / f"temp_pyright_{uuid.uuid4().hex}.py"
    try:
        tmp_path.write_text(temp_source, encoding="utf-8")

        # Stage 0: AUTO-FORMAT
        subprocess.run(
            ["uv", "run", "ruff", "format", str(tmp_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=REQUEST_TIMEOUT,
            cwd=str(pkg_root),
            env={**os.environ, "PYTHONPATH": "."},
        )

        # Stage 1: RUFF (baseline-aware, only fail on NEW errors)
        baseline_ruff_errors = _get_ruff_errors(orig_code) if orig_code else set()
        current_ruff_errors = _get_ruff_errors(temp_source)
        new_ruff_errors = current_ruff_errors - baseline_ruff_errors
        if new_ruff_errors:
            clean_errors = "\n".join(sorted(new_ruff_errors))
            return False, (
                f"CRITICAL: Refactoring introduced new Ruff linter errors:\n{clean_errors}\n"
                f"Fix these errors. If you hallucinated a type hint (F821), change it to `dict`, `list`, or `Any`."
            )

        # Stage 2: Pyright baseline comparison
        if baseline_errors or temp_source:
            current_errors = _get_normalized_pyright_errors(temp_source)
            new_introduced = current_errors - baseline_errors
            if new_introduced:
                return (
                    False,
                    (
                        f"CRITICAL: Refactoring introduced {len(new_introduced)} new pyright error(s): "
                        f"{new_introduced}. Fix the introduced type errors before proceeding."
                    ),
                )

        return True, ""
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


class FunctionCandidateScanner(ast.NodeVisitor):
    CONTROL_NODES = (ast.If, ast.Try, ast.For, ast.While, ast.With)

    def __init__(
        self,
        filename: str,
        code_lines: list[str],
        full_file_source: str = "",
        header_contract: HeaderSymbolContract | None = None,
    ) -> None:
        self.filename = filename
        self.code_lines = code_lines
        self.full_file_source = full_file_source
        self.header_contract = header_contract or extract_header_symbol_contract(full_file_source)
        self.candidates: list[FunctionCandidate] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        comp_vis = ComplexityVisitor()
        comp_vis.visit(node)
        cc = comp_vis.complexity

        max_depth, max_depth_line, try_issues = self._check_body_nesting(node.body, depth=0)

        if len(try_issues) > 0 or max_depth > 3 or cc > 5:
            end_line = getattr(node, "end_lineno", node.lineno)
            func_code = ast.unparse(node)
            line_count = end_line - node.lineno + 1
            requires_decomposition = cc > 50 or line_count > 200

            priority = 3
            if len(try_issues) > 0:
                priority = 1
            elif max_depth > 3:
                priority = 2

            module_ctx = self.header_contract.to_prompt_section()
            self.candidates.append(
                FunctionCandidate(
                    file_path=self.filename,
                    function_name=node.name,
                    line=node.lineno,
                    end_line=end_line,
                    cc=cc,
                    max_depth=max_depth,
                    priority=priority,
                    try_issues=try_issues,
                    source_code=func_code,
                    full_file_source=self.full_file_source,
                    header_contract=self.header_contract,
                    module_context=module_ctx,
                    line_count=line_count,
                    requires_decomposition=requires_decomposition,
                )
            )

        self.generic_visit(node)

    def _check_body_nesting(self, statements: list[ast.stmt], depth: int) -> tuple[int, int, list[tuple[int, str]]]:
        max_d = depth
        max_line = 0
        try_issues = []

        for stmt in statements:
            if isinstance(stmt, self.CONTROL_NODES):
                current_depth = depth + 1
                if current_depth > max_d:
                    max_d = current_depth
                    max_line = stmt.lineno

                if isinstance(stmt, ast.Try):
                    for inner_stmt in stmt.body:
                        if isinstance(inner_stmt, ast.Try):
                            try_issues.append((inner_stmt.lineno, "Nested Try block inside Try body"))

                    for handler in stmt.handlers:
                        for h_stmt in handler.body:
                            if isinstance(h_stmt, ast.Try):
                                try_issues.append((h_stmt.lineno, "Try block inside Except handler"))

                    if stmt.orelse:
                        for el_stmt in stmt.orelse:
                            if isinstance(el_stmt, (ast.If, ast.Try)):
                                try_issues.append(
                                    (el_stmt.lineno, f"{el_stmt.__class__.__name__} inside Try-Else block")
                                )

                sub_bodies = []
                if isinstance(stmt, ast.If):
                    sub_bodies.append((stmt.body, current_depth))
                    if len(stmt.orelse) == 1 and isinstance(stmt.orelse[0], ast.If):
                        sub_bodies.append((stmt.orelse, depth))
                    else:
                        sub_bodies.append((stmt.orelse, current_depth))
                elif isinstance(stmt, ast.Try):
                    sub_bodies.append((stmt.body, current_depth))
                    for h in stmt.handlers:
                        sub_bodies.append((h.body, current_depth))
                    sub_bodies.append((stmt.orelse, current_depth))
                    sub_bodies.append((stmt.finalbody, current_depth))
                elif isinstance(stmt, (ast.For, ast.While)):
                    sub_bodies.append((stmt.body, current_depth))
                    sub_bodies.append((stmt.orelse, current_depth))
                elif isinstance(stmt, ast.With):
                    sub_bodies.append((stmt.body, current_depth))

                for sb, sb_depth in sub_bodies:
                    if sb:
                        d, line_no, ti = self._check_body_nesting(sb, sb_depth)
                        try_issues.extend(ti)
                        if d > max_d:
                            max_d = d
                            max_line = line_no

        return max_d, max_line, try_issues


def pre_decompose(candidate: FunctionCandidate) -> DecompositionPlan:
    """Deterministically decompose an extremely complex function into logical phases.

    Uses AST analysis to identify top-level control structures (for/while/if blocks)
    and independent statement groups that can be extracted as separate helper functions.

    Returns a DecompositionPlan where:
    - helper_functions contains extracted block source code (to be refactored as separate candidates)
    - main_refactored_code is a placeholder indicating the main function needs reassembly
    - residual_cc is an estimate of the main function's CC after extraction
    """
    source = candidate.source_code
    func_name = candidate.function_name
    plan = DecompositionPlan(
        phase_number=1,
        main_function_name=func_name,
        original_cc=candidate.cc,
    )

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return plan

    func_node = None
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
            func_node = node
            break

    if func_node is None or not func_node.body:
        return plan

    total_cc = candidate.cc
    helper_idx = 0

    for stmt in func_node.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        stmt_cc = _estimate_ast_cc([stmt])
        stmt_lines = getattr(stmt, "end_lineno", stmt.lineno) - stmt.lineno + 1

        if stmt_cc > 3 and stmt_lines >= 3 and total_cc > 15:
            helper_idx += 1
            block_source = ast.unparse(stmt)
            plan.helper_functions.append(block_source)
            plan.helper_candidates.append(
                FunctionCandidate(
                    file_path=candidate.file_path,
                    function_name=f"{func_name}_extracted_{helper_idx}",
                    line=candidate.line,
                    end_line=candidate.end_line,
                    cc=stmt_cc,
                    max_depth=0,
                    priority=3,
                    try_issues=[],
                    source_code=block_source,
                    full_file_source=candidate.full_file_source,
                    header_contract=candidate.header_contract,
                    module_context=candidate.module_context,
                    phase=2,
                    parent_function=func_name,
                    line_count=stmt_lines,
                    requires_decomposition=stmt_cc > 5,
                )
            )
            total_cc = max(1, total_cc - stmt_cc)

    plan.residual_cc = total_cc
    return plan


def _estimate_ast_cc(stmts: list[ast.stmt]) -> int:
    """Estimate CC for a list of AST nodes."""
    cc = 1
    for node in ast.walk(ast.Module(body=stmts)):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.With, ast.Try)):
            cc += 1
        elif isinstance(node, ast.BoolOp):
            cc += len(node.values) - 1
    return cc


def load_prompt_template(path: Path | None = None) -> dict:
    template_path = path or PROMPT_TEMPLATE_PATH
    if not template_path.exists():
        logger.warning(f"Prompt template not found at {template_path}")
        return {}
    with open(template_path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_target_files() -> set[str] | None:
    if not LIST_FILE.exists():
        return None
    with open(LIST_FILE, encoding="utf-8") as f:
        paths = {
            line.strip().lstrip("/") for line in f if line.strip() and not line.startswith("#")
        }
    logger.info(f"Loaded {len(paths)} targeted files from kill_tries_list.txt")
    return paths


def _render_narrative(
    template: dict,
    candidate: FunctionCandidate,
    attempt_num: int,
    what_worked_text: str = "",
    violations_text: str = "",
) -> str:
    attempts_left = str(max(1, MAX_RETRIES - attempt_num + 1))
    header_contract = candidate.header_contract or extract_header_symbol_contract(candidate.full_file_source)
    contract_section = header_contract.to_prompt_section()
    module_context = candidate.module_context or contract_section

    imported_modules_text = ", ".join(sorted(set(header_contract.imported_modules))) if header_contract.imported_modules else "None"
    imported_symbols_text = ", ".join(sorted(set(header_contract.imported_symbols))) if header_contract.imported_symbols else "None"
    top_level_symbols_text = ", ".join(sorted(set(header_contract.top_level_symbols))) if header_contract.top_level_symbols else "None"
    global_constants_text = ", ".join(sorted(set(header_contract.global_constants))) if header_contract.global_constants else "None"

    system_prompt = fill_template(
        template.get("system_prompt", ""),
        file_path=candidate.file_path,
        function_name=candidate.function_name,
        narrative_context="",
        anti_patterns="",
        samples="",
        attempts_left=attempts_left,
        upstream_callers=candidate.upstream_callers,
        module_context=module_context,
        imported_modules_text=imported_modules_text,
        imported_symbols_text=imported_symbols_text,
        top_level_symbols_text=top_level_symbols_text,
        global_constants_text=global_constants_text,
        header_symbol_contract=contract_section,
    )
    system = fill_template(
        template.get("system_instruction", ""),
        file_path=candidate.file_path,
        function_name=candidate.function_name,
        narrative_context="",
        anti_patterns="",
        samples="",
        attempts_left=attempts_left,
        upstream_callers=candidate.upstream_callers,
        module_context=module_context,
        imported_modules_text=imported_modules_text,
        imported_symbols_text=imported_symbols_text,
        top_level_symbols_text=top_level_symbols_text,
        global_constants_text=global_constants_text,
        header_symbol_contract=contract_section,
    )
    anti_patterns = fill_template(
        template.get("anti_patterns", ""),
        anti_patterns_list="",
        file_path=candidate.file_path,
        function_name=candidate.function_name,
    )
    conditions = fill_template(
        template.get("conditions", template.get("rules", "")),
        file_path=candidate.file_path,
        function_name=candidate.function_name,
    )
    full_source = candidate.full_file_source or ""
    is_helper = candidate.phase >= 2 and candidate.parent_function

    return (
        f"{system_prompt}\n\n"
        f"=== HEADER SYMBOL CONTRACT ===\n"
        f"{contract_section}\n\n"
        f"{system}\n\n"
        + (
            f"=== FULL FILE CONTEXT ===\n"
            f"File: {candidate.file_path}\n"
            f"```python\n{full_source}\n```\n\n"
            f"Above is the complete file content. The function `{candidate.function_name}` is at "
            f"line {candidate.line}. Do NOT invent new imports or helper functions — use ONLY "
            f"symbols that already exist in this file or stdlib.\n\n"
            if not is_helper
            else ""
        )
        + f"=== WHAT WENT WRONG ===\n{anti_patterns}\n\n"
        f"=== RULES ===\n{conditions}\n\n"
        f"TARGET: Refactor {candidate.function_name} ({candidate.file_path}:{candidate.line}) to pass all checks.\n"
        f"CC={candidate.cc} | Depth={candidate.max_depth} | Priority={candidate.priority}\n\n"
        f"<source_code>\n{candidate.source_code}\n</source_code>\n"
    )


def format_prompt(
    template: dict,
    candidate: FunctionCandidate,
    attempt: int = 1,
    history: list | None = None,
    what_worked_text: str = "",
    violations_text: str = "",
) -> str:
    if not history:
        return _render_narrative(template, candidate, attempt, what_worked_text, violations_text)

    active_template = load_prompt_template(PROMPT_RETRY_PATH) if PROMPT_RETRY_PATH.exists() else template

    function_name = candidate.function_name
    file_path = candidate.file_path
    attempts_left = MAX_RETRIES - attempt + 1
    source_code = candidate.source_code
    full_source = candidate.full_file_source or ""
    is_helper = candidate.phase >= 2 and candidate.parent_function

    header_contract = candidate.header_contract or extract_header_symbol_contract(full_source)
    contract_section = header_contract.to_prompt_section()
    module_context = candidate.module_context or contract_section

    imported_modules_text = ", ".join(sorted(set(header_contract.imported_modules))) if header_contract.imported_modules else "None"
    imported_symbols_text = ", ".join(sorted(set(header_contract.imported_symbols))) if header_contract.imported_symbols else "None"
    top_level_symbols_text = ", ".join(sorted(set(header_contract.top_level_symbols))) if header_contract.top_level_symbols else "None"
    global_constants_text = ", ".join(sorted(set(header_contract.global_constants))) if header_contract.global_constants else "None"

    system_prompt = fill_template(
        active_template.get("system_prompt", ""),
        attempt=str(attempt),
        function_name=function_name,
        file_path=file_path,
        line=str(candidate.line),
        violations=violations_text,
        what_worked=what_worked_text,
        what_to_fix=violations_text,
        upstream_callers=candidate.upstream_callers,
        module_context=module_context,
        imported_modules_text=imported_modules_text,
        imported_symbols_text=imported_symbols_text,
        top_level_symbols_text=top_level_symbols_text,
        global_constants_text=global_constants_text,
        header_symbol_contract=contract_section,
    )
    sys_prefix = f"{system_prompt}\n\n" if system_prompt and system_prompt.strip() else ""

    anti_patterns = fill_template(
        active_template.get("anti_patterns", ""),
        anti_patterns_list=violations_text,
        file_path=file_path,
        function_name=function_name,
    )
    conditions = fill_template(
        active_template.get("conditions", active_template.get("rules", "")),
        file_path=file_path,
        function_name=function_name,
    )

    return (
        f"{sys_prefix}"
        f"=== HEADER SYMBOL CONTRACT ===\n"
        f"{contract_section}\n\n"
        f"=== ATTEMPT {attempt}/{MAX_RETRIES} (CONCISE DELTA) ===\n\n"
        + (
            f"Full file: {file_path}\n"
            f"```python\n{full_source}\n```\n\n"
            if not is_helper
            else ""
        )
        + f"Previous attempt feedback for {function_name} ({file_path}):\n\n"
        f"ISSUES TO FIX:\n{violations_text}\n\n"
        f"WHAT WORKED (preserve these):\n{what_worked_text}\n\n"
        f"=== ANTI-PATTERNS ===\n{anti_patterns}\n\n"
        f"=== RULES ===\n{conditions}\n\n"
        f"YOU HAVE {attempts_left} ATTEMPT(S) LEFT.\n"
        f"Take your previous attempt and surgically fix only the violations above.\n"
        f"CRITICAL: If you extract helper functions, prefix each with `_{function_name}_`.\n"
        f"CRITICAL: You may ONLY use symbols already defined in the file above. Do NOT invent new imports.\n\n"
        f"<source_code>\n{source_code}\n</source_code>\n"
    )


# =====================================================================
# AST VERIFICATION
# =====================================================================


@logfire.instrument("verify_refactored_ast")
def verify_refactored_ast(
    code: str,
    candidate_name: str = "",
    contract_info: dict | None = None,
    orig_code: str = "",
    orig_cc: int = 0,
    baseline_errors: set[str] | None = None,
    header_contract: HeaderSymbolContract | None = None,
) -> tuple[bool, int, int, str]:
    """Compile and verify that the refactored code passes all AST safety checks.

    Performs 5 sandbox layers:
    1. Syntax check
    2. CC/nesting/try-pyramid checks
    3. Attribute sandbox - detects hallucinated fields
    4. Call sandbox - detects swapped arguments
    5. Signature parity - ensures parameter contract is preserved
    6. Namespace collision - helpers don't shadow existing imports/functions
    """
    violations: list[str] = []
    candidate_cc = 0
    candidate_max_depth = 0

    target_cc = 5

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, 999, 999, f"SyntaxError in refactored code: {e}"

    # 1. Ban unauthorized imports
    safe_modules = {"typing", "collections", "enum", "dataclasses", "itertools", "re"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            violations.append(
                f"unauthorized_symbol: Created a new class `{node.name}` | "
                f"Suggestion: Do not define new classes. Use flat tuples or dicts for data tables."
            )
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            module_name = getattr(node, "module", None)
            if not module_name and isinstance(node, ast.Import):
                module_name = node.names[0].name.split(".")[0]
            if module_name and module_name not in safe_modules and not module_name.startswith("src2"):
                violations.append(
                    f"unauthorized_import: Added an import for `{module_name}` | "
                    f"Suggestion: You may ONLY import from {safe_modules} or internal `src2` modules."
                )

    # 2. Namespace sandbox: harvest original file namespace
    orig_namespace: set[str] = set()
    if orig_code:
        try:
            orig_tree = ast.parse(orig_code)
            for top_node in orig_tree.body:
                if isinstance(top_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    orig_namespace.add(top_node.name)
                elif isinstance(top_node, ast.Assign):
                    for target in top_node.targets:
                        if isinstance(target, ast.Name):
                            orig_namespace.add(target.id)
                elif isinstance(top_node, ast.Import):
                    for alias in top_node.names:
                        orig_namespace.add(alias.asname or alias.name)
                elif isinstance(top_node, ast.ImportFrom):
                    for alias in top_node.names:
                        orig_namespace.add(alias.asname or alias.name)
        except SyntaxError as e:
            logger.warning(f"[verify_refactored_ast] SyntaxError parsing original code for namespace harvest: {e}")

    # 3. Helper naming and namespace collision check
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name != candidate_name:
                if not node.name.startswith("_"):
                    violations.append(
                        f"invalid_helper_name: Helper `{node.name}` must start with an underscore. "
                        f"Suggestion: Rename to _{node.name} or pick a unique _-prefixed name."
                    )
                elif node.name in orig_namespace:
                    violations.append(
                        f"namespace_collision: Helper `{node.name}` shadows an existing import, "
                        f"function, class, or global variable in this file. "
                        f"Suggestion: Pick a unique _-prefixed name for this helper."
                    )

    # 4. Attribute sandbox: detect hallucinated fields
    if orig_code:
        try:
            orig_tree = ast.parse(orig_code)
            orig_attrs = AttributeVisitor()
            orig_attrs.visit(orig_tree)

            new_attrs = AttributeVisitor()
            new_attrs.visit(tree)

            whitelist: set[str] = {
                "get",
                "append",
                "model_dump",
                "model_copy",
                "items",
                "keys",
                "values",
                "add",
                "update",
                "split",
                "strip",
                "replace",
                "join",
                "format",
                "startswith",
                "endswith",
                "lower",
                "upper",
                "info",
                "error",
                "warning",
                "exception",
                "debug",
                "exists",
                "resolve",
                "parent",
                "name",
                "isoformat",
                "now",
                "today",
                "group",
                "match",
                "search",
                "encode",
                "decode",
                "find",
                "rfind",
                "partition",
                "rpartition",
                "splitlines",
                "capitalize",
                "title",
                "swapcase",
                "isdigit",
                "isalpha",
                "isalnum",
                "isspace",
                "count",
                "index",
                "remove",
                "pop",
                "insert",
                "extend",
                "clear",
                "update",
                "setdefault",
                "get",
                "copy",
                "items",
                "keys",
                "values",
                "query",
                "fetchone",
                "fetchall",
                "execute",
                "executemany",
                "fetchmany",
                "close",
                "connect",
                "cursor",
                "commit",
                "rollback",
                "begin",
                "savepoint",
                "execute_script",
                "description",
                "connection",
                "rowcount",
                "lastrowid",
                # Domain & Pydantic-AI whitelist
                "parts",
                "role",
                "content",
                "output",
                "data",
                "events",
                "structure",
                "gender",
                "alias",
                "day_pillar",
                "month_pillar",
                "year_pillar",
                "hour_pillar",
                "date",
                "days",
                "strftime",
                "isoformat",
                "value",
                "result",
                "message_history",
                "profile",
                "session",
                "conversation_history",
                "target_dates",
                "intent",
                "sentiment",
                "mental_model",
                "user_state",
                "rag_context",
                "structural_map",
                "shen_sha_context",
                "day_scores",
                "monthly_context",
                "score_legend",
                "language",
                "parse_mode",
                "text",
                "step",
                "metadata",
                "ModelRequest",
                "ModelResponse",
                "TextPart",
                "UserPromptPart",
            }
            hallucinated = (new_attrs.attributes - orig_attrs.attributes) - whitelist
            if hallucinated:
                violations.append(
                    f"hallucinated_fields: You invented attributes that do not exist on the original objects: {hallucinated} | "
                    f"Suggestion: {VIOLATION_SUGGESTIONS['hallucinated_fields']}"
                )
        except Exception:
            pass

    # 5. Call signature sandbox: detect argument swaps
    if orig_code:
        try:
            builtin_methods = {
                "isinstance", "getattr", "hasattr", "setattr", "len", "str", "int", "float", "bool",
                "list", "dict", "set", "tuple", "any", "all", "print", "type", "range", "enumerate",
                "zip", "min", "max", "sum", "sorted", "reversed", "super", "get", "append", "extend",
                "gather", "add", "update", "model_validate", "model_dump", "parse_mode", "format",
                "encode", "decode", "split", "strip", "join", "replace", "startswith", "endswith",
                "lower", "upper", "create_task", "add_done_callback", "discard", "getLogger",
                "from_url", "aclose", "model_validate_json", "strftime", "isoformat", "run",
            }
            orig_tree = ast.parse(orig_code)
            orig_call_vis = CallVisitor()
            orig_call_vis.visit(orig_tree)

            new_call_vis = CallVisitor()
            new_call_vis.visit(tree)

            orig_func_names = {call[0] for call in orig_call_vis.calls if call[0] not in builtin_methods}

            for new_call in new_call_vis.calls:
                func_name, new_args = new_call
                if func_name in orig_func_names and new_call not in orig_call_vis.calls:
                    # Relax false-positive argument swap checking on domain calls using keyword args
                    if func_name in new_call_vis.calls_with_keywords or func_name in orig_call_vis.calls_with_keywords:
                        continue
                    violations.append(
                        f"argument_swap: You changed the arguments passed to `{func_name}`. "
                        f"You passed {new_args}. | "
                        f"Suggestion: {VIOLATION_SUGGESTIONS['argument_swap']}"
                    )
        except Exception:
            pass

    # 6. Signature parity check
    if orig_code and candidate_name:
        try:
            orig_tree = ast.parse(orig_code)
            orig_main_node = next(
                (
                    n
                    for n in orig_tree.body
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == candidate_name
                ),
                None,
            )
            if not orig_main_node:
                orig_main_node = next(
                    (
                        n
                        for n in ast.walk(orig_tree)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == candidate_name
                    ),
                    None,
                )

            if orig_main_node:
                orig_sig = extract_function_signature(orig_main_node)
                ref_main_node = next(
                    (
                        n
                        for n in ast.walk(tree)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == candidate_name
                    ),
                    None,
                )
                if not ref_main_node:
                    violations.append(
                        f"missing_function: The main target function `{candidate_name}` is missing or renamed in refactored code | "
                        f"Suggestion: {VIOLATION_SUGGESTIONS['missing_function']}"
                    )
                else:
                    ref_sig = extract_function_signature(ref_main_node)
                    if orig_sig != ref_sig:
                        diffs = [k for k, v in orig_sig.items() if ref_sig.get(k) != v]
                        for diff in diffs:
                            param_violation = f"signature_{diff}"
                            suggestion = VIOLATION_SUGGESTIONS.get(
                                param_violation, "Restore the original signature for this parameter."
                            )
                            violations.append(f"signature_mismatch:{candidate_name}:{diff} | Suggestion: {suggestion}")
        except Exception:
            pass

    # 7. Contract preservation: cleanup calls from upstream callers
    if contract_info:
        for required in contract_info.get("exceptions_and_cleanup", []):
            if required.startswith("cleanup:"):
                method = required.split(":", 1)[1]
                if method not in code:
                    violations.append(
                        f"cleanup_missing:{method} | Suggestion: {VIOLATION_SUGGESTIONS['cleanup_missing']}"
                    )

    # Section 6: Symbol Scope Check using SymbolScopeVisitor
    resolved_contract = header_contract or (
        extract_header_symbol_contract(orig_code) if orig_code else HeaderSymbolContract()
    )
    scope_visitor = SymbolScopeVisitor(resolved_contract, code)
    unimported_list = scope_visitor.inspect(tree)
    if unimported_list:
        allowed = (
            resolved_contract.imported_symbols
            if resolved_contract and resolved_contract.imported_symbols
            else (
                sorted(set(resolved_contract.top_level_symbols + resolved_contract.global_constants))
                if resolved_contract
                else []
            )
        )
        for item in unimported_list:
            name = item["name"]
            line_no = item.get("line", 0)
            ctx_line = item.get("context", "")
            category = item.get("category", "unimported_symbol")
            cat_label = category if category == "unimported_symbol" else f"unimported_symbol: {category}"
            ctx_str = f" line {line_no} (`{ctx_line}`)" if ctx_line else (f" line {line_no}" if line_no else "")
            violations.append(
                f"{cat_label}: Referenced symbol '{name}' at{ctx_str} which is not imported or defined in header contract. "
                f"Available imported symbols: {allowed} | Suggestion: Use standard primitives (dict, list, str, int, float, bool, Any, Optional) or imported models."
            )

    # 9. CC and nesting checks
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            comp_vis = ComplexityVisitor()
            comp_vis.visit(node)
            func_cc = comp_vis.complexity

            scanner = FunctionCandidateScanner("test.py", code.splitlines())
            func_depth, _, try_issues = scanner._check_body_nesting(node.body, depth=0)

            if node.name == candidate_name:
                candidate_cc = func_cc
                candidate_max_depth = func_depth

            if len(try_issues) > 0:
                violations.append(f"try_pyramid:{try_issues} | Suggestion: {VIOLATION_SUGGESTIONS['try_pyramid']}")
            node_target_cc = target_cc
            if func_cc > node_target_cc:
                violations.append(
                    f"cc_exceeds:{node.name} has CC={func_cc} (target <={node_target_cc}, original was {orig_cc}) | "
                    f"Suggestion: {VIOLATION_SUGGESTIONS['cc_exceeds']}"
                )
            if func_depth > 3:
                violations.append(
                    f"nesting_exceeds:{node.name} depth={func_depth} (must be <=3) | "
                    f"Suggestion: {VIOLATION_SUGGESTIONS['nesting_exceeds']}"
                )

    if violations:
        return (
            False,
            candidate_cc,
            candidate_max_depth,
            "VIOLATIONS FOUND:\n" + "\n".join(f"  - {v}" for v in violations),
        )

    return (
        True,
        candidate_cc,
        candidate_max_depth,
        "Passed Flat Control Flow, semantic attribute sandbox, argument sandbox, signature parity, namespace sandbox, and pyright regression checks — all clean.",
    )


# =====================================================================
# REFACTORING ENGINE
# =====================================================================


async def refactor_single_attempt_with_llm(
    candidate: FunctionCandidate,
    attempt: int,
    history: list,
    prompt: str,
    template: dict,
    cand_idx: int = 0,
    total_cand: int = 0,
) -> tuple[bool, list, str, RefactorResult | None]:
    req_id = str(uuid.uuid4())[:8]
    _provider = get_model_provider_name(CONTROL_SHEET.scanner_model)
    start_t = time.time()

    logger.info(
        f"🔵 [{get_timestamp()}] [{cand_idx}/{total_cand}][REQ {req_id}] provider={_provider} candidate={candidate.function_name} ({candidate.file_path}:{candidate.line}) attempt={attempt}/{MAX_RETRIES}",
    )

    try:
        full_source = ""
        target_path = pkg_root / candidate.file_path
        if target_path.exists():
            full_source = target_path.read_text(encoding="utf-8")

        is_helper = candidate.phase >= 2 and candidate.parent_function
        if is_helper:
            full_source = ""

        baseline_errors = get_file_baseline_errors(candidate.file_path, pkg_root) if full_source else set()

        deps_obj = RefactorDeps(
            orig_code=candidate.source_code,
            full_file_source=full_source,
            file_path=candidate.file_path,
            line=candidate.line,
            end_line=candidate.end_line,
            func_name=candidate.function_name,
            baseline_errors=baseline_errors,
            header_contract=candidate.header_contract or extract_header_symbol_contract(full_source),
        )

        result = await _refactor_agent.run(prompt, message_history=history, deps=deps_obj)
        elapsed = round(time.time() - start_t, 2)
        history = result.all_messages()
        verdict: RefactoringVerdict = result.output

        full_code = verdict.refactored_code + (
            "\n\n" + "\n\n".join(verdict.helper_functions) if verdict.helper_functions else ""
        )
        passed, new_cc, new_depth, msg = verify_refactored_ast(
            full_code,
            candidate.function_name,
            orig_code=candidate.source_code,
            orig_cc=candidate.cc,
            baseline_errors=baseline_errors,
            header_contract=deps_obj.header_contract,
        )

        if passed:
            logger.info(
                f"✅ [{get_timestamp()}] [PASSED {req_id}] {candidate.function_name} PASSED on attempt {attempt}/{MAX_RETRIES}! (Duration: {elapsed}s)",
            )
            res = RefactorResult(
                file_path=candidate.file_path,
                function_name=candidate.function_name,
                line=candidate.line,
                status="APPROVED",
                attempts=attempt,
                original_cc=candidate.cc,
                refactored_cc=new_cc,
                original_depth=candidate.max_depth,
                refactored_depth=new_depth,
                refactored_code=verdict.refactored_code,
                helper_functions=verdict.helper_functions,
                explanation=verdict.explanation,
                verification_msg=msg,
                reasoning_and_plan=getattr(verdict, "reasoning_and_plan", ""),
            )
            return True, history, prompt, res

        logger.warning(f"  ⚠️ [Attempt {attempt}/{MAX_RETRIES} Retry] {candidate.function_name} failed AST check: {msg}")

        # Check if failure is a runtime Pytest error (FAILED_RUNTIME)
        is_runtime_error = "FAILED_RUNTIME" in msg or "Pytest integration" in msg
        if is_runtime_error and attempt >= MAX_RETRIES:
            res = RefactorResult(
                file_path=candidate.file_path,
                function_name=candidate.function_name,
                line=candidate.line,
                status="FAILED_RUNTIME",
                attempts=attempt,
                original_cc=candidate.cc,
                refactored_cc=new_cc,
                original_depth=candidate.max_depth,
                refactored_depth=new_depth,
                refactored_code=candidate.source_code,
                helper_functions=[],
                explanation=f"Pytest runtime failure after {attempt} attempts: {msg}",
                verification_msg=msg,
            )
            return False, history, prompt, res

        # Pytest runtime failure re-injection: inject error into message history
        if is_runtime_error:
            pytest_err = msg
            history = history + [
                ModelRequest(
                    parts=[
                        UserPromptPart(
                            content=(
                                f"RUNTIME LOGIC DRIFT: Your refactoring passed syntax checks but FAILED the Pytest integration suite:\n"
                                f"```\n{pytest_err}\n```\n"
                                f"You MUST fix the logic drift (e.g., check iteration order, rounding, < vs <=, variable scoping)."
                            )
                        )
                    ]
                )
            ]

        retry_prompt = format_prompt(template, candidate, attempt + 1, history, violations_text=msg)

        if attempt >= MAX_RETRIES:
            res = RefactorResult(
                file_path=candidate.file_path,
                function_name=candidate.function_name,
                line=candidate.line,
                status="FAILED_VERIFICATION",
                attempts=attempt,
                original_cc=candidate.cc,
                refactored_cc=new_cc,
                original_depth=candidate.max_depth,
                refactored_depth=new_depth,
                refactored_code=candidate.source_code,
                helper_functions=[],
                explanation=f"Failed after {MAX_RETRIES} attempts: {msg}",
                verification_msg=msg,
            )
            return False, history, retry_prompt, res

        return False, history, retry_prompt, None

    except Exception as e:
        logger.error(f"Pydantic-AI attempt {attempt} failed for {candidate.function_name}: {e}")
        err_str = str(e).lower()
        is_fatal = any(
            term in err_str
            for term in [
                "token limit",
                "context length",
                "max_tokens",
                "rate limit",
                "token_limit",
                "resource_exhausted",
            ]
        )
        if is_fatal or attempt >= MAX_RETRIES:
            res = RefactorResult(
                file_path=candidate.file_path,
                function_name=candidate.function_name,
                line=candidate.line,
                status="LLM_ERROR",
                attempts=attempt,
                original_cc=candidate.cc,
                refactored_cc=candidate.cc,
                original_depth=candidate.max_depth,
                refactored_depth=candidate.max_depth,
                refactored_code=candidate.source_code,
                helper_functions=[],
                explanation=f"LLM error: {e}",
                verification_msg=str(e),
            )
            return False, history, prompt, res

        retry_prompt = format_prompt(template, candidate, attempt + 1, history, violations_text=str(e))
        return False, history, retry_prompt, None


# =====================================================================
# MAIN PIPELINE
# =====================================================================


def scan_all_candidates(target_files: set[str] | None = None) -> list[FunctionCandidate]:
    logger.info("Scanning AST for Flat Control Flow candidates...")
    candidates: list[FunctionCandidate] = []
    root_resolved = pkg_root.resolve()

    if target_files:
        files_to_scan = []
        for tf in sorted(target_files):
            p = (pkg_root / tf).resolve()
            if p.is_file():
                files_to_scan.append(p)
            elif p.is_dir():
                files_to_scan.extend(sorted(p.rglob("*.py")))
    else:
        files_to_scan = sorted(SRC2_DIR.rglob("*.py"))

    for py_file in files_to_scan:
        if py_file.is_file():
            try:
                rel_path = str(py_file.resolve().relative_to(root_resolved))
            except ValueError:
                rel_path = str(py_file)
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))
                scanner = FunctionCandidateScanner(rel_path, content.splitlines(), content)
                scanner.visit(tree)
                candidates.extend(scanner.candidates)
            except Exception as e:
                logger.warning(f"Skipped {py_file.name}: {e}")

    logger.info(f"✅ Found {len(candidates)} candidates violating Flat Control Flow standards.")
    return candidates


def save_checkpoint_item(res: RefactorResult | dict) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(res, RefactorResult):
        line = res.model_dump_json()
    else:
        line = json.dumps(res)
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_candidate_complete(item: dict | RefactorResult) -> bool:
    """Check if a candidate result is fully complete (APPROVED with refactored_cc <= 5 and refactored_depth <= 3)."""
    if isinstance(item, RefactorResult):
        return item.status == "APPROVED" and item.refactored_cc <= 5 and item.refactored_depth <= 3
    if isinstance(item, dict):
        status = item.get("status")
        cc = item.get("refactored_cc")
        depth = item.get("refactored_depth")
        if status != "APPROVED" or cc is None or depth is None:
            return False
        try:
            return int(cc) <= 5 and int(depth) <= 3
        except (ValueError, TypeError):
            return False
    return False


def load_checkpoint() -> dict[str, dict]:
    """Load previously completed results from JSONL checkpoint file."""
    completed: dict[str, dict] = {}
    if CHECKPOINT_FILE.exists():
        try:
            with open(CHECKPOINT_FILE, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        item = json.loads(line)
                        key = f"{item.get('file_path', '')}:{item.get('function_name', '')}"
                        if is_candidate_complete(item):
                            completed[key] = item
                        elif key in completed:
                            completed.pop(key, None)
            logger.info(f"Loaded {len(completed)} prior results from checkpoint ({CHECKPOINT_FILE.name}).")
        except Exception as e:
            logger.warning(f"Failed loading checkpoint: {e}")
    return completed


async def main_async(do_refactor: bool, priorities: list[int], limit: int, resume: bool) -> None:
    target_files = load_target_files()
    candidates = scan_all_candidates(target_files=target_files)
    targets = [c for c in candidates if c.priority in priorities]

    if limit > 0:
        targets = targets[:limit]

    print(f"\n✨ Scanned {len(candidates)} total candidates. Processing {len(targets)} matching candidates...")

    template = load_prompt_template()
    queue: asyncio.Queue = asyncio.Queue()

    checkpoint_map = load_checkpoint() if resume else {}

    need_llm: list[FunctionCandidate] = []

    for c in targets:
        key = f"{c.file_path}:{c.function_name}"
        if (
            resume
            and key in checkpoint_map
            and is_candidate_complete(checkpoint_map[key])
        ):
            continue
        need_llm.append(c)

    print(f"✨ {len(need_llm)} functions require LLM refactoring.", flush=True)

    decomposed_targets: list[FunctionCandidate] = []
    for c in need_llm:
        if c.requires_decomposition:
            logger.info(
                f"🔀 Pre-decomposing {c.function_name} ({c.file_path}:{c.line}) "
                f"CC={c.cc} lines={c.line_count} into phases"
            )
            plan = pre_decompose(c)
            if plan.helper_functions:
                main_candidate = FunctionCandidate(
                    file_path=c.file_path,
                    function_name=c.function_name,
                    line=c.line,
                    end_line=c.end_line,
                    cc=max(1, plan.residual_cc),
                    max_depth=c.max_depth,
                    priority=c.priority,
                    try_issues=c.try_issues,
                    source_code=c.source_code,
                    full_file_source=c.full_file_source,
                    header_contract=c.header_contract,
                    module_context=c.module_context,
                    phase=1,
                    parent_function="",
                    line_count=c.line_count,
                    requires_decomposition=False,
                )
                decomposed_targets.append(main_candidate)
                for hc in plan.helper_candidates:
                    decomposed_targets.append(hc)
                logger.info(
                    f"🔀 Decomposition produced {len(plan.helper_candidates)} helpers "
                    f"for {c.function_name} (CC {c.cc} → {plan.residual_cc})"
                )
            else:
                decomposed_targets.append(c)
        else:
            decomposed_targets.append(c)

    need_llm = decomposed_targets

    if not need_llm:
        print(
            f"\n✨ All {len(targets)} candidates passed or were previously approved. Nothing to refactor.", flush=True
        )
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        all_results = [r for r in checkpoint_map.values() if isinstance(r, dict)]
        summary_data = {
            "total_scanned_candidates": len(candidates),
            "refactored_count": len([r for r in all_results if is_candidate_complete(r)]),
            "approved": [r for r in all_results if is_candidate_complete(r)],
            "failed": [r for r in all_results if not is_candidate_complete(r)],
        }
        REPORT_FILE.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
        logger.info(f"Report saved to {REPORT_FILE}")
        return

    for idx, c in enumerate(need_llm, start=1):
        prompt = format_prompt(template, c, attempt=1)
        await queue.put(
            {"candidate": c, "index": idx, "total": len(need_llm), "attempt": 1, "history": [], "prompt": prompt}
        )

    semaphore = asyncio.Semaphore(3)
    results: list[RefactorResult] = []

    async def worker() -> None:
        while True:
            try:
                item = await queue.get()
            except asyncio.CancelledError:
                break
            cand: FunctionCandidate = item["candidate"]
            async with semaphore:
                passed, new_hist, next_prmpt, res = await refactor_single_attempt_with_llm(
                    cand, item["attempt"], item["history"], item["prompt"], template, item["index"], item["total"]
                )
            if res is not None:
                save_checkpoint_item(res)
                results.append(res)
                key = f"{res.file_path}:{res.function_name}"
                checkpoint_map[key] = res.model_dump() if isinstance(res, RefactorResult) else res
            else:
                await queue.put(
                    {
                        "candidate": cand,
                        "index": item["index"],
                        "total": item["total"],
                        "attempt": item["attempt"] + 1,
                        "history": new_hist,
                        "prompt": next_prmpt,
                    }
                )
            queue.task_done()

    workers = [asyncio.create_task(worker()) for _ in range(3)]
    await queue.join()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "total_scanned_candidates": len(candidates),
        "refactored_count": len([r for r in results if is_candidate_complete(r)]),
        "approved": [r.model_dump() for r in results if is_candidate_complete(r)],
        "failed_verification": [r.model_dump() for r in results if r.status == "FAILED_VERIFICATION"],
        "failed_runtime": [r.model_dump() for r in results if r.status == "FAILED_RUNTIME"],
        "errors": [r.model_dump() for r in results if r.status == "LLM_ERROR"],
    }
    REPORT_FILE.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    logger.info(f"Report saved to {REPORT_FILE}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kill-Tries AST Scanner & Refactorer")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--no-resume", action="store_true", help="Do not resume from checkpoint file")
    parser.add_argument("--priority", type=str, default="all")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    priorities = [1, 2, 3] if args.priority == "all" else [int(p) for p in args.priority.split(",") if p.isdigit()]
    asyncio.run(main_async(do_refactor=not args.scan_only, priorities=priorities, limit=args.limit, resume=not args.no_resume))


if __name__ == "__main__":
    main()
