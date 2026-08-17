from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("baseline_dir", type=Path)
    parser.add_argument("candidate_dir", type=Path)
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--atol", type=float, default=0.0)
    args = parser.parse_args()

    differences = compare_csv_dirs(
        args.baseline_dir.resolve(),
        args.candidate_dir.resolve(),
        rtol=args.rtol,
        atol=args.atol,
    )
    if differences:
        print("CSV comparison failed:")
        for difference in differences:
            print(f"- {difference}")
        return 1

    print("CSV comparison passed.")
    return 0


def compare_csv_dirs(
    baseline_dir: Path,
    candidate_dir: Path,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    baseline_files = sorted(path.name for path in baseline_dir.glob("*.csv"))
    candidate_files = sorted(path.name for path in candidate_dir.glob("*.csv"))
    differences: list[str] = []

    if baseline_files != candidate_files:
        differences.append(
            f"file lists differ: baseline={baseline_files}, candidate={candidate_files}"
        )
        return differences

    for filename in baseline_files:
        differences.extend(
            compare_csv_files(
                baseline_dir / filename,
                candidate_dir / filename,
                rtol=rtol,
                atol=atol,
            )
        )

    return differences


def compare_csv_files(
    baseline_path: Path,
    candidate_path: Path,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    baseline = pd.read_csv(baseline_path)
    candidate = pd.read_csv(candidate_path)
    differences: list[str] = []

    if list(baseline.columns) != list(candidate.columns):
        differences.append(f"{baseline_path.name}: columns differ")
        return differences

    if baseline.shape != candidate.shape:
        differences.append(
            f"{baseline_path.name}: shape differs {baseline.shape} != {candidate.shape}"
        )
        return differences

    for column in baseline.columns:
        left = baseline[column]
        right = candidate[column]
        left_numeric = pd.to_numeric(left, errors="coerce")
        right_numeric = pd.to_numeric(right, errors="coerce")
        numeric_mask = left_numeric.notna() | right_numeric.notna()

        if numeric_mask.any():
            if not np.allclose(
                left_numeric[numeric_mask],
                right_numeric[numeric_mask],
                rtol=rtol,
                atol=atol,
                equal_nan=True,
            ):
                row = _first_numeric_difference(
                    left_numeric,
                    right_numeric,
                    numeric_mask,
                    rtol=rtol,
                    atol=atol,
                )
                differences.append(
                    f"{baseline_path.name}: numeric column differs: {column} "
                    f"at row {row}: baseline={left.iloc[row]!r}, candidate={right.iloc[row]!r}"
                )

        text_mask = ~numeric_mask
        left_text = left[text_mask].fillna("")
        right_text = right[text_mask].fillna("")
        if text_mask.any() and not left_text.equals(right_text):
            row = _first_text_difference(left, right, text_mask)
            differences.append(
                f"{baseline_path.name}: text column differs: {column} "
                f"at row {row}: baseline={left.iloc[row]!r}, candidate={right.iloc[row]!r}"
            )

    return differences


def _first_numeric_difference(
    left: pd.Series,
    right: pd.Series,
    mask: pd.Series,
    *,
    rtol: float,
    atol: float,
) -> int:
    for row in left[mask].index:
        if not np.allclose(
            [left.iloc[row]],
            [right.iloc[row]],
            rtol=rtol,
            atol=atol,
            equal_nan=True,
        ):
            return int(row)
    return int(left[mask].index[0])


def _first_text_difference(left: pd.Series, right: pd.Series, mask: pd.Series) -> int:
    for row in left[mask].index:
        if str(left.iloc[row] if pd.notna(left.iloc[row]) else "") != str(
            right.iloc[row] if pd.notna(right.iloc[row]) else ""
        ):
            return int(row)
    return int(left[mask].index[0])


if __name__ == "__main__":
    sys.exit(main())
