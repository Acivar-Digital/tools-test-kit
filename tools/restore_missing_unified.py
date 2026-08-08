import re

# We will read the HEAD version of unified.py (original)
# And the current version, then append the missing classes from HEAD to current.
import subprocess

result = subprocess.run(["git", "show", "HEAD:src2/core/schemas/unified.py"], capture_output=True, text=True)
original_unified = result.stdout

with open("src2/core/schemas/unified.py") as f:
    current_unified = f.read()

missing_classes = [
    "ExternalPillarTrigger", "PalaceAssociation", "GenerativeStatus",
    "ActiveDisruptor", "OpenedTomb", "ReleasedElement", "StemComboModifier",
    "AllianceImprovementDetails", "EngineOutputs", "Module4Results",
    "PalaceEvent", "TriggerPotency", "Event", "RiskFactor"
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
        f.write("\n\n# --- Restored missing classes from truncation ---\n" + to_append)
    print("Restored missing classes.")
else:
    print("No missing classes found or extracted.")
