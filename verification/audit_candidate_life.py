from __future__ import annotations

import argparse
import csv
import json
import sys
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
from multiscale_fatigue_model_ijf_2026.field_values import FieldValuesFunction


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit candidate return/selection without changing the fatigue kernel.")
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    if args.seed != 42:
        parser.error("This audit validates first-element preparation against the captured seed42 inputs.")
    config = load_simulation_config(args.config_file, base_dir=args.base_dir, output_dir=args.report.parent)
    config = replace(config, cache_dir=args.cache_dir, random_seed=args.seed,
                     sigma_nom=(135, 140), iteration_count=1, n_symm=1)

    def first_element_fields(field_input, material, load_index):
        # All sampling/interpolation at (0.05, 0.05) is unchanged. Do not prepare
        # unused surface coordinates; the fatigue specimen itself stays intact.
        local_input = replace(field_input, y_lim=field_input.active_element_size[0],
                              z_lim=field_input.active_element_size[1])
        return FieldValuesFunction(local_input, material, load_index)

    with patch("multiscale_fatigue_model_ijf_2026.context.FieldValuesFunction", first_element_fields):
        data = build_context(config).input_data

    rows = []
    summaries = []
    current_stress = 135
    first_nan = None
    original_ctsd = crack_life._calculate_ctsd_value
    raw_code = crack_life._crack_life_raw.__code__

    def capture_ctsd(a, c, n, ratios, delta_tau, boundaries, k):
        nonlocal first_nan
        result = original_ctsd(a, c, n, ratios, delta_tau, boundaries, k)
        if current_stress == 135 and first_nan is None and not np.all(np.isfinite(result)):
            first_nan = dict(a=a, c=c, n=n, ratios=ratios[:n + 2],
                             delta_tau=delta_tau, boundaries=boundaries[:n + 2], interaction_constant=k)
        return result

    def observe_return(frame, event, result):
        if event != "return" or not isinstance(result, tuple):
            return
        state = frame.f_locals
        if state.get("stop_reason"):
            end = state["stop_reason"]
        elif state.get("stop_due_to_ctsd_evaluation"):
            end = "grain_layers_exhausted" if state.get("unstable_fracture") else "initial_ctsd_stop"
        elif state.get("unstable_fracture"):
            end = "unstable_fracture"
        elif state.get("ctsd_below_stage2_threshold"):
            end = "stage2_threshold"
        elif state.get("stop_due_to_life_integration_limit"):
            end = "life_integration_limit"
        else:
            end = "evaluation_loop_end"
        diagnostics = state["diagnostics"]
        last = float(state["S_cyc0"][-1])
        limit = float(state["nTemp"])
        rows.append(dict(
            sigma_nom=current_stress, candidate_call=len(rows) + 1, grain_size=state["r0"],
            end_branch=end, last_evaluation_index=state["i"], last_crack_depth=state["aii"],
            valid_until_index=state["valid_until_index"], last_ctsd=float(np.asarray(state["Δδ"]).item()),
            ctsd_threshold=data.crack_growth.delta_delta_th,
            observed_nonfinite_ctsd=any(d.context.get("quantity") == "ctsd" for d in diagnostics),
            last_cycles=last, comparison_limit=limit, is_complete=state["is_complete"],
            eligible_by_existing_rule=bool(state["is_complete"] and last < limit),
        ))

    def trace_calls(frame, event, arg):
        if frame.f_code is raw_code:
            frame.f_trace_lines = False
            return observe_return
        return None

    history_length = data.evaluation_points.eval_num_stage1 + 3 * data.evaluation_points.eval_num_stage2
    with patch.object(crack_life, "_calculate_ctsd_value", capture_ctsd):
        previous_trace = sys.gettrace()
        try:
            sys.settrace(trace_calls)
            for load_index, current_stress in enumerate((135, 140)):
                fields = data.stress_fields.by_load[load_index]
                first = replace(data.specimen, ae_num=1, ae_yz=data.specimen.ae_yz[:1])
                target = _rank_area_elements(first, fields)[0]
                start = len(rows)
                result = calculate_element_life(
                    data, load_index=load_index, area_element_rank=0, area_element_index=0,
                    symmetry_index=0, stress_tensor=target.stress_tensor,
                    max_shear_stress=target.max_shear_stress, field_values=fields,
                    cycles_result=[10**18] * history_length, crack_depth_result=[0] * history_length,
                )
                summaries.append(dict(sigma_nom=current_stress, candidate_count=len(rows) - start,
                                      history_state=result.history_state,
                                      initial_history_reasons=sorted(result.initial_history_reasons),
                                      returned_cycles=result.cycles[-1]))
        finally:
            sys.settrace(previous_trace)

    reference = json.loads(args.reference.read_text(encoding="utf-8"))["ctsd"]
    assert first_nan is not None, "The reference CTSD NaN was not reproduced."
    for key in ("a", "c", "n", "delta_tau", "boundaries", "interaction_constant"):
        np.testing.assert_array_equal(first_nan[key], reference[key], err_msg=key)
    for actual, expected in zip(first_nan["ratios"], reference["ratios"], strict=True):
        np.testing.assert_array_equal(actual, expected)
    print("First-element CTSD inputs match the full-field seed42 capture exactly.")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = dict(seed=args.seed, area_element_index=0, symmetry_index=0,
                   reference_inputs_match_exactly=True, results=summaries,
                   note="Local first-element runs; not a replay of the original unseeded full iterations.")
    args.report.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"Candidate audit: {args.report}")


if __name__ == "__main__":
    main()
