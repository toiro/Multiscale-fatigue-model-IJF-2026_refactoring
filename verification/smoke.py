from __future__ import annotations

from pathlib import Path

import numpy as np

from multiscale_fatigue_model_ijf_2026.calculation import calculate_load_case
from multiscale_fatigue_model_ijf_2026.calculation.inputs import (
    CalculationInputData,
    CrackGrowthConstants,
    EvaluationPointDefinition,
    FieldDataForCalculation,
    MaterialStrengthProperties,
    MicrostructureModel,
    SpecimenGeometry,
    WeightFunctionData,
)
from multiscale_fatigue_model_ijf_2026.config import SimulationConfig


def run_import_smoke(repo_root: Path) -> None:
    config = SimulationConfig.smoke(repo_root=repo_root)
    if config.random_seed != 42:
        raise AssertionError("smoke config did not preserve the expected seed")
    if config.max_active_elements != 1:
        raise AssertionError("smoke config did not preserve max_active_elements")


def run_mock_calculation_smoke(repo_root: Path) -> None:
    input_data = _build_mock_input_data()

    result = calculate_load_case(
        input_data,
        0,
        element_life_calculator=_fake_element_life,
    )
    if result.sigma_nom != 150.0:
        raise AssertionError("mock calculation returned an unexpected sigma_nom")
    if len(result.iteration_results) != 1:
        raise AssertionError("mock calculation did not return one iteration result")
    if result.iteration_results[0].minimum_life != 10.0:
        raise AssertionError("mock calculation did not preserve the expected minimum life")


class _FakeFieldValues:
    def FieldValues_ACTIVE_Numpy(self, x: float, y: float, z: float) -> list[float]:
        return [1.0, 2.0, 0.5, 0.1, 0.0, 0.0]

    def active_element_total_field_by_depth(
        self,
        x: float,
        y: float,
        z: float,
    ) -> list[float]:
        return self.FieldValues_ACTIVE_Numpy(x, y, z)

    def active_surface_total_field_by_nominal_stress(
        self,
        sigma_nom: float,
        y: float,
        z: float,
    ) -> list[float]:
        return self.FieldValues_ACTIVE_Numpy(0, y, z)


def _build_mock_input_data() -> CalculationInputData:
    return CalculationInputData(
        iteration_numbers=np.array([0]),
        specimen=SpecimenGeometry(
            specimen_type=None,
            remote_type=None,
            width=None,
            thickness=None,
            active_element_area=None,
            active_element_size=None,
            grain_size_lim=None,
            stress_lim=1.0,
            sigma_nom=np.array([150.0]),
            ae_num=1,
            ae_yz=np.array([[0.0, 0.0]]),
            n_symm=1,
        ),
        crack_growth=CrackGrowthConstants(
            r_ratio=None,
            sigma_nom=np.array([150.0]),
            c_paris=None,
            n_paris=None,
            delta_delta_th=None,
            k_tr=None,
            gb_effect=None,
            remote_type=None,
        ),
        evaluation_points=EvaluationPointDefinition(
            eval_num_stage1=1,
            eval_num_stage2=1,
            eval_num_total=None,
            eval_length_lim=None,
            eval_points_full=None,
            eval_points_stage1=None,
            eval_points_stage2=None,
        ),
        microstructure=MicrostructureModel(
            first_grain_cdf=None,
            first_grain_cdfr=None,
            first_grain_aspect_cdfr=None,
            first_grain_angle_cdf=None,
            second_grain_cdf=None,
            second_grain_cdfr=None,
            pearlite_rate_normalized=None,
            average_grain_size=None,
            maximum_grain_size=None,
            grains_per_area_element=None,
            generated_grain_data=None,
            grain_layers=None,
            grains_per_layer=None,
            orientation_generator=None,
            slip_plane_resolver=None,
        ),
        material_strength=MaterialStrengthProperties(
            yield_strength=None,
            tensile_strength=None,
            reference_stress=None,
            reduction_in_area=None,
            ferrite_friction_strength=None,
            pearlite_friction_strength=None,
        ),
        weight_function=WeightFunctionData(
            crack_interaction_constant=None,
            qq_function=None,
            secant_ellipse=None,
            weight_function_constants=None,
            weight_function_rbf=None,
            weight_function_rbf_low=None,
            weight_function_rbf_high=None,
            gauss_weights_10=None,
            gauss_points_10=None,
            remote_stress_function=None,
        ),
        field_data=FieldDataForCalculation(
            field_values_by_load={0: _FakeFieldValues()},
            elastic_modulus=None,
            poisson_ratio=None,
            crack_interaction_constant=None,
            node_count=None,
            step_count=None,
            sigma_nom_list=None,
            sigma_to_step=None,
            elastic_field_interpolators=None,
            plastic_field_interpolators=None,
            total_field_interpolators=None,
        ),
    )


def _fake_element_life(input_data: CalculationInputData, **kwargs: object):
    from multiscale_fatigue_model_ijf_2026.calculation.element_life import (
        ElementLifeResult,
    )

    return ElementLifeResult(
        area_element_rank=kwargs["area_element_rank"],
        area_element_index=kwargs["area_element_index"],
        symmetry_index=kwargs["symmetry_index"],
        location_yz=[0.0, 0.0],
        cycles=[10.0],
        crack_depth=[0.1],
        surface_crack_length=[0.2],
        slip_band=[0.3],
        ctsd=[0.0001],
        k_value=[1.2],
        effective_stress=[150.0],
        stress_ratio=[-1.0],
        aspect_ratio=[1.0],
        opening_stress=[10.0],
        grain_boundary_locations=[0.0],
    )
