from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

DETAIL_COLUMNS = {
    "Crack depth",
    "Surface crack length",
    "Slip band",
    "CTSD",
    "Cycles",
    "K Value",
    "Effective Stress",
    "Stress Ratio",
    "Aspect Ratio",
    "Opening Stress",
    "Location of GB",
}

SUMMARY_COLUMNS = {"σ_nom", "Iteration", "minimum life", "yz"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--require-detail", action="store_true")
    parser.add_argument("--require-summary", action="store_true")
    args = parser.parse_args()

    csv_paths = sorted(args.output_dir.glob("*.csv"))
    if not csv_paths:
        print(f"No CSV files found in {args.output_dir}")
        return 4

    detail_count = 0
    summary_count = 0
    errors: list[str] = []

    for path in csv_paths:
        try:
            frame = pd.read_csv(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: cannot read CSV: {exc}")
            continue

        columns = set(frame.columns)
        if DETAIL_COLUMNS.issubset(columns):
            detail_count += 1
        elif SUMMARY_COLUMNS.issubset(columns):
            summary_count += 1
        else:
            errors.append(f"{path.name}: unknown CSV schema: {list(frame.columns)}")

        if frame.empty:
            errors.append(f"{path.name}: CSV has no rows")

    if args.require_detail and detail_count == 0:
        errors.append("No detail CSV was found")
    if args.require_summary and summary_count == 0:
        errors.append("No summary CSV was found")

    if errors:
        print("CSV validation failed:")
        for error in errors:
            print(f"- {error}")
        return 5

    print(
        f"CSV validation passed: {len(csv_paths)} file(s), "
        f"{detail_count} detail, {summary_count} summary."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
