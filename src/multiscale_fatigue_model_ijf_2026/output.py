from __future__ import annotations

import json
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .calculation.diagnostics import CalculationDiagnostic, CrackLifeDiagnosticError
from .calculation.element_life import ElementLifeResult
from .calculation.load_case import LoadCaseResult
from .context import SimulationContext


@dataclass(frozen=True)
class OutputContext:
    output_dir: Path
    model_name: str
    n_paris: float
    delta_delta_th: float
    ferrite_friction_strength: float
    r_ratio: float


def build_output_context(context: SimulationContext) -> OutputContext:
    return OutputContext(
        output_dir=context.config.output_dir,
        model_name=context.model_files.output_filename_body,
        n_paris=context.params.n_paris,
        delta_delta_th=context.params.Δδ_th,
        ferrite_friction_strength=context.output_ferrite_friction_strength,
        r_ratio=context.params.R_ratio,
    )


def detail_filename(
    context: OutputContext,
    load_result: LoadCaseResult,
    iteration: int,
) -> str:
    return (
        f"{context.model_name}_{context.n_paris}_{context.delta_delta_th}_"
        f"{load_result.sigma_nom}_{context.ferrite_friction_strength}_"
        f"{iteration}.{context.r_ratio}.csv"
    )


def summary_filename(context: OutputContext, load_result: LoadCaseResult) -> str:
    return (
        f"{context.model_name}_{context.n_paris}_{context.delta_delta_th}_"
        f"{load_result.sigma_nom}_{context.ferrite_friction_strength}."
        f"{context.r_ratio}.csv"
    )


def status_filename(context: OutputContext, load_result: LoadCaseResult) -> str:
    return (
        f"{context.model_name}_{context.n_paris}_{context.delta_delta_th}_"
        f"{load_result.sigma_nom}_{context.ferrite_friction_strength}."
        f"{context.r_ratio}.status.csv"
    )


def element_result_to_dataframe(result: ElementLifeResult) -> pd.DataFrame:
    max_len = max(len(result.crack_depth), len(result.grain_boundary_locations))
    return pd.DataFrame(
        {
            "Crack depth": _pad_list(result.crack_depth, max_len),
            "Surface crack length": _pad_list(result.surface_crack_length, max_len),
            "Slip band": _pad_list(result.slip_band, max_len),
            "CTSD": _pad_list(result.ctsd, max_len),
            "Cycles": _pad_list(result.cycles, max_len),
            "K Value": _pad_list(result.k_value, max_len),
            "Effective Stress": _pad_list(result.effective_stress, max_len),
            "Stress Ratio": _pad_list(result.stress_ratio, max_len),
            "Aspect Ratio": _pad_list(result.aspect_ratio, max_len),
            "Opening Stress": _pad_list(result.opening_stress, max_len),
            "Location of GB": _pad_list(result.grain_boundary_locations, max_len),
        }
    )


def summary_to_dataframe(load_result: LoadCaseResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            [
                load_result.sigma_nom,
                iteration.iteration,
                iteration.minimum_life,
                iteration.weakest_location_yz,
            ]
            for iteration in load_result.iteration_results
        ],
        columns=["σ_nom", "Iteration", "minimum life", "yz"],
    )


def status_to_dataframe(load_result: LoadCaseResult) -> pd.DataFrame:
    rows = []
    for iteration in load_result.iteration_results:
        result = iteration.best_element_result
        rows.append(
            {
                "σ_nom": load_result.sigma_nom,
                "Iteration": iteration.iteration,
                "minimum life": iteration.minimum_life,
                "selected is complete": (
                    np.nan if result is None else result.is_complete
                ),
                "selected stop reason": (
                    np.nan if result is None else result.stop_reason
                ),
                "selected valid until index": (
                    np.nan if result is None else result.valid_until_index
                ),
                "complete element count": iteration.complete_element_count,
                "domain limited element count": (
                    iteration.domain_limited_element_count
                ),
                "incomplete element count": iteration.incomplete_element_count,
            }
        )
    return pd.DataFrame(rows)


def write_load_case_outputs(
    context: OutputContext, load_result: LoadCaseResult, *, write_diagnostics: bool = False,
) -> None:
    output_dir = context.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    for iteration_result in load_result.iteration_results:
        if iteration_result.best_element_result is None:
            continue
        filename = detail_filename(context, load_result, iteration_result.iteration - 1)
        element_result_to_dataframe(iteration_result.best_element_result).to_csv(
            output_dir / filename,
            index=False,
        )

    summary_to_dataframe(load_result).to_csv(
        output_dir / summary_filename(context, load_result),
        index=False,
    )
    if any(
        iteration.incomplete_element_count > 0
        for iteration in load_result.iteration_results
    ):
        status_to_dataframe(load_result).to_csv(
            output_dir / status_filename(context, load_result),
            index=False,
        )
    if write_diagnostics:
        write_load_case_diagnostics(context, load_result)


_INITIAL_REASONS = {
    "maximum_shear_condition_not_met": "Maximum shear stress did not exceed ferrite friction strength.",
    "no_evaluated_ferrite_grain": "No ferrite grain satisfied the size selection condition.",
    "resolved_shear_condition_not_met": "Resolved shear stress did not exceed ferrite friction strength.",
    "no_candidate_adopted": "Crack calculation was called but no history was adopted; detailed cause unclassified.",
}


_DIAGNOSTIC_DESCRIPTIONS = {
    "CrackLifeDiagnosticError": ("unexpected", "Invalid numerical state."),
    "WeightFunctionDomainError": ("outside_domain", "Weight-function domain limit."),
    "negative_integrated_cycles": (
        "unclassified",
        "Negative integrated cycles; legacy stop retained, model meaning unconfirmed.",
    ),
    "grain_layers_exhausted": (
        "unclassified",
        "CTSD evaluation exhausted grain layers; legacy stop retained, model meaning unconfirmed.",
    ),
}


def _describe_diagnostic(diagnostic: CalculationDiagnostic) -> tuple[str, str]:
    """Apply reporting policy without changing the observed calculation fact."""
    classification, description = _DIAGNOSTIC_DESCRIPTIONS.get(
        diagnostic.reason, ("unclassified", diagnostic.reason),
    )
    return classification, diagnostic.message if diagnostic.message is not None else description


def write_load_case_diagnostics(context: OutputContext, load_result: LoadCaseResult) -> None:
    """Link detail data rows (1-based, excluding header) to observed problems.

    Events include discarded candidates. Their occurrence in the same iteration
    does not establish that they caused a selected history's zero value.
    Calculation indices in event context are 0-based; iteration is 1-based.
    """
    diagnostic_dir = context.output_dir / "diagnostics"
    diagnostic_dir.mkdir(parents=True, exist_ok=True)
    event_filename = summary_filename(context, load_result) + ".events.csv"
    events = []
    for iteration in load_result.iteration_results:
        event_ids = []
        selected_event_ids = []
        observed_classifications = set()
        result = iteration.best_element_result
        for number, diagnostic in enumerate(iteration.diagnostics, start=1):
            classification, message = _describe_diagnostic(diagnostic)
            observed_classifications.add(classification)
            event_id = f"iteration-{iteration.iteration}-event-{number}"
            event_ids.append(event_id)
            if result is not None and (
                result.selected_grain_index is not None
                and diagnostic.context.get("area_element_index") == result.area_element_index
                and diagnostic.context.get("symmetry_index") == result.symmetry_index
                and diagnostic.context.get("grain_index") == result.selected_grain_index
            ):
                selected_event_ids.append(event_id)
            events.append({
                "event_id": event_id, "model": context.model_name,
                "classification": classification,
                "reason": diagnostic.reason, "message": message,
                "context": json.dumps(diagnostic.context, ensure_ascii=False, default=str),
            })
        if result is None:
            continue
        filename = detail_filename(context, load_result, iteration.iteration - 1)
        frame = element_result_to_dataframe(result)
        rows = []
        for index, row in frame.iterrows():
            zero_row = row["Crack depth"] == 0 and row["CTSD"] == 0
            status = "no_problem_observed_at_monitored_checks"
            reason = "Selected calculated history."
            if result.history_state == "initial":
                reasons = result.initial_history_reasons
                reason = "Initial values written; the selected element has no adopted crack history. " + " ".join(
                    _INITIAL_REASONS.get(code, code) for code in sorted(reasons)
                )
                if not reasons or "no_candidate_adopted" in reasons:
                    status = "unclassified"
                else:
                    status = "expected_conditions"
            elif result.history_state is None:
                status = "unclassified"
                reason = "History provenance was not supplied by the element calculator."
            elif zero_row:
                status = "unclassified"
                reason = "Zero value in adopted history; detailed normal termination classification deferred."
            if event_ids:
                status = "issues_observed_in_same_iteration"
                reason += " See events; occurrence alone does not establish the cause of this row."
            rows.append({
                "detail_file": filename, "data_row": index + 1,
                "model": context.model_name, "sigma_nom": load_result.sigma_nom,
                "iteration": iteration.iteration, "zero_depth_and_ctsd": zero_row,
                "history_state": result.history_state or "unclassified", "diagnostic_status": status,
                "selected_area_element_index": result.area_element_index,
                "selected_area_element_rank": result.area_element_rank,
                "selected_symmetry_index": result.symmetry_index,
                "selected_grain_index": result.selected_grain_index,
                "observed_classifications": ";".join(sorted(observed_classifications)),
                "reason": reason, "events_file": event_filename if event_ids else "",
                "iteration_initial_history_reasons": ";".join(sorted(iteration.initial_history_reasons)),
                "iteration_event_ids": ";".join(event_ids),
                "selected_candidate_event_ids": ";".join(selected_event_ids),
            })
        pd.DataFrame(rows).to_csv(diagnostic_dir / (filename + ".rows.csv"), index=False)
    if events:
        pd.DataFrame(events).to_csv(diagnostic_dir / event_filename, index=False)
        observed = sorted({f"{event['classification']}: {event['reason']}" for event in events})
        print("Observed calculation diagnostics: " + "; ".join(observed))
        print(f"Calculation diagnostics: {diagnostic_dir / event_filename}")
    print(f"Detail row diagnostics: {diagnostic_dir}")


def write_failure_diagnostic(
    output_dir: Path, exc: Exception, **context: object,
) -> None:
    """Persist a fatal diagnostic without inventing a result row or continuing."""
    directory = output_dir / "diagnostics"
    directory.mkdir(parents=True, exist_ok=True)
    diagnostic = exc.diagnostic() if isinstance(exc, CrackLifeDiagnosticError) else CalculationDiagnostic(
        reason=type(exc).__name__, message=str(exc),
    )
    classification, message = _describe_diagnostic(diagnostic)
    if diagnostic.reason not in _DIAGNOSTIC_DESCRIPTIONS:
        classification = "unexpected"  # An uncaught failure, not an unclassified returned event.
    diagnostic.context.update(context)
    path = directory / "failure.csv"
    pd.DataFrame([{
        "classification": classification,
        "reason": diagnostic.reason, "message": message,
        "context": json.dumps(diagnostic.context, ensure_ascii=False, default=str),
        "traceback": "".join(traceback.format_exception(exc)),
        "result_row": "No result row written for the failed load case.",
    }]).to_csv(path, index=False)
    print(f"Calculation stopped ({classification}): {message}")
    print(f"Failure diagnostic: {path}")


def _pad_list(values: Sequence[object] | np.ndarray, target_len: int) -> list[object]:
    if isinstance(values, np.ndarray):
        values = values.tolist()
    return list(values) + [np.nan] * (target_len - len(values))
