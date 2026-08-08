import json
import sys
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings

sys.path.append(str(Path(__file__).parent.parent))
from admin.dotenv import api_key, base_url, model_name


class AuditResponse(BaseModel):
    review: str = Field(
        description="Detailed technical reasoning of what replaced this code in src2, naming specific files/functions."
    )
    recommendation: str = Field(
        description="Drop (Recommended) or Restore (Recommended) with strict verification reason."
    )

provider = OpenAIProvider(base_url=base_url, api_key=api_key)
model = OpenAIChatModel(model_name=model_name, provider=provider)

agent = Agent(
    model,
    output_type=AuditResponse,
    retries=3,
    system_prompt=(
        "You are an expert Python codebase auditor specializing in migration verification. "
        "Your task is to review a flagged dead code symbol (class or function) and determine if it is truly dead in `src2/` or if it got accidentally dropped or has callers. "
        "Look for any alternative implementations in `src2/` that replaced it. "
        "Do NOT write generic descriptions like 'Confirmed unused'. Always provide a specific technical replacement path if one exists."
    )
)

def main():
    deepdive_md_path = Path("TEST/codes/Dead_Codes_20260628_DeepDive.md")
    json_store_path = Path("TEST/codes/20260626_SRC2/dead_code_deepdive_results.json")

    if not deepdive_md_path.exists():
        print(f"Error: {deepdive_md_path} not found.")
        return

    # Load Truly Dead items from the matrix JSON
    comp_json_path = Path("TEST/codes/20260626_SRC2/dead_code_comparison.json")
    if not comp_json_path.exists():
        print(f"Error: {comp_json_path} not found.")
        return

    with open(comp_json_path, encoding="utf-8") as f:
        comp_data = json.load(f)

    truly_dead = comp_data.get("truly_dead", [])
    total_items = len(truly_dead)
    print(f"Loaded {total_items} legacy dead items to audit one-by-one.")

    # Load existing results if any to resume progress
    results = {}
    if json_store_path.exists():
        try:
            with open(json_store_path, encoding="utf-8") as f:
                results = json.load(f)
        except Exception:
            pass

    for idx, item in enumerate(truly_dead, 1):
        name = item["name"]
        file_src2 = item["file_path_src2"]

        # Check if already processed
        unique_key = f"{name}::{file_src2}"
        if unique_key in results:
            print(f"[{idx}/{total_items}] Skipping already audited: {name}")
            continue

        print(f"[{idx}/{total_items}] Deep-dive auditing symbol: {name} in {file_src2}...")

        # Find file contents to pass as context
        file_path = Path(file_src2)
        content = ""
        if file_path.exists():
            try:
                content = file_path.read_text(errors="ignore")
            except Exception as e:
                content = f"[Error reading file: {e}]"

        prompt = (
            f"Symbol Name: {name}\n"
            f"Symbol Type: {item['type']}\n"
            f"File Path in src2: {file_src2}\n\n"
            f"File Content context:\n```python\n{content}\n```\n\n"
            f"Please verify if this symbol `{name}` is truly unused or if it has callers. "
            "Examine if its logic got consolidated into another function or replaced by a new pattern. "
            "Respond with specific details."
        )

        try:
            response = agent.run_sync(prompt, model_settings=ModelSettings(max_tokens=1024))
            audit_out = response.output

            results[unique_key] = {
                "name": name,
                "type": item["type"],
                "file_path_src": item["file_path_src"],
                "line_src": item["line_src"],
                "file_path_src2": file_src2,
                "line_src2": item.get("line_src2", item.get("line_src", 1)),
                "reason_src2": item.get("reason_src2", ""),
                "review": audit_out.review,
                "recommendation": audit_out.recommendation
            }

            # Write immediately to prevent progress loss
            json_store_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_store_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)

        except Exception as e:
            print(f"Error auditing {name}: {e}", file=sys.stderr)

    # Now, format the saved JSON results back into the DeepDive Markdown file
    # Group strictly by functional domain
    def categorize_path(file_path: str, name_val: str) -> str:
        fp_lower = file_path.lower()
        name_lower = name_val.lower()
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

    for val in results.values():
        cat = categorize_path(val["file_path_src2"], val["name"])
        categorized_data[cat].append(val)

    md_lines = []
    md_lines.append("# 🛑 Truly Dead Legacy Code Decision Matrix (Dead in both `src` and `src2`)\n")
    md_lines.append("> [post] timestamp=2026-06-26\n")
    md_lines.append("> Review the dead codes listed under each category. Use the **Review / Replaced By** column to identify why they became obsolete, and update the **Final Decision** column to document the action.\n\n")

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

            clean_review = item["review"].replace("|", "\\|").replace("\n", " ")
            decision_box = f"[x] {item['recommendation']}" if "Recommended" in item['recommendation'] else f"[ ] {item['recommendation']}"

            md_lines.append(f"| {idx} | `{item['name']}`<br>({item['type']}) | {file_link_src} | {file_link_src2} | {clean_reason} | {clean_review} | {decision_box} |\n")
        md_lines.append("\n")

    md_content = "".join(md_lines)
    with open(deepdive_md_path, "w", encoding="utf-8") as f:
        f.write(md_content)

    print(f"Deep-dive Markdown report regenerated at: {deepdive_md_path}")

if __name__ == "__main__":
    main()
