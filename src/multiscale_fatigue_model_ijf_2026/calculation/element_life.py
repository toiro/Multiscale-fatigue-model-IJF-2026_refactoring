from __future__ import annotations

import random  # The random library is used to generate random numbers
import warnings
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np  # The NumPy library is used to process arrays

# Warning policy: keep legacy suppression until numerical-warning handling is reviewed.
warnings.filterwarnings("ignore", category=np.RankWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

from .crack_life import CrackLifeResult, calculate_crack_life
from .inputs import (
    CalculationInputData,
    FieldValueProvider,
    LocationYZ,
    NumericHistory,
    NumericValue,
    StressTensor,
)


@dataclass
class ElementLifeResult:
    """Best crack-growth history found for one active area element."""

    area_element_rank: int
    area_element_index: int
    symmetry_index: int
    location_yz: LocationYZ
    cycles: NumericHistory
    crack_depth: NumericHistory
    surface_crack_length: NumericHistory
    slip_band: NumericHistory
    ctsd: NumericHistory
    k_value: NumericHistory
    effective_stress: NumericHistory
    stress_ratio: NumericHistory
    aspect_ratio: NumericHistory
    opening_stress: NumericHistory
    grain_boundary_locations: NumericHistory


def _is_better_crack_candidate(
    crack_result: CrackLifeResult,
    cycles_result: NumericHistory,
) -> bool:
    return crack_result.cycles[-1] < cycles_result[-1]


def _element_life_raw(
    input_data: CalculationInputData,
    *,
    load_index: int,
    ia0: int,
    n: int,
    ia: int,
    σ: StressTensor,
    τ_max: float,
    field_values: FieldValueProvider,
    S_cyc_result: NumericHistory,
    S_ai_result: NumericHistory,
) -> ElementLifeResult:
    specimen = input_data.specimen
    crack_growth = input_data.crack_growth
    evaluation_points = input_data.evaluation_points
    microstructure = input_data.microstructure
    material_strength = input_data.material_strength
    weight_function = input_data.weight_function

    def CrackLifeCalc(
        r0: float,
        or1: NumericHistory,
        y: float,
        z: float,
        Anai: Callable[[NumericValue], NumericValue],
        field_values: FieldValueProvider,
        S_cyc_result: NumericHistory,
        S_ai_result: NumericHistory,
    ) -> CrackLifeResult:
        return calculate_crack_life(
            input_data,
            load_index=load_index,
            grain_size=r0,
            orientation=or1,
            y=y,
            z=z,
            anai=Anai,
            field_values=field_values,
            cycles_result=S_cyc_result,
            crack_depth_result=S_ai_result,
        )

    # FatigueLife-------------------------------------------Initiate the frcture parameters--------------------------------------------------------
    S_yz = ["no data", "no data"]  # location of crack initiation site
    eval_num_total = evaluation_points.eval_num_total
    S_ai = [0] * eval_num_total  # crack depth[mm]
    S_surf = [0] * eval_num_total  # surface crack length [mm]
    S_Δδ = [0] * eval_num_total  # CTSD[mm]
    S_c = [0] * eval_num_total  # slip band length [mm]
    S_K = [0] * eval_num_total
    S_asp = [1] * eval_num_total
    S_RR = [crack_growth.r_ratio] * eval_num_total
    S_σ = [0] * eval_num_total
    S_cyc = [10**15] * eval_num_total  # number of loading cycles
    S_σ_op = [0] * eval_num_total
    rd = 0  # d/dmax
    RnList = []

    def adopt_best_crack_candidate(
        crack_result: CrackLifeResult,
        Grain_i: int,
    ) -> None:
        nonlocal S_yz
        nonlocal S_ai
        nonlocal S_surf
        nonlocal S_Δδ
        nonlocal S_K
        nonlocal S_asp
        nonlocal S_RR
        nonlocal S_σ
        nonlocal S_c
        nonlocal S_cyc
        nonlocal S_cyc_result
        nonlocal S_σ_op
        nonlocal rd
        nonlocal RnList

        # Random sampling: crack-initiation location inside the area element.
        S_yz = [
            y + specimen.active_element_size[0] * (random.random() - 0.5),
            z + specimen.active_element_size[1] * (random.random() - 0.5),
        ]

        S_ai = crack_result.crack_depth
        S_surf = crack_result.surface_crack_length
        S_Δδ = crack_result.ctsd
        S_K = crack_result.k_value
        S_asp = crack_result.aspect_ratio
        S_RR = crack_result.stress_ratio
        S_σ = crack_result.effective_stress
        S_c = crack_result.slip_band
        S_cyc = crack_result.cycles
        S_cyc_result = crack_result.cycles
        S_σ_op = crack_result.opening_stress
        rd = FList[Grain_i] / microstructure.maximum_grain_size
        RnList = crack_result.grain_boundary_locations
        print(
            f"  Ae No. {(ia0) * specimen.n_symm + n+1}  Grain: {Grain_i + 1}/{FNum} ({fNum})  d/dmax={rd}  "
            + f"  N={S_cyc[-1]}"
            + f" yz={S_yz}"
        )

    # ----------------------------------------------sub_function__START------------------------------------------------
    def makeFList() -> NumericHistory:  # Definition of the function makeFList to generate the list of FirstGrain grain sizes, perlite short and long diameters
        Aej = specimen.active_element_area  # area of area element Ae
        d = 0  # flag for loop termination
        fww = 25
        n_max = round(fww * microstructure.grains_per_area_element)
        FList0 = [
            [] for _ in range(n_max)
        ]  # List of FirstGrain grain sizes, perlite short and long diameters

        i = 0
        while d != 1:
            # Random sampling: choose ferrite or pearlite surface grain.
            PorF = random.random()
            if PorF > microstructure.pearlite_rate_normalized:
                i += 1
                # Random sampling: ferrite grain size at the active surface.
                fd = microstructure.first_grain_cdf(random.random())

                if Aej < (np.pi * fd**2) / 4:
                    fd = np.sqrt((4 * Aej) / np.pi)
                    d = 1
                FList0.append(fd)
                Aej -= (np.pi * fd**2) / 4
            else:
                # Random sampling: pearlite thickness and paired ferrite length.
                r = random.random()
                pw = microstructure.second_grain_cdf(r)
                pl = microstructure.first_grain_cdf(r)

                if Aej < np.pi / 4 * pw * pl:
                    pw = (4 * Aej) / (np.pi * pl)
                    d = 1

                Aej -= np.pi / 4 * pw * pl

        FList = [sublist for sublist in FList0 if sublist]
        sorted_FList = sorted(FList, reverse=True)
        return sorted_FList

    # generateFoList
    def generateFoList() -> list[NumericHistory]:
        FoList = microstructure.orientation_generator(FNum).tolist()

        return FoList

    # Anai method for crack shape calculation
    def prepareAnai(y: float, z: float) -> Callable[[NumericValue], NumericValue]:
        def prepare_sigma_grad(
            y: float, z: float
        ) -> np.ndarray:  # calculate the gradient of the stress field on surface
            xx = np.arange(0, specimen.thickness * 0.9, 0.01)
            σ_grad0 = [
                (
                    x / specimen.thickness,
                    2 * field_values.active_element_total_field_by_depth(x, y, z)[1],
                )
                for x in xx
            ]  # normalize
            coeff = np.polyfit(
                [item[0] for item in σ_grad0], [item[1] for item in σ_grad0], 19
            )
            return coeff

        coeffs = prepare_sigma_grad(y, z)
        sigma_grad = np.poly1d(coeffs)

        def f1_derivative(xx: NumericValue) -> NumericValue:
            derivative_coefficients = np.polyder(sigma_grad).coeffs
            first_derivative = np.poly1d(derivative_coefficients)
            return first_derivative(xx)

        def Anai0(xx: NumericValue) -> NumericValue:
            return -0.06 + 0.47 * 0.5 * (
                f1_derivative(0.5 * xx) * 0.5 + f1_derivative(xx)
            ) / sigma_grad((0))

        def Anai(xx: NumericValue) -> NumericValue:
            xx_vals = (xx * (1 + weight_function.gauss_points_10)) / 2
            BB = Anai0(xx_vals)
            return 1 + (xx / 2) * np.dot(BB, weight_function.gauss_weights_10)

        return Anai

    # ----------------------------------------------sub_function__END------------------------------------------------

    y = specimen.ae_yz[ia][0]
    z = specimen.ae_yz[ia][1]

    FList = makeFList()
    FNum = len(FList)
    fNum = np.sum(
        np.heaviside(
            np.array(FList)
            - specimen.grain_size_lim * microstructure.maximum_grain_size,
            0,
        )
    )

    FoList = generateFoList()
    Anai = prepareAnai(y, z)
    if τ_max > material_strength.ferrite_friction_strength and fNum > 0:
        # Life evaluation loop for single element----------------------------------------------Area Element---------------------------------------------------------------
        for Grain_i in range(int(fNum)):
            τ1, θn1, θs1 = microstructure.slip_plane_resolver(FoList[0], σ)
            if τ1 > material_strength.ferrite_friction_strength:
                crack_result = CrackLifeCalc(
                    FList[Grain_i],
                    FoList[Grain_i],
                    y,
                    z,
                    Anai,
                    field_values,
                    S_cyc_result,
                    S_ai_result,
                )

                if _is_better_crack_candidate(crack_result, S_cyc_result):
                    adopt_best_crack_candidate(crack_result, Grain_i)

    else:
        print(
            f"  Ae No. {(ia0) * specimen.n_symm + n+1}  fatigue crack will not initiate in this area element"
        )
    return ElementLifeResult(
        area_element_rank=n,
        area_element_index=ia,
        symmetry_index=ia0,
        location_yz=S_yz,
        cycles=S_cyc,
        crack_depth=S_ai,
        surface_crack_length=S_surf,
        slip_band=S_c,
        ctsd=S_Δδ,
        k_value=S_K,
        effective_stress=S_σ,
        stress_ratio=S_RR,
        aspect_ratio=S_asp,
        opening_stress=S_σ_op,
        grain_boundary_locations=RnList,
    )


# -------------------------------------------------------------------------------------------------------------------------------------------


def calculate_element_life(
    input_data: CalculationInputData,
    *,
    load_index: int,
    area_element_rank: int,
    symmetry_index: int,
    area_element_index: int,
    stress_tensor: StressTensor,
    max_shear_stress: float,
    field_values: FieldValueProvider,
    cycles_result: NumericHistory,
    crack_depth_result: NumericHistory,
) -> ElementLifeResult:
    """Evaluate one area element and return the best crack candidate history.

    Execution order:
    1. Prepare one active area element, symmetry index, and stress tensor.
    2. Run the legacy-equivalent element kernel with CalculationInputData.
    3. Return the best area-element crack history as ElementLifeResult.
    """
    return _element_life_raw(
        input_data,
        load_index=load_index,
        ia0=symmetry_index,
        n=area_element_rank,
        ia=area_element_index,
        σ=stress_tensor,
        τ_max=max_shear_stress,
        field_values=field_values,
        S_cyc_result=cycles_result,
        S_ai_result=crack_depth_result,
    )
