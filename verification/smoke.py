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
            remote_type=0,
            width=1.0,
            thickness=1.0,
            active_element_area=1.0,
            active_element_size=[1.0, 1.0],
            grain_size_lim=0.0,
            stress_lim=1.0,
            sigma_nom=np.array([150.0]),
            ae_num=1,
            ae_yz=np.array([[0.0, 0.0]]),
            n_symm=1,
        ),
        crack_growth=CrackGrowthConstants(
            r_ratio=-1.0,
            sigma_nom=np.array([150.0]),
            c_paris=1.0,
            n_paris=1.0,
            delta_delta_th=0.0,
            k_tr=1.0,
            gb_effect=0,
            remote_type=0,
        ),
        evaluation_points=EvaluationPointDefinition(
            eval_num_stage1=1,
            eval_num_stage2=1,
            eval_num_total=1,
            eval_length_lim=1.0,
            eval_points_full=lambda r1: [r1],
            eval_points_stage1=None,
            eval_points_stage2=[1.0],
        ),
        microstructure=MicrostructureModel(
            first_grain_cdf=lambda r: 1.0,
            first_grain_cdfr=lambda r: 1.0,
            first_grain_aspect_cdfr=lambda r: 1.0,
            first_grain_angle_cdf=lambda r: 0.0,
            second_grain_cdf=lambda r: 1.0,
            second_grain_cdfr=lambda r: 1.0,
            pearlite_rate_normalized=0.0,
            average_grain_size=1.0,
            maximum_grain_size=1.0,
            grains_per_area_element=1.0,
            generated_grain_data=[],
            grain_layers=1,
            grains_per_layer=1,
            orientation_generator=lambda count: np.zeros((count, 3)),
            slip_plane_resolver=lambda *args: (1.0, np.ones(3), np.ones(3)),
        ),
        material_strength=MaterialStrengthProperties(
            yield_strength=1.0,
            tensile_strength=1.0,
            reference_stress=1.0,
            reduction_in_area=1.0,
            ferrite_friction_strength=1.0,
            pearlite_friction_strength=1.0,
        ),
        weight_function=WeightFunctionData(
            crack_interaction_constant=1.0,
            qq_function=lambda asp: 1.0,
            secant_ellipse=lambda asp: 1.0,
            weight_function_constants=[],
            stage1_weight_function_points=np.array([[0.0, 0.0]]),
            stage1_weight_function_values=np.array([1.0]),
            stage1_weight_function_has_linear_points=True,
            stage1_weight_function_at_min=0.0,
            stage1_weight_function_at_max=0.0,
            stage1_weight_function_ac_min=0.0,
            stage1_weight_function_ac_max=0.0,
            stage2_weight_function=lambda at, ac: 1.0,
            gauss_weights_10=np.array([1.0]),
            gauss_points_10=np.array([0.0]),
            remote_stress_function=lambda at, ac: 1.0,
        ),
        field_data=FieldDataForCalculation(
            field_values_by_load={0: _FakeFieldValues()},
            elastic_modulus=1.0,
            poisson_ratio=0.3,
            crack_interaction_constant=1.0,
            node_count=1,
            step_count=1,
            sigma_nom_list=np.array([150.0]),
            sigma_to_step=lambda sigma: 0,
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
