import json
from pathlib import Path


def main():
    src_audit_path = Path("TEST/codes/20260626_SRC2/dead_code_audit_main.json")
    src2_audit_path = Path("TEST/codes/20260626_SRC2/dead_code_audit.json")

    if not src_audit_path.exists() or not src2_audit_path.exists():
        print("Error: Make sure both JSON audit files exist.")
        return

    with open(src_audit_path, encoding="utf-8") as f:
        src_audit = json.load(f).get("audit_results", [])

    with open(src2_audit_path, encoding="utf-8") as f:
        src2_audit = json.load(f).get("audit_results", [])

    src_by_name = {}
    for item in src_audit:
        src_by_name.setdefault(item["name"], []).append(item)

    truly_dead = []

    for item2 in src2_audit:
        name = item2["name"]
        status2 = item2["status"]
        file2 = item2["file_path"]
        t2 = item2["type"]
        reason2 = item2.get("reason", "")

        src_matches = src_by_name.get(name, [])
        if not src_matches:
            continue

        item1 = None
        for match in src_matches:
            if Path(match["file_path"]).name == Path(file2).name:
                item1 = match
                break
        if not item1:
            item1 = src_matches[0]

        status1 = item1["status"]

        if status2 == "CONFIRMED_DEAD" and status1 == "CONFIRMED_DEAD":
            truly_dead.append({
                "name": name,
                "type": t2,
                "file_path_src": item1["file_path"],
                "line_src": item1["line"],
                "file_path_src2": file2,
                "line_src2": item2["line"],
                "reason_src2": reason2
            })

    def categorize_path(file_path: str, name: str) -> str:
        fp_lower = file_path.lower()
        name_lower = name.lower()
        if "math" in fp_lower or "engine/" in fp_lower or "module" in fp_lower or "solar" in fp_lower or "calendar" in fp_lower or "star" in fp_lower:
            return "Metaphysical Core & Bazi Math"
        elif "openrouter" in fp_lower or "simplifier" in fp_lower or "narrative" in fp_lower or "summarizer" in fp_lower or "prompt" in fp_lower:
            return "Narrative Generation & LLM API"
        elif "validator" in fp_lower or "guardrail" in fp_lower or "safety" in fp_lower or "qi_sha" in name_lower or "words" in name_lower:
            return "Guardrails & Content Validation"
        elif "bot/" in fp_lower or "intake" in fp_lower or "handler" in fp_lower or "conductor" in fp_lower or "telegram" in fp_lower:
            return "Bot Orchestration & Intake Flow"
        elif "db" in fp_lower or "memory" in fp_lower or "store" in fp_lower or "storage" in fp_lower or "billing" in fp_lower or "session" in fp_lower:
            return "DB, Cache & Infrastructure"
        else:
            return "Telemetry & Internal Utilities"

    categorized_data = {
        "Metaphysical Core & Bazi Math": [],
        "Narrative Generation & LLM API": [],
        "Guardrails & Content Validation": [],
        "Bot Orchestration & Intake Flow": [],
        "DB, Cache & Infrastructure": [],
        "Telemetry & Internal Utilities": []
    }

    for item in truly_dead:
        cat = categorize_path(item["file_path_src2"], item["name"])
        categorized_data[cat].append(item)

    # Render report with additional columns
    md_lines = []
    md_lines.append("# 🛑 Truly Dead Legacy Code Decision Matrix (Dead in both `src` and `src2`)\n")
    md_lines.append("> [!IMPORTANT]\n")
    md_lines.append("> Review the dead codes listed under each category. Use the **Review / Replaced By** column to identify why they became obsolete, and update the **Final Decision** column (e.g., Drop, Restore) to document the action.\n\n")

    for category, items in categorized_data.items():
        md_lines.append(f"## {category}\n")
        if not items:
            md_lines.append("No dead items identified in this category.\n\n")
            continue

        md_lines.append("| S/No. | Symbol Name / Type | src Location | src2 Location | Reason (src2 Audit) | Review / Replaced By | Final Decision |\n")
        md_lines.append("|---|---|---|---|---|---|---|\n")

        for idx, item in enumerate(sorted(items, key=lambda x: x["name"]), 1):
            clean_reason = item["reason_src2"].replace("|", "\\|").replace("\n", " ")
            file_link_src = f"[{Path(item['file_path_src']).name}](file://{Path(item['file_path_src']).absolute()}#L{item['line_src']})"
            file_link_src2 = f"[{Path(item['file_path_src2']).name}](file://{Path(item['file_path_src2']).absolute()}#L{item['line_src2']})"

            # Reset all items to clean manual check placeholders
            review_placeholder = "Needs manual check"
            decision_placeholder = "[ ] Drop / [ ] Restore"

            md_lines.append(f"| {idx} | `{item['name']}`<br>({item['type']}) | {file_link_src} | {file_link_src2} | {clean_reason} | {review_placeholder} | {decision_placeholder} |\n")
        md_lines.append("\n")

    md_content = "".join(md_lines)
    out_md = Path("TEST/codes/Dead_Codes_20260628_DeepDive.md")
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Deep-dive report updated with matrix columns at: {out_md}")

if __name__ == "__main__":
    main()
