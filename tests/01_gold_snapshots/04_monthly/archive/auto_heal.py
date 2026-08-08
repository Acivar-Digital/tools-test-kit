import re
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

# Add project root to path so we can import from admin and src2
sys.path.append(str(Path(__file__).resolve().parents[3]))

from admin.controls.controls import gemma_4_31b_it


# 1. Define the Agent's Dependencies to track iteration state
class DebuggerDeps:
    def __init__(self, test_command: str, max_iterations: int = 5):
        self.test_command = test_command
        self.max_iterations = max_iterations
        self.current_iteration = 0
        self.last_run_output = ""


# 2. Define the Structured Output from the Agent for clear reasoning
class FixAction(BaseModel):
    reasoning: str = Field(description="Why this error is happening and how to fix it.")
    file_path: str = Field(description="Relative path to the file to modify.")
    explanation_of_change: str = Field(description="A description of the changes being made.")


# 3. Instantiate the Agent using the pre-configured Gemma model
agent = Agent(
    gemma_4_31b_it,
    deps_type=DebuggerDeps,
    result_type=FixAction,
    system_prompt=(
        "You are an elite, autonomous auto-healing debugger agent.\n"
        "Your goal is to fix the codebase so that the test suite passes.\n"
        "1. Analyze the traceback and error message provided.\n"
        "2. Use the `read_file` tool to inspect the failing file and surrounding lines.\n"
        "3. Use the `apply_fix` tool to surgically modify the file.\n"
        "4. Explain your reasoning and the change in your final response.\n"
        "STRICT RULES:\n"
        "- Do not guess. Read the file first before editing.\n"
        "- Make the smallest possible surgical change to fix the issue.\n"
        "- Never modify files in the `src/` directory (only `src2/` or tests)."
    ),
)

# =====================================================================
# Tools
# =====================================================================


@agent.tool
def read_file(ctx: RunContext[DebuggerDeps], relative_path: str, start_line: int, end_line: int) -> str:
    """Reads a range of lines from a source file in the workspace."""
    path = Path(relative_path)
    if not path.exists():
        return f"Error: File {relative_path} does not exist."
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(0, start_line - 1)
        end = min(len(lines), end_line)
        content = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines[start:end], start=start))
        return f"--- Content of {relative_path} (Lines {start_line}-{end_line}) ---\n{content}"
    except Exception as e:
        return f"Error reading file: {e}"


@agent.tool
def apply_fix(ctx: RunContext[DebuggerDeps], relative_path: str, target_code: str, replacement_code: str) -> str:
    """Replaces a specific block of code in a file with a corrected version."""
    path = Path(relative_path)
    if not path.exists():
        return f"Error: File {relative_path} does not exist."
    if "src/" in relative_path:
        return "Error: Modifying the src/ directory is strictly banned. Modify src2/ instead."

    try:
        content = path.read_text(encoding="utf-8")
        if target_code not in content:
            return f"Error: Could not find exact target code block in {relative_path}. Make sure whitespace matches."

        new_content = content.replace(target_code, replacement_code, 1)
        path.write_text(new_content, encoding="utf-8")
        return f"Success: Surgically replaced code in {relative_path}."
    except Exception as e:
        return f"Error applying fix: {e}"


# =====================================================================
# Main Execution Loop
# =====================================================================


def run_test(command: str) -> tuple[bool, str]:
    """Runs the test command and returns (passed, output)."""
    print(f"\n🚀 Running test: {command}...")
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    output = f"--- STDOUT ---\n{result.stdout}\n--- STDERR ---\n{result.stderr}"
    return result.returncode == 0, output


async def main():
    # Target test command
    # [baziforecaster-only: TEST/GOLD/run.py not in kit download. See KIT_PATH-based run via 'uv run pytest examples'.]
    # [baziforecaster-only: TEST/GOLD/run.py not in kit download]
    test_cmd = "uv run TEST/GOLD/run.py --test 04_daily --test 05_forecast"  # [baziforecaster-only: not in kit download]
    deps = DebuggerDeps(test_command=test_cmd, max_iterations=5)

    for i in range(deps.max_iterations):
        deps.current_iteration = i + 1
        print(f"\n🔄 --- Iteration {deps.current_iteration}/{deps.max_iterations} ---")

        passed, output = run_test(deps.test_command)
        deps.last_run_output = output

        if passed:
            print("🎉 Success! The test suite passed.")
            sys.exit(0)

        print("❌ Test failed. Activating Pydantic AI Debugger...")

        # Extract traceback snippet to save tokens
        tracebacks = re.findall(r"Traceback .*?(?=\n\n|\Z)", output, re.DOTALL)
        tb_context = "\n".join(tracebacks) if tracebacks else output[-1000:]

        prompt = (
            f"The test command `{deps.test_command}` failed.\n"
            f"Here is the traceback/error context:\n"
            f"```\n{tb_context}\n```\n"
            f"Please investigate the cause, read the relevant file, and apply a fix."
        )

        result = await agent.run(prompt, deps=deps)
        print("\n🤖 Agent Decision:")
        print(f"  Reasoning: {result.data.reasoning}")
        print(f"  File: {result.data.file_path}")
        print(f"  Fix Applied: {result.data.explanation_of_change}")

    print("\n🚨 Max iterations reached. Auto-heal failed to resolve the issue.")
    sys.exit(1)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
