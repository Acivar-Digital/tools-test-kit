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


class DuplicationCandidate(BaseModel):
    name: str = Field(description="The duplicated code block preview.")
    file_a: str = Field(description="First file containing the duplicated block.")
    line_a: int = Field(description="Line number in File A.")
    file_b: str = Field(description="Second file containing the duplicated block.")
    line_b: int = Field(description="Line number in File B.")
    block_length: int = Field(description="Number of identical lines.")


class AuditResult(BaseModel):
    name: str = Field(description="Description of the duplicated code block.")
    file_path: str = Field(description="First file path.")
    line: int = Field(description="Line number.")
    status: str = Field(description="Verdict: 'DUPLICATION' or 'FALSE_POSITIVE'.")
    severity: str = Field(description="Severity: 'HIGH' (critical business math/logic cloned), 'LOW' (standard boilerplate).")
    reason: str = Field(description="A concise 1 to 2 sentence explanation of why this is a duplication violation and how to share it.")
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
        "You are an expert software engineer and code quality auditor.\n"
        "Your task is to review a candidate duplicated block of code (identical block of lines found in multiple files) flagged by static analysis.\n"
        "Determine if the block represents a true duplication (DUPLICATION) that should be refactored into a shared utility function to comply with DRY (Don't Repeat Yourself) principles, "
        "or if it is a false positive (FALSE_POSITIVE) like standard imports, boilerplates, class properties, or schema field declarations."
    ),
)


def find_duplications(file_contents: dict[str, str], min_lines: int = 8) -> list[DuplicationCandidate]:
    candidates = []
    file_paths = list(file_contents.keys())

    # Compile files line lists
    file_lines = {f: [line.strip() for line in content.splitlines()] for f, content in file_contents.items()}

    for i in range(len(file_paths)):
        for j in range(i + 1, len(file_paths)):
            file_a = file_paths[i]
            file_b = file_paths[j]
            lines_a = file_lines[file_a]
            lines_b = file_lines[file_b]

            # Find matching blocks

            idx_a = 0
            while idx_a < len(lines_a):
                line_a = lines_a[idx_a]
                # Skip empty lines and imports
                if not line_a or line_a.startswith("import") or line_a.startswith("from"):
                    idx_a += 1
                    continue

                idx_b = 0
                while idx_b < len(lines_b):
                    line_b = lines_b[idx_b]
                    if line_a == line_b and line_a not in ("", "pass", "return"):
                        # Count matches
                        k = 0
                        while (idx_a + k < len(lines_a)) and (idx_b + k < len(lines_b)):
                            la = lines_a[idx_a + k]
                            lb = lines_b[idx_b + k]
                            if la == lb and la not in ("", "pass", "return"):
                                k += 1
                            else:
                                break

                        if k >= min_lines:
                            candidates.append(
                                DuplicationCandidate(
                                    name=f"Duplicate Block ({k} lines)",
                                    file_a=file_a,
                                    line_a=idx_a + 1,
                                    file_b=file_b,
                                    line_b=idx_b + 1,
                                    block_length=k
                                )
                            )
                            idx_a += k - 1
                            break
                    idx_b += 1
                idx_a += 1
    return candidates


def audit_candidate_with_llm(candidate: DuplicationCandidate, file_contents: dict[str, str]) -> AuditResult:
    import time

    # Firing takes a 4-second pause to prevent rate-limiting/overload
    print("Pausing 4 seconds before next audit call...")
    time.sleep(4.0)
    content_a = file_contents.get(candidate.file_a, "").splitlines()
    snippet = "\n".join(content_a[candidate.line_a - 1 : candidate.line_a - 1 + candidate.block_length])

    prompt = (
        f"File A: {candidate.file_a} (Line {candidate.line_a})\n"
        f"File B: {candidate.file_b} (Line {candidate.line_b})\n"
        f"Duplicate Line Count: {candidate.block_length}\n\n"
        "Here is the duplicated code block:\n"
        "```python\n"
        f"{snippet}\n"
        "```\n\n"
        "Audit if this represents a true copy-paste logic violation (DUPLICATION) or standard boilerplate (FALSE_POSITIVE)."
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
        out.write("# 🕵️ Code Duplication & Copypasta Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if not report.audit_results:
            out.write("🎉 *No code duplications found! Codebase is perfectly DRY.*\n")
        else:
            for item in sorted(report.audit_results, key=lambda x: x.line):
                status_emoji = "🛑" if item.status == "DUPLICATION" else "✅"
                out.write(f"### {status_emoji} `{item.name}`\n")
                out.write(f"- **File A**: `{item.file_path}` (Line {item.line})\n")
                out.write(f"- **Verdict**: `{item.status}`\n")
                out.write(f"- **Severity**: `{item.severity}`\n")
                out.write(f"- **Reasoning**: {item.reason}\n\n")
                out.write("---\n\n")


def main():
    files = get_src2_files()
    file_contents = {}

    for file_path in files:
        path_str = str(file_path)
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                content = f.read()
                file_contents[path_str] = content
        except Exception as e:
            print(f"Error parsing {path_str}: {e}", file=sys.stderr)

    candidates = find_duplications(file_contents)
    import argparse
    parser = argparse.ArgumentParser(description="Duplication Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(candidates)
    print(f"Scan complete. Found {total_candidates} candidate duplications to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(candidates, 1):
            print(f"[{idx}] Block {cand.name} duplicated between:\n    - {cand.file_a}:{cand.line_a}\n    - {cand.file_b}:{cand.line_b}")
        sys.exit(0)

    report = AuditReport(scanned_files_count=len(files))
    output_dir = Path("kit-hygiene/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "duplication_audit.json"
    existing_results = {}
    if json_path.exists():
        try:
            with open(json_path, encoding="utf-8") as f:
                existing_data = json.load(f)
                for res in existing_data.get("audit_results", []):
                    existing_results[(res.get("file_path"), res.get("line"), res.get("name"))] = res
        except Exception as e:
            print(f"WARNING: Failed to load existing JSON report: {e}", file=sys.stderr)
    md_path = output_dir / "duplication_audit.md"

    for index, candidate in enumerate(candidates, 1):
        key = (candidate.file_a, candidate.line_a, candidate.name)
        if key in existing_results:
            print(f"[{index}/{total_candidates}] Skipping already audited duplication in {candidate.file_a}:{candidate.line_a}")
            res_data = existing_results[key]
            audit = AuditResult(**res_data)
            audit.updated_at = datetime.now().astimezone().isoformat()
            report.audit_results.append(audit)
            continue
        print(f"[{index}/{total_candidates}] Auditing duplicate block in {candidate.file_a}:{candidate.line_a}...")
        try:
            audit = audit_candidate_with_llm(candidate, file_contents)
            audit.file_path = candidate.file_a
            audit.line = candidate.line_a
            report.audit_results.append(audit)

            with open(json_path, "w", encoding="utf-8") as f:
                f.write(report.model_dump_json(indent=2))
        except Exception as e:
            print(f"WARNING: Auditing failed for duplicate block: {e}", file=sys.stderr)

    generate_markdown_report(report, md_path)
    print(f"Rendered Markdown report saved to {md_path}")


if __name__ == "__main__":
    main()
