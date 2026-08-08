import json
from pathlib import Path


def main():
    json_store_path = Path("TEST/codes/20260626_SRC2/dead_code_deepdive_results.json")
    json_out_path = Path("TEST/codes/20260626_SRC2/dead_code_deepdive_results_DropOnly.json")

    if not json_store_path.exists():
        print(f"Error: {json_store_path} not found.")
        return

    with open(json_store_path, encoding="utf-8") as f:
        data = json.load(f)

    # Filter dictionary keeping ONLY entries where recommendation is exactly "Drop (Recommended)"
    drop_only_data = {
        key: val for key, val in data.items()
        if val.get("recommendation") == "Drop (Recommended)"
    }

    # Save to the new JSON file
    with open(json_out_path, "w", encoding="utf-8") as f:
        json.dump(drop_only_data, f, indent=2)

    print(f"Filtered DropOnly JSON saved successfully to: {json_out_path}")
    print(f"Total DropOnly items: {len(drop_only_data)}")

if __name__ == "__main__":
    main()
