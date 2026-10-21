from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .abaqus import AbaqusDatabaseCreator, AbaqusImportInput
from .calculation.inputs import CalculationInputData
from .config import SimulationConfig
from .field_values import FieldValuesFunction, FieldValuesInput
from .input_preparation import build_calculation_input_data_from_prepared_objects
from .material import MaterialDataImporter, MaterialImportInput
from .parameters import PaperModelParameters, build_parameter_snapshot
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
    input_data: CalculationInputData
    output_ferrite_friction_strength: float
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
    input_data = build_calculation_input_data_from_prepared_objects(
        params,
        material,
        field_values_by_load,
        weight_function_domain_policy=config.weight_function_domain_policy,
    )

    return SimulationContext(
        config=config,
        params=params,
        model_files=model_files,
        input_data=input_data,
        output_ferrite_friction_strength=(
            material.mechanical_properties.ferrite_friction_strength
        ),
        parameter_snapshot=build_parameter_snapshot(params),
    )


def build_calculation_input_data(context: SimulationContext) -> CalculationInputData:
    return context.input_data


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
