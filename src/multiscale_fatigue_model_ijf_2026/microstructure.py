from __future__ import annotations

import datetime
import math
import pickle
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class MicrostructureGeneratedData:
    """Generated stochastic microstructure cache used during crack propagation."""

    generated_grain_data: object
    pearlite_rate_normalized: float | None
    grain_layers: int | None
    grains_per_layer: int | None


def generate_particle_data(
    *,
    steel: str,
    specimen_type: str,
    thickness: float,
    pearlite_rate: float,
    ferrite_friction_strength: float,
    pearlite_friction_strength: float | None,
    first_grain_cdf,
    first_grain_cdfr,
    second_grain_cdf,
    second_grain_cdfr,
    first_grain_aspect_cdfr,
    first_grain_angle_cdf,
    g_data_path: Path,
) -> MicrostructureGeneratedData:
    """Load or generate particle data while preserving the legacy random order."""

    pearlite_rate_normalized = _calculate_pearlite_rate_normalized(
        pearlite_rate=pearlite_rate,
        first_grain_cdfr=first_grain_cdfr,
        second_grain_cdfr=second_grain_cdfr,
    )
    generated_grain_data = _load_or_create_grain_data(
        steel=steel,
        specimen_type=specimen_type,
        pearlite_rate_normalized=pearlite_rate_normalized,
        ferrite_friction_strength=ferrite_friction_strength,
        pearlite_friction_strength=pearlite_friction_strength,
        first_grain_cdfr=first_grain_cdfr,
        second_grain_cdfr=second_grain_cdfr,
        first_grain_aspect_cdfr=first_grain_aspect_cdfr,
        first_grain_angle_cdf=first_grain_angle_cdf,
        g_data_path=g_data_path,
    )
    grain_layers, grains_per_layer = _estimate_model_size(
        specimen_type=specimen_type,
        thickness=thickness,
        pearlite_rate_normalized=pearlite_rate_normalized,
        first_grain_cdf=first_grain_cdf,
        second_grain_cdf=second_grain_cdf,
        first_grain_aspect_cdfr=first_grain_aspect_cdfr,
    )
    return MicrostructureGeneratedData(
        generated_grain_data=generated_grain_data,
        pearlite_rate_normalized=pearlite_rate_normalized,
        grain_layers=grain_layers,
        grains_per_layer=grains_per_layer,
    )


def _calculate_pearlite_rate_normalized(
    *,
    pearlite_rate: float,
    first_grain_cdfr,
    second_grain_cdfr,
) -> float:
    # Random sampling: estimate phase volume factors from grain distributions.
    vp = np.mean(
        [
            second_grain_cdfr(r) * first_grain_cdfr(r)
            for r in [random.random() for _ in range(100000)]
        ]
    )
    vf = np.mean([first_grain_cdfr(random.random()) ** 2 for _ in range(100000)])
    pearlite_rate_normalized = (pearlite_rate / vp) / (
        pearlite_rate / vp + (1 - pearlite_rate) / vf
    )
    print("VP:", vp)
    print("VF:", vf)
    print("PRateN:", pearlite_rate_normalized)
    return pearlite_rate_normalized


def _load_or_create_grain_data(
    *,
    steel: str,
    specimen_type: str,
    pearlite_rate_normalized: float,
    ferrite_friction_strength: float,
    pearlite_friction_strength: float | None,
    first_grain_cdfr,
    second_grain_cdfr,
    first_grain_aspect_cdfr,
    first_grain_angle_cdf,
    g_data_path: Path,
):
    if g_data_path.exists():
        with open(g_data_path, "rb") as file:
            generated_grain_data = pickle.load(file)
            print("Finish loading gData.pkl", datetime.datetime.now())
        if _is_valid_grain_data(generated_grain_data):
            return generated_grain_data
        print("Cached gData.pkl is invalid; regenerating.", datetime.datetime.now())

    print("Start generating gData.pkl", datetime.datetime.now())
    n_data = 1000000
    # Random sampling: generated grain list; keep call order unchanged.
    random_values = np.random.rand(5, n_data)
    if steel in ["Bainite", "Martensite", "H"]:
        grain_inputs = [
            [
                row[0],
                first_grain_cdfr(row[2]),
                np.array(0),
                first_grain_aspect_cdfr(row[1]),
            ]
            for row in random_values.T
        ]
    elif specimen_type == "CS":
        grain_inputs = [
            [
                row[0],
                first_grain_cdfr(row[1]),
                second_grain_cdfr(row[2]),
                first_grain_aspect_cdfr(row[3]),
                np.pi / 180 * first_grain_angle_cdf(row[4]),
            ]
            for row in random_values.T
        ]
    else:
        grain_inputs = [
            [
                row[0],
                first_grain_cdfr(row[1]),
                second_grain_cdfr(row[1]),
                first_grain_aspect_cdfr(row[3]),
                np.pi / 180 * first_grain_angle_cdf(row[4]) - np.pi / 2,
            ]
            for row in random_values.T
        ]

    generated_grain_data = [
        _make_particle_entry(
            *grain_input,
            specimen_type=specimen_type,
            pearlite_rate_normalized=pearlite_rate_normalized,
            ferrite_friction_strength=ferrite_friction_strength,
            pearlite_friction_strength=pearlite_friction_strength,
        )
        for grain_input in grain_inputs
    ]
    print("Finish generating gData.pkl", datetime.datetime.now())

    with open(g_data_path, "wb") as file:
        pickle.dump(generated_grain_data, file)
    return generated_grain_data


def _is_valid_grain_data(generated_grain_data) -> bool:
    if not generated_grain_data:
        return False
    sample = generated_grain_data[:100]
    return all(
        row is not None and hasattr(row, "__len__") and len(row) == 3
        for row in sample
    )


def _make_particle_entry(
    r,
    d,
    t,
    ra,
    ang=0,
    *,
    specimen_type: str,
    pearlite_rate_normalized: float,
    ferrite_friction_strength: float,
    pearlite_friction_strength: float | None,
):
    if r > pearlite_rate_normalized:
        if specimen_type == "CS":
            return [
                ferrite_friction_strength,
                d
                * np.sqrt(
                    np.sqrt(
                        (np.cos(ang) ** 2 + ra**4 * np.sin(ang) ** 2)
                        / (np.sin(ang) ** 2 + ra**4 * np.cos(ang) ** 2)
                    )
                ),
                d
                * np.sqrt(
                    np.sqrt(
                        (np.sin(ang) ** 2 + ra**4 * np.cos(ang) ** 2)
                        / (np.cos(ang) ** 2 + ra**4 * np.sin(ang) ** 2)
                    )
                ),
            ]
        return [
            ferrite_friction_strength,
            d
            * np.sqrt(
                np.sqrt(
                    (np.sin(ang) ** 2 + ra**4 * np.cos(ang) ** 2)
                    / (np.cos(ang) ** 2 + ra**4 * np.sin(ang) ** 2)
                )
            ),
            d
            * np.sqrt(
                np.sqrt(
                    (np.cos(ang) ** 2 + ra**4 * np.sin(ang) ** 2)
                    / (np.sin(ang) ** 2 + ra**4 * np.cos(ang) ** 2)
                )
            ),
        ]
    elif specimen_type == "CS":
        return [
            pearlite_friction_strength,
            math.sqrt(
                t
                * d
                * ra
                * math.sqrt(
                    (t**2 * math.cos(ang) ** 2 + d**2 * ra**2 * math.sin(ang) ** 2)
                    / (
                        t**2 * math.sin(ang) ** 2
                        + d**2 * ra**2 * math.cos(ang) ** 2
                    )
                )
            ),
            math.sqrt(
                t
                * d
                * ra
                * math.sqrt(
                    (t**2 * math.sin(ang) ** 2 + d**2 * ra**2 * math.cos(ang) ** 2)
                    / (
                        t**2 * math.cos(ang) ** 2
                        + d**2 * ra**2 * math.sin(ang) ** 2
                    )
                )
            ),
        ]
    return [
        pearlite_friction_strength,
        math.sqrt(
            t
            * d
            * ra
            * math.sqrt(
                (t**2 * math.sin(ang) ** 2 + d**2 * ra**2 * math.cos(ang) ** 2)
                / (
                    t**2 * math.cos(ang) ** 2
                    + d**2 * ra**2 * math.sin(ang) ** 2
                )
            )
        ),
        math.sqrt(
            t
            * d
            * ra
            * math.sqrt(
                (t**2 * math.cos(ang) ** 2 + d**2 * ra**2 * math.sin(ang) ** 2)
                / (
                    t**2 * math.sin(ang) ** 2
                    + d**2 * ra**2 * math.cos(ang) ** 2
                )
            )
        ),
    ]


def _estimate_model_size(
    *,
    specimen_type: str,
    thickness: float,
    pearlite_rate_normalized: float,
    first_grain_cdf,
    second_grain_cdf,
    first_grain_aspect_cdfr,
) -> tuple[int, int]:
    # Random sampling: ferrite projected areas for model-size estimate.
    part1 = [
        (first_grain_cdf(random.random())) ** 2
        for _ in range(int(50000 * (1 - pearlite_rate_normalized)))
    ]
    # Random sampling: pearlite projected areas for model-size estimate.
    part2 = [
        first_grain_cdf(random.random()) * second_grain_cdf(random.random())
        for _ in range(int(50000 * pearlite_rate_normalized))
    ]
    area_samples = part1 + part2

    area_factor = 6 if specimen_type == "Smooth" else 3
    grains_per_layer = round(area_factor * ((2 * thickness**2) / np.mean(area_samples)))

    # Random sampling: mean through-thickness grain size estimate.
    mean_grain_depth = np.mean(
        [
            first_grain_cdf(random.random()) * first_grain_aspect_cdfr(random.random())
            for _ in range(50000)
        ]
    )
    grain_layers = round((thickness * area_factor) / mean_grain_depth)
    return grain_layers, grains_per_layer
