from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .calculation.element_life import calculate_element_life
from .calculation.inputs import CalculationInputData
from .calculation.load_case import LoadCaseResult, calculate_load_case
from .output import OutputContext, write_load_case_outputs


@dataclass
class SimulationResult:
    output_dir: Path | None
    load_case_results: list[LoadCaseResult] = field(default_factory=list)


def run_simulation(
    input_data: CalculationInputData,
    *,
    output_context: OutputContext | None = None,
    write_outputs: bool = True,
    element_life_calculator=calculate_element_life,
) -> SimulationResult:
    """Run all load cases from calculation-only input data.

    Execution order:
    1. Require OutputContext only when CSV writing is enabled.
    2. For each nominal stress, calculate the load case result.
    3. Append the structured result.
    4. Write CSV files outside the calculation package when requested.
    """
    if write_outputs and output_context is None:
        raise ValueError("output_context is required when write_outputs is True")

    output_dir = output_context.output_dir if output_context is not None else None
    result = SimulationResult(output_dir=output_dir)
    for load_index in range(len(input_data.crack_growth.sigma_nom)):
        load_result = calculate_load_case(
            input_data,
            load_index,
            element_life_calculator=element_life_calculator,
        )
        result.load_case_results.append(load_result)
        if write_outputs:
            write_load_case_outputs(output_context, load_result)
    return result
