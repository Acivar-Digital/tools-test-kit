import ast
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from _bootstrap import pkg_root  # noqa: F401,E402

from pydantic import BaseModel, Field  # noqa: E402
from pydantic_ai import Agent  # noqa: E402
from pydantic_ai.settings import ModelSettings  # noqa: E402
from utils import get_src2_files  # noqa: E402

from control import CONTROL_SHEET  # noqa: E402


class EngineSchemaCandidate(BaseModel):
    name: str = Field(description="The name of the function/method.")
    file_path: str = Field(description="The source file path relative to workspace root.")
    line: int = Field(description="The line number where the function is defined.")
    signature: str = Field(description="The parsed signature of the function.")
    func_context: str = Field(description="The source code of the function def.")


class SchemaAuditResult(BaseModel):
    name: str = Field(description="The name of the function audited.")
    file_path: str = Field(description="The file path of the candidate.")
    line: int = Field(description="The line number of the candidate.")
    status: str = Field(description="Verdict: 'SCHEMA_HAZARD' (non-compliant/raw dicts) or 'FALSE_POSITIVE' (compliant/helper).")
    severity: str = Field(description="Severity: 'HIGH' (major module entry point/API contract), 'LOW' (internal helper/math formula).")
    reason: str = Field(description="A concise 1 to 2 sentence explanation of the status verdict.")
    updated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(), description="The ISO datetime string when audited.")


class SchemaAuditReport(BaseModel):
    scanned_files_count: int = Field(description="Total number of Python files scanned.")
    audit_results: list[SchemaAuditResult] = Field(default_factory=list)
    failed_audits: list[dict] = Field(default_factory=list)


# Fetch model from the controls mapping
scanner_model = CONTROL_SHEET.scanner_model

schema_audit_agent = Agent(
    scanner_model,
    output_type=SchemaAuditResult,
    retries=3,
    system_prompt=(
        "You are an expert Python AST and API design auditor.\n"
        "Your task is to review function signatures in BaZi calculation modules.\n"
        "Determine if the function uses Pydantic schema models (such as ChartProfile, InteractionOutput, etc.) "
        "as inputs and outputs for complex structure validation.\n"
        "If a function handles complex data payloads using raw dict or list instead of Pydantic models, "
        "mark it as 'SCHEMA_HAZARD'.\n"
        "If it is a simple helper function (e.g. math helper, simple string translator, or correctly typed primitive function), "
        "or if it is already fully using Pydantic models, mark it as 'FALSE_POSITIVE'."
    ),
)


def is_potential_schema_hazard(node: ast.FunctionDef) -> bool:
    # 1. Check arguments
    for arg in node.args.args:
        # Skip 'self' or 'cls' in classes
        if arg.arg in ("self", "cls"):
            continue
        if not arg.annotation:
            return True  # Untyped argument is a potential hazard

        # Check if annotation unparses to dict, list, Dict, List, Any
        annot_str = ast.unparse(arg.annotation).strip()
        if any(x in annot_str for x in ("dict", "Dict", "list", "List", "Any")):
            return True

    # 2. Check return type
    if not node.returns:
        return True  # Untyped return is a potential hazard

    returns_str = ast.unparse(node.returns).strip()
    if any(x in returns_str for x in ("dict", "Dict", "list", "List", "Any")):
        return True

    return False


class FunctionDefExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path, content: str):
        self.file_path = file_path
        self.content_lines = content.splitlines()
        self.candidates: list[EngineSchemaCandidate] = []

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # We only check top-level or method functions (skip nested ones for cleanliness)
        if not is_potential_schema_hazard(node):
            self.generic_visit(node)
            return

        start_line = node.lineno
        # Approximate end line using the body lines
        end_line = max(node.end_lineno or start_line, start_line + len(node.body))
        func_context = "\n".join(self.content_lines[start_line - 1:end_line])

        # Get signature representation
        args_list = []
        for arg in node.args.args:
            annotation = ""
            if arg.annotation:
                annotation = f": {ast.unparse(arg.annotation)}"
            args_list.append(f"{arg.arg}{annotation}")
        returns = ""
        if node.returns:
            returns = f" -> {ast.unparse(node.returns)}"
        signature = f"def {node.name}({', '.join(args_list)}){returns}"

        self.candidates.append(
            EngineSchemaCandidate(
                name=node.name,
                file_path=str(self.file_path),
                line=node.lineno,
                signature=signature,
                func_context=func_context
            )
        )
        self.generic_visit(node)


def audit_candidate_with_llm(candidate: EngineSchemaCandidate) -> SchemaAuditResult:
    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)

    prompt = (
        f"File Path: {candidate.file_path}\n"
        f"Function Name: {candidate.name}\n"
        f"Signature: {candidate.signature}\n"
        f"Line Number: {candidate.line}\n\n"
        "Here is the function code:\n"
        "```python\n"
        f"{candidate.func_context}\n"
        "```\n\n"
        "Determine if this function signature is a 'SCHEMA_HAZARD' (non-compliant) or a 'FALSE_POSITIVE' (compliant or exempt helper)."
    )

    backoffs = [90.0, 120.0, 240.0]
    max_attempts = len(backoffs) + 1
    for attempt in range(1, max_attempts + 1):
        try:
            response = schema_audit_agent.run_sync(prompt, model_settings=ModelSettings(max_tokens=1024))
            return response.output
        except Exception as e:
            if attempt < max_attempts:
                sleep_time = backoffs[attempt - 1]
                print(f"WARNING: API call failed ({e}). Backing off for {sleep_time:.1f}s (attempt {attempt}/{max_attempts})...", file=sys.stderr)
                time.sleep(sleep_time)
            else:
                print(f"CRITICAL: API call failed after {max_attempts} attempts. Shutting down.", file=sys.stderr)
                sys.exit(1)


def generate_markdown_report(report: SchemaAuditReport, md_path: Path):
    with open(md_path, "w", encoding="utf-8") as out:
        out.write("# 🕵️ Engine Schema Compliance Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` engine files.\n\n")

        hazards = [r for r in report.audit_results if r.status == "SCHEMA_HAZARD"]
        if not hazards:
            out.write("🎉 *All engine functions are compliant! No schema hazards found.*\n")
        else:
            by_file = {}
            for result in report.audit_results:
                f = result.file_path
                by_file.setdefault(f, []).append(result)

            for f, list_results in sorted(by_file.items()):
                out.write(f"## 📂 `{f}`\n\n")
                for item in sorted(list_results, key=lambda x: x.line):
                    status_emoji = "🛑" if item.status == "SCHEMA_HAZARD" else "✅"
                    out.write(f"### {status_emoji} Line {item.line}: `{item.name}` in `{item.file_path}`\n")
                    out.write(f"- **Verdict**: `{item.status}`\n")
                    out.write(f"- **Severity**: `{item.severity}`\n")
                    out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")


def main():
    files = get_src2_files()
    # Filter only engine files
    engine_files = [f for f in files if "src2/engine" in str(f)]
    all_candidates = []
    file_contents = {}

    for file_path in engine_files:
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content

            tree = ast.parse(content, filename=path_str)
            extractor = FunctionDefExtractor(file_path, content)
            extractor.visit(tree)
            all_candidates.extend(extractor.candidates)
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    import argparse
    parser = argparse.ArgumentParser(description="Engine Schemas Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(all_candidates)
    print(f"Scan complete. Found {total_candidates} engine functions to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(all_candidates, 1):
            print(f"[{idx}] {cand.name} in {cand.file_path}:{cand.line} (Signature: {cand.signature})")
        sys.exit(0)

    report = SchemaAuditReport(scanned_files_count=len(engine_files))
    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "engine_schemas_audit.json"

    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    audit = SchemaAuditResult(**res)
                    existing_results[(res.get("file_path"), res.get("name"))] = audit
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)

    # Pre-populate report with existing results so we never lose them when overwriting incrementally
    report.audit_results = list(existing_results.values())

    # Sort all_candidates so that cached candidates are processed first
    all_candidates.sort(key=lambda c: 0 if (c.file_path, c.name) in existing_results else 1)

    md_path = output_dir / "engine_schemas_audit.md"

    for index, candidate in enumerate(all_candidates, 1):
        key = (candidate.file_path, candidate.name)
        if key in existing_results:
            print(f"[{index}/{total_candidates}] Skipping already audited candidate: {candidate.name} in {candidate.file_path}:{candidate.line}")
            existing_results[key].line = candidate.line
            continue

        print(f"[{index}/{total_candidates}] Auditing {candidate.name} in {candidate.file_path}:{candidate.line}...")
        try:
            audit = audit_candidate_with_llm(candidate)
            audit.file_path = candidate.file_path
            audit.line = candidate.line
            report.audit_results.append(audit)

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            print(f"CRITICAL: Auditing failed for {candidate.name}: {e}. Shutting down.", file=sys.stderr)
            sys.exit(1)

    generate_markdown_report(report, md_path)
    print(f"Rendered Markdown report saved to {md_path}")


if __name__ == "__main__":
    main()
