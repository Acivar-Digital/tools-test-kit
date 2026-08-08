
import json
from pathlib import Path


def export_monthly_reports(chat_id):
    print(f"--- EXPORTING 12 MONTHLY REPORTS FOR {chat_id} ---")

    # Paths
    base_dir = Path("_prd/999000001/front_to_back")
    master_path = base_dir / "master.json"

    if not master_path.exists():
        print(f"Error: {master_path} not found.")
        return

    # Official target dir
    target_dir = Path(f"_prd/users/{chat_id}/reports/2026")
    target_dir.mkdir(parents=True, exist_ok=True)

    with open(master_path, encoding="utf-8") as f:
        data = json.load(f)

    monthly_forecasts = data.get("monthly_forecasts", [])

    for i, month in enumerate(monthly_forecasts):
        meta = month.get("month_metadata", {})
        name = meta.get("month_name", f"Month_{i+1}")
        # Clean name for filename
        safe_name = name.replace(" ", "_")

        # Extract markdown content from Module 6a
        content = month.get("engine_outputs", {}).get("module_6a", {}).get("content", "")

        if not content:
            print(f"Warning: No content found for {name}")
            continue

        file_path = target_dir / f"{i+1:02d}_{safe_name}.md"
        with open(file_path, "w", encoding="utf-8") as out:
            out.write(f"# {name} Executive Report\n\n")
            out.write(content)
        print(f"Exported: {file_path.name}")

    # Also copy the annual summary and HTML report
    summary_src = base_dir / "executive_summary.md"
    html_src = base_dir / "final_report.html"

    if summary_src.exists():
        with open(target_dir / "Annual_Executive_Summary.md", "w", encoding="utf-8") as out:
            out.write(summary_src.read_text(encoding="utf-8"))
        print("Copied Annual_Executive_Summary.md")

    if html_src.exists():
        with open(target_dir / "Premium_Report_2026.html", "w", encoding="utf-8") as out:
            out.write(html_src.read_text(encoding="utf-8"))
        print("Copied Premium_Report_2026.html")

    print(f"--- EXPORT COMPLETE: {target_dir.absolute()} ---")

if __name__ == "__main__":
    export_monthly_reports(999000001)
