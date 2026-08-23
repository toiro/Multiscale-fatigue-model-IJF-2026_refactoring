from __future__ import annotations

import math  # The math library is used to perform mathematical operations
import random  # The random library is used to generate random numbers
import warnings
from dataclasses import dataclass
from itertools import groupby

import numpy as np  # The NumPy library is used to process arrays
from scipy.interpolate import (
    griddata,
)  # The scipy library is used to perform interpolation
from scipy.optimize import brentq

# Warning policy: keep legacy suppression until numerical-warning handling is reviewed.
warnings.filterwarnings("ignore", category=np.RankWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

from typing import Any

from .inputs import CalculationInputData, NumericHistory


@dataclass
class CrackLifeResult:
    """Single candidate crack-growth history used inside calculation."""

    ctsd: NumericHistory
    k_value: NumericHistory
    aspect_ratio: NumericHistory
    stress_ratio: NumericHistory
    effective_stress: NumericHistory
    slip_band: NumericHistory
    cycles: NumericHistory
    crack_depth: NumericHistory
    surface_crack_length: NumericHistory
    grain_boundary_locations: NumericHistory
    opening_stress: NumericHistory


@dataclass
class GrainBoundaryData:
    """Grain-boundary layers generated once for one candidate crack.

    The fields correspond to the legacy `σ_f_List`, `rnList`, `Nd`, `PnList`,
    `RnAS`, and `orList`, but name the physical role used by CTSD evaluation.
    """

    friction_strengths: np.ndarray
    boundary_depths: np.ndarray
    grain_counts: np.ndarray
    adjacent_grains: list[Any]
    boundary_fractions: list[Any]
    orientations: list[NumericHistory]


def _crack_result_from_raw(raw: tuple[object, ...]) -> CrackLifeResult:
    """Name the legacy crack raw tuple without changing tuple order.

    Raw tuple order:
    1. CTSD
    2. K value
    3. aspect ratio
    4. stress ratio
    5. effective stress
    6. slip-band length
    7. cycles
    8. crack depth
    9. surface crack length
    10. grain-boundary locations
    11. opening stress
    """

    (
        ctsd,
        k_value,
        aspect_ratio,
        stress_ratio,
        effective_stress,
        slip_band,
        cycles,
        crack_depth,
        surface_crack_length,
        grain_boundary_locations,
        opening_stress,
    ) = raw
    return CrackLifeResult(
        ctsd=ctsd,
        k_value=k_value,
        aspect_ratio=aspect_ratio,
        stress_ratio=stress_ratio,
        effective_stress=effective_stress,
        slip_band=slip_band,
        cycles=cycles,
        crack_depth=crack_depth,
        surface_crack_length=surface_crack_length,
        grain_boundary_locations=grain_boundary_locations,
        opening_stress=opening_stress,
    )


def _safe_arccos(x: Any) -> Any:
    if isinstance(x, np.ndarray):
        if x.dtype == object:
            inner = x.item()
            if isinstance(inner, (np.ndarray, list, tuple)):
                raise TypeError(
                    f"safe_arccos: object scalar 中身が非スカラーです: {type(inner)} {inner!r}"
                )
            x = inner
        elif x.ndim != 0:
            raise AssertionError(...)
    elif not isinstance(x, (int, float, complex, bool)):
        raise TypeError(...)
    return np.arccos(np.clip(x, -1, 1))


def _build_evaluation_points(
    r1: float,
    rt1: float,
    rnList: Any,
    evaluation_points: Any,
    microstructure: Any,
    crack_growth: Any,
) -> tuple[list[Any], list[Any], int]:
    if crack_growth.gb_effect == 0:
        ai = evaluation_points.eval_points_full(r1)
        surfai = evaluation_points.eval_points_full(r1)
        nai = len(ai)
    else:

        Ai1 = evaluation_points.eval_points_stage1(r1)
        Ai1[-1] = r1 - microstructure.average_grain_size / 1000  #

        rni0 = (
            np.array(
                [2, 3]
                + [
                    1 + int(sum(np.heaviside(ai - rnList, 0)))
                    for ai in evaluation_points.eval_points_stage2
                ]
            )
            - 1
        )
        rni1 = np.unique(rni0)
        rni = rni1[1:] if rni1[0] == 0 else rni1

        Ai2 = (
            np.array(
                [
                    [
                        rnList[rn - 1] + microstructure.average_grain_size / 1000,
                        0.5 * (rnList[rn] + rnList[rn - 1]),
                        rnList[rn] - microstructure.average_grain_size / 1000,
                    ]
                    for rn in rni
                ]
            )
            .flatten()
            .tolist()
        )
        ai = sorted(Ai1 + Ai2)
        nai = len(ai)

        surfai = ai.copy()
        surfai[: evaluation_points.eval_num_stage1] = [
            2 * rt1
        ] * evaluation_points.eval_num_stage1

    return ai, surfai, nai


def _build_crack_aspect_function(r1: float, rt1: float, Anai: Any, specimen: Any) -> Any:
    # Definition of a function that returns the crack aspect ratio from the crack depth at specific crack length
    # r1:crack depth，rt1：crack length，Anai：crack aspect ratio
    def F2(n: Any) -> Any:
        return 1 + 0.7637 * n**2 + 0.2604 * n**4 + 0.04296 * n**6 + 0.002796 * n**8

    def Wu(a: Any, a0: Any, rr0: Any) -> Any:
        if a == 0:
            return 1
        elif a0 == 0:
            return F2(a) ** (-1 / 3)
        else:
            return (F2(a) - (a0 / a) ** 3 * (F2(a0) - rr0 ** (-3))) ** (-1 / 3)

    def ff000(a: Any) -> Any:
        wu1 = Wu(a, r1 / specimen.thickness, r1 / rt1)
        wu2 = Wu(a, 0, 0)
        wu3 = Wu(r1, r1 / specimen.thickness, r1 / rt1)
        wu4 = Wu(r1, 0, 0)
        return ((wu1 - wu2) / (wu3 - wu4)) * (
            wu3 - Anai(r1 / specimen.thickness)
        ) + Anai(a / specimen.thickness)

    def ff00(a: Any) -> Any:
        if a < 0.9 * specimen.thickness:
            return 1 / ff000(a)
        else:
            return 1 / ff000(0.9 * specimen.thickness)

    return ff00


def _initial_crack_dimensions(r0: float, microstructure: Any) -> tuple[float, float]:
    # Random sampling: first-grain aspect ratio for the initial crack.
    aspg = microstructure.first_grain_aspect_cdfr(random.random())
    r1 = aspg * r0 * 0.5
    rt1 = r0 * 0.5 / aspg
    return r1, rt1


def _crack_front_arc_length(
    asp0: Any,
    b: float,
    specimen: Any,
    weight_function: Any,
) -> Any:
    asp1 = float(asp0)

    if b * asp0 < specimen.width:
        if asp0 >= 1:
            return b * asp1 * weight_function.secant_ellipse(asp1)
        else:

            return b * weight_function.secant_ellipse(1 / asp1)
    else:
        return specimen.width


def _grain_span_depth(
    rr: float,
    dnList: Any,
    tnList: Any,
    m0: int,
    m_end: int,
) -> tuple[Any, Any]:
    dn_slice = dnList[m0 : m_end + 1]
    tn_slice = tnList[m0 : m_end + 1]
    rr_temp = rr + np.dot(dn_slice, tn_slice) / (2 * np.sum(tn_slice))
    return rr_temp, tn_slice


def _grain_span_front_length(
    rr_temp: Any,
    ff00: Any,
    specimen: Any,
    weight_function: Any,
    use_depth_limit: bool,
) -> Any:
    front_depth = specimen.thickness * 0.9 if use_depth_limit else rr_temp
    return _crack_front_arc_length(ff00(front_depth), rr_temp, specimen, weight_function)


def _find_shrink_offset_for_grain_span(
    *,
    rr: float,
    m0: int,
    m02: int,
    dnList: Any,
    tnList: Any,
    ff00: Any,
    specimen: Any,
    weight_function: Any,
    use_depth_limit: bool,
) -> int:
    nnn = 1
    while True:
        if (m02 - nnn) >= m0:
            rr_temp, tn_slice = _grain_span_depth(rr, dnList, tnList, m0, m02 - nnn)

            if _grain_span_front_length(
                rr_temp, ff00, specimen, weight_function, use_depth_limit
            ) > np.sum(tn_slice):
                break
        else:
            break

        nnn += 1
    return nnn


def _find_expand_offset_for_grain_span(
    *,
    rr: float,
    m0: int,
    m02: int,
    dnList: Any,
    tnList: Any,
    ff00: Any,
    specimen: Any,
    weight_function: Any,
    use_depth_limit: bool,
    grains_per_layer: int,
) -> int:
    nnn = 1
    while True:
        if (m02 + nnn) <= grains_per_layer:
            rr_temp, tn_slice = _grain_span_depth(rr, dnList, tnList, m0, m02 + nnn)

            if _grain_span_front_length(
                rr_temp, ff00, specimen, weight_function, use_depth_limit
            ) < np.sum(tn_slice):
                break
        else:
            break
        nnn += 1
    return nnn


def _generate_grain_boundaries(
    r1: float,
    rt1: float,
    ff00: Any,
    Anai: Any,
    or1: Any,
    *,
    specimen: Any,
    microstructure: Any,
    material_strength: Any,
    weight_function: Any,
    grain_layers: int,
    grains_per_layer: int,
    orientation_generator: Any,
) -> GrainBoundaryData:
    g_data_arr = np.asarray(microstructure.generated_grain_data)
    Ng = grains_per_layer

    # Random sampling: select generated grains along the crack path.
    rand_indices = np.random.randint(0, len(g_data_arr), size=Ng)
    selected_gdata = g_data_arr[rand_indices]
    # selected_gdata = g_data_arr[100:100+Ng]
    g_List = np.vstack(
        ([material_strength.ferrite_friction_strength, r1, rt1], selected_gdata)
    )

    # Keep the legacy local names in this generator because the layer-building
    # equations below still follow the original notation closely. The public
    # boundary is `GrainBoundaryData`, where these arrays get physical names.
    σ_f_List, dnList, tnList = g_List[:, 0], g_List[:, 1], g_List[:, 2]
    # orList = [or1] + [orientation_generator() for _ in range(grains_per_layer)]#
    orList = [or1] + orientation_generator(grains_per_layer).tolist()
    rnList = [0] * grain_layers
    Nd = [0] * grain_layers
    RnA = [[] for _ in range(grain_layers)]
    RnAA = [[] for _ in range(grain_layers)]
    PnList = [[] for _ in range(grain_layers)]
    RnAS = [[] for _ in range(grain_layers)]
    RnAAS = [[] for _ in range(grain_layers)]

    rnList[0] = r1
    Nd[0] = 1
    RnA[0] = [1]
    RnAA[0] = [1]

    n = 0
    n0 = 0  # First grain number containing the crack tip
    n1 = 0  # Last grain number containing the crack tip

    while rnList[n] < 1.05 * specimen.thickness:

        rr = rnList[n]
        m0 = n1 + 1
        if m0 >= grains_per_layer:
            break
        m02 = m0 + (n1 - n0)
        if m02 >= grains_per_layer:
            m02 = grains_per_layer
        gr = 0
        nnn = 1

        if rr < specimen.thickness * 0.9:

            rr0, tn_slice = _grain_span_depth(rr, dnList, tnList, m0, m02)

            if _grain_span_front_length(
                rr0, ff00, specimen, weight_function, False
            ) < np.sum(tn_slice):
                nnn = _find_shrink_offset_for_grain_span(
                    rr=rr,
                    m0=m0,
                    m02=m02,
                    dnList=dnList,
                    tnList=tnList,
                    ff00=ff00,
                    specimen=specimen,
                    weight_function=weight_function,
                    use_depth_limit=False,
                )
                gr = 1

            else:
                nnn = _find_expand_offset_for_grain_span(
                    rr=rr,
                    m0=m0,
                    m02=m02,
                    dnList=dnList,
                    tnList=tnList,
                    ff00=ff00,
                    specimen=specimen,
                    weight_function=weight_function,
                    use_depth_limit=False,
                    grains_per_layer=grains_per_layer,
                )
                gr = 2

        else:
            rr0, tn_slice = _grain_span_depth(rr, dnList, tnList, m0, m02)

            if _grain_span_front_length(
                rr0, ff00, specimen, weight_function, True
            ) < np.sum(tn_slice):
                nnn = _find_shrink_offset_for_grain_span(
                    rr=rr,
                    m0=m0,
                    m02=m02,
                    dnList=dnList,
                    tnList=tnList,
                    ff00=ff00,
                    specimen=specimen,
                    weight_function=weight_function,
                    use_depth_limit=True,
                )
                gr = 1
            else:
                nnn = _find_expand_offset_for_grain_span(
                    rr=rr,
                    m0=m0,
                    m02=m02,
                    dnList=dnList,
                    tnList=tnList,
                    ff00=ff00,
                    specimen=specimen,
                    weight_function=weight_function,
                    use_depth_limit=True,
                    grains_per_layer=grains_per_layer,
                )
                gr = 2

        n0 = n1 + 1
        n1 = m02 - nnn + 1 if gr == 1 else m02 + nnn - 1
        if n1 > grains_per_layer:
            break

        Nd[n + 1] = n1 - n0 + 1

        RnA[n + 1] = tnList[n0 : n1 + 1] / sum(tnList[n0 : n1 + 1])
        RnAA[n + 1] = np.cumsum(RnA[n + 1])
        rnList[n + 1] = rnList[n] + np.dot(RnA[n + 1], dnList[n0 : n1 + 1])
        k0, k1 = 1, 1
        Pn = [0] * (Nd[n] + Nd[n + 1] - 1)

        Pn[Nd[n] + Nd[n + 1] - 2] = [Nd[n], Nd[n + 1]]
        Pn[0] = [0, 0]

        for j in range(1, Nd[n] + Nd[n + 1] - 1):
            if RnAA[n][k0 - 1] < RnAA[n + 1][k1 - 1]:
                k0 += 1
            else:
                k1 += 1
            Pn[j] = [k0 - 1, k1 - 1]

        PnList[n] = Pn
        RnAAS[n] = sorted(np.concatenate((RnAA[n], RnAA[n + 1][:-1])))
        RnAS[n] = np.array(RnAAS[n]) - np.array([0] + RnAAS[n][:-1])
        n += 1

        # if len(PnList[0]) <= 2:
    rnList = np.array(rnList[: n + 1])
    Nd = np.array(Nd[: n + 1])

    RnA = RnAA[: n + 1]
    RnAA = RnAA[: n + 1]
    RnAS = RnAS[:n]
    RnAAS = RnAAS[:n]
    PnList = PnList[:n]

    return GrainBoundaryData(
        friction_strengths=σ_f_List,
        boundary_depths=rnList,
        grain_counts=Nd,
        adjacent_grains=PnList,
        boundary_fractions=RnAS,
        orientations=orList,
    )


def _solve_stage1_slip_band_length(a: float, σ_fr: list[Any], rnlist: float) -> Any:
    def Eq_1(c: Any, a: Any, σ_fr: Any) -> Any:
        epsilon = 1e-10  # Avoid dividing by zero
        return np.pi / 2 - σ_fr[0] * _safe_arccos(a / (c + epsilon))

    upper_bound = rnlist + 100
    max_upper_bound = 1e8
    while upper_bound <= max_upper_bound:
        try:
            c_root = brentq(Eq_1, a + 1e-10, upper_bound, args=(a, σ_fr))
            return c_root
        except ValueError:
            upper_bound *= 10
    return c_root


def _solve_multilayer_slip_band_length(
    a: float,
    n: int,
    σ_fr: list[Any],
    rnList: Any,
) -> Any:
    def Eq_n(c: Any, a: Any, n: int, σ_fr: Any, rnList: Any) -> Any:
        epsilon = 1e-10  # Avoid dividing by zero
        return (
            np.pi * 0.5
            - σ_fr[0] * _safe_arccos(a / (c + epsilon))
            - sum(
                (σ_fr[i + 1] - σ_fr[i]) * _safe_arccos(rnList[i] / (c + epsilon))
                for i in range(n + 1)
            )
        )

    upper_bound = rnList[n] + 10000
    try:
        c_root = brentq(Eq_n, a + 1e-10, upper_bound, args=(a, n, σ_fr, rnList))
        return c_root
    except ValueError:
        c_root = 10000
    return c_root


def _ctsd_geometry_integral(x: Any, c: Any, ad: Any) -> Any:
    if x == ad:
        a = (1 - 1e-3) * ad
    else:
        a = ad

    ca = np.sqrt(c**2 - a**2)
    cx = np.sqrt(c**2 - x**2)
    return a * np.log(abs((ca + cx) / (ca - cx))) - x * np.log(
        abs((x * ca + a * cx) / (x * ca - a * cx))
    )


def _calculate_ctsd_value(
    a: float,
    c: Any,
    n: int,
    σ_fr: list[Any],
    Δτ_j: Any,
    rnList_L: Any,
    crack_interaction_constant: float,
) -> Any:
    if a == 0:
        term1 = 0
    else:
        term1 = 2 * a * σ_fr[0] * np.log(c / a)

    term2 = sum(
        (σ_fr[i + 1] - σ_fr[i]) * _ctsd_geometry_integral(a, c, rnList_L[i])
        for i in range(n + 1)
    )
    result = (
        Δτ_j
        / (np.pi**2 * crack_interaction_constant)
        * (term1 + term2)
    )
    return result.item()


def _average_slip_response_by_grain(
    Pn: Any,
    RnAS_slice: Any,
    τ0: Any,
    t0: Any,
) -> tuple[list[Any], list[Any]]:
    groups = []
    for key, group in groupby(enumerate(Pn), key=lambda x: x[1][1]):
        indices = [idx for idx, _ in group]
        groups.append(indices)

    RnAS_arr = np.array(RnAS_slice)
    τ0_arr = np.array(τ0)
    t0_arr = np.array(t0)

    t_gs = []
    τ_gs = []
    for indices in groups:
        indices = np.array(indices)
        rnas = np.sum(RnAS_arr[indices])
        if rnas == 0:
            τ_avg = np.zeros_like(τ0_arr[indices][0])
            t_avg = np.zeros_like(t0_arr[indices][0])
        else:
            weights = RnAS_arr[indices].reshape(-1, 1, 1)
            τ_avg = np.sum(τ0_arr[indices] * weights, axis=0) / rnas
            t_avg = np.sum(t0_arr[indices] * weights, axis=0) / rnas
        τ_gs.append(τ_avg)
        t_gs.append(t_avg)
    return t_gs, τ_gs


def _advance_ctsd_through_grain_layers(
    *,
    aii: float,
    cc: Any,
    Δδ: Any,
    τ1: Any,
    crack_tip_layer_idx: int,
    σ_fr: list[Any],
    t_List: list[Any],
    τ_List: list[Any],
    grain_boundaries: GrainBoundaryData,
    slip_plane_resolver: Any,
    specimen: Any,
    weight_function: Any,
) -> tuple[Any, Any, bool, bool]:
    unstable_fracture = False
    stop_ctsd_evaluation = False
    boundary_depths = grain_boundaries.boundary_depths
    grains_per_depth_layer = grain_boundaries.grain_counts
    adjacent_grains_by_layer = grain_boundaries.adjacent_grains
    boundary_fraction_by_layer = grain_boundaries.boundary_fractions

    for m in range(len(boundary_depths)):
        layer_idx = crack_tip_layer_idx + m

        if cc < boundary_depths[layer_idx]:
            Δδ = _calculate_ctsd_value(
                aii,
                cc,
                m - 1,
                σ_fr,
                τ1,
                boundary_depths[crack_tip_layer_idx : layer_idx + 1],
                weight_function.crack_interaction_constant,
            )
            break
        elif layer_idx + 2 > len(grains_per_depth_layer):
            unstable_fracture = True
            stop_ctsd_evaluation = True
            break

        first_grain_index_in_layer = sum(grains_per_depth_layer[0 : layer_idx + 1])

        adjacent_grain_pairs = np.array(adjacent_grains_by_layer[layer_idx])

        previous_layer_indices = adjacent_grain_pairs[:, 0].tolist()
        next_layer_indices = adjacent_grain_pairs[:, 1].tolist()

        or_array = np.array(
            [
                grain_boundaries.orientations[
                    first_grain_index_in_layer + next_layer_indices[i]
                ]
                for i in range(len(next_layer_indices))
            ]
        )
        t_array = np.array(
            [
                t_List[m][previous_layer_indices[i]]
                for i in range(len(previous_layer_indices))
            ]
        )
        τ_t0 = slip_plane_resolver(or_array, t_array)

        τ0 = τ_t0[0]
        t0 = [t[0] * np.outer(t[1], t[2]) for t in zip(*τ_t0)]

        t_gs, τ_gs = _average_slip_response_by_grain(
            adjacent_grains_by_layer[layer_idx],
            boundary_fraction_by_layer[layer_idx],
            τ0,
            t0,
        )

        σ_f0 = [
            grain_boundaries.friction_strengths[first_grain_index_in_layer + p[1]]
            for p in adjacent_grains_by_layer[layer_idx]
        ]
        τ0_arr = np.array(τ0)  # shape (N, ...)
        σ_f0_arr = np.array(σ_f0)  # shape (N,)
        temp_array = τ0_arr / σ_f0_arr
        σ_fr[m + 1] = 1 / (boundary_fraction_by_layer[layer_idx].dot(temp_array))

        τ_List[m + 1] = τ_gs.copy()
        t_List[m + 1] = t_gs.copy()

        if σ_fr[m] < 1:
            cc = 1.05 * specimen.thickness
        else:
            cc = _solve_multilayer_slip_band_length(
                aii,
                m,
                σ_fr,
                boundary_depths[crack_tip_layer_idx : layer_idx + 2],
            )

    return cc, Δδ, unstable_fracture, stop_ctsd_evaluation


def _evaluate_ctsd_at_crack_depth(
    aii: float,
    evaluation_index: int,
    Δσ: Any,
    grain_boundaries: GrainBoundaryData,
    *,
    specimen: Any,
    grain_layers: int,
    slip_plane_resolver: Any,
    material_strength: Any,
    weight_function: Any,
) -> tuple[Any, Any, bool, bool]:
    # Calculation of CTSD for each evaluation point
    # aii : crack depth ;
    # Δσ : stress range tensor ;
    # grain_boundaries : friction strengths, orientations, depths, and layer adjacency generated for this crack
    unstable_fracture = False
    stop_ctsd_evaluation = False
    boundary_depths = grain_boundaries.boundary_depths
    grains_per_depth_layer = grain_boundaries.grain_counts
    adjacent_grains_by_layer = grain_boundaries.adjacent_grains
    boundary_fraction_by_layer = grain_boundaries.boundary_fractions

    boundary_depth_list = boundary_depths.tolist()
    crack_tip_layer_idx = boundary_depth_list.index(
        next(filter(lambda x: x > aii, boundary_depth_list))
    )
    crack_tip_in_first_grain = crack_tip_layer_idx == 0
    first_grain_index_in_layer = sum(
        grains_per_depth_layer[0 : crack_tip_layer_idx + 1]
    )

    t_List = [[] for _ in range(grain_layers)]
    τ_List = [[] for _ in range(grain_layers)]
    σ_fr = [0] * grain_layers

    if crack_tip_in_first_grain:
        τ1, θn1, θs1 = slip_plane_resolver(grain_boundaries.orientations[0], Δσ)

        t_List[0] = [τ1 * np.outer(θn1, θs1)]
        τ_List[0] = [τ1]
        σ_fr[0] = material_strength.ferrite_friction_strength / τ1
    else:
        τ_t2_temp = [
            slip_plane_resolver(
                grain_boundaries.orientations[first_grain_index_in_layer + item[1]],
                Δσ,
            )
            for item in adjacent_grains_by_layer[crack_tip_layer_idx]
        ]
        τ_t2 = [list(t) for t in zip(*τ_t2_temp)]

        σ_f0 = [
            grain_boundaries.friction_strengths[first_grain_index_in_layer + item[1]]
            for item in adjacent_grains_by_layer[crack_tip_layer_idx]
        ]

        t_List[0] = [
            TauT2_0 * np.outer(TauT2_1, TauT2_2)
            for TauT2_0, TauT2_1, TauT2_2 in zip(*τ_t2)
        ]
        τ_List[0] = list(τ_t2[0])

        σ_fr[0] = 1 / (
            boundary_fraction_by_layer[crack_tip_layer_idx].dot(
                [τ_t2[0][i] / σ_f0[i] for i in range(len(σ_f0))]
            )
        )  # 问题
        τ1 = boundary_fraction_by_layer[crack_tip_layer_idx].dot(τ_List[0])

    if σ_fr[0] < 1:
        cc = 1.05 * specimen.thickness
        Δδ = 0
        cc, Δδ, unstable_fracture, stop_ctsd_evaluation = (
            _advance_ctsd_through_grain_layers(
                aii=aii,
                cc=cc,
                Δδ=Δδ,
                τ1=τ1,
                crack_tip_layer_idx=crack_tip_layer_idx,
                σ_fr=σ_fr,
                t_List=t_List,
                τ_List=τ_List,
                grain_boundaries=grain_boundaries,
                slip_plane_resolver=slip_plane_resolver,
                specimen=specimen,
                weight_function=weight_function,
            )
        )

    else:
        if evaluation_index == 0:
            cc = 100
            Δδ = 0
            stop_ctsd_evaluation = True
        else:
            cc = _solve_stage1_slip_band_length(
                aii, σ_fr, boundary_depths[0]
            )  # calculate the length of the slip band in Stage I
            Δδ = 0
            cc, Δδ, unstable_fracture, stop_ctsd_evaluation = (
                _advance_ctsd_through_grain_layers(
                    aii=aii,
                    cc=cc,
                    Δδ=Δδ,
                    τ1=τ1,
                    crack_tip_layer_idx=crack_tip_layer_idx,
                    σ_fr=σ_fr,
                    t_List=t_List,
                    τ_List=τ_List,
                    grain_boundaries=grain_boundaries,
                    slip_plane_resolver=slip_plane_resolver,
                    specimen=specimen,
                    weight_function=weight_function,
                )
            )

    return cc, Δδ, unstable_fracture, stop_ctsd_evaluation


def _interpolate_stage2_weight_function(
    at: float,
    ac: float,
    specimen: Any,
    weight_function: Any,
) -> Any:
    # Define the function to calculate KWeight
    interpolated_value = weight_function.stage2_weight_function(at, ac)
    return 1 / np.sqrt(specimen.thickness * at) * interpolated_value


def _interpolate_stage1_weight_function(
    at: float,
    ac: float,
    specimen: Any,
    weight_function: Any,
) -> Any:
    # Define the function to calculate KWeight
    # Extract at, ac, and values from the list of lists
    at_ac_values = [
        item[0] for item in weight_function.weight_function_constants
    ]
    values = [item[1] for item in weight_function.weight_function_constants]

    # Flatten the at_ac_values and values lists
    at_values, ac_values = zip(*at_ac_values)
    at_values = np.array(at_values)
    ac_values = np.array(ac_values)
    values = np.array(values)
    mask_linear = at_values <= 0.1

    if np.any(mask_linear):
        interpolated_value = griddata(
            np.column_stack((at_values[mask_linear], ac_values[mask_linear])),
            values[mask_linear],
            (at, ac),
            method="linear",
        )
    return 1 / np.sqrt(specimen.thickness * at) * interpolated_value


def _integrate_k_stage1(
    aii: float,
    rt1: float,
    y: float,
    z: float,
    specimen: Any,
    weight_function: Any,
    field_values: Any,
) -> np.ndarray:
    # Calculation of K-values via weight functions in the fisrt grain (Stage I)
    at_value = aii / specimen.thickness
    ac_value = aii / rt1
    a1, a2, a3, a4 = _interpolate_stage1_weight_function(
        at_value,
        ac_value,
        specimen,
        weight_function,
    )

    WG1 = [[] for _ in range(6)]
    Results = np.empty(6)
    field_at_gauss_points = [
        field_values.active_element_total_field_by_depth(
            (aii / 2) * (1 + x), y, z
        )
        for x in weight_function.gauss_points_10
    ]

    for i in range(6):
        WG1[i] = [
            (
                a1
                + a2 * (1 / np.sqrt(1 - x))
                + a3 * np.sqrt(1 - x)
                + a4 * (1 - x)
            )
            * field_value[i]
            for field_value, x in zip(
                field_at_gauss_points,
                weight_function.gauss_points_10,
            )
        ]

    for i in range(6):
        array_a = (aii / 2) * np.array(WG1[i])
        array_b = np.array(weight_function.gauss_weights_10)
        Results[i] = np.sum(array_a * array_b)

    return np.array(Results)


def _integrate_k_stage2(
    aii: float,
    asp: float,
    y: float,
    z: float,
    specimen: Any,
    weight_function: Any,
    field_values: Any,
) -> np.ndarray:
    # Calculation of K-values via weight functions in the fisrt grain (Stage II)
    at_value = aii / specimen.thickness

    a1, a2, a3, a4 = _interpolate_stage2_weight_function(
        at_value,
        asp,
        specimen,
        weight_function,
    )
    WG1 = [[] for _ in range(6)]
    Results = np.empty(6)
    field_at_gauss_points = [
        field_values.active_element_total_field_by_depth(
            (aii / 2) * (1 + x), y, z
        )
        for x in weight_function.gauss_points_10
    ]

    for i in range(6):
        WG1[i] = [
            (
                a1
                + a2 * (1 / np.sqrt(1 - x))
                + a3 * np.sqrt(1 - x)
                + a4 * (1 - x)
            )
            * field_value[i]
            for field_value, x in zip(
                field_at_gauss_points,
                weight_function.gauss_points_10,
            )
        ]

    for i in range(6):
        array_a = (aii / 2) * np.array(WG1[i])
        array_b = np.array(weight_function.gauss_weights_10)
        Results[i] = np.sum(array_a * array_b)

    return np.array(Results)


def _remote_stress_scale(ai0: float, asp0: float, specimen: Any, weight_function: Any) -> Any:
    # Functions for converting to remote stresses
    if specimen.remote_type == 1:
        return weight_function.remote_stress_function(
            ai0 / specimen.thickness,
            asp0,
        ) * math.sqrt(
            ai0 / weight_function.qq_function(asp0)
        )
    else:
        return math.sqrt(math.pi * ai0)


def _surface_reference_principal_stress(field_values: Any, y: float, z: float) -> Any:
    σ_11, σ_22, σ_33, τ_12, τ_13, τ_23 = np.array(
        field_values.active_element_total_field_by_depth(0, y, z)
    )
    stress_tensor = np.array(
        [[σ_11, τ_12, τ_13], [τ_12, σ_22, τ_23], [τ_13, τ_23, σ_33]]
    )
    eigenvalues_sigma = np.linalg.eigvals(stress_tensor)
    return max(eigenvalues_sigma)


def _calculate_closure_factor(
    evaluation_index: int,
    σ_nom: float,
    σ_app: Any,
    a: float,
    y: float,
    z: float,
    crack_growth: Any,
    material_strength: Any,
    field_values: Any,
    surface_reference_principal_stress: Any,
) -> tuple[Any, Any]:
    def Hysterisis(σ_nom1: Any, y: float, z: float) -> Any:
        σ_11, σ_22, σ_33, τ_12, τ_13, τ_23 = np.array(
            field_values.active_surface_total_field_by_nominal_stress(σ_nom1, y, z)
        )
        σ = np.array(
            [[σ_11, τ_12, τ_13], [τ_12, σ_22, τ_23], [τ_13, τ_23, σ_33]]
        )
        eigenvalues_sigma = np.linalg.eigvals(σ)
        return max(eigenvalues_sigma)

    def OP(
        σ_max: Any, R1: float
    ) -> Any:  # Function returning the crack opening stress for any loading stress, full opening
        def OP00(σ_max: Any, R1: float) -> Any:

            αα = 3  # Plastic constraint factor 3, coefficient in plane strain state.
            r_σ = (
                σ_max / material_strength.reference_stress
                if σ_max <= material_strength.reference_stress
                else 1
            )
            A0 = (0.825 - 0.34 * αα + 0.05 * αα**2) * (
                np.cos(np.pi / 2 * r_σ)
            ) ** (1 / αα)
            A1 = (0.415 - 0.071 * αα) * r_σ
            A3 = 2 * A0 + A1 - 1
            A2 = 1 - A0 - A1 - A3

            if R1 >= 0:
                σ_op = (A0 + A1 * R1 + A2 * R1**2 + A3 * R1**3) * σ_max
            elif -1 <= R1 < 0:
                σ_op = (A0 + A1 * R1) * σ_max
            else:
                σ_op = None

            return σ_op

        OP00_val = OP00(σ_max, R1)
        if OP00_val > σ_max * R1:
            return OP00_val
        else:
            return σ_max * R1

    σ_max = σ_app / (1 - crack_growth.r_ratio)
    σ_min = crack_growth.r_ratio * σ_max
    σ_op = OP(σ_max, crack_growth.r_ratio)  # remote crack opening stress
    σ_op_max = σ_min + (σ_op - σ_min) * (1 - np.exp(-crack_growth.k_tr * a))
    if evaluation_index <= 3:
        return 1.0, σ_min
    if σ_op_max > σ_min:

        ε_0 = surface_reference_principal_stress
        ε_1 = Hysterisis(((σ_op_max - σ_min) / (σ_max - σ_min) * σ_nom), y, z)
        return (ε_0 - ε_1) / ε_0, σ_op_max
    else:
        return 1.0, σ_op_max


def _calculate_stress_state_at_crack_depth(
    i: int,
    aii: float,
    rt1: float,
    y: float,
    z: float,
    ff00: Any,
    *,
    specimen: Any,
    evaluation_points: Any,
    crack_growth: Any,
    material_strength: Any,
    weight_function: Any,
    field_values: Any,
    surface_reference_principal_stress: Any,
    load_index: int,
) -> tuple[Any, Any, Any, Any, Any, Any]:
    is_stage1 = i < evaluation_points.eval_num_stage1

    if not is_stage1:
        if aii <= specimen.thickness * 0.95:
            asp = 1 / ff00(aii)
            K = _integrate_k_stage2(
                aii, asp, y, z, specimen, weight_function, field_values
            )
            σ_remote = 2 * K / _remote_stress_scale(
                aii, asp, specimen, weight_function
            )
            UU, σ_op = _calculate_closure_factor(
                i,
                crack_growth.sigma_nom[load_index],
                σ_remote[1],
                aii,
                y,
                z,
                crack_growth,
                material_strength,
                field_values,
                surface_reference_principal_stress,
            )
            σ_11, σ_22, σ_33, τ_12, τ_13, τ_23 = σ_remote
            Δσ = UU * np.array(
                [[σ_11, τ_12, τ_13], [τ_12, σ_22, τ_23], [τ_13, τ_23, σ_33]]
            )
            stress_state_branch = "stage2_weight_function"
        else:
            asp = 1 / ff00(0.95 * specimen.thickness)
            K = _integrate_k_stage2(
                0.95 * specimen.thickness,
                asp,
                y,
                z,
                specimen,
                weight_function,
                field_values,
            )
            σ_remote = 2 * K / _remote_stress_scale(
                aii, asp, specimen, weight_function
            )
            UU, σ_op = _calculate_closure_factor(
                i,
                crack_growth.sigma_nom[load_index],
                σ_remote[1],
                0.95 * specimen.thickness,
                y,
                z,
                crack_growth,
                material_strength,
                field_values,
                surface_reference_principal_stress,
            )
            σ_11, σ_22, σ_33, τ_12, τ_13, τ_23 = σ_remote
            Δσ = UU * np.array(
                [[σ_11, τ_12, τ_13], [τ_12, σ_22, τ_23], [τ_13, τ_23, σ_33]]
            )
            stress_state_branch = "stage2_depth_capped_weight_function"
    else:

        if i > 0:
            asp = aii / rt1
            K = _integrate_k_stage1(
                aii, rt1, y, z, specimen, weight_function, field_values
            )
            σ_remote = 2 * K / _remote_stress_scale(
                aii, asp, specimen, weight_function
            )
            UU, σ_op = _calculate_closure_factor(
                i,
                crack_growth.sigma_nom[load_index],
                σ_remote[1],
                aii,
                y,
                z,
                crack_growth,
                material_strength,
                field_values,
                surface_reference_principal_stress,
            )
            σ_11, σ_22, σ_33, τ_12, τ_13, τ_23 = σ_remote
            Δσ = UU * np.array(
                [[σ_11, τ_12, τ_13], [τ_12, σ_22, τ_23], [τ_13, τ_23, σ_33]]
            )
            stress_state_branch = "stage1_weight_function"
        else:
            K = [0, 0, 0, 0, 0, 0]
            asp = aii / rt1
            σ_remote = 2 * np.array(
                field_values.active_element_total_field_by_depth(0, y, z)
            )
            UU, σ_op = _calculate_closure_factor(
                i,
                crack_growth.sigma_nom[load_index],
                σ_remote[1],
                aii,
                y,
                z,
                crack_growth,
                material_strength,
                field_values,
                surface_reference_principal_stress,
            )
            σ_11, σ_22, σ_33, τ_12, τ_13, τ_23 = σ_remote
            Δσ = UU * np.array(
                [[σ_11, τ_12, τ_13], [τ_12, σ_22, τ_23], [τ_13, τ_23, σ_33]]
            )
            stress_state_branch = "initial_surface_field"

    if np.isnan(Δσ).any():
        print("σ_remote:", σ_remote)
        print("K:", K)
        print("rt1:", rt1)
        print("asp:", asp)
        print("aii:", aii)
        print("stress_state_branch=", stress_state_branch)
    return asp, σ_remote[1], K[1], UU, Δσ, σ_op


def _nnf(x: Any) -> Any:
    if x == 0:
        return 10**18
    elif 0 < x < 1:
        return 1 + (-0.7 * math.log(x.item())) ** 1.5
    else:
        return 1


def _integrate_stage1_life_cycle(
    i: int,
    ai: list[Any],
    nTemp: Any,
    S_Δδ0: list[Any],
    S_cyc0: list[Any],
    dNdaList: list[Any],
    LifeMin: Any,
    crack_growth: Any,
) -> tuple[list[Any], list[Any], bool]:
    if i == 0:
        S_cyc0[i] = 0
        dNda = 0
    else:
        if S_Δδ0[i - 1] == 0 or S_Δδ0[i] == 0:
            return S_cyc0, dNdaList, False

        dNda0 = 1 / (crack_growth.c_paris * S_Δδ0[i - 1] ** crack_growth.n_paris)
        dNda1 = 1 / (crack_growth.c_paris * S_Δδ0[i] ** crack_growth.n_paris)
        dNda = 0.5 * (dNda0 + dNda1)

        S_cyc0[i] = dNda * (ai[i] - ai[i - 1]) + S_cyc0[i - 1]
    NSuspend = _nnf(S_cyc0[i] / nTemp)

    # To improve the calculation efficiency, the calculation is terminated when the number of cycles exceeds 10 times the minimum life
    if S_cyc0[i] > NSuspend * LifeMin(ai[i]):
        return S_cyc0, dNdaList, True

    if S_cyc0[i] > 10 * LifeMin(ai[i]):
        return S_cyc0, dNdaList, True

    dNdaList[0] = [0, dNda]
    return S_cyc0, dNdaList, False


def _integrate_stage2_life_cycle_window(
    i: int,
    rnList: Any,
    ai: list[Any],
    nTemp: Any,
    S_Δδ0: list[Any],
    S_cyc0: list[Any],
    dNdaList: list[Any],
    LifeMin: Any,
    evaluation_points: Any,
    crack_growth: Any,
) -> tuple[list[Any], list[Any], bool]:
    ai1, ai2 = ai[i - 1] - ai[i - 2], ai[i] - ai[i - 2]
    dNda0 = 1 / (
        crack_growth.c_paris
        * (
            S_Δδ0[i - 2] ** crack_growth.n_paris
            - crack_growth.delta_delta_th**crack_growth.n_paris
        )
    )
    dNda1 = (
        1
        / (
            crack_growth.c_paris
            * (
                S_Δδ0[i - 1] ** crack_growth.n_paris
                - crack_growth.delta_delta_th**crack_growth.n_paris
            )
        )
        - dNda0
    )
    dNda2 = (
        1
        / (
            crack_growth.c_paris
            * (
                S_Δδ0[i] ** crack_growth.n_paris
                - crack_growth.delta_delta_th**crack_growth.n_paris
            )
        )
        - dNda0
    )

    if ai1 * ai2 * (ai1 - ai2) == 0:
        return S_cyc0, dNdaList, False

    αα = (ai2 * dNda1 - ai1 * dNda2) / (ai1 * ai2 * (ai1 - ai2))
    ββ = (ai2**2 * dNda1 - ai1**2 * dNda2) / (ai1 * ai2 * (ai2 - ai1))
    γγ = dNda0

    dNda = (1 / ai2) * (
        (1 / 3) * αα * ai2**3 + (1 / 2) * ββ * ai2**2 + γγ * ai2
    )
    grNum = int((i - evaluation_points.eval_num_stage1 + 1) / 3)
    lineNum = int(sum(np.heaviside(ai[i] - rnListi, 0) for rnListi in rnList))
    dNdaList[grNum] = [lineNum, dNda]
    lineNumPrev, dNdaPrev = dNdaList[grNum - 1]
    rnPrev = rnList[lineNumPrev]

    # Stage II cycle integration updates the three evaluation points in the current grain-boundary window.
    S_cyc0[i - 2] = (
        S_cyc0[i - 3]
        + dNdaPrev * (rnPrev - ai[i - 3])
        + ((dNdaPrev + dNda) / 2) * (rnList[lineNum - 1] - rnPrev)
        + dNda * (ai[i - 2] - rnList[lineNum - 1])
    )
    S_cyc0[i - 1] = S_cyc0[i - 2] + dNda * (ai[i - 1] - ai[i - 2])
    S_cyc0[i] = S_cyc0[i - 1] + dNda * (ai[i] - ai[i - 1])

    if min(S_cyc0[i - 2 : i + 1]) > nTemp or min(S_cyc0[i - 2 : i + 1]) < 0:
        return S_cyc0, dNdaList, True

    for ii in range(i - 2, i + 1):
        if S_cyc0[ii] > nTemp:
            return S_cyc0, dNdaList, True
        NSuspend = _nnf(S_cyc0[ii] / nTemp)

        if S_cyc0[ii] > NSuspend * LifeMin(ai[ii]):
            return S_cyc0, dNdaList, True

        if S_cyc0[ii] > 10 * LifeMin(ai[ii]):
            return S_cyc0, dNdaList, True

    return S_cyc0, dNdaList, False


def _integrate_life_cycle(
    i: int,
    cc: Any,
    rnList: Any,
    ai: list[Any],
    nTemp: Any,
    S_Δδ0: list[Any],
    Scyc0Copy: list[Any],
    dNdaListCopy: list[Any],
    LifeMin: Any,
    evaluation_points: Any,
    crack_growth: Any,
) -> tuple[list[Any], list[Any], bool]:
    S_cyc0 = Scyc0Copy.copy()
    dNdaList = dNdaListCopy.copy()
    stop_life_integration = False

    # Stage I
    is_stage1 = i < evaluation_points.eval_num_stage1
    is_stage2_integration_point = (
        i - evaluation_points.eval_num_stage1 + 1
    ) % 3 == 0

    if is_stage1:
        return _integrate_stage1_life_cycle(
            i,
            ai,
            nTemp,
            S_Δδ0,
            S_cyc0,
            dNdaList,
            LifeMin,
            crack_growth,
        )

    elif is_stage2_integration_point:
        return _integrate_stage2_life_cycle_window(
            i,
            rnList,
            ai,
            nTemp,
            S_Δδ0,
            S_cyc0,
            dNdaList,
            LifeMin,
            evaluation_points,
            crack_growth,
        )

    return S_cyc0, dNdaList, stop_life_integration


def _initialize_crack_growth_history(
    nai: int,
    specimen: Any,
    crack_growth: Any,
) -> tuple[
    list[Any],
    list[Any],
    list[Any],
    list[Any],
    list[Any],
    list[Any],
    list[Any],
    list[Any],
]:
    # Crack-growth history arrays aligned with evaluation-point index i.
    # Stage I is i < eval_num_stage1; later points are Stage II candidates.
    S_Δδ0 = [0] * nai
    S_K0 = [0] * nai  # K value
    S_asp0 = [1] * nai  # crack aspect ratio
    S_RR0 = [crack_growth.r_ratio] * nai  # effective stress ratio
    S_σ0 = [0] * nai  # effective stress
    S_c0 = [1.05 * specimen.thickness] * nai  # slip-band length
    S_cyc0 = [10**18] * nai  # loading cycles
    S_σ_op0 = [0] * nai  # opening stress
    return S_Δδ0, S_K0, S_asp0, S_RR0, S_σ0, S_c0, S_cyc0, S_σ_op0


def _record_crack_point_state(
    i: int,
    aii: float,
    *,
    cc: Any,
    Δδ: Any,
    K: Any,
    UU: Any,
    Δσ: Any,
    σ_op: Any,
    asp: Any,
    rt1: float,
    is_stage2: bool,
    surfai: list[Any],
    S_Δδ0: list[Any],
    S_K0: list[Any],
    S_asp0: list[Any],
    S_RR0: list[Any],
    S_σ0: list[Any],
    S_c0: list[Any],
    S_σ_op0: list[Any],
    crack_growth: Any,
) -> None:
    S_c0[i] = cc
    S_Δδ0[i] = Δδ
    S_RR0[i] = (1 - crack_growth.r_ratio) * UU
    S_K0[i] = K
    S_σ0[i] = Δσ[1]
    S_σ_op0[i] = σ_op
    S_asp0[i] = 1 / asp if is_stage2 else (0 if i == 0 else rt1 / aii)
    surfai[i] = 2 * S_asp0[i] * aii if is_stage2 else 2 * rt1


def _record_unstable_fracture_history(
    i: int,
    nai: int,
    S_Δδ0: list[Any],
    S_cyc0: list[Any],
    S_c0: list[Any],
) -> None:
    for j in range(i, nai):
        S_Δδ0[j] = float("inf")
        S_cyc0[j] = S_cyc0[j - 1]
        S_c0[i] = float("inf")


def _fill_history_after_through_thickness(
    i: int,
    nai: int,
    *,
    cc: Any,
    specimen: Any,
    S_Δδ0: list[Any],
    S_K0: list[Any],
    S_asp0: list[Any],
    S_RR0: list[Any],
    S_σ0: list[Any],
    S_c0: list[Any],
    S_cyc0: list[Any],
    S_σ_op0: list[Any],
) -> None:
    cc0gr = (
        int(sum(np.heaviside(specimen.thickness - S_c0i, 0) for S_c0i in S_c0))
        - 1
    )
    Nf0 = S_cyc0[cc0gr]
    Nf2 = S_cyc0[cc0gr + 1]
    cc0 = S_c0[cc0gr]
    cc2 = S_c0[cc0gr + 1]
    Nf1 = (
        S_cyc0[i]
        if cc == specimen.thickness
        else (
            (cc2 - specimen.thickness) * Nf0
            + (specimen.thickness - cc0) * Nf2
        )
        / (cc2 - cc0)
    )

    for iii in range(cc0gr + 1, nai):
        S_cyc0[iii] = Nf1
        S_Δδ0[iii] = S_Δδ0[cc0gr]
        S_c0[iii] = specimen.thickness
        S_K0[iii] = S_K0[cc0gr]
        S_asp0[iii] = S_asp0[cc0gr]
        S_RR0[iii] = S_RR0[cc0gr]
        S_σ0[iii] = S_σ0[cc0gr]
        S_σ_op0[iii] = S_σ_op0[cc0gr]


def _crack_life_raw(
    input_data: CalculationInputData,
    *,
    load_index: int,
    r0: float,
    or1: Any,
    y: float,
    z: float,
    Anai: Any,
    field_values: Any,
    S_cyc_result: list[Any],
    S_ai_result: list[Any],
) -> tuple[Any, ...]:
    """Run the crack-growth kernel while preserving the original calculation order.

    Execution order:
    1. Read calculation-only views from CalculationInputData.
    2. Build the life-limit interpolation from prior element results.
    3. Draw initial crack dimensions and generate grain boundaries.
    4. Build evaluation crack depths.
    5. For each crack depth, calculate stress state, CTSD, and life increment.
    6. Stop on threshold, instability, inherited shorter life, or through-thickness crack.
    """
    specimen = input_data.specimen
    crack_growth = input_data.crack_growth
    evaluation_points = input_data.evaluation_points
    microstructure = input_data.microstructure
    material_strength = input_data.material_strength
    weight_function = input_data.weight_function
    grain_layers = microstructure.grain_layers
    grains_per_layer = microstructure.grains_per_layer
    orientation_generator = microstructure.orientation_generator
    slip_plane_resolver = microstructure.slip_plane_resolver
    load_quene = load_index

    nTemp = S_cyc_result[-1]
    Scyc1st = list(zip(S_ai_result, S_cyc_result)) + [
        [specimen.thickness, S_cyc_result[-1]]
    ]
    LifeMin = lambda x: np.interp(
        x,
        [row[0] for row in Scyc1st],
        [row[1] for row in Scyc1st],
        left=10**18,
        right=10**18,
    )

    # Preserve the legacy random sequence: the first sampled crack aspect is discarded.
    _initial_crack_dimensions(r0, microstructure)

    # Grain boundary model.
    dNdaList = [1 for _ in range(len(evaluation_points.eval_points_stage2) + 10)]
    unstable_fracture = False
    r1, rt1 = _initial_crack_dimensions(r0, microstructure)
    ff00 = _build_crack_aspect_function(r1, rt1, Anai, specimen)

    # start_time = time.time()
    grain_boundaries = _generate_grain_boundaries(
        r1,
        rt1,
        ff00,
        Anai,
        or1,
        specimen=specimen,
        microstructure=microstructure,
        material_strength=material_strength,
        weight_function=weight_function,
        grain_layers=grain_layers,
        grains_per_layer=grains_per_layer,
        orientation_generator=orientation_generator,
    )
    boundary_depths = grain_boundaries.boundary_depths
    # end_time = time.time()

    ai, surfai, nai = _build_evaluation_points(
        r1,
        rt1,
        boundary_depths,
        evaluation_points,
        microstructure,
        crack_growth,
    )
    (
        S_Δδ0,
        S_K0,
        S_asp0,
        S_RR0,
        S_σ0,
        S_c0,
        S_cyc0,
        S_σ_op0,
    ) = _initialize_crack_growth_history(nai, specimen, crack_growth)
    surface_reference_principal_stress = _surface_reference_principal_stress(
        field_values, y, z
    )
    # Calculate CTSD, slip zone length, and number of loading cycles for each crack length， then loop for life calculation.
    # start_time_LIFE = time.time()
    for i in range(nai):
        aii = ai[i]
        is_stage1 = i < evaluation_points.eval_num_stage1
        is_stage2 = not is_stage1
        is_stage2_integration_point = (
            i - evaluation_points.eval_num_stage1 + 1
        ) % 3 == 0

        # Stress intensity, remote stress, closure, and CTSD.
        asp, σ_remote, K, UU, Δσ, σ_op = _calculate_stress_state_at_crack_depth(
            i,
            aii,
            rt1,
            y,
            z,
            ff00,
            specimen=specimen,
            evaluation_points=evaluation_points,
            crack_growth=crack_growth,
            material_strength=material_strength,
            weight_function=weight_function,
            field_values=field_values,
            surface_reference_principal_stress=surface_reference_principal_stress,
            load_index=load_quene,
        )
        # start_time_CTSD = time.time()
        (
            cc,
            Δδ,
            unstable_fracture,
            stop_due_to_ctsd_evaluation,
        ) = _evaluate_ctsd_at_crack_depth(
            aii,
            i,
            Δσ,
            grain_boundaries,
            specimen=specimen,
            grain_layers=grain_layers,
            slip_plane_resolver=slip_plane_resolver,
            material_strength=material_strength,
            weight_function=weight_function,
        )
        # end_time_CTSD = time.time()

        if stop_due_to_ctsd_evaluation:
            break

        if unstable_fracture:
            _record_unstable_fracture_history(i, nai, S_Δδ0, S_cyc0, S_c0)
            break

        ctsd_below_stage2_threshold = is_stage2 and Δδ < crack_growth.delta_delta_th
        if ctsd_below_stage2_threshold:
            break

        # Life integration.
        _record_crack_point_state(
            i,
            aii,
            cc=cc,
            Δδ=Δδ,
            K=K,
            UU=UU,
            Δσ=Δσ,
            σ_op=σ_op,
            asp=asp,
            rt1=rt1,
            is_stage2=is_stage2,
            surfai=surfai,
            S_Δδ0=S_Δδ0,
            S_K0=S_K0,
            S_asp0=S_asp0,
            S_RR0=S_RR0,
            S_σ0=S_σ0,
            S_c0=S_c0,
            S_σ_op0=S_σ_op0,
            crack_growth=crack_growth,
        )
        # start_time_cycle = time.time()
        S_cyc0, dNdaList, stop_due_to_life_integration_limit = _integrate_life_cycle(
            i,
            cc,
            boundary_depths,
            ai,
            nTemp,
            S_Δδ0,
            S_cyc0,
            dNdaList,
            LifeMin,
            evaluation_points,
            crack_growth,
        )
        # end_time_cycle = time.time()

        if stop_due_to_life_integration_limit:
            break

        through_thickness_stage2_window = (
            cc >= specimen.thickness and is_stage2_integration_point
        )
        if through_thickness_stage2_window:
            _fill_history_after_through_thickness(
                i,
                nai,
                cc=cc,
                specimen=specimen,
                S_Δδ0=S_Δδ0,
                S_K0=S_K0,
                S_asp0=S_asp0,
                S_RR0=S_RR0,
                S_σ0=S_σ0,
                S_c0=S_c0,
                S_cyc0=S_cyc0,
                S_σ_op0=S_σ_op0,
            )
    # end_time_LIFE = time.time()

    return (
        S_Δδ0,
        S_K0,
        S_asp0,
        S_RR0,
        S_σ0,
        S_c0,
        S_cyc0,
        ai,
        surfai,
        boundary_depths,
        S_σ_op0,
    )




def calculate_crack_life(
    input_data: CalculationInputData,
    *,
    load_index: int,
    grain_size: float,
    orientation: Any,
    y: float,
    z: float,
    anai: Any,
    field_values: Any,
    cycles_result: list[Any],
    crack_depth_result: list[Any],
) -> CrackLifeResult:
    """Evaluate one crack and convert the legacy raw tuple to CrackLifeResult."""
    raw = _crack_life_raw(
        input_data,
        load_index=load_index,
        r0=grain_size,
        or1=orientation,
        y=y,
        z=z,
        Anai=anai,
        field_values=field_values,
        S_cyc_result=cycles_result,
        S_ai_result=crack_depth_result,
    )
    return _crack_result_from_raw(raw)
