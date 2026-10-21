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
Stage2WeightFunction = Callable[[float, float], object]
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

    remote_type: int
    width: float
    thickness: float
    active_element_area: float
    active_element_size: list[float]
    grain_size_lim: float
    stress_lim: float
    sigma_nom: np.ndarray
    ae_num: int
    ae_yz: np.ndarray
    n_symm: int


@dataclass(frozen=True)
class CrackGrowthConstants:
    """Fatigue crack-growth constants and model switches.

    This groups Paris-law constants, CTSD threshold, stress ratio, grain-boundary
    effect, remote-stress conversion type, and opening-stress parameter.
    """

    r_ratio: float
    sigma_nom: np.ndarray
    c_paris: float
    n_paris: float
    delta_delta_th: float
    k_tr: float
    gb_effect: int
    remote_type: int


@dataclass(frozen=True)
class EvaluationPointDefinition:
    """Evaluation-point rules for Stage I and Stage II crack growth.

    Stage I points are inside the first grain. Stage II points are outside the
    first grain and may be combined with generated grain-boundary locations.
    """

    eval_num_stage1: int
    eval_num_stage2: int
    eval_num_total: int
    eval_length_lim: float
    eval_points_full: EvaluationPointFunction | None
    eval_points_stage1: EvaluationPointFunction | None
    eval_points_stage2: list[float]


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
    second_grain_cdf: FloatInterpolator
    second_grain_cdfr: FloatInterpolator
    pearlite_rate_normalized: float
    average_grain_size: float
    maximum_grain_size: float
    grains_per_area_element: float
    generated_grain_data: GeneratedGrainData
    grain_layers: int
    grains_per_layer: int
    orientation_generator: Callable[[int], np.ndarray]
    slip_plane_resolver: Callable[..., tuple[object, object, object]]


@dataclass(frozen=True)
class MaterialStrengthProperties:
    """Mechanical and phase friction strengths used by CTSD and initiation."""

    yield_strength: float
    tensile_strength: float
    reference_stress: float
    reduction_in_area: float
    ferrite_friction_strength: float
    pearlite_friction_strength: float


@dataclass(frozen=True)
class WeightFunctionData:
    """Weight-function and remote-stress resources for K-value calculation."""

    crack_interaction_constant: float
    qq_function: FloatInterpolator
    secant_ellipse: FloatInterpolator
    weight_function_constants: WeightFunctionConstants
    stage1_weight_function_points: np.ndarray
    stage1_weight_function_values: np.ndarray
    stage1_weight_function_has_linear_points: bool
    stage1_weight_function_at_min: float
    stage1_weight_function_at_max: float
    stage1_weight_function_ac_min: float
    stage1_weight_function_ac_max: float
    stage2_weight_function: Stage2WeightFunction
    gauss_weights_10: np.ndarray
    gauss_points_10: np.ndarray
    remote_stress_function: FloatInterpolator


@dataclass(frozen=True)
class StressFieldData:
    """Stress field lookup functions used by each nominal-stress load case."""

    by_load: dict[int, FieldValueProvider]


@dataclass(frozen=True)
class CalculationInputData:
    """Physical inputs prepared for the calculation kernel.

    This is a reading view over prepared model parameters and material data. It is
    intentionally not a general-purpose API; it makes the parameter groups that
    enter the paper's calculation model explicit.
    """

    weight_function_domain_policy: str
    iteration_numbers: np.ndarray
    specimen: SpecimenGeometry
    crack_growth: CrackGrowthConstants
    evaluation_points: EvaluationPointDefinition
    microstructure: MicrostructureModel
    material_strength: MaterialStrengthProperties
    weight_function: WeightFunctionData
    stress_fields: StressFieldData
