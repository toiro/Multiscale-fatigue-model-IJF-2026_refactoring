from __future__ import annotations

import argparse
from pathlib import Path

from multiscale_fatigue_model_ijf_2026.calculation.element_life import (
    calculate_element_life,
)
from multiscale_fatigue_model_ijf_2026.calculation.load_case import (
    _rank_area_elements,
)
from multiscale_fatigue_model_ijf_2026.config import load_simulation_config
from multiscale_fatigue_model_ijf_2026.context import (
    build_calculation_input_data,
    build_context,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run one ranked area element for troubleshooting."
    )
    parser.add_argument("--config-file", type=Path, required=True)
    parser.add_argument("--base-dir", type=Path, default=Path("resources"))
    parser.add_argument("--cache-dir", type=Path, default=Path("outputs/condition_cache"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/troubleshooting"))
    parser.add_argument("--load-index", type=int, default=0)
    parser.add_argument("--area-element-rank", type=int, required=True)
    parser.add_argument("--symmetry-index", type=int, default=1)
    args = parser.parse_args()

    config = load_simulation_config(
        args.config_file,
        base_dir=args.base_dir,
        output_dir=args.output_dir,
    )
    config = config.__class__(**{**config.__dict__, "cache_dir": args.cache_dir})

    context = build_context(config)
    input_data = build_calculation_input_data(context)
    field_values = input_data.stress_fields.by_load[args.load_index]
    ranked_elements = _rank_area_elements(input_data.specimen, field_values)

    rank_index = args.area_element_rank - 1
    symmetry_index = args.symmetry_index - 1
    if rank_index < 0 or rank_index >= len(ranked_elements):
        raise ValueError(
            f"area-element-rank must be between 1 and {len(ranked_elements)}"
        )
    if symmetry_index < 0 or symmetry_index >= input_data.specimen.n_symm:
        raise ValueError(
            f"symmetry-index must be between 1 and {input_data.specimen.n_symm}"
        )

    target = ranked_elements[rank_index]
    history_length = (
        input_data.evaluation_points.eval_num_stage1
        + 3 * input_data.evaluation_points.eval_num_stage2
    )
    cycles_result = [10**18] * history_length
    crack_depth_result = [0] * history_length

    print("Targeted element diagnosis")
    print("  config:", args.config_file)
    print("  load_index:", args.load_index)
    print("  area_element_rank:", args.area_element_rank, "/", len(ranked_elements))
    print("  area_element_index:", target.area_element_index)
    print("  symmetry_index:", args.symmetry_index)
    print("  max_shear_stress:", target.max_shear_stress)

    result = calculate_element_life(
        input_data,
        load_index=args.load_index,
        area_element_rank=rank_index,
        area_element_index=target.area_element_index,
        symmetry_index=symmetry_index,
        stress_tensor=target.stress_tensor,
        max_shear_stress=target.max_shear_stress,
        field_values=field_values,
        cycles_result=cycles_result,
        crack_depth_result=crack_depth_result,
    )
    print("Targeted element diagnosis completed")
    print("  minimum_cycles:", result.cycles[-1])
    print("  location_yz:", result.location_yz)


if __name__ == "__main__":
    main()
