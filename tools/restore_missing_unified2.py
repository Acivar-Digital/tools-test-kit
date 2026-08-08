import re
import subprocess

result = subprocess.run(["git", "show", "HEAD:src2/core/schemas/unified.py"], capture_output=True, text=True)
original_unified = result.stdout

with open("src2/core/schemas/unified.py") as f:
    current_unified = f.read()

missing_classes = [
    "SiShenHarmonyStability", "CompatibilityResult", "DmStrengthTier1",
    "ClashAdjustedDmScore", "CombinationStrength", "HarmonyStrength",
    "ElementAbsence", "StarvationFlag", "TriggerPotency"
]

to_append = ""

for cls in missing_classes:
    if f"class {cls}" not in current_unified:
        # Extract from original
        match = re.search(fr'(class {cls}.*?)(?=\nclass |\n\n\n|$)', original_unified, flags=re.DOTALL)
        if match:
            to_append += "\n" + match.group(1).strip() + "\n"

if to_append:
    with open("src2/core/schemas/unified.py", "a") as f:
        f.write("\n" + to_append)
    print("Restored missing classes 2.")
else:
    print("No missing classes found or extracted 2.")
