from __future__ import annotations

from multiscale_fatigue_model_ijf_2026.parameters import (
    SUPPORTED_PARAMETER_CONDITIONS,
    NominalStressExtractionMode,
    PaperModelParameters,
    WeightFunctionTableFamily,
)

EXPECTED_CONDITION_SUMMARY = {
    ("B", "Smooth", "T16"): {
        "width": 5.0,
        "thickness": 1.35,
        "stress_lim": 0.1,
        "ae_num": 375,
        "eval_num_stage2": 20,
        "weight_function_table_family": WeightFunctionTableFamily.SMOOTH,
        "nominal_stress_extraction_mode": NominalStressExtractionMode.SMOOTH_DSLOAD,
    },
    ("B", "R008", "T24"): {
        "width": 5.0,
        "thickness": 1.9,
        "stress_lim": 0.2,
        "ae_num": 100,
        "eval_num_stage2": 24,
        "weight_function_table_family": WeightFunctionTableFamily.THREE_POINT_BENDING,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.THREE_POINT_BENDING_RF1
        ),
    },
    ("B", "R100", "T24"): {
        "width": 5.0,
        "thickness": 1.9,
        "stress_lim": 0.5,
        "ae_num": 80,
        "eval_num_stage2": 24,
        "weight_function_table_family": WeightFunctionTableFamily.THREE_POINT_BENDING,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.THREE_POINT_BENDING_RF1
        ),
    },
    ("G", "Smooth", "T16"): {
        "width": 5.0,
        "thickness": 1.35,
        "stress_lim": 0.1,
        "ae_num": 375,
        "eval_num_stage2": 20,
        "weight_function_table_family": WeightFunctionTableFamily.SMOOTH,
        "nominal_stress_extraction_mode": NominalStressExtractionMode.SMOOTH_DSLOAD,
    },
    ("G", "R008", "T24"): {
        "width": 5.0,
        "thickness": 1.9,
        "stress_lim": 0.2,
        "ae_num": 100,
        "eval_num_stage2": 24,
        "weight_function_table_family": WeightFunctionTableFamily.THREE_POINT_BENDING,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.THREE_POINT_BENDING_RF1
        ),
    },
    ("G", "R100", "T24"): {
        "width": 5.0,
        "thickness": 1.9,
        "stress_lim": 0.5,
        "ae_num": 80,
        "eval_num_stage2": 24,
        "weight_function_table_family": WeightFunctionTableFamily.THREE_POINT_BENDING,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.THREE_POINT_BENDING_RF1
        ),
    },
    ("N50R", "Smooth", "T16"): {
        "width": 5.0,
        "thickness": 1.35,
        "stress_lim": 0.1,
        "ae_num": 375,
        "eval_num_stage2": 20,
        "weight_function_table_family": WeightFunctionTableFamily.SMOOTH,
        "nominal_stress_extraction_mode": NominalStressExtractionMode.SMOOTH_DSLOAD,
    },
    ("N50R", "R008", "T24"): {
        "width": 5.0,
        "thickness": 1.9,
        "stress_lim": 0.2,
        "ae_num": 100,
        "eval_num_stage2": 24,
        "weight_function_table_family": WeightFunctionTableFamily.THREE_POINT_BENDING,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.THREE_POINT_BENDING_RF1
        ),
    },
    ("N50R", "R100", "T24"): {
        "width": 5.0,
        "thickness": 1.9,
        "stress_lim": 0.4,
        "ae_num": 80,
        "eval_num_stage2": 24,
        "weight_function_table_family": WeightFunctionTableFamily.THREE_POINT_BENDING,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.THREE_POINT_BENDING_RF1
        ),
    },
    ("N50R", "CS", "T50"): {
        "width": 1.5,
        "thickness": 4.5,
        "stress_lim": 1.0,
        "ae_num": 5,
        "eval_num_stage2": 50,
        "weight_function_table_family": WeightFunctionTableFamily.COMPACT_SPECIMEN,
        "nominal_stress_extraction_mode": (
            NominalStressExtractionMode.COMPACT_SPECIMEN_DSLOAD
        ),
    },
}


def main() -> None:
    if SUPPORTED_PARAMETER_CONDITIONS != set(EXPECTED_CONDITION_SUMMARY):
        expected = _format_conditions(set(EXPECTED_CONDITION_SUMMARY))
        actual = _format_conditions(SUPPORTED_PARAMETER_CONDITIONS)
        raise AssertionError(
            "SUPPORTED_PARAMETER_CONDITIONS does not match expected conditions.\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}"
        )

    for condition, expected in sorted(EXPECTED_CONDITION_SUMMARY.items()):
        steel, specimen_type, thickness_sign = condition
        params = PaperModelParameters(
            steel=steel,
            specimen_type=specimen_type,
            thickness_sign=thickness_sign,
        )
        actual = {
            "width": params.width,
            "thickness": params.thickness,
            "stress_lim": params.stress_lim,
            "ae_num": params.AeNum,
            "eval_num_stage2": params.eval_num_stage2,
            "weight_function_table_family": params.weight_function_table_family,
            "nominal_stress_extraction_mode": params.nominal_stress_extraction_mode,
        }
        if actual != expected:
            raise AssertionError(
                f"Unexpected parameter summary for {params.name}: "
                f"expected {expected}, got {actual}"
            )
        if params.name != f"{steel}_{specimen_type}_{thickness_sign}":
            raise AssertionError(f"Unexpected model name: {params.name}")
        if params.specimen_type != specimen_type:
            raise AssertionError(f"Unexpected specimen_type alias: {params.name}")
        if params.thickness_sign != thickness_sign:
            raise AssertionError(f"Unexpected thickness_sign alias: {params.name}")
        if params.cache_name_key != f"{steel}_{specimen_type}":
            raise AssertionError(f"Unexpected cache_name_key: {params.name}")
        if params.resolved_condition.condition.model_name != params.name:
            raise AssertionError(f"Resolved condition name mismatch: {params.name}")
        if len(params.eval_points_stage2) + 2 != params.eval_num_stage2:
            raise AssertionError(f"Stage II point count mismatch for {params.name}")

    _assert_unsupported_condition_is_rejected()
    print(
        "Parameter condition check passed: "
        f"{len(EXPECTED_CONDITION_SUMMARY)} condition(s)."
    )


def _assert_unsupported_condition_is_rejected() -> None:
    try:
        PaperModelParameters(
            steel="B",
            specimen_type="CS",
            thickness_sign="T50",
        )
    except ValueError:
        return
    raise AssertionError("Unsupported condition B_CS_T50 was not rejected")


def _format_conditions(conditions: set[tuple[str, str, str]]) -> str:
    return ", ".join(
        f"{steel}_{specimen_type}_{thickness_sign}"
        for steel, specimen_type, thickness_sign in sorted(conditions)
    )


if __name__ == "__main__":
    main()
