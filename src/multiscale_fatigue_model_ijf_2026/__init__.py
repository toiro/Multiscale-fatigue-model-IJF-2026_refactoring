"""Refactored reference implementation for the multiscale fatigue model.

This package is organized for reading the paper implementation, not for a
general-purpose library API. Suggested reading order:

1. config.py and parameters.py for input/model conditions.
2. material.py and field_values.py for calculation data preparation.
3. calculation/inputs.py for the physical quantities passed to the kernel.
4. runner.py and calculation/load_case.py for execution order.
5. calculation/element_life.py and calculation/crack_life.py for the model core.
6. output.py for CSV output.
"""

from .calculation import (
    CalculationInputData,
    CrackGrowthConstants,
    ElementLifeResult,
    EvaluationPointDefinition,
    IterationResult,
    LoadCaseResult,
    MaterialStrengthProperties,
    MicrostructureModel,
    SpecimenGeometry,
    StressFieldData,
    WeightFunctionData,
    calculate_crack_life,
    calculate_element_life,
    calculate_load_case,
)
from .config import SimulationConfig
from .context import SimulationContext, build_context
from .output import OutputContext, build_output_context
from .runner import SimulationResult, run_simulation


def main() -> None:
    from .cli import main as cli_main

    cli_main()


__all__ = [
    "SimulationConfig",
    "SimulationContext",
    "CalculationInputData",
    "OutputContext",
    "CrackGrowthConstants",
    "EvaluationPointDefinition",
    "MaterialStrengthProperties",
    "MicrostructureModel",
    "SpecimenGeometry",
    "StressFieldData",
    "WeightFunctionData",
    "build_context",
    "build_output_context",
    "ElementLifeResult",
    "IterationResult",
    "LoadCaseResult",
    "SimulationResult",
    "calculate_crack_life",
    "calculate_element_life",
    "calculate_load_case",
    "run_simulation",
    "main",
]
