from __future__ import annotations

import argparse
import pickle
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference_cache", type=Path)
    parser.add_argument("candidate_cache", type=Path)
    parser.add_argument("--rtol", type=float, default=0.0)
    parser.add_argument("--atol", type=float, default=0.0)
    args = parser.parse_args()

    differences = compare_cache_files(
        args.reference_cache.resolve(),
        args.candidate_cache.resolve(),
        rtol=args.rtol,
        atol=args.atol,
    )
    if differences:
        print("Abaqus cache comparison failed:")
        for difference in differences:
            print(f"- {difference}")
        return 1

    print("Abaqus cache comparison passed.")
    return 0


def compare_cache_files(
    reference_path: Path,
    candidate_path: Path,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    with reference_path.open("rb") as file:
        reference = pickle.load(file)
    with candidate_path.open("rb") as file:
        candidate = pickle.load(file)

    differences: list[str] = []
    reference_items = list(reference.items())
    candidate_items = list(candidate.items())

    if len(reference_items) != len(candidate_items):
        return [
            "entry counts differ: "
            f"reference={len(reference_items)}, candidate={len(candidate_items)}"
        ]

    for index, ((reference_key, reference_value), (candidate_key, candidate_value)) in enumerate(
        zip(reference_items, candidate_items)
    ):
        label = _cache_label(index, reference_key, candidate_key)
        differences.extend(
            _compare_value(label, reference_value, candidate_value, rtol=rtol, atol=atol)
        )

    return differences


def _cache_label(index: int, reference_key: str, candidate_key: str) -> str:
    labels = {
        0: "EE",
        1: "nu",
        2: "AA",
        3: "nnm",
        4: "step",
        5: "sigma_nom_list",
        6: "f_sigma",
        7: "EES",
        8: "PES",
        9: "AES",
    }
    label = labels.get(index, reference_key)
    if reference_key != candidate_key:
        return f"{label} ({reference_key!r} vs {candidate_key!r})"
    return label


def _compare_value(
    label: str,
    reference: object,
    candidate: object,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    if _is_scalar(reference) and _is_scalar(candidate):
        if reference != candidate:
            return [f"{label}: scalar differs: {reference!r} != {candidate!r}"]
        return []

    if _is_interp1d(reference) and _is_interp1d(candidate):
        return _compare_interp1d(label, reference, candidate, rtol=rtol, atol=atol)

    if _is_linear_nd_group(reference) and _is_linear_nd_group(candidate):
        return _compare_linear_nd_group(label, reference, candidate, rtol=rtol, atol=atol)

    return _compare_array_like(label, reference, candidate, rtol=rtol, atol=atol)


def _compare_interp1d(
    label: str,
    reference: object,
    candidate: object,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    differences: list[str] = []
    differences.extend(_compare_array_like(f"{label}.x", reference.x, candidate.x, rtol=rtol, atol=atol))
    differences.extend(_compare_array_like(f"{label}.y", reference.y, candidate.y, rtol=rtol, atol=atol))
    if reference.axis != candidate.axis:
        differences.append(f"{label}.axis differs: {reference.axis!r} != {candidate.axis!r}")
    if reference.bounds_error != candidate.bounds_error:
        differences.append(
            f"{label}.bounds_error differs: {reference.bounds_error!r} != {candidate.bounds_error!r}"
        )
    return differences


def _compare_linear_nd_group(
    label: str,
    reference: list[list[object]],
    candidate: list[list[object]],
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    differences: list[str] = []
    if len(reference) != len(candidate):
        return [f"{label}: outer length differs: {len(reference)} != {len(candidate)}"]

    for i, (reference_row, candidate_row) in enumerate(zip(reference, candidate)):
        if len(reference_row) != len(candidate_row):
            differences.append(
                f"{label}[{i}]: inner length differs: {len(reference_row)} != {len(candidate_row)}"
            )
            continue
        for j, (reference_interp, candidate_interp) in enumerate(zip(reference_row, candidate_row)):
            item_label = f"{label}[{i}][{j}]"
            differences.extend(
                _compare_linear_nd_interpolator(
                    item_label, reference_interp, candidate_interp, rtol=rtol, atol=atol
                )
            )
    return differences


def _compare_linear_nd_interpolator(
    label: str,
    reference: object,
    candidate: object,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    differences: list[str] = []
    for attr in ["points", "values", "scale", "values_shape", "fill_value", "is_complex"]:
        differences.extend(
            _compare_array_like(
                f"{label}.{attr}",
                getattr(reference, attr),
                getattr(candidate, attr),
                rtol=rtol,
                atol=atol,
            )
        )
    return differences


def _compare_array_like(
    label: str,
    reference: object,
    candidate: object,
    *,
    rtol: float,
    atol: float,
) -> list[str]:
    reference_array = np.asarray(reference)
    candidate_array = np.asarray(candidate)

    if reference_array.shape != candidate_array.shape:
        return [
            f"{label}: shape differs: "
            f"{reference_array.shape} != {candidate_array.shape}"
        ]

    if np.issubdtype(reference_array.dtype, np.number) and np.issubdtype(
        candidate_array.dtype, np.number
    ):
        equal = np.allclose(reference_array, candidate_array, rtol=rtol, atol=atol, equal_nan=True)
    else:
        equal = np.array_equal(reference_array, candidate_array)

    if equal:
        return []

    return [f"{label}: values differ; max_abs_diff={_max_abs_diff(reference_array, candidate_array)}"]


def _max_abs_diff(reference: np.ndarray, candidate: np.ndarray) -> str:
    try:
        return str(float(np.nanmax(np.abs(reference - candidate))))
    except (TypeError, ValueError):
        return "n/a"


def _is_scalar(value: object) -> bool:
    return isinstance(value, (int, float, str, bool, np.integer, np.floating))


def _is_interp1d(value: object) -> bool:
    return hasattr(value, "x") and hasattr(value, "y") and value.__class__.__name__ == "interp1d"


def _is_linear_nd_group(value: object) -> bool:
    if not isinstance(value, list) or not value or not isinstance(value[0], list):
        return False
    first = value[0][0]
    return first.__class__.__name__ == "LinearNDInterpolator"


if __name__ == "__main__":
    sys.exit(main())
