from __future__ import annotations

from pathlib import Path


def resolve_input_path(base_dir: Path, filename: str) -> Path:
    return Path(base_dir).resolve() / filename


def resolve_cache_path(cache_dir: Path, filename: str) -> Path:
    return Path(cache_dir).resolve() / filename


def specimen_model_name(*, steel: str, specimen_type: str, thickness_sign: str) -> str:
    return f"{steel}_{specimen_type}_{thickness_sign}"


def abaqus_dat_filename(*, model_name: str) -> str:
    return f"{model_name}.dat"


def abaqus_inp_filename(*, model_name: str) -> str:
    return f"{model_name}.inp"


def field_values_filename(*, steel: str, specimen_type: str) -> str:
    return f"{steel}_{specimen_type}_FieldValues.pkl"


def grain_data_filename(*, steel: str, specimen_type: str) -> str:
    return f"{steel}_{specimen_type}_gData.pkl"


def first_grain_size_filename(*, steel: str, first_grain: str) -> str:
    return f"{steel}_{first_grain} grain size.csv"


def first_grain_aspect_filename(*, steel: str, first_grain: str) -> str:
    return f"{steel}_{first_grain} grain aspect ratio.csv"


def first_grain_angle_filename(*, steel: str, first_grain: str) -> str:
    return f"{steel}_{first_grain} grain angle.csv"


def second_grain_thickness_prefix(*, steel: str, second_grain: str) -> str:
    return f"{steel}_{second_grain} thickness"


def monotonic_tensile_filename(*, steel: str) -> str:
    return f"{steel}_Monotonic tensile test.csv"


def friction_strength_filename(*, steel: str) -> str:
    return f"{steel}_Friction strength.csv"


def weight_function_constants_filename() -> str:
    return "CombinedData_Ellipse_WF_CF.json"
