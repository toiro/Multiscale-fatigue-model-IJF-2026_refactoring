from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .calculation.element_life import ElementLifeResult
from .calculation.load_case import LoadCaseResult
from .context import SimulationContext


@dataclass(frozen=True)
class OutputContext:
    output_dir: Path
    model_name: str
    n_paris: float
    delta_delta_th: float
    ferrite_friction_strength: float
    r_ratio: float


def build_output_context(context: SimulationContext) -> OutputContext:
    return OutputContext(
        output_dir=context.config.output_dir,
        model_name=context.model_files.output_filename_body,
        n_paris=context.params.n_paris,
        delta_delta_th=context.params.Δδ_th,
        ferrite_friction_strength=context.output_ferrite_friction_strength,
        r_ratio=context.params.R_ratio,
    )


def detail_filename(
    context: OutputContext,
    load_result: LoadCaseResult,
    iteration: int,
) -> str:
    return (
        f"{context.model_name}_{context.n_paris}_{context.delta_delta_th}_"
        f"{load_result.sigma_nom}_{context.ferrite_friction_strength}_"
        f"{iteration}.{context.r_ratio}.csv"
    )


def summary_filename(context: OutputContext, load_result: LoadCaseResult) -> str:
    return (
        f"{context.model_name}_{context.n_paris}_{context.delta_delta_th}_"
        f"{load_result.sigma_nom}_{context.ferrite_friction_strength}."
        f"{context.r_ratio}.csv"
    )


def element_result_to_dataframe(result: ElementLifeResult) -> pd.DataFrame:
    max_len = max(len(result.crack_depth), len(result.grain_boundary_locations))
    return pd.DataFrame(
        {
            "Crack depth": _pad_list(result.crack_depth, max_len),
            "Surface crack length": _pad_list(result.surface_crack_length, max_len),
            "Slip band": _pad_list(result.slip_band, max_len),
            "CTSD": _pad_list(result.ctsd, max_len),
            "Cycles": _pad_list(result.cycles, max_len),
            "K Value": _pad_list(result.k_value, max_len),
            "Effective Stress": _pad_list(result.effective_stress, max_len),
            "Stress Ratio": _pad_list(result.stress_ratio, max_len),
            "Aspect Ratio": _pad_list(result.aspect_ratio, max_len),
            "Opening Stress": _pad_list(result.opening_stress, max_len),
            "Location of GB": _pad_list(result.grain_boundary_locations, max_len),
        }
    )


def summary_to_dataframe(load_result: LoadCaseResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            [
                load_result.sigma_nom,
                iteration.iteration,
                iteration.minimum_life,
                iteration.weakest_location_yz,
            ]
            for iteration in load_result.iteration_results
        ],
        columns=["σ_nom", "Iteration", "minimum life", "yz"],
    )


def write_load_case_outputs(context: OutputContext, load_result: LoadCaseResult) -> None:
    output_dir = context.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for iteration_result in load_result.iteration_results:
        if iteration_result.best_element_result is None:
            continue
        filename = detail_filename(context, load_result, iteration_result.iteration - 1)
        element_result_to_dataframe(iteration_result.best_element_result).to_csv(
            output_dir / filename,
            index=False,
        )

    summary_to_dataframe(load_result).to_csv(
        output_dir / summary_filename(context, load_result),
        index=False,
    )


def _pad_list(values: Sequence[object] | np.ndarray, target_len: int) -> list[object]:
    if isinstance(values, np.ndarray):
        values = values.tolist()
    return list(values) + [np.nan] * (target_len - len(values))
