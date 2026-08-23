from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from multiscale_fatigue_model_ijf_2026.config import load_simulation_config
from multiscale_fatigue_model_ijf_2026.context import (
    _build_paper_model_parameters,
    _resolve_model_files,
)
from multiscale_fatigue_model_ijf_2026.parameters import SUPPORTED_PARAMETER_CONDITIONS
from multiscale_fatigue_model_ijf_2026.paths import (
    field_values_filename,
    specimen_model_name,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Check lightweight condition configs and context boundary resolution "
            "without loading Abaqus/material data."
        )
    )
    parser.add_argument("repo_root", type=Path)
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    config_dir = repo_root / "verification" / "configs" / "conditions"
    resources_dir = repo_root / "resources"
    cache_root = repo_root / "outputs" / "verification_cache_layout"
    output_dir = repo_root / "outputs" / "verification_context_boundary"

    configs = sorted(config_dir.glob("lightweight_*.json"))
    conditions_from_configs = set()

    for config_path in configs:
        config = load_simulation_config(
            config_path,
            base_dir=resources_dir,
            output_dir=output_dir,
        )
        config = replace(config, cache_dir=cache_root)
        params = _build_paper_model_parameters(config)
        condition = (params.steel, params.specimen_type, params.thickness_sign)
        conditions_from_configs.add(condition)

        model_name = specimen_model_name(
            steel=params.steel,
            specimen_type=params.specimen_type,
            thickness_sign=params.thickness_sign,
        )
        expected_input_dir = resources_dir / model_name
        expected_cache_dir = cache_root / model_name
        model_files = _resolve_model_files(config, params)

        if model_files.input_dir != expected_input_dir.resolve():
            raise AssertionError(
                f"{config_path.name}: unexpected input_dir "
                f"{model_files.input_dir}"
            )
        if model_files.cache_dir != expected_cache_dir.resolve():
            raise AssertionError(
                f"{config_path.name}: unexpected cache_dir "
                f"{model_files.cache_dir}"
            )
        if model_files.model_name != model_name:
            raise AssertionError(f"{config_path.name}: unexpected model_name")
        if model_files.output_filename_body != model_name:
            raise AssertionError(
                f"{config_path.name}: unexpected output filename body"
            )
        expected_field_cache = field_values_filename(
            steel=params.steel,
            specimen_type=params.specimen_type,
        )
        if model_files.field_values_cache_filename != expected_field_cache:
            raise AssertionError(
                f"{config_path.name}: unexpected FieldValues cache filename"
            )

    if conditions_from_configs != SUPPORTED_PARAMETER_CONDITIONS:
        missing = SUPPORTED_PARAMETER_CONDITIONS - conditions_from_configs
        extra = conditions_from_configs - SUPPORTED_PARAMETER_CONDITIONS
        raise AssertionError(
            "Condition config set mismatch. "
            f"Missing: {_format_conditions(missing)}; "
            f"Extra: {_format_conditions(extra)}"
        )

    print(f"Context boundary check passed: {len(configs)} config(s).")


def _format_conditions(conditions: set[tuple[str, str, str]]) -> str:
    if not conditions:
        return "(none)"
    return ", ".join(
        specimen_model_name(
            steel=steel,
            specimen_type=specimen_type,
            thickness_sign=thickness_sign,
        )
        for steel, specimen_type, thickness_sign in sorted(conditions)
    )


if __name__ == "__main__":
    main()
