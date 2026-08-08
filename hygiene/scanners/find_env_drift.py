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


class EnvDriftCandidate(BaseModel):
    name: str = Field(description="The name of the environment variable.")
    file_path: str = Field(description="The source file path relative to workspace root.")
    line: int = Field(description="The starting line number of the candidate block.")
    type: str = Field(description="Type: undocumented (used in code, missing in example) or unused_example (in example, not in code).")


class AuditResult(BaseModel):
    name: str = Field(description="The name of the env variable.")
    file_path: str = Field(description="The file path of the candidate.")
    line: int = Field(description="The line number of the candidate.")
    type: str = Field(description="Type: undocumented or unused_example.")
    status: str = Field(description="Verdict: 'DRIFT_VIOLATION' or 'FALSE_POSITIVE'.")
    severity: str = Field(description="Severity: 'HIGH' (critical secret/config missing from example), 'LOW' (minor diagnostic flag).")
    reason: str = Field(description="A concise 1 to 2 sentence explanation of why this represents env drift or a false positive.")
    updated_at: str = Field(default_factory=lambda: datetime.now().astimezone().isoformat(), description="The ISO datetime string when this violation was audited or updated.")


class AuditReport(BaseModel):
    scanned_files_count: int = Field(description="Total number of Python files scanned.")
    audit_results: list[AuditResult] = Field(default_factory=list)
    failed_audits: list[dict] = Field(default_factory=list)


scanner_model = CONTROL_SHEET.scanner_model

audit_agent = Agent(
    scanner_model,
    output_type=AuditResult,
    retries=3,
    system_prompt=(
        "You are an expert devops and systems auditor.\n"
        "Your task is to review a candidate environment variable drift violation (where a variable is referenced in code but missing from `.env.example` or vice versa).\n"
        "Inspect the context and determine if it is a true environment drift violation (DRIFT_VIOLATION) that breaks staging/deployments, "
        "or if it is a false positive (FALSE_POSITIVE) such as standard library fallbacks (e.g., PORT) or system-level settings."
    ),
)


class EnvVarExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.env_vars: list[tuple[str, int]] = []

    def visit_Call(self, node: ast.Call):
        # Look for os.getenv("VAR") or os.environ.get("VAR")
        is_env_call = False
        var_name = ""
        if isinstance(node.func, ast.Attribute) and node.func.attr == "getenv":
            is_env_call = True
        elif isinstance(node.func, ast.Attribute) and node.func.attr == "get":
            # Check if value is os.environ
            if isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "environ":
                is_env_call = True

        if is_env_call and node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
            var_name = node.args[0].value
            self.env_vars.append((var_name, node.lineno))

        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript):
        # Look for os.environ["VAR"]
        if isinstance(node.value, ast.Attribute) and node.value.attr == "environ":
            if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                self.env_vars.append((node.slice.value, node.lineno))
        self.generic_visit(node)


def load_env_example_vars() -> set[str]:
    example_path = Path(".env.example")
    vars_in_example = set()
    if example_path.exists():
        try:
            with open(example_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        parts = line.split("=", 1)
                        if parts:
                            vars_in_example.add(parts[0].strip())
        except Exception as e:
            print(f"Warning: Could not read .env.example: {e}", file=sys.stderr)
    return vars_in_example


def audit_candidate_with_llm(candidate: EnvDriftCandidate, file_contents: dict[str, str]) -> AuditResult:
    import time

    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)
    cand_file = candidate.file_path
    content = file_contents.get(cand_file, "")
    lines = content.splitlines()

    start_idx = max(0, candidate.line - 5)
    end_idx = min(len(lines), candidate.line + 10)
    code_snippet = "\n".join(f"{idx}: {line}" for idx, line in zip(range(start_idx + 1, end_idx + 1), lines[start_idx:end_idx]))

    prompt = (
        f"File Path: {cand_file}\n"
        f"Variable Name: {candidate.name}\n"
        f"Type of Drift: {candidate.type}\n"
        f"Target Line: {candidate.line}\n\n"
        "Here is the code block around this candidate:\n"
        "```python\n"
        f"{code_snippet}\n"
        "```\n\n"
        "Audit if this represents a true env drift violation (DRIFT_VIOLATION) or a standard library fallback (FALSE_POSITIVE)."
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
    with open(md_path, "w", encoding="utf-8") as out:
        out.write("# 🕵️ Environment Variables Drift Audit Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if not report.audit_results:
            out.write("🎉 *No environment drift detected! .env.example matches the codebase.*\n")
        else:
            by_file = {}
            for result in report.audit_results:
                f = result.file_path
                by_file.setdefault(f, []).append(result)

            for f, list_results in sorted(by_file.items()):
                out.write(f"## 📂 `{f}`\n\n")
                for item in sorted(list_results, key=lambda x: x.line):
                    status_emoji = "🛑" if item.status == "DRIFT_VIOLATION" else "✅"
                    out.write(f"### {status_emoji} Line {item.line}: `{item.name}` ({item.type})\n")
                    out.write(f"- **Verdict**: `{item.status}`\n")
                    out.write(f"- **Severity**: `{item.severity}`\n")
                    out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")


def main():
    files = get_src2_files()
    example_vars = load_env_example_vars()
    file_contents = {}
    code_vars = {}

    for file_path in files:
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content

            tree = ast.parse(content, filename=path_str)
            extractor = EnvVarExtractor(file_path)
            extractor.visit(tree)
            for var_name, line in extractor.env_vars:
                code_vars.setdefault(var_name, []).append((path_str, line))
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    candidates = []
    # 1. Undocumented variables (in code, missing in example)
    for var_name, occurrences in code_vars.items():
        if var_name not in example_vars:
            for path_str, line in occurrences:
                candidates.append(
                    EnvDriftCandidate(
                        name=var_name,
                        file_path=path_str,
                        line=line,
                        type="undocumented"
                    )
                )

    # 2. Unused example variables (in example, missing in code)
    for var_name in example_vars:
        if var_name not in code_vars:
            candidates.append(
                EnvDriftCandidate(
                    name=var_name,
                    file_path=".env.example",
                    line=1,
                    type="unused_example"
                )
            )

    import argparse
    parser = argparse.ArgumentParser(description="Env Drift Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(candidates)
    print(f"Scan complete. Found {total_candidates} environment drift candidates to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(candidates, 1):
            print(f"[{idx}] {cand.name} ({cand.type}) in {cand.file_path}:{cand.line}")
        sys.exit(0)

    report = AuditReport(scanned_files_count=len(files))
    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "env_drift_audit.json"
    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    existing_results[(res.get("file_path"), res.get("line"), res.get("name"))] = res
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)
    md_path = output_dir / "env_drift_audit.md"

    for index, candidate in enumerate(candidates, 1):
        key = (candidate.file_path, candidate.line, candidate.name)
        if key in existing_results:
            print(f"[{index}/{total_candidates}] Skipping already audited candidate: {candidate.name} in {candidate.file_path}:{candidate.line}")
            res_data = existing_results[key]
            audit = AuditResult(**res_data)
            audit.updated_at = datetime.now().astimezone().isoformat()
            report.audit_results.append(audit)
            continue
        print(f"[{index}/{total_candidates}] Auditing {candidate.name} in {candidate.file_path}:{candidate.line}...")
        try:
            # For unused_example, context is empty
            audit = audit_candidate_with_llm(candidate, file_contents)
            audit.file_path = candidate.file_path
            audit.line = candidate.line
            audit.type = candidate.type
            report.audit_results.append(audit)

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            print(f"WARNING: Auditing failed for {candidate.name}: {e}", file=sys.stderr)

    generate_markdown_report(report, md_path)
    print(f"Rendered Markdown report saved to {md_path}")


if __name__ == "__main__":
    main()
