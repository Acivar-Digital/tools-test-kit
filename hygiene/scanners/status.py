#!/usr/bin/env python3
"""
CC Reduction Status Scanner
Calculates live Cyclomatic Complexity for all functions in 99_YOLO_Mode.md,
cross-referencing with beads ticket status.
"""

import ast
import os
import re
import sys


def compute_cc(node: ast.AST) -> int:
    cc = 1
    for child in ast.walk(node):
        if isinstance(
            child,
            (
                ast.If,
                ast.While,
                ast.For,
                ast.AsyncFor,
                ast.ExceptHandler,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            cc += 1
        elif isinstance(child, ast.BoolOp):
            cc += len(child.values) - 1
        elif isinstance(child, ast.IfExp):
            cc += 1
        elif isinstance(child, ast.Match):
            cc += len(child.cases)
    return cc


def scan_live_cc(target_dir: str = "src2") -> dict[str, dict[str, int]]:
    all_violations: dict[str, dict[str, int]] = {}
    for root, _, files in os.walk(target_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        tree = ast.parse(f.read(), filename=filepath)
                    for node in ast.walk(tree):
                        if isinstance(
                            node, (ast.FunctionDef, ast.AsyncFunctionDef)
                        ):
                            cc = compute_cc(node)
                            if cc > 5:
                                all_violations.setdefault(filepath, {})[
                                    node.name
                                ] = cc
                except Exception:
                    pass
    return all_violations


def parse_yolo_mode(
    yolo_path: str = "kit-hygiene/scanners/99_YOLO_Mode.md",
) -> dict[str, list[dict]]:
    batch_items: dict[str, list[dict]] = {}
    current_batch = None

    if not os.path.exists(yolo_path):
        print(f"Error: {yolo_path} not found.")
        sys.exit(1)

    with open(yolo_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if line_str.startswith("## Batch "):
                current_batch = line_str.replace("## ", "").strip()
                batch_items[current_batch] = []
            elif (
                line_str.startswith("| ")
                and current_batch
                and not line_str.startswith("| #")
                and not line_str.startswith("|---")
            ):
                m = re.search(
                    r"\|\s*\d+\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|",
                    line_str,
                )
                if m:
                    fp, fn, cc, tid = m.groups()
                    batch_items[current_batch].append(
                        {
                            "file": fp.strip(),
                            "function": fn.strip(),
                            "cc": int(cc),
                            "ticket": tid.strip(),
                        }
                    )
    return batch_items


def main():
    live_cc = scan_live_cc()
    batch_items = parse_yolo_mode()

    total_items = 0
    total_active = 0
    total_clean = 0

    print("=======================================================================")
    print("                 CC REDUCTION PROGRESS STATUS                          ")
    print("=======================================================================\n")

    for batch_name, items in batch_items.items():
        active = []
        clean = []
        for item in items:
            fp = item["file"]
            fn = item["function"]
            if fp in live_cc and fn in live_cc[fp]:
                item["current_cc"] = live_cc[fp][fn]
                active.append(item)
            else:
                clean.append(item)

        b_total = len(items)
        b_active = len(active)
        b_clean = len(clean)
        pct = (b_clean / b_total * 100) if b_total > 0 else 100.0

        total_items += b_total
        total_active += b_active
        total_clean += b_clean

        print(
            f"[{batch_name}] {b_clean}/{b_total} Clean ({pct:5.1f}%) | {b_active} Remaining"
        )
        if active:
            for a in active:
                print(
                    f"   └── OPEN: {a['file']} :: {a['function']} (CC={a['current_cc']}) -> {a['ticket']}"
                )

    print("\n-----------------------------------------------------------------------")
    overall_pct = (total_clean / total_items * 100) if total_items > 0 else 100.0
    print(
        f"OVERALL SUMMARY: {total_clean}/{total_items} Complete ({overall_pct:.1f}%) | {total_active} Remaining"
    )
    print("=======================================================================\n")


if __name__ == "__main__":
    main()
