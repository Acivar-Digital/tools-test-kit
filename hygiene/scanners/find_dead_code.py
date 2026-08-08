import ast
import json
import re
import sys
from datetime import datetime
from pathlib import Path

from _bootstrap import pkg_root  # noqa: F401,E402

from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.settings import ModelSettings  # noqa: E402
from utils import get_src2_files  # noqa: E402

from control import CONTROL_SHEET  # noqa: E402


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
    status: str = Field(
        description="Status of the code symbol: 'CONFIRMED_DEAD', 'DISCONNECTED_CORE_LOGIC', or 'FALSE_POSITIVE'."
    )
    reason: str = Field(
        description="A concise 1 to 2 sentence explanation of why it is dead, disconnected, or dynamically called."
    )
    updated_at: str | None = Field(default=None, description="Timestamp of when the audit was performed.")


class AuditReport(BaseModel):
    scanned_files_count: int = Field(description="Total number of Python files scanned.")
    audit_results: list[AuditResult] = Field(
        default_factory=list, description="Audit results for all scanned candidate definitions."
    )
    failed_audits: list[dict] = Field(
        default_factory=list, description="List of definitions that failed LLM validation due to errors."
    )


scanner_model = CONTROL_SHEET.scanner_model

audit_agent = Agent(
    scanner_model,
    output_type=AuditResult,
    retries=3,
    system_prompt=(
        "You are an expert static analyzer and code auditor. "
        "Your task is to review a candidate 'dead' function or class, inspect its code context and references in other files, "
        "and confirm if it is indeed dead (never called/imported), if it represents disconnected core logic (unused in the active pipeline but referenced in book/manual documentation), "
        "or if it is a false positive (called dynamically, e.g., via getattr, eval, or as an entry point webhook)."
    ),
)


def load_verified_manual_terms() -> dict[str, str]:
    """Reads all markdown files in the verified book folder and returns a mapping of word -> filename."""
    manual_dir = Path("_docs/DEV/V31/01_workflow/03_final_OWL_06_VERIFIED")
    terms = {}
    if not manual_dir.exists():
        print(f"Warning: Manual directory {manual_dir} not found.", file=sys.stderr)
        return terms

    for md_file in manual_dir.glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8").lower()
            # Clean up content to find matching words
            words = re.findall(r"\b\w+\b", content)
            for w in words:
                if len(w) > 3:  # Only index meaningful length words
                    terms[w] = md_file.name
        except Exception as e:
            print(f"Warning reading {md_file.name}: {e}", file=sys.stderr)
    return terms


def check_against_manuals(name: str, manual_terms: dict[str, str]) -> str | None:
    """Checks if a function name or parts of it appear in the verified manual."""
    name_lower = name.lower()
    # Direct match
    if name_lower in manual_terms:
        return manual_terms[name_lower]

    # Split by snake_case and match components
    parts = name_lower.split("_")
    for part in parts:
        if len(part) > 4 and part in manual_terms:
            return manual_terms[part]

    return None


class DefinitionExtractor(ast.NodeVisitor):
    """AST visitor to collect function and class definitions, identifying entrypoints."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.definitions: list[CodeDefinition] = []
        self.whitelisted_names: set[str] = set()

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

            # Common entry point keywords
            keywords = ["router", "app", "message", "command", "webhook", "post", "get", "put", "delete", "handler"]
            if any(k in dec_name.lower() for k in keywords):
                self.whitelisted_names.add(name)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if not node.name.startswith("__"):
            self.definitions.append(
                CodeDefinition(name=node.name, file_path=str(self.file_path), line=node.lineno, type="function")
            )
            self._check_decorators(node, node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        if not node.name.startswith("__"):
            self.definitions.append(
                CodeDefinition(name=node.name, file_path=str(self.file_path), line=node.lineno, type="async_function")
            )
            self._check_decorators(node, node.name)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        if not node.name.startswith("__"):
            self.definitions.append(
                CodeDefinition(name=node.name, file_path=str(self.file_path), line=node.lineno, type="class")
            )
            self._check_decorators(node, node.name)
        self.generic_visit(node)


def is_module_imported(ref_tree: ast.AST, ref_file: Path, def_file: Path, name: str) -> bool:
    """Check if the referencing file actually imports the module containing the definition."""
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
                # Relative import
                slice_len = len(ref_parts) - (node.level - 1)
                base_parts = ref_parts[:slice_len]
                if node.module:
                    imported_mod = ".".join(base_parts + (node.module,))
                else:
                    imported_mod = ".".join(base_parts)
            else:
                # Absolute import
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
    """Extract a small context window (5 lines before/after) for each reference match."""
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
                context = "\n".join(
                    f"{idx}: {line_str}"
                    for idx, line_str in zip(range(start_idx + 1, end_idx + 1), lines[start_idx:end_idx])
                )
                snippets.append(f"--- Reference in {f_path} (Lines {start_idx + 1}-{end_idx}) ---\n{context}")
                matches_found += 1
                if matches_found >= 5:  # Limit context per file
                    break

    return "\n\n".join(snippets)


def audit_candidate_with_llm(
    definition: CodeDefinition,
    file_contents: dict[str, str],
    referencing_files: list[str],
    matched_manual: str | None = None,
) -> AuditResult:
    import time

    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)
    """Send candidate definition and its call-site context to the LLM for reachability verification."""
    def_file = definition.file_path
    def_content = file_contents.get(def_file, "")

    # Extract definition context
    lines = def_content.splitlines()
    start_idx = max(0, definition.line - 2)
    end_idx = min(len(lines), definition.line + 30)
    code_snippet = "\n".join(lines[start_idx:end_idx])

    # Extract match context from referencing files
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
    )
    if matched_manual:
        prompt += (
            f"NOTE: This symbol has been detected as referenced in the verified manual chapter: {matched_manual}.\n"
            "If it is not active, it is likely 'DISCONNECTED_CORE_LOGIC' rather than 'CONFIRMED_DEAD'.\n\n"
        )

    prompt += "Perform a walkthrough of the codebase references. Audit if this definition is truly dead, disconnected core logic, or a false positive."

    backoffs = [90.0, 120.0, 240.0]
    max_attempts = len(backoffs) + 1
    for attempt in range(1, max_attempts + 1):
        try:
            response = audit_agent.run_sync(prompt, model_settings=ModelSettings(max_tokens=1024))
            return response.output
        except Exception as e:
            if attempt < max_attempts:
                sleep_time = backoffs[attempt - 1]
                print(
                    f"WARNING: API call failed ({e}). Backing off for {sleep_time:.1f}s (attempt {attempt}/{max_attempts})...",
                    file=sys.stderr,
                )
                time.sleep(sleep_time)
            else:
                print(
                    f"CRITICAL: API call failed after {max_attempts} attempts. Shutting down.",
                    file=sys.stderr,
                )
                sys.exit(1)


def generate_markdown_report(report: AuditReport, md_path: Path):
    """Deterministically convert the Pydantic/JSON audit report to Markdown."""
    with open(md_path, "w", encoding="utf-8") as out:
        out.write("# 🕵️ Dead Code Audit Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if report.failed_audits:
            out.write(
                f"⚠️ **Warning**: `{len(report.failed_audits)}` definitions failed to audit due to LLM errors. Details at the bottom of the report.\n\n"
            )

        if not report.audit_results:
            if not report.failed_audits:
                out.write("🎉 *No dead code found! All definitions appear to have active references.*\n")
            else:
                out.write("ℹ️ *No dead code candidates could be audited successfully due to errors.*\n")
        else:
            # Group by file for clean display
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

        if report.failed_audits:
            out.write("## ⚠️ Failed Audits (LLM / API Errors)\n\n")
            out.write(
                "The following definitions could not be audited successfully because the LLM/API call failed:\n\n"
            )
            for item in report.failed_audits:
                out.write(
                    f"- `{item['name']}` defined in `{item['file_path']}` (Line {item['line']}): **Error**: `{item['error']}`\n"
                )
            out.write("\n")


def load_manual_whitelist() -> set[str]:
    """Load whitelisted symbol names from kit-hygiene/whitelist.txt if it exists."""
    whitelist = set()
    whitelist_file = Path("kit-hygiene/whitelist.txt")
    if whitelist_file.exists():
        try:
            with open(whitelist_file, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        whitelist.add(line)
        except Exception as e:
            print(f"Warning: Could not read kit-hygiene/whitelist.txt: {e}", file=sys.stderr)
    return whitelist


def main():
    files = get_src2_files()

    # 1. Catalog all definitions and AST-based whitelists
    all_defs: dict[str, list[CodeDefinition]] = {}
    file_contents: dict[str, str] = {}
    ast_trees: dict[str, ast.AST] = {}
    decorator_whitelisted: set[str] = set()

    for file_path in files:
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content

            # Parse AST
            tree = ast.parse(content, filename=path_str)
            ast_trees[path_str] = tree
            extractor = DefinitionExtractor(file_path)
            extractor.visit(tree)

            decorator_whitelisted.update(extractor.whitelisted_names)

            for definition in extractor.definitions:
                if definition.name not in all_defs:
                    all_defs[definition.name] = []
                all_defs[definition.name].append(definition)
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    # 2. Whitelist compilation (Manual + Decorator + Standard entrypoints)
    whitelist: set[str] = {
        "main",
        "telegram_webhook",
        "agent_webhook",
        "debug_session",
        "process_webhook_logic",
        "define_system_prompt",
        "add_the_users_name",
        "add_the_date",
    }
    whitelist.update(decorator_whitelisted)
    whitelist.update(load_manual_whitelist())

    candidates_and_references = []

    # 3. Reference check with Import & Call-site verification
    for name, occurrences in all_defs.items():
        if name in whitelist:
            continue

        pattern = re.compile(rf"\b{re.escape(name)}\b")

        for definition in occurrences:
            def_file_str = definition.file_path
            def_file_path = Path(def_file_str)
            referencing_files = []

            # Check every file for usage
            for other_file, content in file_contents.items():
                if other_file == def_file_str:
                    # Check if the name is referenced anywhere else in the same defining file
                    lines = content.splitlines()
                    def_line_idx = definition.line - 1
                    used_elsewhere = False
                    for idx, line in enumerate(lines):
                        if idx == def_line_idx:
                            continue
                        if pattern.search(line):
                            used_elsewhere = True
                            break
                    if used_elsewhere:
                        referencing_files.append(other_file)
                else:
                    if pattern.search(content):
                        other_tree = ast_trees.get(other_file)
                        other_file_path = Path(other_file)
                        # Verify if other_file actually imports the module defining the candidate
                        if other_tree and is_module_imported(other_tree, other_file_path, def_file_path, name):
                            referencing_files.append(other_file)

            if not referencing_files:
                candidates_and_references.append((definition, referencing_files))

    import argparse
    parser = argparse.ArgumentParser(description="Dead Code Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(candidates_and_references)
    print(f"AST scan complete. Found {total_candidates} candidate dead definitions to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, (definition, referencing_files) in enumerate(candidates_and_references, 1):
            print(f"[{idx}] {definition.name} ({definition.type}) in {definition.file_path}:{definition.line}")
        sys.exit(0)

    # 4. LLM Auditing loop (Saves directly to JSON, then renders Markdown locally)
    report = AuditReport(scanned_files_count=len(files))
    manual_terms = load_verified_manual_terms()

    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "dead_code_audit.json"
    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    existing_results[(res.get("file_path"), res.get("line"), res.get("name"))] = res
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)
    md_path = output_dir / "dead_code_audit.md"

    for index, (definition, referencing_files) in enumerate(candidates_and_references, 1):
        key = (definition.file_path, definition.line, definition.name)
        if key in existing_results:
            print(
                f"[{index}/{total_candidates}] Skipping already audited definition: {definition.name} in {definition.file_path}"
            )
            res_data = existing_results[key]
            audit = AuditResult(**res_data)
            audit.updated_at = datetime.now().astimezone().isoformat()
            report.audit_results.append(audit)
            continue
        print(f"[{index}/{total_candidates}] Auditing {definition.name} in {definition.file_path}...")
        try:
            matched_manual = check_against_manuals(definition.name, manual_terms)
            audit = audit_candidate_with_llm(definition, file_contents, referencing_files, matched_manual)

            # Ensure file details match Pydantic schema
            audit.file_path = definition.file_path
            audit.line = definition.line
            audit.type = definition.type

            report.audit_results.append(audit)

            # Immediate write to JSON file to prevent progress loss
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))

        except Exception as e:
            error_msg = str(e)
            print(
                f"WARNING: Auditing failed or exhausted retries for {definition.name} in {definition.file_path}: {error_msg}",
                file=sys.stderr,
            )
            report.failed_audits.append(
                {
                    "name": definition.name,
                    "file_path": definition.file_path,
                    "line": definition.line,
                    "error": error_msg,
                }
            )
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))

    # 5. Convert JSON report to Markdown deterministically
    try:
        generate_markdown_report(report, md_path)
        print(f"Rendered Markdown report saved to {md_path}")
    except Exception as e:
        print(f"Error generating Markdown report: {e}", file=sys.stderr)

    print(f"\nAudit completed. JSON store stored in {json_path}")


if __name__ == "__main__":
    main()
