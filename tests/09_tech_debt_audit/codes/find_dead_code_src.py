import ast
import json
import re
import subprocess
import sys
from pathlib import Path

# Add workspace root to sys.path to resolve admin imports when run directly
sys.path.append(str(Path(__file__).parent.parent))

from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.models.openai import OpenAIChatModel  # noqa: E402
from pydantic_ai.providers.openai import OpenAIProvider  # noqa: E402
from pydantic_ai.settings import ModelSettings  # noqa: E402

from admin.dotenv import api_key, base_url, model_name  # noqa: E402


class CodeDefinition(BaseModel):
    name: str = Field(description="The name of the function, async function, or class.")
    file_path: str = Field(description="The source file path relative to workspace root.")
    line: int = Field(description="The starting line number of the definition.")
    type: str = Field(description="The type of definition: function, async_function, or class.")

class AuditResult(BaseModel):
    name: str = Field(description="Name of the audited function/class.")
    file_path: str = Field(description="The file path where it is defined.")
    line: int = Field(description="The line number where it is defined.")
    type: str = Field(description="The definition type (function, async_function, class).")
    status: str = Field(description="Status of the code symbol: 'CONFIRMED_DEAD' or 'FALSE_POSITIVE'.")
    reason: str = Field(
        description="A concise 1 to 2 sentence explanation of why it is dead or how it is dynamically called."
    )

class AuditReport(BaseModel):
    scanned_files_count: int = Field(description="Total number of Python files scanned.")
    audit_results: list[AuditResult] = Field(
        default_factory=list, description="Audit results for all scanned candidate definitions."
    )
    failed_audits: list[dict] = Field(
        default_factory=list, description="List of definitions that failed LLM validation due to errors."
    )

provider = OpenAIProvider(base_url=base_url, api_key=api_key)
model = OpenAIChatModel(model_name=model_name, provider=provider)

audit_agent = Agent(
    model,
    output_type=AuditResult,
    retries=3,
    system_prompt=(
        "You are an expert static analyzer and codebase auditor. "
        "Your task is to review a candidate 'dead' function or class, inspect its code context, and confirm if it is dead ('CONFIRMED_DEAD') or alive ('FALSE_POSITIVE').\n\n"
        "STRICT RUNTIME AUDIT RULES:\n"
        "1. METHOD INVOCATIONS: If the symbol is a class method, search the codebase context for instances of `object.method_name(...)` or `self.method_name(...)`. If it is called on an instance, it is alive.\n"
        "2. FRAMEWORK DECORATORS: Check the decorators of the symbol. If it has Pydantic decorators (like `@model_validator`, `@field_validator`) or agent tool registers (like `@agent.tool`, `@agent.system_prompt`), it is invoked dynamically by the framework and is alive.\n"
        "3. OVERRIDE METHODS: Check if the method overrides a parent method from a library base class (e.g., overriding `EmbeddingBase.embed`). If it is a polymorphic implementation of a library interface, it is alive.\n"
        "4. DYNAMIC RETRIEVAL: Check if the symbol name is used inside `getattr` calls or matches key strings in configuration dictionaries. If so, it is alive.\n"
        "5. DOMAIN CONTEXT: Examine internal helper functions (starting with an underscore). If the parent function in the same module is alive and delegates to this helper, the helper is alive.\n\n"
        "Unless you are absolutely certain there are 0 runtime or static references across the entire codebase, classify it as 'FALSE_POSITIVE'."
    ),
)

def get_files(directory: str) -> list[Path]:
    """Get all Python files under the directory that are not ignored by git."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", directory],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
        if not lines:
            raise ValueError("No files found by git")
        paths = [Path(l) for l in lines]
        return [p for p in paths if p.is_file() and p.suffix == ".py" and p.name != "__init__.py"]
    except Exception:
        return [
            p
            for p in Path(directory).rglob("*.py")
            if p.is_file() and p.name != "__init__.py" and "__pycache__" not in p.parts
        ]

class DefinitionExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.definitions = []
        self.whitelisted_names = set()

    def _check_decorators(self, node, name: str):
        for decorator in node.decorator_list:
            dec_name = ""
            if isinstance(decorator, ast.Name):
                dec_name = decorator.id
            elif isinstance(decorator, ast.Attribute):
                dec_name = decorator.attr
            elif isinstance(decorator, ast.Call):
                if isinstance(decorator.func, ast.Name):
                    dec_name = decorator.func.id
                elif isinstance(decorator.func, ast.Attribute):
                    dec_name = decorator.func.attr
            keywords = ["router", "app", "message", "command", "webhook", "post", "get", "put", "delete", "handler"]
            if any(k in dec_name.lower() for k in keywords):
                self.whitelisted_names.add(name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not node.name.startswith("__"):
            # Use virtual path in definitions
            virtual_path = str(self.file_path).replace("scratch/main_src/", "")
            self.definitions.append(
                CodeDefinition(name=node.name, file_path=virtual_path, line=node.lineno, type="function")
            )
            self._check_decorators(node, node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not node.name.startswith("__"):
            virtual_path = str(self.file_path).replace("scratch/main_src/", "")
            self.definitions.append(
                CodeDefinition(name=node.name, file_path=virtual_path, line=node.lineno, type="async_function")
            )
            self._check_decorators(node, node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not node.name.startswith("__"):
            virtual_path = str(self.file_path).replace("scratch/main_src/", "")
            self.definitions.append(
                CodeDefinition(name=node.name, file_path=virtual_path, line=node.lineno, type="class")
            )
            self._check_decorators(node, node.name)
        self.generic_visit(node)

def is_module_imported(ref_tree: ast.AST, ref_file: Path, def_file: Path, name: str) -> bool:
    def_parts = def_file.with_suffix("").parts
    def_mod = ".".join(def_parts)
    ref_parts = ref_file.parent.parts

    for node in ast.walk(ref_tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == def_mod or alias.name.startswith(def_mod + "."):
                    return True
        elif isinstance(node, ast.ImportFrom):
            imported_mod = ""
            if node.level > 0:
                slice_len = len(ref_parts) - (node.level - 1)
                base_parts = ref_parts[:slice_len]
                if node.module:
                    imported_mod = ".".join(base_parts + (node.module,))
                else:
                    imported_mod = ".".join(base_parts)
            else:
                if node.module:
                    imported_mod = node.module

            if imported_mod == def_mod:
                for alias in node.names:
                    if alias.name == name or alias.name == "*":
                        return True
            elif def_mod.startswith(imported_mod + "."):
                remaining = def_mod[len(imported_mod) + 1 :]
                next_part = remaining.split(".")[0]
                for alias in node.names:
                    if alias.name == next_part or alias.name == "*":
                        return True
    return False

def get_match_context_snippets(name: str, file_contents: dict[str, str], referencing_files: list[str]) -> str:
    snippets = []
    pattern = re.compile(rf"\b{re.escape(name)}\b")

    for f_path in referencing_files:
        content = file_contents.get(f_path, "")
        lines = content.splitlines()
        matches_found = 0

        for line_idx, line in enumerate(lines, 1):
            if pattern.search(line):
                start_idx = max(0, line_idx - 6)
                end_idx = min(len(lines), line_idx + 5)
                context = "\n".join(f"{idx}: {line_str}" for idx, line_str in zip(range(start_idx + 1, end_idx + 1), lines[start_idx:end_idx]))
                snippets.append(f"--- Reference in {f_path} (Lines {start_idx+1}-{end_idx}) ---\n{context}")
                matches_found += 1
                if matches_found >= 5:
                    break

    return "\n\n".join(snippets)

def audit_candidate_with_llm(
    definition: CodeDefinition, file_contents: dict[str, str], referencing_files: list[str]
) -> AuditResult:
    def_file = definition.file_path
    def_content = file_contents.get(def_file, "")
    lines = def_content.splitlines()
    start_idx = max(0, definition.line - 2)
    end_idx = min(len(lines), definition.line + 30)
    code_snippet = "\n".join(lines[start_idx:end_idx])

    reference_context = get_match_context_snippets(definition.name, file_contents, referencing_files)
    if not reference_context:
        reference_context = "No static references found in other files (0 matches)."

    prompt = (
        f"File Path: {def_file}\n"
        f"Definition Type: {definition.type}\n"
        f"Name: {definition.name}\n"
        f"Defined on Line: {definition.line}\n\n"
        "Here is the code block around this definition:\n"
        "```python\n"
        f"{code_snippet}\n"
        "```\n\n"
        "Here is the context of how/where this symbol is referenced in other codebase files:\n"
        f"{reference_context}\n\n"
        "Perform a walkthrough of the codebase references. Audit if this definition is truly dead or a false positive."
    )

    response = audit_agent.run_sync(prompt, model_settings=ModelSettings(max_tokens=1024))
    return response.output

def generate_markdown_report(report: AuditReport, md_path: Path):
    with open(md_path, "w", encoding="utf-8") as out:
        out.write("# 🕵️ Dead Code Audit Report (Main Branch)\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src/`.\n\n")

        if report.failed_audits:
            out.write(f"⚠️ **Warning**: `{len(report.failed_audits)}` definitions failed to audit due to LLM errors. Details at the bottom of the report.\n\n")

        if not report.audit_results:
            if not report.failed_audits:
                out.write("🎉 *No dead code found!*\n")
            else:
                out.write("ℹ️ *No dead code candidates could be audited successfully due to errors.*\n")
        else:
            by_file: dict[str, list[AuditResult]] = {}
            for result in report.audit_results:
                f = result.file_path
                if f not in by_file:
                    by_file[f] = []
                by_file[f].append(result)

            for f, dead_list in sorted(by_file.items()):
                out.write(f"## 📂 `{f}`\n\n")
                for item in sorted(dead_list, key=lambda x: x.line):
                    status_emoji = "🛑" if item.status == "CONFIRMED_DEAD" else "✅"
                    out.write(f"### {status_emoji} `{item.name}` (Line {item.line})\n")
                    out.write(f"- **Type**: {item.type.capitalize()}\n")
                    out.write(f"- **Verdict**: `{item.status}`\n")
                    out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")

def main():
    files = get_files("scratch/main_src/src")
    print(f"Found {len(files)} files to scan in scratch/main_src/src...")

    all_defs: dict[str, list[CodeDefinition]] = {}
    file_contents: dict[str, str] = {}
    ast_trees: dict[str, ast.AST] = {}
    decorator_whitelisted: set[str] = set()

    for file_path in files:
        # Map to virtual path starting with src/
        virtual_path_str = str(file_path).replace("scratch/main_src/", "")
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[virtual_path_str] = content

            tree = ast.parse(content, filename=virtual_path_str)
            ast_trees[virtual_path_str] = tree
            extractor = DefinitionExtractor(file_path)
            extractor.visit(tree)

            decorator_whitelisted.update(extractor.whitelisted_names)

            for definition in extractor.definitions:
                if definition.name not in all_defs:
                    all_defs[definition.name] = []
                all_defs[definition.name].append(definition)
        except Exception as e:
            print(f"Error parsing {file_path}: {e}", file=sys.stderr)

    whitelist = {
        "main", "telegram_webhook", "agent_webhook", "debug_session",
        "process_webhook_logic", "define_system_prompt", "add_the_users_name", "add_the_date"
    }
    whitelist.update(decorator_whitelisted)

    candidates_and_references = []

    for name, occurrences in all_defs.items():
        if name in whitelist:
            continue

        pattern = re.compile(rf"\b{re.escape(name)}\b")

        for definition in occurrences:
            def_file_str = definition.file_path
            def_file_path = Path(def_file_str)
            referencing_files = []

            for other_file, content in file_contents.items():
                if other_file == def_file_str:
                    continue

                if pattern.search(content):
                    other_tree = ast_trees.get(other_file)
                    other_file_path = Path(other_file)
                    if other_tree and is_module_imported(other_tree, other_file_path, def_file_path, name):
                        referencing_files.append(other_file)

            if not referencing_files:
                candidates_and_references.append((definition, referencing_files))

    total_candidates = len(candidates_and_references)
    print(f"AST scan complete. Found {total_candidates} candidate dead definitions in main src to audit.")

    report = AuditReport(scanned_files_count=len(files))
    output_dir = Path("TEST/codes/20260626_SRC2")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dead_code_audit_main.json"
    md_path = output_dir / "dead_code_audit_main.md"

    # Load existing progress if available
    already_audited = {}
    already_failed = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for item in existing_data.get("audit_results", []):
                    already_audited[(item["file_path"], item["name"])] = AuditResult(**item)
                for item in existing_data.get("failed_audits", []):
                    already_failed[(item["file_path"], item["name"])] = item
            print(f"Loaded {len(already_audited)} existing audited items and {len(already_failed)} failed items from progress file.")
        except Exception as e:
            print(f"Could not load progress file: {e}")

    # Only run LLM validation on candidates
    for index, (definition, referencing_files) in enumerate(candidates_and_references, 1):
        key = (definition.file_path, definition.name)
        if key in already_audited:
            print(f"[{index}/{total_candidates}] Skipping {definition.name} (already audited)...")
            report.audit_results.append(already_audited[key])
            continue

        print(f"[{index}/{total_candidates}] Auditing {definition.name} in {definition.file_path}...")
        try:
            audit = audit_candidate_with_llm(definition, file_contents, referencing_files)
            audit.file_path = definition.file_path
            audit.line = definition.line
            audit.type = definition.type
            report.audit_results.append(audit)

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            error_msg = str(e)
            print(f"WARNING: Auditing failed for {definition.name}: {error_msg}", file=sys.stderr)
            report.failed_audits.append({
                "name": definition.name,
                "file_path": definition.file_path,
                "line": definition.line,
                "error": error_msg
            })
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))

    try:
        generate_markdown_report(report, md_path)
        print(f"Rendered Markdown report saved to {md_path}")
    except Exception as e:
        print(f"Error generating Markdown report: {e}", file=sys.stderr)

    print(f"\nAudit completed. JSON report saved to {json_path}")

if __name__ == "__main__":
    main()
