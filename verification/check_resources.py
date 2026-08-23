from __future__ import annotations

import argparse
import json
from pathlib import Path

from multiscale_fatigue_model_ijf_2026.config import SIMULATION_CONFIG_KEYS
from multiscale_fatigue_model_ijf_2026.parameters import SUPPORTED_PARAMETER_CONDITIONS
from multiscale_fatigue_model_ijf_2026.paths import (
    first_grain_angle_filename,
    first_grain_aspect_filename,
    first_grain_size_filename,
    friction_strength_filename,
    monotonic_tensile_filename,
    second_grain_thickness_prefix,
    specimen_model_name,
    weight_function_constants_filename,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check that each supported resource condition has input files."
    )
    parser.add_argument("resources_dir", type=Path)
    args = parser.parse_args()

    resources_dir = args.resources_dir.resolve()
    if not resources_dir.is_dir():
        raise FileNotFoundError(f"resources directory not found: {resources_dir}")

    expected_dirs = {
        specimen_model_name(
            steel=steel,
            specimen_type=specimen_type,
            thickness_sign=thickness_sign,
        )
        for steel, specimen_type, thickness_sign in SUPPORTED_PARAMETER_CONDITIONS
    }
    non_condition_dirs = {"configs"}
    actual_dirs = {
        path.name
        for path in resources_dir.iterdir()
        if path.is_dir() and path.name not in non_condition_dirs
    }

    missing_dirs = sorted(expected_dirs - actual_dirs)
    extra_dirs = sorted(actual_dirs - expected_dirs)
    errors = []
    if missing_dirs:
        errors.append("Missing condition directories: " + ", ".join(missing_dirs))
    if extra_dirs:
        errors.append("Unexpected condition directories: " + ", ".join(extra_dirs))

    for steel, specimen_type, thickness_sign in sorted(SUPPORTED_PARAMETER_CONDITIONS):
        model_name = specimen_model_name(
            steel=steel,
            specimen_type=specimen_type,
            thickness_sign=thickness_sign,
        )
        condition_dir = resources_dir / model_name
        if not condition_dir.is_dir():
            continue
        errors.extend(_missing_files_for_condition(condition_dir, steel, model_name))

    errors.extend(_config_errors(resources_dir, expected_dirs))

    if errors:
        raise AssertionError("\n".join(errors))

    print(f"Resource manifest check passed: {len(expected_dirs)} condition(s).")


def _missing_files_for_condition(
    condition_dir: Path,
    steel: str,
    model_name: str,
) -> list[str]:
    missing = []
    required_files = [
        f"{model_name}.inp",
        first_grain_size_filename(steel=steel, first_grain="Ferrite"),
        first_grain_aspect_filename(steel=steel, first_grain="Ferrite"),
        first_grain_angle_filename(steel=steel, first_grain="Ferrite"),
        friction_strength_filename(steel=steel),
        monotonic_tensile_filename(steel=steel),
        weight_function_constants_filename(),
    ]

    for filename in required_files:
        if not (condition_dir / filename).is_file():
            missing.append(f"{condition_dir.name}: missing {filename}")

    dat_file = condition_dir / f"{model_name}.dat"
    dat_zip_file = condition_dir / f"{model_name}.dat.zip"
    if not dat_file.is_file() and not dat_zip_file.is_file():
        missing.append(f"{condition_dir.name}: missing {model_name}.dat or .dat.zip")

    pearlite_prefix = second_grain_thickness_prefix(
        steel=steel,
        second_grain="Pearlite",
    )
    pearlite_files = [
        path
        for path in condition_dir.iterdir()
        if path.is_file()
        and path.name.startswith(pearlite_prefix)
        and path.suffix.lower() == ".csv"
    ]
    if not pearlite_files:
        missing.append(f"{condition_dir.name}: missing {pearlite_prefix}*.csv")

    return missing


def _config_errors(resources_dir: Path, expected_dirs: set[str]) -> list[str]:
    config_dir = resources_dir / "configs"
    if not config_dir.is_dir():
        return [f"Missing normal condition config directory: {config_dir}"]

    config_files = {path.stem: path for path in config_dir.glob("*.json")}
    missing_configs = sorted(expected_dirs - set(config_files))
    extra_configs = sorted(set(config_files) - expected_dirs)

    errors = []
    if missing_configs:
        errors.append("Missing normal condition configs: " + ", ".join(missing_configs))
    if extra_configs:
        errors.append("Unexpected normal condition configs: " + ", ".join(extra_configs))

    normal_defaults = {
        "crystal": "BCC",
        "r_ratio": -1,
        "c_paris": 18,
        "n_paris": 1.8,
        "delta_delta_th": 0.000063,
        "sigma_nom": [150, 160, 170, 180, 190],
        "iteration_count": 4,
        "n_symm": 4,
    }

    for model_name, config_path in sorted(config_files.items()):
        if model_name not in expected_dirs:
            continue
        with config_path.open(encoding="utf-8") as file:
            data = json.load(file)

        unknown_keys = sorted(set(data) - SIMULATION_CONFIG_KEYS)
        if unknown_keys:
            errors.append(
                f"{config_path.relative_to(resources_dir)}: unknown keys "
                + ", ".join(unknown_keys)
            )

        if "random_seed" in data:
            errors.append(f"{model_name}: normal config must not set random_seed")
        if "max_active_elements" in data:
            errors.append(f"{model_name}: normal config must not set max_active_elements")

        steel, specimen_type, thickness_sign = model_name.split("_")
        expected_values = {
            "steel": steel,
            "specimen_type": specimen_type,
            "thickness_sign": thickness_sign,
            **normal_defaults,
        }
        for key, expected_value in expected_values.items():
            actual_value = data.get(key)
            if actual_value != expected_value:
                errors.append(
                    f"{model_name}: expected {key}={expected_value!r}, "
                    f"got {actual_value!r}"
                )

    return errors


if __name__ == "__main__":
    main()
