from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, TypeAlias

import numpy as np

Number: TypeAlias = int | float | np.integer | np.floating
NumericValue: TypeAlias = Number | np.ndarray
NumericHistory: TypeAlias = list[NumericValue]
LocationYZ: TypeAlias = list[float] | list[str]
StressTensor: TypeAlias = np.ndarray
FloatInterpolator = Callable[..., object]
EvaluationPointFunction = Callable[[float], list[float]]
WeightFunctionConstants: TypeAlias = list[list[Number]]
GeneratedGrainData: TypeAlias = list[list[Number]]


class FieldValueProvider(Protocol):
    def active_element_total_field_by_depth(
        self,
        x: float,
        y: float,
        z: float,
    ) -> list[Number]:
        ...

    def active_surface_total_field_by_nominal_stress(
        self,
        sigma_nom: float,
        y: float,
        z: float,
    ) -> list[Number]:
        ...


@dataclass(frozen=True)
class SpecimenGeometry:
    """Specimen and active-area conditions used by the crack-growth calculation.

    These values come from prepared paper-model parameters and correspond to the specimen geometry,
    active zone, applied nominal stress list, and symmetry settings.
    """

    specimen_type: str | None
    remote_type: int | None
    width: float | None
    thickness: float | None
    active_element_area: float | None
    active_element_size: list[float] | None
    grain_size_lim: float | None
    stress_lim: float | None
    sigma_nom: np.ndarray | None
    ae_num: int | None
    ae_yz: np.ndarray | None
    n_symm: int | None


@dataclass(frozen=True)
class CrackGrowthConstants:
    """Fatigue crack-growth constants and model switches.

    This groups Paris-law constants, CTSD threshold, stress ratio, grain-boundary
    effect, remote-stress conversion type, and opening-stress parameter.
    """

    r_ratio: float | None
    sigma_nom: np.ndarray | None
    c_paris: float | None
    n_paris: float | None
    delta_delta_th: float | None
    k_tr: float | None
    gb_effect: int | None
    remote_type: int | None


@dataclass(frozen=True)
class EvaluationPointDefinition:
    """Evaluation-point rules for Stage I and Stage II crack growth.

    Stage I points are inside the first grain. Stage II points are outside the
    first grain and may be combined with generated grain-boundary locations.
    """

    eval_num_stage1: int | None
    eval_num_stage2: int | None
    eval_num_total: int | None
    eval_length_lim: float | None
    eval_points_full: EvaluationPointFunction | None
    eval_points_stage1: EvaluationPointFunction | None
    eval_points_stage2: list[float] | None


@dataclass(frozen=True)
class MicrostructureModel:
    """Microstructure distributions and generated stochastic grain data.

    Distribution fields come from measured CSV inputs. generated_grain_data,
    grain_layers, and grains_per_layer come from the cached/generated model
    microstructure and are kept together because their random sequence matters.
    """

    first_grain_cdf: FloatInterpolator
    first_grain_cdfr: FloatInterpolator
    first_grain_aspect_cdfr: FloatInterpolator
    first_grain_angle_cdf: FloatInterpolator
    second_grain_cdf: FloatInterpolator | None
    second_grain_cdfr: FloatInterpolator | None
    pearlite_rate_normalized: float | None
    average_grain_size: float | None
    maximum_grain_size: float | None
    grains_per_area_element: float | None
    generated_grain_data: GeneratedGrainData
    grain_layers: int | None
    grains_per_layer: int | None
    orientation_generator: Callable[[int], np.ndarray]
    slip_plane_resolver: Callable[..., tuple[object, object, object]]


@dataclass(frozen=True)
class MaterialStrengthProperties:
    """Mechanical and phase friction strengths used by CTSD and initiation."""

    yield_strength: float | None
    tensile_strength: float | None
    reference_stress: float | None
    reduction_in_area: float | None
    ferrite_friction_strength: float | None
    pearlite_friction_strength: float | None


@dataclass(frozen=True)
class WeightFunctionData:
    """Weight-function and remote-stress resources for K-value calculation."""

    crack_interaction_constant: float | None
    qq_function: FloatInterpolator
    secant_ellipse: FloatInterpolator
    weight_function_constants: WeightFunctionConstants
    weight_function_rbf: object
    weight_function_rbf_low: object
    weight_function_rbf_high: object
    gauss_weights_10: np.ndarray
    gauss_points_10: np.ndarray
    remote_stress_function: FloatInterpolator


@dataclass(frozen=True)
class FieldDataForCalculation:
    """Abaqus field cache and precomputed field values used in stress lookup."""

    field_values_by_load: dict[int, FieldValueProvider] | None
    elastic_modulus: float | None
    poisson_ratio: float | None
    crack_interaction_constant: float | None
    node_count: int | None
    step_count: int | None
    sigma_nom_list: np.ndarray | None
    sigma_to_step: FloatInterpolator | None
    elastic_field_interpolators: object
    plastic_field_interpolators: object
    total_field_interpolators: object


@dataclass(frozen=True)
class CalculationInputData:
    """Physical inputs prepared for the calculation kernel.

    This is a reading view over prepared model parameters and material data. It is
    intentionally not a general-purpose API; it makes the parameter groups that
    enter the paper's calculation model explicit.
    """

    iteration_numbers: np.ndarray | None
    specimen: SpecimenGeometry
    crack_growth: CrackGrowthConstants
    evaluation_points: EvaluationPointDefinition
    microstructure: MicrostructureModel
    material_strength: MaterialStrengthProperties
    weight_function: WeightFunctionData
    field_data: FieldDataForCalculation
