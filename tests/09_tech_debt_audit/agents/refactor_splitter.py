import os
import re

FILES_TO_PROCESS = [
    "src/engine/prompt_engine.py",
    "src/engine/openrouter.py",
    "src/bot/app.py",
    "src/engine/module3_interaction.py",
    "src/bot/chronomancer_handler.py",
    "src/engine/module0_geju.py"
]

def split_file(path):
    print(f"Processing {path}...")
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"  [!] Failed to read {path}: {e}")
        return

    # Pattern: FILE: [path]\n[code]\n--- or end of file
    # We'll use a more robust split by looking for the markers
    parts = re.split(r"^FILE: ", content, flags=re.MULTILINE)

    # The first part might be empty or some preamble

    for part in parts:
        if not part.strip():
            continue

        # Split into header line and code
        lines = part.split("\n", 1)
        if len(lines) < 2:
            continue

        target_path = lines[0].strip()
        code_block = lines[1]

        # Remove trailing separator if present
        code_block = re.split(r"^---$", code_block, flags=re.MULTILINE)[0].strip()

        print(f"  -> Extracting {target_path}...")

        # Ensure directory exists
        os.makedirs(os.path.dirname(target_path), exist_ok=True)

        # Write to target path
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(code_block)

    print(f"Done with {path}.\n")

if __name__ == "__main__":
    for p in FILES_TO_PROCESS:
        split_file(p)
    print("All files processed.")
