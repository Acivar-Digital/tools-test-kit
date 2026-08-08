
with open("src2/engine/module6_ten_gods.py") as f:
    content = f.read()

# Replace DictMap imports
content = content.replace("DictMap,\n", "")
content = content.replace("DictMap[float]", "list[str]") # Will fix later if needed

with open("src2/engine/module6_ten_gods.py", "w") as f:
    f.write(content)
print("Initial replacements done")
