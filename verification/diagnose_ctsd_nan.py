from __future__ import annotations

import argparse
import json
import warnings
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import numpy as np

from multiscale_fatigue_model_ijf_2026.calculation import crack_life
from multiscale_fatigue_model_ijf_2026.calculation.element_life import (
    calculate_element_life,
)
from multiscale_fatigue_model_ijf_2026.calculation.load_case import _rank_area_elements
from multiscale_fatigue_model_ijf_2026.config import load_simulation_config
from multiscale_fatigue_model_ijf_2026.context import build_context


class CTSDNaNFound(Exception):
    """End this diagnostic run immediately after capturing a non-finite CTSD."""


def _json_value(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture inputs to the first non-finite CTSD in one element.")
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--load-index", type=int, default=0)
    parser.add_argument("--area-element-rank", type=int, default=1)
    args = parser.parse_args()
    config = load_simulation_config(args.config_file, base_dir=args.base_dir, output_dir=args.report.parent)
    sigma_nom = config.sigma_nom[args.load_index]
    # A new, seed-fixed local reproduction; not a replay of an unseeded run.
    config = replace(config, cache_dir=args.cache_dir, random_seed=args.seed,
                     sigma_nom=(sigma_nom,), iteration_count=1, n_symm=1)
    context = build_context(config)
    data = context.input_data
    field_values = data.stress_fields.by_load[0]
    target = _rank_area_elements(data.specimen, field_values)[args.area_element_rank - 1]
    trace = {"seed": args.seed, "sigma_nom": sigma_nom,
             "area_element_index": target.area_element_index,
             "area_element_rank": args.area_element_rank - 1, "symmetry_index": 0,
             "root_calls": []}
    current_geometry = []
    original_geometry = crack_life._ctsd_geometry_integral
    original_ctsd = crack_life._calculate_ctsd_value
    original_stage1 = crack_life._solve_stage1_slip_band_length
    original_multilayer = crack_life._solve_multilayer_slip_band_length
    original_evaluate = crack_life._evaluate_ctsd_at_crack_depth

    def geometry(x, c, ad):
        with warnings.catch_warnings(record=True) as caught, np.errstate(all="warn"):
            warnings.simplefilter("always", RuntimeWarning)
            result = original_geometry(x, c, ad)
        effective_ad = (1 - 1e-3) * ad if x == ad else ad
        current_geometry.append({"x": x, "c": c, "ad": ad, "effective_ad": effective_ad,
                                 "c2_minus_ad2": c**2 - effective_ad**2,
                                 "c2_minus_x2": c**2 - x**2, "result": result,
                                 "warnings": [str(w.message) for w in caught]})
        return result

    def stage1(a, ratios, boundary):
        result = original_stage1(a, ratios, boundary)
        trace["root_calls"].append({"kind": "stage1", "a": a, "ratios": list(ratios),
                                    "boundary": boundary, "root": result})
        return result

    def multilayer(a, n, ratios, boundaries):
        result = original_multilayer(a, n, ratios, boundaries)
        trace["root_calls"].append({"kind": "multilayer", "a": a, "n": n,
                                    "ratios": list(ratios), "boundaries": list(boundaries),
                                    "root": result})
        return result

    def evaluate(aii, evaluation_index, delta_sigma, grain_boundaries, **kwargs):
        trace["evaluation"] = {"index": evaluation_index, "a": aii, "delta_sigma": delta_sigma,
                               "boundary_depths": grain_boundaries.boundary_depths,
                               "orientations": grain_boundaries.orientations}
        return original_evaluate(aii, evaluation_index, delta_sigma, grain_boundaries, **kwargs)

    def ctsd(a, c, n, ratios, delta_tau, boundaries, k):
        current_geometry.clear()
        with warnings.catch_warnings(record=True) as caught, np.errstate(all="warn"):
            warnings.simplefilter("always", RuntimeWarning)
            result = original_ctsd(a, c, n, ratios, delta_tau, boundaries, k)
        if not np.all(np.isfinite(result)):
            trace["ctsd"] = {"a": a, "c": c, "n": n, "ratios": list(ratios),
                             "delta_tau": delta_tau, "boundaries": list(boundaries),
                             "interaction_constant": k, "result": result,
                             "geometry": list(current_geometry),
                             "warnings": [str(w.message) for w in caught]}
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(json.dumps(trace, ensure_ascii=False, indent=2, default=_json_value), encoding="utf-8")
            raise CTSDNaNFound
        return result

    length = data.evaluation_points.eval_num_stage1 + 3 * data.evaluation_points.eval_num_stage2
    with ExitStack() as stack:
        for name, function in (("_ctsd_geometry_integral", geometry), ("_calculate_ctsd_value", ctsd),
                               ("_solve_stage1_slip_band_length", stage1),
                               ("_solve_multilayer_slip_band_length", multilayer),
                               ("_evaluate_ctsd_at_crack_depth", evaluate)):
            stack.enter_context(patch.object(crack_life, name, function))
        try:
            calculate_element_life(
                data, load_index=0, area_element_rank=args.area_element_rank - 1,
                area_element_index=target.area_element_index, symmetry_index=0,
                stress_tensor=target.stress_tensor, max_shear_stress=target.max_shear_stress,
                field_values=field_values, cycles_result=[10**18] * length, crack_depth_result=[0] * length,
            )
        except CTSDNaNFound:
            print(f"Non-finite CTSD captured: {args.report}")
            return
    raise RuntimeError("No non-finite CTSD was observed in this targeted element.")


if __name__ == "__main__":
    main()
