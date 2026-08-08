#!/usr/bin/env python3

import os
from pathlib import Path

target_root = os.getenv("KIT_TARGET_ROOT")
if not target_root:
    raise RuntimeError("KIT_TARGET_ROOT is required — set it in kit-tools/.env to your target repository path.")
f = str(Path(target_root) / os.getenv("KIT_SOURCE_ROOT", "src") / "interfaces/telegram/utils.py")

with open(f, encoding="utf-8") as fh:
    content = fh.read()

B = chr(92)   # literal backslash \
OB = B + B    # double backslash \\ (Python escaped backslash)

old = (
    f'    text = text.replace("{B}$rightarrow$", "{chr(8594)}")\n'
    f'    text = text.replace("{B}rightarrow", "{chr(8594)}")\n'
    f'    text = text.replace("{B}$leftarrow$", "{chr(8592)}")\n'
    f'    text = text.replace("{B}leftarrow", "{chr(8592)}")\n'
    f'    text = text.replace("{B}$implies$", "{chr(8658)}")\n'
    f'    text = text.replace("{B}implies", "{chr(8658)}")\n'
)

new = (
    f'    text = text.replace("{OB}$rightarrow$", "{chr(8594)}")\n'
    f'    text = text.replace("{OB}rightarrow", "{chr(8594)}")\n'
    f'    text = text.replace("{OB}$leftarrow$", "{chr(8592)}")\n'
    f'    text = text.replace("{OB}leftarrow", "{chr(8592)}")\n'
    f'    text = text.replace("{OB}$implies$", "{chr(8658)}")\n'
    f'    text = text.replace("{OB}implies", "{chr(8658)}")\n'
)

if old in content:
    content = content.replace(old, new)
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(content)
    print("Fixed: replaced single-backslash with double-backslash in _preprocess_telegram_text")
else:
    print("OLD pattern not found - checking what's actually there")
    idx = content.find("def _preprocess_telegram_text")
    section = content[idx:idx + 300]
    for i, line in enumerate(section.split(chr(10)), 1):
        print(f"{i}: {repr(line)}")
