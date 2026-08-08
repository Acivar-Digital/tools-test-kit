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


class CircularDepCandidate(BaseModel):
    name: str = Field(description="The dependency cycle path representation.")
    file_path: str = Field(description="The entrypoint file of the cycle.")
    line: int = Field(description="The line number of the import causing the cycle.")
    cycle_path: list[str] = Field(description="The list of files forming the import cycle.")


class AuditResult(BaseModel):
    name: str = Field(description="The cycle path description.")
    file_path: str = Field(description="The entrypoint file path.")
    line: int = Field(description="The import line number.")
    status: str = Field(description="Verdict: 'CIRCULAR_DEP' or 'FALSE_POSITIVE'.")
    severity: str = Field(
        description="Severity: 'HIGH' (real loop causing runtime failures), 'LOW' (unused/dormant loop)."
    )
    reason: str = Field(
        description="A concise 1 to 2 sentence explanation of why this loop is a problem and how to resolve it."
    )
    updated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(),
        description="The ISO datetime string when this violation was audited or updated.",
    )


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
        "You are an expert software architect and static analyzer.\n"
        "Your task is to review a candidate circular dependency import loop flagged by static analysis.\n"
        "Verify if the import path creates a true circular import loop (CIRCULAR_DEP) that can cause runtime ImportErrors, "
        "or if it is a false positive (FALSE_POSITIVE) such as imports inside functions/methods (which are resolved lazily at runtime)."
    ),
)


class ImportExtractor(ast.NodeVisitor):
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.imports: list[tuple[str, int, bool]] = []  # (module_imported, line_no, is_local_inside_function)
        self.inside_function = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        old = self.inside_function
        self.inside_function = True
        self.generic_visit(node)
        self.inside_function = old

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        old = self.inside_function
        self.inside_function = True
        self.generic_visit(node)
        self.inside_function = old

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            self.imports.append((alias.name, node.lineno, self.inside_function))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module:
            self.imports.append((node.module, node.lineno, self.inside_function))
        self.generic_visit(node)


def find_cycles(graph: dict[str, list[tuple[str, int, bool]]]) -> list[CircularDepCandidate]:
    cycles = []
    visited = {}
    path = []

    def dfs(node: str):
        visited[node] = 1  # visiting
        path.append(node)

        for neighbor, line, is_local in graph.get(node, []):
            # Resolve relative imports/shorthands to module paths
            # Simple shorthand matching for src2 structure
            if not neighbor.startswith("src2."):
                # Try to map relative import or shorthands
                resolved = f"src2.{neighbor}"
                if resolved not in graph:
                    # Try packages/modules matching
                    for g_key in graph.keys():
                        if g_key.endswith(f".{neighbor}") or g_key == neighbor:
                            resolved = g_key
                            break
            else:
                resolved = neighbor

            if resolved in graph:
                if visited.get(resolved, 0) == 1:
                    # Found a cycle!
                    cycle_idx = path.index(resolved)
                    cycle_path = path[cycle_idx:] + [resolved]
                    cycles.append(
                        CircularDepCandidate(
                            name=" -> ".join(cycle_path), file_path=node, line=line, cycle_path=cycle_path
                        )
                    )
                elif visited.get(resolved, 0) == 0:
                    dfs(resolved)

        path.pop()
        visited[node] = 2  # fully visited

    for node in graph.keys():
        if visited.get(node, 0) == 0:
            dfs(node)

    return cycles


def audit_candidate_with_llm(candidate: CircularDepCandidate, file_contents: dict[str, str]) -> AuditResult:
    import time

    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)
    cand_file = candidate.file_path
    content = file_contents.get(cand_file, "")
    lines = content.splitlines()

    start_idx = max(0, candidate.line - 5)
    end_idx = min(len(lines), candidate.line + 10)
    code_snippet = "\n".join(
        f"{idx}: {line}" for idx, line in zip(range(start_idx + 1, end_idx + 1), lines[start_idx:end_idx])
    )

    prompt = (
        f"File Path: {cand_file}\n"
        f"Import Line: {candidate.line}\n"
        f"Cycle Path: {candidate.name}\n\n"
        "Here is the code block around this candidate import:\n"
        "```python\n"
        f"{code_snippet}\n"
        "```\n\n"
        "Audit if this represents a true circular dependency hazard (CIRCULAR_DEP) or a lazy/safe functional import (FALSE_POSITIVE)."
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
        out.write("# 🕵️ Circular Dependency Audit Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if not report.audit_results:
            out.write("🎉 *No circular dependencies found! Clean import DAG.*\n")
        else:
            by_file = {}
            for result in report.audit_results:
                f = result.file_path
                by_file.setdefault(f, []).append(result)

            for f, list_results in sorted(by_file.items()):
                out.write(f"## 📂 `{f}`\n\n")
                for item in sorted(list_results, key=lambda x: x.line):
                    status_emoji = "🛑" if item.status == "CIRCULAR_DEP" else "✅"
                    out.write(f"### {status_emoji} Line {item.line}: `{item.name}`\n")
                    out.write(f"- **Verdict**: `{item.status}`\n")
                    out.write(f"- **Severity**: `{item.severity}`\n")
                    out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")


def main():
    files = get_src2_files()
    graph = {}
    file_contents = {}

    for file_path in files:
        # Convert path to module name, e.g. src2/engine/prompt_maker.py -> src2.engine.prompt_maker
        module_path = str(file_path.with_suffix("")).replace("/", ".")
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content

            tree = ast.parse(content, filename=path_str)
            extractor = ImportExtractor(file_path)
            extractor.visit(tree)
            graph[module_path] = extractor.imports
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    candidates = find_cycles(graph)
    import argparse
    parser = argparse.ArgumentParser(description="Circular Dependencies Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(candidates)
    print(f"Scan complete. Found {total_candidates} candidate circular dependency import loops to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(candidates, 1):
            mapped_file = cand.file_path.replace(".", "/") + ".py"
            print(f"[{idx}] {cand.name} in {mapped_file}:{cand.line}")
        sys.exit(0)

    report = AuditReport(scanned_files_count=len(files))
    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "circular_deps_audit.json"
    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    existing_results[(res.get("file_path"), res.get("line"), res.get("name"))] = res
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)
    md_path = output_dir / "circular_deps_audit.md"

    for index, candidate in enumerate(candidates, 1):
        # Map module name back to actual file path for display
        mapped_file = candidate.file_path.replace(".", "/") + ".py"
        key = (mapped_file, candidate.line, candidate.name)
        if key in existing_results:
            print(f"[{index}/{total_candidates}] Skipping already audited cycle: {candidate.name}")
            res_data = existing_results[key]
            audit = AuditResult(**res_data)
            audit.updated_at = datetime.now().astimezone().isoformat()
            report.audit_results.append(audit)
            continue
        print(f"[{index}/{total_candidates}] Auditing cycle {candidate.name}...")
        try:
            candidate.file_path = mapped_file
            audit = audit_candidate_with_llm(candidate, file_contents)
            audit.file_path = mapped_file
            audit.line = candidate.line
            report.audit_results.append(audit)

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            print(f"WARNING: Auditing failed for cycle: {e}", file=sys.stderr)

    generate_markdown_report(report, md_path)
    print(f"Rendered Markdown report saved to {md_path}")


if __name__ == "__main__":
    main()
