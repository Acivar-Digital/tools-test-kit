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
import json
import logging
import os
import subprocess
import sys
import tempfile
import textwrap
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
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart

# Ensure repo root in sys.path
from _bootstrap import pkg_root  # noqa: F401,E402

from virtual_ast_buffer import VirtualASTBuffer  # noqa: E402
from control import CONTROL_SHEET  # noqa: E402

# Initialize Logfire instrumentation once globally
try:
    logfire.configure(send_to_logfire=False)
    logfire.instrument_pydantic_ai()
except Exception:
    pass

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
    base_url = getattr(getattr(model, "provider", None), "base_url", "")
    if "antigravity" in base_url or ":8045" in base_url:
        return "antigravity_manager"
    if "literouter" in base_url or base_url.endswith(":7766/v1"):
        return "literouter"
    if "openrouter" in base_url:
        return "openrouter"
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


# =====================================================================
# PYDANTIC 2.0 DOMAIN SCHEMAS
# =====================================================================

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
    upstream_callers: str = ""
    module_context: str = ""


class RefactoringVerdict(BaseModel):
    """Pydantic 2.0 schema for LLM structured refactoring output with strict constraints."""

    model_config = ConfigDict(strip_whitespace=True, validate_assignment=True)

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

    @field_validator("refactored_code", "helper_functions", mode="before")
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

        safe_modules = {"typing", "collections", "enum", "dataclasses", "itertools"}
        unauthorized_imports = []

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
        except SyntaxError:
            pass

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
            except SyntaxError:
                pass

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


class RefactorResult(BaseModel):
    """Pydantic 2.0 schema for checkpoint and report items."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    file_path: str
    function_name: str
    line: int
    status: str  # "APPROVED", "FAILED_VERIFICATION", "LLM_ERROR"
    attempts: int
    original_cc: int
    refactored_cc: int
    original_depth: int
    refactored_depth: int
    refactored_code: str
    helper_functions: list[str] = Field(default_factory=list)
    explanation: str
    verification_msg: str


refactor_result_adapter = TypeAdapter(RefactorResult)


# =====================================================================
# PYDANTIC-AI AGENT & OUTPUT VALIDATION
# =====================================================================

_refactor_agent = Agent(
    model=CONTROL_SHEET.scanner_model,
    deps_type=RefactorDeps,
    output_type=RefactoringVerdict,
    instructions="You are a principal Python architect strictly enforcing Flat Control Flow.",
    retries=3,
    model_settings={"temperature": 0.0},
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


class ReturnVisitor(ast.NodeVisitor):
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
        except SyntaxError:
            pass

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
    except SyntaxError:
        pass

    # 3. Live Compiler Sandbox using VirtualASTBuffer
    if ctx.deps.full_file_source and ctx.deps.func_name:
        try:
            buf = VirtualASTBuffer(ctx.deps.full_file_source, ctx.deps.file_path)
            temp_source = buf.replace_function(
                ctx.deps.func_name,
                result.refactored_code,
                result.helper_functions,
            )
            temp_source = ensure_pydantic_imports(
                temp_source,
                result.refactored_code
                + (
                    "\n\n" + "\n\n".join(h.rstrip() for h in result.helper_functions)
                    if result.helper_functions
                    else ""
                ),
            )
        except Exception as e:
            msg = f"CRITICAL: Refactored code AST replacement failed in VirtualASTBuffer: {e}"
            logger.warning(f"[ModelRetry] VirtualASTBuffer Replace Error: {msg}")
            raise ModelRetry(msg)

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(temp_source)

            # Format and check with Ruff
            subprocess.run(["uv", "run", "ruff", "format", tmp_path], capture_output=True, text=True, check=False)
            ruff_res = subprocess.run(
                ["uv", "run", "ruff", "check", tmp_path], capture_output=True, text=True, check=False
            )
            if ruff_res.returncode != 0:
                clean_errors = "\n".join(
                    [line.split(":", 1)[-1].strip() for line in ruff_res.stdout.splitlines() if ":" in line]
                )
                logger.warning(f"[ModelRetry] Ruff error:\n{clean_errors}")
                raise ModelRetry(
                    f"CRITICAL: Code caused Ruff linter errors:\n{clean_errors}\n"
                    f"Fix these errors. If you hallucinated a type hint (F821), change it to `dict`, `list`, or `Any`."
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    return result


# =====================================================================
# AST SCANNER & UTILITIES
# =====================================================================

class FunctionCandidateScanner(ast.NodeVisitor):
    CONTROL_NODES = (ast.If, ast.Try, ast.For, ast.While, ast.With)

    def __init__(self, filename: str, code_lines: list[str]) -> None:
        self.filename = filename
        self.code_lines = code_lines
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

            priority = 3
            if len(try_issues) > 0:
                priority = 1
            elif max_depth > 3:
                priority = 2

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
                )
            )

        self.generic_visit(node)

    def _check_body_nesting(
        self, statements: list[ast.stmt], depth: int
    ) -> tuple[int, int, list[tuple[int, str]]]:
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
        paths = {line.strip() for line in f if line.strip() and not line.startswith("#")}
    logger.info(f"Loaded {len(paths)} targeted files from kill_tries_list.txt")
    return paths


def format_prompt(
    template: dict,
    candidate: FunctionCandidate,
    attempt: int = 1,
    history: list | None = None,
    what_worked_text: str = "",
    violations_text: str = "",
) -> str:
    if not history:
        return _render_narrative(template, candidate, attempt, history, what_worked_text, violations_text)

    function_name = candidate.function_name
    file_path = candidate.file_path
    attempts_left = 5 - attempt + 1
    source_code = candidate.source_code

    return (
        f"=== ATTEMPT {attempt}/5 (CONCISE DELTA) ===\n\n"
        f"Previous attempt feedback for {function_name} ({file_path}):\n\n"
        f"ISSUES TO FIX:\n{violations_text}\n\n"
        f"WHAT WORKED (preserve these):\n{what_worked_text}\n\n"
        f"YOU HAVE {attempts_left} ATTEMPT(S) LEFT.\n"
        f"Take your previous attempt and surgically fix only the violations above.\n"
        f"CRITICAL: If you extract helper functions, prefix each with `_{function_name}_`.\n\n"
        f"<source_code>\n{source_code}\n</source_code>\n"
    )


def _render_narrative(
    template: dict,
    candidate: FunctionCandidate,
    attempt_num: int,
    history: list | None = None,
    what_worked_text: str = "",
    violations_text: str = "",
) -> str:
    system_prompt = template.get("system_prompt", "")
    system = template.get("system_instruction", "")
    anti_patterns = template.get("anti_patterns", "")

    return (
        f"{system_prompt}\n\n{system}\n\n"
        f"=== WHAT WENT WRONG ===\n{anti_patterns}\n\n"
        f"=== RULES ===\n{template.get('conditions', template.get('rules', ''))}\n\n"
        f"TARGET: Refactor {candidate.function_name} ({candidate.file_path}:{candidate.line}) to pass all checks.\n"
        f"CC={candidate.cc} | Depth={candidate.max_depth} | Priority={candidate.priority}\n\n"
        f"<source_code>\n{candidate.source_code}\n</source_code>\n"
    )


def ensure_pydantic_imports(source: str, ref_code: str) -> str:
    has_basemodel = False
    has_field = False
    try:
        source_tree = ast.parse(source)
        for node in ast.walk(source_tree):
            if isinstance(node, ast.ImportFrom) and node.module == "pydantic":
                for alias in node.names:
                    name = alias.asname or alias.name
                    if name == "BaseModel":
                        has_basemodel = True
                    elif name == "Field":
                        has_field = True
    except Exception:
        pass

    uses_basemodel = False
    uses_field = False
    try:
        ref_tree = ast.parse(ref_code)
        for node in ast.walk(ref_tree):
            if isinstance(node, ast.Name):
                if node.id == "BaseModel":
                    uses_basemodel = True
                elif node.id == "Field":
                    uses_field = True
    except Exception:
        pass

    needed = []
    if uses_basemodel and not has_basemodel:
        needed.append("BaseModel")
    if uses_field and not has_field:
        needed.append("Field")
    if not needed:
        return source

    import_line = f"from pydantic import {', '.join(needed)}\n"
    return import_line + source


# =====================================================================
# AST VERIFICATION
# =====================================================================

def verify_refactored_ast(
    code: str, candidate_name: str = "", contract_info: dict | None = None, orig_code: str = "", orig_cc: int = 0
) -> tuple[bool, int, int, str]:
    violations: list[str] = []
    target_cc = 5 if orig_cc <= 5 else (orig_cc - 1)

    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return False, 999, 999, f"SyntaxError in refactored code: {e}"

    candidate_cc = 0
    candidate_max_depth = 0

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
                violations.append(f"try_pyramid:{try_issues}")

            node_target_cc = target_cc if node.name == candidate_name else 5
            if func_cc > node_target_cc:
                violations.append(f"cc_exceeds:{node.name} has CC={func_cc} (target <={node_target_cc})")

            if func_depth > 3:
                violations.append(f"nesting_exceeds:{node.name} depth={func_depth} (must be <=3)")

    if violations:
        return False, candidate_cc, candidate_max_depth, "VIOLATIONS FOUND:\n" + "\n".join(f"  - {v}" for v in violations)

    return True, candidate_cc, candidate_max_depth, "Passed verification."


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
    model_obj = CONTROL_SHEET.scanner_model
    model_name = getattr(model_obj, "model_name", str(model_obj))
    _provider = get_model_provider_name(CONTROL_SHEET.scanner_model)
    start_t = time.time()

    print(
        f"🔵 [{get_timestamp()}] [{cand_idx}/{total_cand}][REQ {req_id}] provider={_provider} candidate={candidate.function_name} ({candidate.file_path}:{candidate.line}) attempt={attempt}/5",
        flush=True,
    )

    try:
        full_source = ""
        target_path = pkg_root / candidate.file_path
        if target_path.exists():
            full_source = target_path.read_text(encoding="utf-8")

        deps_obj = RefactorDeps(
            orig_code=candidate.source_code,
            full_file_source=full_source,
            file_path=candidate.file_path,
            line=candidate.line,
            end_line=candidate.end_line,
            func_name=candidate.function_name,
        )

        result = await _refactor_agent.run(prompt, message_history=history, deps=deps_obj)
        elapsed = round(time.time() - start_t, 2)
        history = result.all_messages()
        verdict: RefactoringVerdict = result.output

        full_code = verdict.refactored_code + ("\n\n" + "\n\n".join(verdict.helper_functions) if verdict.helper_functions else "")
        passed, new_cc, new_depth, msg = verify_refactored_ast(
            full_code, candidate.function_name, orig_code=candidate.source_code, orig_cc=candidate.cc
        )

        if passed:
            print(f"✅ [{get_timestamp()}] [PASSED {req_id}] {candidate.function_name} PASSED on attempt {attempt}/5! (Duration: {elapsed}s)", flush=True)
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
            )
            return True, history, prompt, res

        logger.warning(f"  ⚠️ [Attempt {attempt}/5 Retry] {candidate.function_name} failed AST check: {msg}")
        retry_prompt = format_prompt(template, candidate, attempt + 1, history, violations_text=msg)

        if attempt >= 5:
            res = RefactorResult(
                file_path=candidate.file_path,
                function_name=candidate.function_name,
                line=candidate.line,
                status="FAILED_VERIFICATION",
                attempts=5,
                original_cc=candidate.cc,
                refactored_cc=new_cc,
                original_depth=candidate.max_depth,
                refactored_depth=new_depth,
                refactored_code=candidate.source_code,
                helper_functions=[],
                explanation=f"Failed after 5 attempts: {msg}",
                verification_msg=msg,
            )
            return False, history, retry_prompt, res

        return False, history, retry_prompt, None

    except Exception as e:
        logger.error(f"Pydantic-AI attempt {attempt} failed for {candidate.function_name}: {e}")
        if attempt >= 5:
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
    logger.info("Scanning src2/ AST for Flat Control Flow candidates...")
    candidates: list[FunctionCandidate] = []
    root_resolved = pkg_root.resolve()

    for py_file in sorted(SRC2_DIR.rglob("*.py")):
        if py_file.is_file():
            rel_path = str(py_file.resolve().relative_to(root_resolved))
            if target_files and rel_path not in target_files:
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(py_file))
                scanner = FunctionCandidateScanner(rel_path, content.splitlines())
                scanner.visit(tree)
                candidates.extend(scanner.candidates)
            except Exception as e:
                logger.warning(f"Skipped {py_file.name}: {e}")

    logger.info(f"✅ Found {len(candidates)} candidates violating Flat Control Flow standards.")
    return candidates


def save_checkpoint_item(res: RefactorResult) -> None:
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_FILE, "a", encoding="utf-8") as f:
        f.write(res.model_dump_json() + "\n")


async def main_async(do_refactor: bool, priorities: list[int], limit: int, resume: bool) -> None:
    target_files = load_target_files()
    candidates = scan_all_candidates(target_files=target_files)
    targets = [c for c in candidates if c.priority in priorities]

    if limit > 0:
        targets = targets[:limit]

    print(f"\n✨ Scanned {len(candidates)} total candidates. Processing {len(targets)} matching candidates...")

    template = load_prompt_template()
    queue: asyncio.Queue = asyncio.Queue()

    for idx, c in enumerate(targets, start=1):
        prompt = format_prompt(template, c, attempt=1)
        await queue.put({"candidate": c, "index": idx, "total": len(targets), "attempt": 1, "history": [], "prompt": prompt})

    semaphore = asyncio.Semaphore(3)
    results: list[RefactorResult] = []

    async def worker_task(item: dict) -> None:
        cand: FunctionCandidate = item["candidate"]
        async with semaphore:
            passed, new_hist, next_prmpt, res = await refactor_single_attempt_with_llm(
                cand, item["attempt"], item["history"], item["prompt"], template, item["index"], item["total"]
            )
        if res is not None:
            save_checkpoint_item(res)
            results.append(res)
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

    active_tasks = set()
    while not queue.empty() or active_tasks:
        if not queue.empty():
            item = await queue.get()
            t = asyncio.create_task(worker_task(item))
            active_tasks.add(t)
            t.add_done_callback(active_tasks.discard)
            await asyncio.sleep(2.0)
        else:
            await asyncio.sleep(0.5)

    REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "total_scanned_candidates": len(candidates),
        "refactored_count": len(results),
        "approved": [r.model_dump() for r in results if r.status == "APPROVED"],
        "failed": [r.model_dump() for r in results if r.status != "APPROVED"],
    }
    REPORT_FILE.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    logger.info(f"Report saved to {REPORT_FILE}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Kill-Tries AST Scanner & Refactorer")
    parser.add_argument("--scan-only", action="store_true")
    parser.add_argument("--priority", type=str, default="all")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    priorities = [1, 2, 3] if args.priority == "all" else [int(p) for p in args.priority.split(",") if p.isdigit()]
    asyncio.run(main_async(do_refactor=not args.scan_only, priorities=priorities, limit=args.limit, resume=True))


if __name__ == "__main__":
    main()