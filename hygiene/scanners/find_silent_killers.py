import ast
import json
import sys
from datetime import datetime
from pathlib import Path

from _bootstrap import pkg_root  # noqa: F401,E402

from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.settings import ModelSettings  # noqa: E402
from utils import get_src2_files  # noqa: E402

from control import CONTROL_SHEET  # noqa: E402


class SilentKillerCandidate(BaseModel):
    name: str = Field(description="The name of the variable, function, or block type.")
    file_path: str = Field(description="The source file path relative to workspace root.")
    line: int = Field(description="The starting line number of the candidate block.")
    type: str = Field(description="The type of candidate: swallowed_exception or silent_fallback.")


class AuditResult(BaseModel):
    name: str = Field(description="The name of the symbol/block audited.")
    file_path: str = Field(description="The file path of the candidate.")
    line: int = Field(description="The line number of the candidate.")
    type: str = Field(description="Type: swallowed_exception or silent_fallback.")
    status: str = Field(description="Verdict: 'SILENT_KILLER' or 'FALSE_POSITIVE'.")
    severity: str = Field(description="Severity of the violation: 'HIGH' (dangerous swallow), 'MEDIUM' (fallback with defaults), or 'LOW' (standard safe check).")
    reason: str = Field(
        description="A concise 1 to 2 sentence explanation of why it is a silent killer or how it is a safe fallback."
    )
    updated_at: str | None = Field(default=None, description="Timestamp of when the audit was performed.")


class AuditReport(BaseModel):
    scanned_files_count: int = Field(description="Total number of Python files scanned.")
    audit_results: list[AuditResult] = Field(
        default_factory=list, description="Audit results for all scanned candidate blocks."
    )
    failed_audits: list[dict] = Field(
        default_factory=list, description="List of candidates that failed LLM validation due to errors."
    )


scanner_model = CONTROL_SHEET.scanner_model

audit_agent = Agent(
    scanner_model,
    output_type=AuditResult,
    retries=3,
    system_prompt=(
        "You are an expert static analyzer and code quality auditor.\n"
        "Your task is to review a code snippet flagged as a potential 'silent killer' (e.g., swallowed exceptions, try/except pass, or silent default fallbacks).\n"
        "Inspect the context and determine if it is a dangerous silent failure that violates 'fail loudly' principles, "
        "or if it is a safe/intended fallback (like loading optional local configurations or checking dictionary presence)."
    ),
)


class SilentKillerExtractor(ast.NodeVisitor):
    """AST visitor to collect swallowed exceptions and silent fallbacks."""

    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.candidates: list[SilentKillerCandidate] = []

    def visit_Try(self, node: ast.Try):
        for handler in node.handlers:
            # Check if there is a 'raise' statement or loud handling in handler body
            is_loud = False
            for child in ast.walk(handler):
                if isinstance(child, ast.Raise):
                    is_loud = True
                    break
                if isinstance(child, ast.Call):
                    func = child.func
                    # Check logger.exception, logger.error, logger.warning
                    if isinstance(func, ast.Attribute):
                        val_id = getattr(func.value, "id", None)
                        if val_id == "logger" and func.attr in ("exception", "error", "warning"):
                            is_loud = True
                            break
                    # Check sys.exit, exit
                    elif isinstance(func, ast.Name):
                        if func.id in ("exit", "sys.exit"):
                            is_loud = True
                            break
            if not is_loud:
                handler_name = "Exception"
                if isinstance(handler.type, ast.Name):
                    handler_name = handler.type.id
                elif isinstance(handler.type, ast.Attribute):
                    handler_name = handler.type.attr
                self.candidates.append(
                    SilentKillerCandidate(
                        name=handler_name,
                        file_path=str(self.file_path),
                        line=handler.lineno,
                        type="swallowed_exception"
                    )
                )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        is_fallback = False
        name = ""
        if isinstance(node.func, ast.Name) and node.func.id == "_safe_get":
            is_fallback = True
            name = "_safe_get"
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            # Only flag dict.get if default value is explicitly N/A, Unknown, or Null
            default_arg = None
            if len(node.args) >= 2:
                default_arg = node.args[1]
            for kw in node.keywords:
                if kw.arg == "default":
                    default_arg = kw.value
                    break

            if default_arg:
                is_suspect_default = False
                if isinstance(default_arg, ast.Constant) and isinstance(default_arg.value, str):
                    if default_arg.value.lower() in ("n/a", "unknown", "null"):
                        is_suspect_default = True

                if is_suspect_default:
                    is_fallback = True
                    name = "dict.get"

        if is_fallback:
            self.candidates.append(
                SilentKillerCandidate(
                    name=name,
                    file_path=str(self.file_path),
                    line=node.lineno,
                    type="silent_fallback"
                )
            )
        self.generic_visit(node)


def audit_candidate_with_llm(
    candidate: SilentKillerCandidate, file_contents: dict[str, str]
) -> AuditResult:
    import time

    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)
    """Send candidate and its surrounding code context to the LLM for silent killer audit."""
    cand_file = candidate.file_path
    content = file_contents.get(cand_file, "")
    lines = content.splitlines()

    # Extract context: 10 lines before, 30 lines after
    start_idx = max(0, candidate.line - 10)
    end_idx = min(len(lines), candidate.line + 30)
    code_snippet = "\n".join(f"{idx}: {line}" for idx, line in zip(range(start_idx + 1, end_idx + 1), lines[start_idx:end_idx]))

    prompt = (
        f"File Path: {cand_file}\n"
        f"Candidate Type: {candidate.type}\n"
        f"Symbol Name: {candidate.name}\n"
        f"Target Line: {candidate.line}\n\n"
        "Here is the code block around this candidate:\n"
        "```python\n"
        f"{code_snippet}\n"
        "```\n\n"
        "Perform a walkthrough of this code context. Audit if this represents a dangerous silent failure/fallback (SILENT_KILLER) or a safe, expected pattern (FALSE_POSITIVE)."
    )

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
        out.write("# 🕵️ Silent Killers & Fallback Audit Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if report.failed_audits:
            out.write(f"⚠️ **Warning**: `{len(report.failed_audits)}` candidates failed to audit due to LLM errors.\n\n")

        if not report.audit_results:
            if not report.failed_audits:
                out.write("🎉 *No silent killers or fallbacks found! All files adhere to the 'fail loudly' policy.*\n")
            else:
                out.write("ℹ️ *No candidate could be audited successfully due to errors.*\n")
        else:
            # Group by file for clean display
            by_file: dict[str, list[AuditResult]] = {}
            for result in report.audit_results:
                f = result.file_path
                if f not in by_file:
                    by_file[f] = []
                by_file[f].append(result)

            for f, list_results in sorted(by_file.items()):
                out.write(f"## 📂 `{f}`\n\n")
                for item in sorted(list_results, key=lambda x: x.line):
                    status_emoji = "🛑" if item.status == "SILENT_KILLER" else "✅"
                    out.write(f"### {status_emoji} Line {item.line}: `{item.name}` ({item.type})\n")
                    out.write(f"- **Verdict**: `{item.status}`\n")
                    out.write(f"- **Severity**: `{item.severity}`\n")
                    out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")

        if report.failed_audits:
            out.write("## ⚠️ Failed Audits (LLM / API Errors)\n\n")
            for item in report.failed_audits:
                out.write(f"- `{item['name']}` in `{item['file_path']}` (Line {item['line']}): **Error**: `{item['error']}`\n")
            out.write("\n")


def main():
    files = get_src2_files()

    all_candidates: list[SilentKillerCandidate] = []
    file_contents: dict[str, str] = {}

    for file_path in files:
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content

            tree = ast.parse(content, filename=path_str)
            extractor = SilentKillerExtractor(file_path)
            extractor.visit(tree)

            all_candidates.extend(extractor.candidates)
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    import argparse
    parser = argparse.ArgumentParser(description="Silent Killer Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(all_candidates)
    print(f"AST scan complete. Found {total_candidates} candidate silent killers to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(all_candidates, 1):
            print(f"[{idx}] {cand.name} ({cand.type}) in {cand.file_path}:{cand.line}")
        sys.exit(0)

    report = AuditReport(scanned_files_count=len(files))

    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "silent_killers_audit.json"
    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    existing_results[(res.get("file_path"), res.get("line"), res.get("name"))] = res
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)
    md_path = output_dir / "silent_killers_audit.md"

    for index, candidate in enumerate(all_candidates, 1):
        key = (candidate.file_path, candidate.line, candidate.name)
        if key in existing_results:
            print(f"[{index}/{total_candidates}] Skipping already audited candidate: {candidate.name} in {candidate.file_path}:{candidate.line}")
            res_data = existing_results[key]
            audit = AuditResult(**res_data)
            audit.updated_at = datetime.now().astimezone().isoformat()
            report.audit_results.append(audit)
            continue
        print(f"[{index}/{total_candidates}] Auditing {candidate.name} ({candidate.type}) in {candidate.file_path}:{candidate.line}...")
        try:
            audit = audit_candidate_with_llm(candidate, file_contents)

            # Keep keys aligned with the static candidate details
            audit.file_path = candidate.file_path
            audit.line = candidate.line
            audit.type = candidate.type

            report.audit_results.append(audit)

            # Persist JSON store immediately
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))

        except Exception as e:
            error_msg = str(e)
            print(f"WARNING: Auditing failed for {candidate.name} at {candidate.file_path}:{candidate.line}: {error_msg}", file=sys.stderr)
            report.failed_audits.append({
                "name": candidate.name,
                "file_path": candidate.file_path,
                "line": candidate.line,
                "error": error_msg
            })
            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))

    try:
        generate_markdown_report(report, md_path)
        print(f"Rendered Markdown report saved to {md_path}")
    except Exception as e:
        print(f"Error generating Markdown report: {e}", file=sys.stderr)

    print(f"\nAudit completed. JSON store stored in {json_path}")


if __name__ == "__main__":
    main()
