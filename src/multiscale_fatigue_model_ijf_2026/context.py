from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

import numpy as np

from .abaqus import AbaqusDatabaseCreator, AbaqusImportInput
from .calculation.inputs import (
    CalculationInputData,
    CrackGrowthConstants,
    EvaluationPointDefinition,
    FieldDataForCalculation,
    FieldValueProvider,
    MaterialStrengthProperties,
    MicrostructureModel,
    SpecimenGeometry,
    WeightFunctionData,
)
from .config import SimulationConfig
from .field_values import FieldValuesFunction, FieldValuesInput
from .material import MaterialDataImporter, MaterialImportInput
from .parameters import (
    PaperModelParameters,
    build_parameter_snapshot,
    generate_euler_angles,
    resolve_slip_plane,
)
from .paths import field_values_filename, resolve_cache_path, resolve_condition_dir


@dataclass
class ResolvedModelFiles:
    input_dir: Path
    cache_dir: Path
    model_name: str
    output_filename_body: str
    field_values_cache_filename: str


@dataclass
class SimulationContext:
    config: SimulationConfig
    params: PaperModelParameters
    model_files: ResolvedModelFiles
    material: object
    field_values_by_load: dict[int, FieldValueProvider]
    parameter_snapshot: dict[str, object] = field(default_factory=dict)


def build_context(config: SimulationConfig) -> SimulationContext:
    """Build reusable simulation state before the fatigue calculation starts.

    Execution order:
    1. Seed Python and NumPy random generators when requested.
    2. Resolve input/cache directories and construct paper-model parameters.
    3. Apply lightweight verification overrides from SimulationConfig.
    4. Create the Abaqus field cache if it does not exist.
    5. Load material data and precompute FieldValuesFunction for each load.
    """
    if config.random_seed is not None:
        random.seed(config.random_seed)
        np.random.seed(config.random_seed)

    params = _build_paper_model_parameters(config)
    model_files = _resolve_model_files(config, params)

    pkl_file_name = resolve_cache_path(
        model_files.cache_dir,
        model_files.field_values_cache_filename,
    )
    if not pkl_file_name.exists():
        AbaqusDatabaseCreator(
            _build_abaqus_input(params, model_files),
            base_dir=model_files.input_dir,
            cache_dir=model_files.cache_dir,
        )

    material_input = _build_material_input(params)
    material = MaterialDataImporter(
        material_input, base_dir=model_files.input_dir, cache_dir=model_files.cache_dir
    )
    field_values_input = _build_field_values_input(params)
    field_values_by_load = {
        load_index: FieldValuesFunction(field_values_input, material, load_index)
        for load_index in range(len(params.σ_nom))
    }

    return SimulationContext(
        config=config,
        params=params,
        model_files=model_files,
        material=material,
        field_values_by_load=field_values_by_load,
        parameter_snapshot=build_parameter_snapshot(params),
    )


def build_calculation_input_data(context: SimulationContext) -> CalculationInputData:
    return build_calculation_input_data_from_prepared_objects(
        context.params,
        context.material,
        context.field_values_by_load,
    )


def _build_paper_model_parameters(config: SimulationConfig) -> PaperModelParameters:
    params = PaperModelParameters(
        **{
            key: value
            for key, value in {
                "steel": config.steel,
                "specimen_type": config.specimen_type,
                "thickness_sign": config.thickness_sign,
                "crystal": config.crystal,
                "r_ratio": config.r_ratio,
                "c_paris": config.c_paris,
                "n_paris": config.n_paris,
                "delta_delta_th": config.delta_delta_th,
            }.items()
            if value is not None
        }
    )
    _apply_config_overrides(params, config)
    return params


def _resolve_model_files(
    config: SimulationConfig,
    params: PaperModelParameters,
) -> ResolvedModelFiles:
    condition = params.condition
    input_dir = resolve_condition_dir(config.base_dir, condition.model_name)
    if config.cache_dir:
        cache_dir = Path(config.cache_dir).resolve() / condition.model_name
    else:
        cache_dir = resolve_condition_dir(Path(config.base_dir), condition.model_name)
    cache_dir.mkdir(parents=True, exist_ok=True)
    return ResolvedModelFiles(
        input_dir=input_dir,
        cache_dir=cache_dir,
        model_name=condition.model_name,
        output_filename_body=condition.model_name,
        field_values_cache_filename=field_values_filename(
            steel=condition.steel,
            specimen_type=condition.specimen_type,
        ),
    )


def _build_abaqus_input(
    params: PaperModelParameters,
    model_files: ResolvedModelFiles,
) -> AbaqusImportInput:
    return AbaqusImportInput(
        model_name=model_files.model_name,
        steel=params.steel,
        specimen_type=params.specimen_type,
        nominal_stress_extraction_mode=params.nominal_stress_extraction_mode,
        width=params.width,
        thickness=params.thickness,
    )


def _build_material_input(params: PaperModelParameters) -> MaterialImportInput:
    return MaterialImportInput(
        steel=params.steel,
        specimen_type=params.specimen_type,
        weight_function_table_family=params.weight_function_table_family,
        thickness=params.thickness,
        active_element_area=params.active_element_area,
        first_grain=params.FirstGrain,
        second_grain=params.SecondGrain,
    )


def _build_field_values_input(params: PaperModelParameters) -> FieldValuesInput:
    return FieldValuesInput(
        sigma_nom=params.σ_nom,
        y_lim=params.y_lim,
        z_lim=params.z_lim,
        active_element_size=params.active_element_size,
        thickness=params.thickness,
    )


def build_calculation_input_data_from_prepared_objects(
    params: PaperModelParameters,
    material: object,
    field_values_by_load: dict[int, FieldValueProvider],
) -> CalculationInputData:
    return CalculationInputData(
        iteration_numbers=params.iteration_num,
        specimen=_build_specimen_geometry(params),
        crack_growth=_build_crack_growth_constants(params),
        evaluation_points=_build_evaluation_point_definition(params),
        microstructure=_build_microstructure_model(params, material),
        material_strength=_build_material_strength_properties(material),
        weight_function=_build_weight_function_data(material),
        field_data=_build_field_data_for_calculation(material, field_values_by_load),
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
    material: object,
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


def _build_material_strength_properties(material: object) -> MaterialStrengthProperties:
    strength = material.mechanical_properties
    return MaterialStrengthProperties(
        yield_strength=strength.yield_strength,
        tensile_strength=strength.tensile_strength,
        reference_stress=strength.reference_stress,
        reduction_in_area=strength.reduction_in_area,
        ferrite_friction_strength=strength.ferrite_friction_strength,
        pearlite_friction_strength=strength.pearlite_friction_strength,
    )


def _build_weight_function_data(material: object) -> WeightFunctionData:
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


def _build_field_data_for_calculation(
    material: object,
    field_values_by_load: dict[int, FieldValueProvider],
) -> FieldDataForCalculation:
    field = material.abaqus_field_cache
    return FieldDataForCalculation(
        field_values_by_load=field_values_by_load,
        elastic_modulus=field.elastic_modulus,
        poisson_ratio=field.poisson_ratio,
        crack_interaction_constant=field.crack_interaction_constant,
        node_count=field.node_count,
        step_count=field.step_count,
        sigma_nom_list=field.sigma_nom_list,
        sigma_to_step=field.sigma_to_step,
        elastic_field_interpolators=field.elastic_field_interpolators,
        plastic_field_interpolators=field.plastic_field_interpolators,
        total_field_interpolators=field.total_field_interpolators,
    )


def _apply_config_overrides(params: PaperModelParameters, config: SimulationConfig) -> None:
    if config.sigma_nom is not None:
        sigma_nom = np.array(config.sigma_nom)
        if np.all(np.equal(np.mod(sigma_nom, 1), 0)):
            sigma_nom = sigma_nom.astype(int)
        params.σ_nom = sigma_nom
    if config.iteration_count is not None:
        if config.iteration_count < 1:
            raise ValueError("iteration_count must be greater than or equal to 1")
        params.iteration_num = np.arange(0, config.iteration_count, 1)
    if config.n_symm is not None:
        params.n_symm = config.n_symm
    if config.max_active_elements is not None:
        if config.max_active_elements < 1:
            raise ValueError("max_active_elements must be greater than or equal to 1")
        params.stress_lim = min(1.0, config.max_active_elements / params.AeNum)
