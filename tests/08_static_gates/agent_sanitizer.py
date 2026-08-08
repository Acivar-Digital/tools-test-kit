import os
import sys


def sanitize_agent_script(file_path: str):
    """
    Surgically fixes common LLM-introduced escape artifacts in generated code.
    Specifically:
    - Literal double-backslashes followed by n (\\\\n) -> actual newline (\\n)
    - Literal double-backslashes followed by u (\\\\u) -> actual unicode prefix (\\u)
    """
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found.")
        return

    with open(file_path, encoding="utf-8") as f:
        content = f.read()

    # Fix double-escaped newlines and unicode artifacts
    sanitized = content.replace("\\\\n", "\\n").replace("\\\\u", "\\u")

    if sanitized != content:
        with open(file_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(sanitized)
        print(f"✅ Sanitized: {file_path} (Fixed escape artifacts)")
    else:
        print(f"Clean: {file_path} (No artifacts detected)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python 08_static_gates/agent_sanitizer.py <file_path>")
    else:
        sanitize_agent_script(sys.argv[1])
