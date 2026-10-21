from __future__ import annotations

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np

from .element_life import ElementLifeResult, calculate_element_life
from .inputs import (
    CalculationInputData,
    FieldValueProvider,
    LocationYZ,
    SpecimenGeometry,
)


@dataclass(frozen=True)
class AreaElementStress:
    area_element_index: int
    stress_tensor: np.ndarray
    max_shear_stress: float


@dataclass
class IterationResult:
    iteration: int
    minimum_life: float
    weakest_location_yz: LocationYZ | None
    best_element_result: ElementLifeResult | None
    complete_element_count: int = 0
    domain_limited_element_count: int = 0
    incomplete_element_count: int = 0


@dataclass
class LoadCaseResult:
    load_index: int
    sigma_nom: float
    iteration_results: list[IterationResult] = field(default_factory=list)


def calculate_load_case(
    input_data: CalculationInputData,
    load_index: int,
    *,
    element_life_calculator: Callable[..., ElementLifeResult] = calculate_element_life,
) -> LoadCaseResult:
    """Calculate fatigue life for one nominal-stress load case.

    Execution order:
    1. Select field values for the load index.
    2. Rank active area elements by maximum shear stress.
    3. Loop over iterations, ranked area elements, and symmetry positions.
    4. Delegate one-element life calculation.
    5. Keep the shortest life and weakest location for the load case.
    """
    specimen = input_data.specimen
    evaluation_points = input_data.evaluation_points
    iteration_numbers = input_data.iteration_numbers
    field_values = input_data.stress_fields.by_load[load_index]

    ranked_elements = _rank_area_elements(specimen, field_values)
    imax = min(round(specimen.ae_num * specimen.stress_lim), len(ranked_elements))

    load_result = LoadCaseResult(
        load_index=load_index,
        sigma_nom=input_data.crack_growth.sigma_nom[load_index],
    )

    print("imax :", imax)
    for iteration_index in range(len(iteration_numbers)):
        min_cycles = 10**18
        best_result: ElementLifeResult | None = None
        partial_result: ElementLifeResult | None = None
        weakest_location = None
        complete_element_count = 0
        domain_limited_element_count = 0
        incomplete_element_count = 0

        s_ai_sub = [0] * (
            evaluation_points.eval_num_stage1 + 3 * evaluation_points.eval_num_stage2
        )
        s_cyc_sub = [10**18] * (
            evaluation_points.eval_num_stage1 + 3 * evaluation_points.eval_num_stage2
        )

        for rank in range(imax):
            print("Element", rank + 1, "Total:", imax)
            for symmetry_index in range(specimen.n_symm):
                print("  Symmetry", symmetry_index + 1, "Total:", specimen.n_symm)
                element_result = element_life_calculator(
                    input_data,
                    load_index=load_index,
                    area_element_rank=rank,
                    area_element_index=ranked_elements[rank].area_element_index,
                    symmetry_index=symmetry_index,
                    stress_tensor=ranked_elements[rank].stress_tensor,
                    max_shear_stress=ranked_elements[rank].max_shear_stress,
                    field_values=field_values,
                    cycles_result=s_cyc_sub,
                    crack_depth_result=s_ai_sub,
                )
                if element_result.is_complete:
                    complete_element_count += 1
                else:
                    incomplete_element_count += 1
                    if element_result.stop_reason == "weight_function_domain_limit":
                        domain_limited_element_count += 1
                    if partial_result is None:
                        partial_result = element_result

                if (
                    element_result.is_complete
                    and element_result.cycles[-1] < s_cyc_sub[-1]
                ):
                    s_cyc_sub = element_result.cycles
                    s_ai_sub = element_result.crack_depth
                    best_result = element_result

            if best_result is not None and best_result.cycles[-1] < min_cycles:
                min_cycles = best_result.cycles[-1]
                weakest_location = best_result.location_yz

        output_result = best_result if best_result is not None else partial_result

        load_result.iteration_results.append(
            IterationResult(
                iteration=int(iteration_numbers[iteration_index]) + 1,
                minimum_life=min_cycles,
                weakest_location_yz=weakest_location,
                best_element_result=output_result,
                complete_element_count=complete_element_count,
                domain_limited_element_count=domain_limited_element_count,
                incomplete_element_count=incomplete_element_count,
            )
        )

        if weakest_location is not None:
            print(
                "  Nf=",
                min_cycles,
                "   (y,z)=(",
                weakest_location[0],
                ",",
                weakest_location[1],
                ")  ",
                datetime.datetime.now(),
            )

    return load_result


def _rank_area_elements(
    specimen: SpecimenGeometry,
    field_values: FieldValueProvider,
) -> list[AreaElementStress]:
    def stress_ae(index: int) -> AreaElementStress | None:
        y = specimen.ae_yz[index, 0]
        z = specimen.ae_yz[index, 1]
        stress = np.array(field_values.active_element_total_field_by_depth(0, y, z))
        if np.isnan(stress[0]):
            return None
        sigma_11, sigma_22, sigma_33, tau_12, tau_13, tau_23 = (2 * stress).tolist()
        delta_sigma = np.array(
            [
                [sigma_11, tau_12, tau_13],
                [tau_12, sigma_22, tau_23],
                [tau_13, tau_23, sigma_33],
            ]
        )
        eigenvalues = np.linalg.eigvals(delta_sigma)
        tau_max = (max(eigenvalues) - min(eigenvalues)) / 2.0
        return AreaElementStress(
            area_element_index=index,
            stress_tensor=delta_sigma,
            max_shear_stress=tau_max,
        )

    stress_list = [stress_ae(index) for index in range(specimen.ae_num)]
    return sorted(
        [item for item in stress_list if item is not None],
        key=lambda item: item.max_shear_stress,
        reverse=True,
    )
