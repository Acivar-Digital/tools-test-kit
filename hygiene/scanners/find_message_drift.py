import ast
import sys
from datetime import datetime
from pathlib import Path

import yaml

from _bootstrap import pkg_root, target_root  # noqa: F401,E402

from pydantic import BaseModel, Field  # noqa: E402
from utils import get_src2_files  # noqa: E402

# Paths
BASE_DIR = target_root  # scanned repo root (TARGET_ROOT env; default = repo root)
MESSAGES_PATH = BASE_DIR / "src2" / "interfaces" / "telegram" / "messages.yaml"
SRC_DIR = BASE_DIR / "src2"


class MessageDriftCandidate(BaseModel):
    name: str = Field(description="The message key.")
    file_path: str = Field(description="The source file referencing this key, or messages.yaml.")
    line: int = Field(description="Line number of referencing call.")
    type: str = Field(
        description="Type: missing_message (in code but not in YAML) or unused_message (in YAML but not in code)."
    )


class AuditResult(BaseModel):
    name: str = Field(description="The message key name.")
    file_path: str = Field(description="The file path where drift is detected.")
    line: int = Field(description="The line number.")
    type: str = Field(description="Type: missing_message or unused_message.")
    status: str = Field(description="Verdict: 'DRIFT_VIOLATION' or 'FALSE_POSITIVE'.")
    severity: str = Field(
        description="Severity: 'HIGH' (missing user message in telegram translation), 'LOW' (unused message key)."
    )
    reason: str = Field(description="A concise 1 to 2 sentence explanation of why this represents drift.")
    updated_at: str = Field(
        default_factory=lambda: datetime.now().astimezone().isoformat(),
        description="The ISO datetime string when audited.",
    )


class AuditReport(BaseModel):
    scanned_files_count: int = Field(description="Total number of Python files scanned.")
    audit_results: list[AuditResult] = Field(default_factory=list)
    failed_audits: list[dict] = Field(default_factory=list)


def load_messages() -> dict:
    """Load messages.yaml as a dictionary."""
    if not MESSAGES_PATH.exists():
        return {}
    with open(MESSAGES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_messages(data: dict) -> None:
    """Write the updated messages back to the yaml file preserving order."""
    with open(MESSAGES_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)


def find_message_keys_in_file(file_path: Path) -> list[tuple[str, int]]:
    """Parse a python file and return all message keys referenced via
    `text_manager.get("key")` or `text_manager["key"]` calls with line numbers.
    """
    with open(file_path, encoding="utf-8", errors="ignore") as f:
        source = f.read()
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    keys = []

    class MessageVisitor(ast.NodeVisitor):
        def visit_Call(self, node: ast.Call):
            # text_manager.get("key")
            if (
                isinstance(node.func, ast.Attribute)
                and getattr(node.func.value, "id", None) == "text_manager"
                and node.func.attr == "get"
            ):
                if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                    keys.append((node.args[0].value, node.lineno))
            self.generic_visit(node)

        def visit_Subscript(self, node: ast.Subscript):
            # text_manager["key"]
            if isinstance(node.value, ast.Name) and node.value.id == "text_manager":
                if isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, str):
                    keys.append((node.slice.value, node.lineno))
            self.generic_visit(node)

    MessageVisitor().visit(tree)
    return keys


def collect_usage(files: list[Path]) -> dict[str, list[tuple[str, int]]]:
    """Walk through files and build a mapping of message key → list of (file_path, line_no) occurrences."""
    usage = {}
    for file_path in files:
        if file_path.suffix != ".py":
            continue
        occurrences = find_message_keys_in_file(file_path)
        path_str = str(file_path)
        for key, line in occurrences:
            usage.setdefault(key, []).append((path_str, line))
    return usage


def audit_candidate_locally(candidate: MessageDriftCandidate) -> AuditResult:
    if candidate.type == "missing_message":
        status = "DRIFT_VIOLATION"
        severity = "HIGH"
        reason = f"Message key `{candidate.name}` is referenced in codebase but missing from `messages.yaml`."
    else:
        status = "FALSE_POSITIVE"  # Unused messages are not blocking failures, just warnings
        severity = "LOW"
        reason = f"Message key `{candidate.name}` is defined in `messages.yaml` but not active in codebase."

    return AuditResult(
        name=candidate.name,
        file_path=candidate.file_path,
        line=candidate.line,
        type=candidate.type,
        status=status,
        severity=severity,
        reason=reason,
    )


def generate_markdown_report(report: AuditReport, md_path: Path):
    with open(md_path, "w", encoding="utf-8") as out:
        out.write("# 🕵️ Telegram Message Keys Drift Report\n\n")
        out.write(f"Scanned `{report.scanned_files_count}` files in `src2/`.\n\n")

        if not report.audit_results:
            out.write("🎉 *No message key drift detected! messages.yaml is perfectly synchronized.*\n")
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
    messages = load_messages()
    usage = collect_usage(files)

    # 1. Generate comments/usage sync back to YAML
    serial_counter = 1
    for key, data in messages.items():
        if not isinstance(data, dict):
            messages[key] = {"value": data}
            data = messages[key]
        data["_usage"] = []
        occurrences = usage.get(key, [])
        # Deduplicate file references for yaml usage comments
        used_files = sorted(list(set(occ[0] for occ in occurrences)))
        for module_path in used_files:
            comment = f"# {serial_counter:04d} {module_path}"
            data["_usage"].append(comment)
            serial_counter += 1
    save_messages(messages)
    print("Synced YAML messages metadata with codebase usage.")

    # 2. Compile Candidates
    candidates = []

    # Missing message keys (in code, missing in YAML)
    for key, occurrences in usage.items():
        if key not in messages:
            for path_str, line in occurrences:
                candidates.append(
                    MessageDriftCandidate(name=key, file_path=path_str, line=line, type="missing_message")
                )

    # Unused message keys (in YAML, missing in code)
    for key in messages:
        if key not in usage:
            candidates.append(
                MessageDriftCandidate(
                    name=key, file_path="src2/interfaces/telegram/messages.yaml", line=1, type="unused_message"
                )
            )

    import argparse
    parser = argparse.ArgumentParser(description="Message Drift Scanner")
    parser.add_argument("--scripts", action="store_true", help="Run only static checks and print candidates")
    args = parser.parse_args()

    total_candidates = len(candidates)
    print(f"Scan complete. Found {total_candidates} message drift candidates to audit.")

    if args.scripts:
        print("\nCandidates found:")
        for idx, cand in enumerate(candidates, 1):
            print(f"[{idx}] {cand.name} ({cand.type}) in {cand.file_path}:{cand.line}")
        sys.exit(0)

    report = AuditReport(scanned_files_count=len(files))
    output_dir = pkg_root / "reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "message_drift_audit.json"
    md_path = output_dir / "message_drift_audit.md"

    for index, candidate in enumerate(candidates, 1):
        print(f"[{index}/{total_candidates}] Auditing {candidate.name} in {candidate.file_path}:{candidate.line}...")
        try:
            audit = audit_candidate_locally(candidate)
            report.audit_results.append(audit)
        except Exception as e:
            print(f"WARNING: Auditing failed for candidate {candidate.name}: {e}", file=sys.stderr)

    with open(json_path, "w", encoding="utf-8") as f:
        f.write(report.model_dump_json(indent=2))

    generate_markdown_report(report, md_path)
    print(f"Rendered Markdown report saved to {md_path}")


if __name__ == "__main__":
    main()
