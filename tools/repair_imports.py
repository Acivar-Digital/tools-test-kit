import re
from pathlib import Path

files_to_clean = [
    "src2/engine/prompt_maker.py",
    "src2/engine/prompt_stitcher.py",
    "src2/engine/prompt_checker.py",
    "src2/engine/monthly_generator.py"
]

for file in files_to_clean:
    path = Path(file)
    if not path.exists():
        continue
    content = path.read_text()

    # Remove dead legacy imports
    content = re.sub(r'    GE_JU_CATEGORY_MAP,\n', '', content)
    content = re.sub(r'    GE_JU_LIFE_STAGE_MATRIX,\n', '', content)
    content = re.sub(r'    STEMS,\n', '', content)

    path.write_text(content)

print("Cleaned legacy imports from prompt scripts.")
