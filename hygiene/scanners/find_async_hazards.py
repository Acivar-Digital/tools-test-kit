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


class AsyncHazardCandidate(BaseModel):
    name: str = Field(description="The name of the blocking call.")
    file_path: str = Field(description="The source file path relative to workspace root.")
    line: int = Field(description="The line number where the blocking call is found.")
    func_context: str = Field(description="The async function enclosing the blocking call.")


class AuditResult(BaseModel):
    name: str = Field(description="The name of the call audited.")
    file_path: str = Field(description="The file path of the candidate.")
    line: int = Field(description="The line number of the candidate.")
    status: str = Field(description="Verdict: 'ASYNC_HAZARD' or 'FALSE_POSITIVE'.")
    severity: str = Field(description="Severity: 'HIGH' (blocks event loop on hot API path), 'LOW' (infrequent/startup task).")
    reason: str = Field(description="A concise 1 to 2 sentence explanation of why it is a hazard or a false positive.")
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
        "You are an expert asynchronous programming auditor.\n"
        "Your task is to review a candidate event loop blocker (blocking synchronous call inside an async function) flagged by static analysis.\n"
        "Determine if the synchronous call represents a true async hazard (ASYNC_HAZARD) that blocks the asyncio event loop on active paths, "
        "or if it is a false positive (FALSE_POSITIVE) like synchronous calls executed inside standard executors/threads or startup-only tasks."
    ),
)


class AsyncHazardExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.candidates: list[AsyncHazardCandidate] = []
        self.current_async_func = None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        old_func = self.current_async_func
        self.current_async_func = node.name
        self.generic_visit(node)
        self.current_async_func = old_func

    def visit_Call(self, node: ast.Call):
        if self.current_async_func:
            is_hazard = False
            name = ""

            # 1. Check for time.sleep
            if isinstance(node.func, ast.Attribute) and node.func.attr == "sleep":
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "time":
                    is_hazard = True
                    name = "time.sleep"

            # 2. Check for requests HTTP calls
            elif isinstance(node.func, ast.Attribute) and node.func.attr in ["get", "post", "put", "delete", "request"]:
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "requests":
                    is_hazard = True
                    name = f"requests.{node.func.attr}"

            # 3. Check for standard open() I/O
            elif isinstance(node.func, ast.Name) and node.func.id == "open":
                is_hazard = True
                name = "open"

            # 4. Check for subprocess synchronous runs
            elif isinstance(node.func, ast.Attribute) and node.func.attr in ["run", "popen", "call", "check_output"]:
                if isinstance(node.func.value, ast.Name) and node.func.value.id == "subprocess":
                    is_hazard = True
                    name = f"subprocess.{node.func.attr}"

            if is_hazard:
                self.candidates.append(
                    AsyncHazardCandidate(
                        name=name,
                        file_path=str(self.file_path),
                        line=node.lineno,
                        func_context=self.current_async_func
                    )
                )

        self.generic_visit(node)


def audit_candidate_with_llm(candidate: AsyncHazardCandidate, file_contents: dict[str, str]) -> AuditResult:
    import time

    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)
    cand_file = candidate.file_path
    content = file_contents.get(cand_file, "")
    lines = content.splitlines()

    start_idx = max(0, candidate.line - 10)
    end_idx = min(len(lines), candidate.line + 20)
    code_snippet = "\n".join(f"{idx}: {line}" for idx, line in zip(range(start_idx + 1, end_idx + 1), lines[start_idx:end_idx]))

    prompt = (
        f"File Path: {cand_file}\n"
        f"Enclosing Async Function: {candidate.func_context}\n"
        f"Blocking Call: {candidate.name}\n"
        f"Line Number: {candidate.line}\n\n"
        "Here is the code block around this candidate:\n"
        "```python\n"
        f"{code_snippet}\n"
        "```\n\n"
        "Audit if this represents a true event loop hazard (ASYNC_HAZARD) or a safe synchronous call (FALSE_POSITIVE)."
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
        out.write("# 🕵️ Async Hazards & Event Loop Blockers Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if not report.audit_results:
            out.write("🎉 *No async hazards found! All event loop paths look clean.*\n")
        else:
            by_file = {}
            for result in report.audit_results:
                f = result.file_path
                by_file.setdefault(f, []).append(result)

            for f, list_results in sorted(by_file.items()):
                out.write(f"## 📂 `{f}`\n\n")
                for item in sorted(list_results, key=lambda x: x.line):
                    status_emoji = "🛑" if item.status == "ASYNC_HAZARD" else "✅"
                    out.write(f"### {status_emoji} Line {item.line}: `{item.name}` in `{item.file_path}`\n")
                    out.write(f"- **Verdict**: `{item.status}`\n")
                    out.write(f"- **Severity**: `{item.severity}`\n")
                    out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")


def main():
    files = get_src2_files()
    all_candidates = []
    file_contents = {}

    for file_path in files:
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content

            tree = ast.parse(content, filename=path_str)
            extractor = AsyncHazardExtractor(file_path)
            extractor.visit(tree)
            all_candidates.extend(extractor.candidates)
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    import argparse
    parser = argparse.ArgumentParser(description="Async Hazards Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(all_candidates)
    print(f"Scan complete. Found {total_candidates} candidate async hazards to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(all_candidates, 1):
            print(f"[{idx}] {cand.name} in {cand.file_path}:{cand.line} (enclosed by {cand.func_context})")
        sys.exit(0)

    report = AuditReport(scanned_files_count=len(files))
    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "async_hazards_audit.json"
    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    existing_results[(res.get("file_path"), res.get("line"), res.get("name"))] = res
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)
    md_path = output_dir / "async_hazards_audit.md"

    for index, candidate in enumerate(all_candidates, 1):
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
            audit = audit_candidate_with_llm(candidate, file_contents)
            audit.file_path = candidate.file_path
            audit.line = candidate.line
            report.audit_results.append(audit)

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            print(f"WARNING: Auditing failed for {candidate.name}: {e}", file=sys.stderr)

    generate_markdown_report(report, md_path)
    print(f"Rendered Markdown report saved to {md_path}")


if __name__ == "__main__":
    main()
