from __future__ import annotations

from functools import partial

from .calculation.inputs import (
    CalculationInputData,
    CrackGrowthConstants,
    EvaluationPointDefinition,
    FieldValueProvider,
    MaterialStrengthProperties,
    MicrostructureModel,
    SpecimenGeometry,
    StressFieldData,
    WeightFunctionData,
)
from .material import MaterialDataImporter
from .parameters import PaperModelParameters, generate_euler_angles, resolve_slip_plane


def build_calculation_input_data_from_prepared_objects(
    params: PaperModelParameters,
    material: MaterialDataImporter,
    field_values_by_load: dict[int, FieldValueProvider],
    *,
    weight_function_domain_policy: str = "error",
) -> CalculationInputData:
    return CalculationInputData(
        weight_function_domain_policy=weight_function_domain_policy,
        iteration_numbers=params.iteration_num,
        specimen=_build_specimen_geometry(params),
        crack_growth=_build_crack_growth_constants(params),
        evaluation_points=_build_evaluation_point_definition(params),
        microstructure=_build_microstructure_model(params, material),
        material_strength=_build_material_strength_properties(material),
        weight_function=_build_weight_function_data(material),
        stress_fields=_build_stress_field_data(field_values_by_load),
    )


def _build_specimen_geometry(params: PaperModelParameters) -> SpecimenGeometry:
    return SpecimenGeometry(
        remote_type=params.remote_type,
        width=params.width,
        thickness=params.thickness,
        active_element_area=params.active_element_area,
        active_element_size=params.active_element_size,
        grain_size_lim=params.grain_size_lim,
        stress_lim=params.stress_lim,
        sigma_nom=params.σ_nom,
        ae_num=params.AeNum,
        ae_yz=params.AeYZ,
        n_symm=params.n_symm,
    )


def _build_crack_growth_constants(params: PaperModelParameters) -> CrackGrowthConstants:
    return CrackGrowthConstants(
        r_ratio=params.R_ratio,
        sigma_nom=params.σ_nom,
        c_paris=params.c_paris,
        n_paris=params.n_paris,
        delta_delta_th=params.Δδ_th,
        k_tr=params.k_tr,
        gb_effect=params.gb_effect,
        remote_type=params.remote_type,
    )


def _build_evaluation_point_definition(
    params: PaperModelParameters,
) -> EvaluationPointDefinition:
    return EvaluationPointDefinition(
        eval_num_stage1=params.eval_num_stage1,
        eval_num_stage2=params.eval_num_stage2,
        eval_num_total=params.eval_num_total,
        eval_length_lim=params.eval_lenghth_lim,
        eval_points_full=params.eval_points_full,
        eval_points_stage1=params.eval_points_stage1,
        eval_points_stage2=params.eval_points_stage2,
    )


def _build_microstructure_model(
    params: PaperModelParameters,
    material: MaterialDataImporter,
) -> MicrostructureModel:
    grain = material.grain_distributions
    generated = material.microstructure_data
    return MicrostructureModel(
        first_grain_cdf=grain.first_grain_cdf,
        first_grain_cdfr=grain.first_grain_cdfr,
        first_grain_aspect_cdfr=grain.first_grain_aspect_cdfr,
        first_grain_angle_cdf=grain.first_grain_angle_cdf,
        second_grain_cdf=grain.second_grain_cdf,
        second_grain_cdfr=grain.second_grain_cdfr,
        pearlite_rate_normalized=generated.pearlite_rate_normalized,
        average_grain_size=grain.average_grain_size,
        maximum_grain_size=grain.maximum_grain_size,
        grains_per_area_element=grain.grains_per_area_element,
        generated_grain_data=generated.generated_grain_data,
        grain_layers=generated.grain_layers,
        grains_per_layer=generated.grains_per_layer,
        orientation_generator=generate_euler_angles,
        slip_plane_resolver=partial(resolve_slip_plane, params.crystal),
    )


def _build_material_strength_properties(
    material: MaterialDataImporter,
) -> MaterialStrengthProperties:
    strength = material.mechanical_properties
    return MaterialStrengthProperties(
        yield_strength=strength.yield_strength,
        tensile_strength=strength.tensile_strength,
        reference_stress=strength.reference_stress,
        reduction_in_area=strength.reduction_in_area,
        ferrite_friction_strength=strength.ferrite_friction_strength,
        pearlite_friction_strength=strength.pearlite_friction_strength,
    )


def _build_weight_function_data(material: MaterialDataImporter) -> WeightFunctionData:
    field = material.abaqus_field_cache
    weight = material.weight_function_resources
    return WeightFunctionData(
        crack_interaction_constant=field.crack_interaction_constant,
        qq_function=weight.qq_function,
        secant_ellipse=weight.secant_ellipse,
        weight_function_constants=weight.weight_function_constants,
        stage1_weight_function_points=weight.stage1_weight_function_points,
        stage1_weight_function_values=weight.stage1_weight_function_values,
        stage1_weight_function_has_linear_points=weight.stage1_weight_function_has_linear_points,
        stage1_weight_function_at_min=weight.stage1_weight_function_at_min,
        stage1_weight_function_at_max=weight.stage1_weight_function_at_max,
        stage1_weight_function_ac_min=weight.stage1_weight_function_ac_min,
        stage1_weight_function_ac_max=weight.stage1_weight_function_ac_max,
        stage2_weight_function=weight.stage2_weight_function,
        gauss_weights_10=weight.gauss_weights_10,
        gauss_points_10=weight.gauss_points_10,
        remote_stress_function=weight.remote_stress_function,
    )


def _build_stress_field_data(
    field_values_by_load: dict[int, FieldValueProvider],
) -> StressFieldData:
    return StressFieldData(by_load=field_values_by_load)
