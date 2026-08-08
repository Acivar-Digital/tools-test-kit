#!/usr/bin/env python3
import argparse
import re
import sys
from pathlib import Path

from pydantic_ai import Agent  # noqa: E402
from control import ControlSheet, REPO_ROOT  # noqa: E402


def estimate_tokens(text: str) -> int:
    """Apprx token calculation for Gemma 4 SentencePiece model."""
    return int(len(text) / 3.8)

def extract_lines(lines: list[str], start: int, end: int) -> str:
    """Extract specified line range (1-indexed)."""
    s = max(0, start - 1)
    e = min(len(lines), end)
    extracted = []
    for idx in range(s, e):
        extracted.append(f"{idx + 1}: {lines[idx]}")
    return "\n".join(extracted)

def extract_pattern_context(lines: list[str], pattern: str) -> str:
    """Find all matching lines and extract surrounding context windows."""
    regex = re.compile(pattern, re.IGNORECASE)
    matches = []

    for idx, line in enumerate(lines):
        if regex.search(line):
            matches.append(idx)

    if not matches:
        return f"No matches found for pattern: {pattern}"

    extracted_blocks = []
    visited_lines = set()

    for m_idx in matches:
        start = max(0, m_idx - 5)
        end = min(len(lines), m_idx + 10)

        block = []
        for idx in range(start, end):
            if idx in visited_lines:
                continue
            visited_lines.add(idx)
            prefix = ">>> " if idx == m_idx else "    "
            block.append(f"{idx + 1}:{prefix}{lines[idx]}")

        if block:
            extracted_blocks.append("\n".join(block))

    return "\n\n--- Context Match ---\n\n".join(extracted_blocks)

def main():
    parser = argparse.ArgumentParser(description="Investigate file code/patterns using Gemma 4 model.")
    parser.add_argument("--filename", required=True, help="Path to the file to investigate.")
    parser.add_argument("--query", required=True, help="Specific question or instruction for the investigation.")
    parser.add_argument("--lines", help="Line range to inspect, e.g., '10-100' or single number '50' (1 to 50).")
    parser.add_argument("--pattern", help="Regex pattern to grep for context extraction.")

    args = parser.parse_args()

    # Resolve filename path (sandboxed to REPO_ROOT from control config)
    file_path = Path(args.filename)
    if not file_path.is_absolute():
        file_path = (REPO_ROOT / file_path).resolve()

    if not file_path.exists():
        print(f"Error: File not found at {file_path}")
        sys.exit(1)

    # Sandbox guard: never operate outside REPO_ROOT.
    if not file_path.is_relative_to(REPO_ROOT):
        print(f"Error: Path escape detected: {file_path} (outside {REPO_ROOT})")
        sys.exit(1)

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    lines = content.splitlines()
    code_segment = ""
    mode_desc = ""

    if args.lines:
        match = re.match(r"^(\d+)-(\d+)$", args.lines.strip())
        if match:
            start, end = int(match.group(1)), int(match.group(2))
        else:
            try:
                start, end = 1, int(args.lines.strip())
            except ValueError:
                print(f"Invalid lines format: {args.lines}. Use 'start-end' or a single integer.")
                sys.exit(1)
        code_segment = extract_lines(lines, start, end)
        mode_desc = f"lines {start}-{end}"
    elif args.pattern:
        code_segment = extract_pattern_context(lines, args.pattern)
        mode_desc = f"grep pattern '{args.pattern}'"
    else:
        # Default to entire file (truncated to token limit if necessary)
        code_segment = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
        mode_desc = "full file"

    # Token safety limit checks (12K tokens max context input)
    tokens = estimate_tokens(code_segment)
    if tokens > 12000:
        print(f"⚠️ Warning: Context segment is too large ({tokens} est. tokens). Truncating context to fit 12K limits.")
        # Slice characters to safely fit
        code_segment = code_segment[:int(12000 * 3.8)] + "\n... [Context truncated due to 12K limit] ..."

    # Set up codebase model (sandboxed: CONTROL_SHEET.codebase_model)
    model = ControlSheet.codebase_model
    investigate_agent = Agent(
        model,
        system_prompt=(
            "You are a surgical codebase investigation tool. Your task is to analyze the provided code context "
            "and provide exact, copy-pasteable solutions. DO NOT output conversational filler.\n"
            "Structure your output cleanly in Markdown:\n"
            "1. **Analysis**: Extremely concise summary (max 3 bullet points).\n"
            "2. **Proposed Solution**: Exact code diff or drop-in code block replacement."
        )
    )

    prompt = f"File: {args.filename} (mode: {mode_desc})\n"
    if args.query:
        prompt += f"Query/Instruction: {args.query}\n"
    prompt += f"\n```python\n{code_segment}\n```"

    print(f"🔍 Investigating {file_path.name} ({mode_desc}). Calling codebase model...")
    sys.stdout.flush()

    try:
        res = investigate_agent.run_sync(prompt)
        print("\n" + "="*80)
        print(res.output)
        print("="*80)
    except Exception as e:
        print(f"\nFailed to analyze with codebase model: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
