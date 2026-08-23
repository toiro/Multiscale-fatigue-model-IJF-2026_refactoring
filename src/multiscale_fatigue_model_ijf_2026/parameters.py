from __future__ import annotations

import warnings
from dataclasses import dataclass
from enum import StrEnum
from typing import Callable

import numpy as np

from .paths import specimen_model_name

# Warning policy: keep legacy suppression until numerical-warning handling is reviewed.
warnings.filterwarnings("ignore", category=np.RankWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)


@dataclass(frozen=True)
class SpecimenDimensionDefinition:
    width: float
    thickness: float


@dataclass(frozen=True)
class ActiveZoneDefinition:
    y_lim: float
    z_lim: float
    grain_size_lim: float
    active_element_size: list[float]
    stress_lim: float
    active_element_area: float
    ae_num_y: int
    ae_num_z: int
    ae_num: int
    ae_yz: np.ndarray


@dataclass(frozen=True)
class EvaluationPointRules:
    eval_num_stage1: int
    eval_num_stage2: int
    eval_num_total: int
    eval_length_lim: float
    eval_points_full: Callable[[float], list[float]] | None
    eval_points_stage1: Callable[[float], list[float]] | None
    eval_points_stage2: list[float]


class WeightFunctionTableFamily(StrEnum):
    SMOOTH = "smooth"
    THREE_POINT_BENDING = "three_point_bending"
    COMPACT_SPECIMEN = "compact_specimen"


class NominalStressExtractionMode(StrEnum):
    SMOOTH_DSLOAD = "smooth_dsload"
    THREE_POINT_BENDING_RF1 = "three_point_bending_rf1"
    COMPACT_SPECIMEN_DSLOAD = "compact_specimen_dsload"


@dataclass(frozen=True)
class ActiveZoneSpec:
    y_lim: float
    z_lim: float
    grain_size_lim: float
    active_element_size: list[float]
    stress_lim_by_steel: dict[str, float]


@dataclass(frozen=True)
class SimulationCondition:
    steel: str
    specimen_type: str
    thickness_sign: str
    model_name: str


@dataclass(frozen=True)
class ResolvedParameterCondition:
    condition: SimulationCondition
    dimensions: SpecimenDimensionDefinition
    active_zone: ActiveZoneDefinition
    evaluation_points: EvaluationPointRules
    cache_name_key: str
    weight_function_table_family: WeightFunctionTableFamily
    nominal_stress_extraction_mode: NominalStressExtractionMode


SUPPORTED_PARAMETER_CONDITIONS = {
    ("B", "Smooth", "T16"),
    ("B", "R008", "T24"),
    ("B", "R100", "T24"),
    ("G", "Smooth", "T16"),
    ("G", "R008", "T24"),
    ("G", "R100", "T24"),
    ("N50R", "Smooth", "T16"),
    ("N50R", "R008", "T24"),
    ("N50R", "R100", "T24"),
    ("N50R", "CS", "T50"),
}

THICKNESS_BY_SIGN = {
    "T16": 1.35,
    "T24": 1.9,
    "T50": 4.5,
}

WIDTH_BY_SPECIMEN_TYPE = {
    "Smooth": 5.0,
    "R008": 5.0,
    "R100": 5.0,
    "CS": 1.5,
}

ACTIVE_ZONE_BY_SPECIMEN_TYPE = {
    "Smooth": ActiveZoneSpec(
        y_lim=1.5,
        z_lim=2.5,
        grain_size_lim=0.2,
        active_element_size=[0.1, 0.1],
        stress_lim_by_steel={"B": 0.1, "G": 0.1, "N50R": 0.1},
    ),
    "R008": ActiveZoneSpec(
        y_lim=0.04,
        z_lim=2.5,
        grain_size_lim=0.2,
        active_element_size=[0.02, 0.05],
        stress_lim_by_steel={"B": 0.2, "G": 0.2, "N50R": 0.2},
    ),
    "R100": ActiveZoneSpec(
        y_lim=0.5,
        z_lim=2.5,
        grain_size_lim=0.2,
        active_element_size=[0.125, 0.125],
        stress_lim_by_steel={"B": 0.5, "G": 0.5, "N50R": 0.4},
    ),
    "CS": ActiveZoneSpec(
        y_lim=0.025,
        z_lim=0.75,
        grain_size_lim=0.3,
        active_element_size=[0.025, 0.15],
        stress_lim_by_steel={"G": 1.0, "N50R": 1.0},
    ),
}

STAGE2_POINTS_T16 = [
    0.05,
    0.10,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.35,
]

STAGE2_POINTS_T24 = [
    0.05,
    0.10,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.4,
    1.5,
    1.6,
    1.7,
    1.8,
]

STAGE2_POINTS_T50 = [
    0.05,
    0.10,
    0.15,
    0.2,
    0.25,
    0.3,
    0.35,
    0.4,
    0.5,
    0.6,
    0.7,
    0.8,
    0.9,
    1.0,
    1.1,
    1.2,
    1.3,
    1.4,
    1.5,
    1.6,
    1.7,
    1.8,
    1.9,
    2.0,
    2.1,
    2.2,
    2.3,
    2.4,
    2.5,
    2.6,
    2.7,
    2.8,
    2.9,
    3.0,
    3.1,
    3.2,
    3.3,
    3.4,
    3.5,
    3.6,
    3.7,
    3.8,
    3.9,
    4.0,
    4.1,
    4.2,
    4.3,
    4.4,
]

STAGE2_POINTS_BY_CONDITION = {
    ("B", "Smooth", "T16"): STAGE2_POINTS_T16,
    ("B", "R008", "T24"): STAGE2_POINTS_T24,
    ("B", "R100", "T24"): STAGE2_POINTS_T24,
    ("G", "Smooth", "T16"): STAGE2_POINTS_T16,
    ("G", "R008", "T24"): STAGE2_POINTS_T24,
    ("G", "R100", "T24"): STAGE2_POINTS_T24,
    ("N50R", "Smooth", "T16"): STAGE2_POINTS_T16,
    ("N50R", "R008", "T24"): STAGE2_POINTS_T24,
    ("N50R", "R100", "T24"): STAGE2_POINTS_T24,
    ("N50R", "CS", "T50"): STAGE2_POINTS_T50,
}

WEIGHT_FUNCTION_TABLE_FAMILY_BY_SPECIMEN_TYPE = {
    "Smooth": WeightFunctionTableFamily.SMOOTH,
    "R008": WeightFunctionTableFamily.THREE_POINT_BENDING,
    "R100": WeightFunctionTableFamily.THREE_POINT_BENDING,
    "CS": WeightFunctionTableFamily.COMPACT_SPECIMEN,
}

NOMINAL_STRESS_EXTRACTION_MODE_BY_SPECIMEN_TYPE = {
    "Smooth": NominalStressExtractionMode.SMOOTH_DSLOAD,
    "R008": NominalStressExtractionMode.THREE_POINT_BENDING_RF1,
    "R100": NominalStressExtractionMode.THREE_POINT_BENDING_RF1,
    "CS": NominalStressExtractionMode.COMPACT_SPECIMEN_DSLOAD,
}


class PaperModelParameters:
    """Paper-model input conditions derived before calculation starts.

    This is a mutable attribute bundle only because lightweight verification
    overrides update a few values after construction. The derivation logic lives
    in module-level functions below so researchers can read it without chasing
    class state changes.
    """

    def __init__(
        self,
        *,
        steel: str = "N50R",
        specimen_type: str = "CS",
        thickness_sign: str = "T50",
        crystal: str = "BCC",
        r_ratio: float = -1,
        c_paris: float = 18,
        n_paris: float = 1.8,
        delta_delta_th: float = 0.000063,
    ):
        resolved_condition = resolve_parameter_condition(
            steel=steel,
            specimen_type=specimen_type,
            thickness_sign=thickness_sign,
            gb_effect=1,
        )
        self.resolved_condition = resolved_condition
        self.condition = resolved_condition.condition
        self.steel = self.condition.steel
        self.specimen_type = self.condition.specimen_type
        self.thickness_sign = self.condition.thickness_sign
        self.type = self.specimen_type
        self.T = self.thickness_sign
        self.name = self.condition.model_name
        self.cache_name_key = resolved_condition.cache_name_key
        self.weight_function_table_family = (
            resolved_condition.weight_function_table_family
        )
        self.nominal_stress_extraction_mode = (
            resolved_condition.nominal_stress_extraction_mode
        )
        self.crystal = crystal

        self.n_symm = 4
        self.iteration_num = np.arange(0, 4, 1)
        self.FirstGrain = "Ferrite"
        self.SecondGrain = "Pearlite"

        self.closure_type = 2
        self.R_ratio = r_ratio
        self.σ_nom = np.arange(150, 200, 10)
        self.k_tr = 2 * 14
        self.gb_effect = 1
        self.remote_type = 2
        self.c_paris = c_paris
        self.n_paris = n_paris
        self.Δδ_th = delta_delta_th

        dimensions = resolved_condition.dimensions
        active_zone = resolved_condition.active_zone
        evaluation_points = resolved_condition.evaluation_points

        self.width = dimensions.width
        self.thickness = dimensions.thickness
        self.y_lim = active_zone.y_lim
        self.z_lim = active_zone.z_lim
        self.grain_size_lim = active_zone.grain_size_lim
        self.active_element_size = active_zone.active_element_size
        self.active_element_area = active_zone.active_element_area
        self.stress_lim = active_zone.stress_lim
        self.AeNumY = active_zone.ae_num_y
        self.AeNumZ = active_zone.ae_num_z
        self.AeNum = active_zone.ae_num
        self.AeYZ = active_zone.ae_yz

        self.eval_num_stage1 = evaluation_points.eval_num_stage1
        self.eval_num_stage2 = evaluation_points.eval_num_stage2
        self.eval_num_total = evaluation_points.eval_num_total
        self.eval_lenghth_lim = evaluation_points.eval_length_lim
        self.eval_points_full = evaluation_points.eval_points_full
        self.eval_points_stage1 = evaluation_points.eval_points_stage1
        self.eval_points_stage2 = evaluation_points.eval_points_stage2


def resolve_parameter_condition(
    *,
    steel: str,
    specimen_type: str,
    thickness_sign: str,
    gb_effect: int,
) -> ResolvedParameterCondition:
    _validate_parameter_condition(
        steel=steel,
        specimen_type=specimen_type,
        thickness_sign=thickness_sign,
    )
    condition = SimulationCondition(
        steel=steel,
        specimen_type=specimen_type,
        thickness_sign=thickness_sign,
        model_name=specimen_model_name(
            steel=steel,
            specimen_type=specimen_type,
            thickness_sign=thickness_sign,
        ),
    )
    dimensions = build_specimen_dimensions(
        specimen_type=specimen_type,
        thickness_sign=thickness_sign,
    )
    active_zone = build_active_zone(steel=steel, specimen_type=specimen_type)
    evaluation_points = build_evaluation_point_rules(
        steel=steel,
        specimen_type=specimen_type,
        thickness_sign=thickness_sign,
        thickness=dimensions.thickness,
        gb_effect=gb_effect,
    )
    return ResolvedParameterCondition(
        condition=condition,
        dimensions=dimensions,
        active_zone=active_zone,
        evaluation_points=evaluation_points,
        cache_name_key=f"{steel}_{specimen_type}",
        weight_function_table_family=_weight_function_table_family(specimen_type),
        nominal_stress_extraction_mode=_nominal_stress_extraction_mode(
            specimen_type
        ),
    )


def build_specimen_dimensions(
    *,
    specimen_type: str,
    thickness_sign: str,
) -> SpecimenDimensionDefinition:
    try:
        width = WIDTH_BY_SPECIMEN_TYPE[specimen_type]
        thickness = THICKNESS_BY_SIGN[thickness_sign]
    except KeyError as error:
        raise ValueError(
            "Unsupported specimen dimension condition: "
            f"specimen_type={specimen_type}, thickness_sign={thickness_sign}"
        ) from error

    return SpecimenDimensionDefinition(
        width=width,
        thickness=thickness,
    )


def build_active_zone(*, steel: str, specimen_type: str) -> ActiveZoneDefinition:
    """Define the active surface area evaluated for crack initiation."""

    try:
        spec = ACTIVE_ZONE_BY_SPECIMEN_TYPE[specimen_type]
        stress_lim = spec.stress_lim_by_steel[steel]
    except KeyError as error:
        raise ValueError(
            "Unsupported active-zone condition: "
            f"steel={steel}, specimen_type={specimen_type}"
        ) from error

    active_element_size = spec.active_element_size
    active_element_area = active_element_size[0] * active_element_size[1]
    ae_num_y = int(spec.y_lim / active_element_size[0])
    ae_num_z = int(spec.z_lim / active_element_size[1])
    ae_num = ae_num_y * ae_num_z
    ae_yz = np.array(
        [
            [
                active_element_size[0] * (i - 0.5 if i > 0 else 0),
                active_element_size[1] * (j - 0.5 if j > 0 else 0),
            ]
            for i in range(1, ae_num_y + 1)
            for j in range(1, ae_num_z + 1)
        ]
    )

    return ActiveZoneDefinition(
        y_lim=spec.y_lim,
        z_lim=spec.z_lim,
        grain_size_lim=spec.grain_size_lim,
        active_element_size=active_element_size,
        stress_lim=stress_lim,
        active_element_area=active_element_area,
        ae_num_y=ae_num_y,
        ae_num_z=ae_num_z,
        ae_num=ae_num,
        ae_yz=ae_yz,
    )


def build_evaluation_point_rules(
    *,
    steel: str,
    specimen_type: str,
    thickness_sign: str,
    thickness: float,
    gb_effect: int,
) -> EvaluationPointRules:
    """Define crack-depth evaluation points for Stage I and Stage II."""

    eval_points_full = None
    eval_points_stage1 = None

    if gb_effect == 0:
        eval_num_stage1 = 4
        eval_num_stage2 = 8
        eval_length_lim = 0.95 * thickness

        def eval_points_full(r1):
            return [
                r1 * (1 - ((eval_num_stage1 - i) / eval_num_stage1) ** 3)
                for i in range(eval_num_stage1)
            ] + [
                r1 + (eval_length_lim - r1) * ((i / eval_num_stage2) ** 1.2)
                for i in range(eval_num_stage2)
            ]

    else:
        eval_num_stage1 = 4
        eval_length_lim = 0.98 * thickness

        def eval_points_stage1(r1):
            return [
                r1 * (1 - ((eval_num_stage1 - i + 1) / eval_num_stage1) ** 3)
                for i in range(1, eval_num_stage1 + 1)
            ]

    eval_points_stage2 = _stage2_evaluation_points(
        steel=steel,
        specimen_type=specimen_type,
        thickness_sign=thickness_sign,
    )
    eval_num_stage2 = len(eval_points_stage2) + 2
    eval_num_total = eval_num_stage1 + eval_num_stage2

    return EvaluationPointRules(
        eval_num_stage1=eval_num_stage1,
        eval_num_stage2=eval_num_stage2,
        eval_num_total=eval_num_total,
        eval_length_lim=eval_length_lim,
        eval_points_full=eval_points_full,
        eval_points_stage1=eval_points_stage1,
        eval_points_stage2=eval_points_stage2,
    )


def _stage2_evaluation_points(
    *,
    steel: str,
    specimen_type: str,
    thickness_sign: str,
) -> list[float]:
    condition = (steel, specimen_type, thickness_sign)
    try:
        return list(STAGE2_POINTS_BY_CONDITION[condition])
    except KeyError as error:
        raise ValueError(
            "Unsupported evaluation-point condition: "
            f"steel={steel}, specimen_type={specimen_type}, "
            f"thickness_sign={thickness_sign}"
        ) from error


def _validate_parameter_condition(
    *,
    steel: str,
    specimen_type: str,
    thickness_sign: str,
) -> None:
    condition = (steel, specimen_type, thickness_sign)
    if condition not in SUPPORTED_PARAMETER_CONDITIONS:
        supported = ", ".join(
            f"{condition_steel}_{condition_type}_{condition_thickness}"
            for condition_steel, condition_type, condition_thickness in sorted(
                SUPPORTED_PARAMETER_CONDITIONS
            )
        )
        raise ValueError(
            "Unsupported parameter condition: "
            f"steel={steel}, specimen_type={specimen_type}, "
            f"thickness_sign={thickness_sign}. Supported: {supported}"
        )


def _weight_function_table_family(specimen_type: str) -> WeightFunctionTableFamily:
    try:
        return WEIGHT_FUNCTION_TABLE_FAMILY_BY_SPECIMEN_TYPE[specimen_type]
    except KeyError as error:
        raise ValueError(
            "Unsupported weight-function table condition: "
            f"specimen_type={specimen_type}"
        ) from error


def _nominal_stress_extraction_mode(
    specimen_type: str,
) -> NominalStressExtractionMode:
    try:
        return NOMINAL_STRESS_EXTRACTION_MODE_BY_SPECIMEN_TYPE[specimen_type]
    except KeyError as error:
        raise ValueError(
            "Unsupported Abaqus nominal-stress extraction condition: "
            f"specimen_type={specimen_type}"
        ) from error


def generate_euler_angles(count: int) -> np.ndarray:
    """Random sampling: crystal orientations for slip-plane resolution."""

    phi = np.random.uniform(0, 2 * np.pi, count)
    psi = np.random.uniform(0, 2 * np.pi, count)
    theta = np.arccos(np.random.uniform(-1, 1, count))
    return np.column_stack((phi, theta, psi))


def resolve_slip_plane(crystal: str, ang, DeltaSigma):
    """Resolve the active slip plane for the configured crystal structure."""

    ang = np.atleast_2d(ang)
    if DeltaSigma.ndim == 2:
        DeltaSigma = DeltaSigma[np.newaxis, ...]
    N = ang.shape[0]

    if crystal == "BCC":
        nv = np.array(
            [
                [[1.0, 1.0, 0.0], [1.0, -1.0, 1.0], [-1.0, 1.0, 1.0]],
                [[1.0, -1.0, 0.0], [1.0, 1.0, 1.0], [-1.0, -1.0, 1.0]],
                [[1.0, 0.0, 1.0], [1.0, 1.0, -1.0], [-1.0, 1.0, 1.0]],
                [[-1.0, 0.0, 1.0], [-1.0, 1.0, -1.0], [1.0, 1.0, 1.0]],
                [[0.0, 1.0, 1.0], [1.0, 1.0, -1.0], [1.0, -1.0, 1.0]],
                [[0.0, 1.0, -1.0], [1.0, 1.0, 1.0], [1.0, -1.0, -1.0]],
            ]
        )
    elif crystal == "FCC":
        nv = np.array(
            [
                [
                    [1.0, 1.0, 1.0],
                    [1.0, -1.0, 0.0],
                    [0.0, 1.0, -1.0],
                    [1.0, 0.0, -1.0],
                ],
                [
                    [-1.0, 1.0, 1.0],
                    [1.0, 1.0, 0.0],
                    [0.0, 1.0, -1.0],
                    [1.0, 0.0, 1.0],
                ],
                [
                    [1.0, -1.0, 1.0],
                    [1.0, 1.0, 0.0],
                    [0.0, 1.0, 1.0],
                    [1.0, 0.0, -1.0],
                ],
                [
                    [1.0, 1.0, -1.0],
                    [1.0, -1.0, 0.0],
                    [0.0, 1.0, 1.0],
                    [1.0, 0.0, 1.0],
                ],
            ]
        )
    else:
        raise ValueError("Unsupported crystal type")

    P, D, _ = nv.shape
    C_Psi = np.cos(ang[:, 0])
    C_Theta = np.cos(ang[:, 1])
    C_Phi = np.cos(ang[:, 2])
    S_Psi = np.sin(ang[:, 0])
    S_Theta = np.sin(ang[:, 1])
    S_Phi = np.sin(ang[:, 2])

    g = np.empty((N, 3, 3))
    g[:, 0, 0] = C_Psi * C_Theta * C_Phi - S_Psi * S_Phi
    g[:, 0, 1] = S_Psi * C_Theta * C_Phi + C_Psi * S_Phi
    g[:, 0, 2] = -S_Theta * C_Phi
    g[:, 1, 0] = -C_Psi * C_Theta * S_Phi - S_Psi * C_Phi
    g[:, 1, 1] = -S_Psi * C_Theta * S_Phi + C_Psi * C_Phi
    g[:, 1, 2] = S_Theta * S_Phi
    g[:, 2, 0] = C_Psi * S_Theta
    g[:, 2, 1] = S_Psi * S_Theta
    g[:, 2, 2] = C_Theta

    nv2 = np.einsum("nij,pdj->npdi", g, nv)
    A = nv2[:, :, 0, :]
    B = nv2[:, :, 1:, :]
    tau = np.abs(np.einsum("npi,nij,npdj->npd", A, DeltaSigma, B))

    tau_flat = tau.reshape(N, -1)
    max_idx = np.argmax(tau_flat, axis=1)
    tau_max = np.take_along_axis(tau_flat, max_idx[:, None], axis=1).flatten()

    p_index = max_idx // (D - 1)
    d_index = max_idx % (D - 1)
    max_shear_stress = (1.0 / np.sqrt(6)) * tau_max

    idx = np.arange(N)
    sign_factor = np.sign(nv2[idx, p_index, 0, 0])
    max_principal_stress_dir = (1.0 / np.sqrt(2)) * (
        sign_factor[:, None] * nv2[idx, p_index, 0, :]
    )
    max_theta_n = (1.0 / np.sqrt(3)) * (
        sign_factor[:, None] * nv2[idx, p_index, d_index + 1, :]
    )

    if N == 1:
        max_shear_stress = [max_shear_stress[0]]
        max_principal_stress_dir = max_principal_stress_dir[0]
        max_theta_n = max_theta_n[0]

    return np.array(max_shear_stress), max_principal_stress_dir, max_theta_n


def build_parameter_snapshot(params: object) -> dict[str, object]:
    return {
        "steel": params.steel,
        "specimen_type": params.specimen_type,
        "thickness_sign": params.thickness_sign,
        "name": params.name,
        "cache_name_key": params.cache_name_key,
        "weight_function_table_family": params.weight_function_table_family.value,
        "nominal_stress_extraction_mode": (
            params.nominal_stress_extraction_mode.value
        ),
        "crystal": params.crystal,
        "r_ratio": params.R_ratio,
        "sigma_nom": _snapshot_value(params.σ_nom),
        "iteration_num": _snapshot_value(params.iteration_num),
        "n_symm": params.n_symm,
        "c_paris": params.c_paris,
        "n_paris": params.n_paris,
        "delta_delta_th": params.Δδ_th,
        "width": params.width,
        "thickness": params.thickness,
        "stress_lim": params.stress_lim,
        "active_element_size": _snapshot_value(params.active_element_size),
        "active_element_count": params.AeNum,
        "eval_num_stage1": params.eval_num_stage1,
        "eval_num_stage2": params.eval_num_stage2,
        "eval_num_total": params.eval_num_total,
    }


def _snapshot_value(value: object) -> object:
    if hasattr(value, "tolist"):
        return value.tolist()
    return value
