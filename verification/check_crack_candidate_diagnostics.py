from __future__ import annotations

import json
import random
import tempfile
import unittest
from contextlib import ExitStack, redirect_stdout
from dataclasses import asdict, replace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from multiscale_fatigue_model_ijf_2026 import cli, output
from multiscale_fatigue_model_ijf_2026.calculation import crack_life
from multiscale_fatigue_model_ijf_2026.calculation.diagnostics import (
    CalculationDiagnostic,
    CrackLifeDiagnosticError,
    WeightFunctionDomainError,
)
from multiscale_fatigue_model_ijf_2026.calculation.element_life import (
    calculate_element_life,
)
from multiscale_fatigue_model_ijf_2026.config import SimulationConfig
from multiscale_fatigue_model_ijf_2026.output import OutputContext
from multiscale_fatigue_model_ijf_2026.runner import run_simulation
from verification.smoke import _build_mock_input_data, _fake_element_life_result


class CrackCandidateDiagnosticsVerification(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.context = OutputContext(Path(self.directory.name), "test", 1.8, 0.000063, 1, -1)
        self.input_data = _build_mock_input_data()

    def test_default_run_writes_results_without_diagnostics(self) -> None:
        console = StringIO()
        with redirect_stdout(console):
            run_simulation(self.input_data, output_context=self.context)
        self.assertTrue(list(self.context.output_dir.glob("*.csv")))
        self.assertFalse((self.context.output_dir / "diagnostics").exists())
        self.assertNotIn("diagnostics:", console.getvalue())

    def test_output_switch_preserves_results_random_state_and_status(self) -> None:
        data = replace(self.input_data, specimen=replace(self.input_data.specimen, n_symm=2),
                       weight_function_domain_policy="truncate_candidate")

        def element(data, **kwargs):
            # Retain an incomplete candidate event while selecting the complete one.
            random.random()
            np.random.random()
            if kwargs["symmetry_index"] == 0:
                result = _fake_element_life_result(
                    kwargs, is_complete=False, stop_reason="weight_function_domain_limit",
                    valid_until_index=0, cycles=[np.nan],
                )
                result.diagnostics = [CalculationDiagnostic("WeightFunctionDomainError", {"at": 0.2})]
                return result
            return _fake_element_life_result(kwargs)

        runs = []
        for enabled in (False, True):
            context = replace(self.context, output_dir=self.context.output_dir / str(enabled))
            random.seed(42)
            np.random.seed(42)
            console = StringIO()
            with redirect_stdout(console):
                result = run_simulation(
                    data, output_context=context, write_diagnostics=enabled,
                    element_life_calculator=element,
                )
            files = {p.name: p.read_bytes() for p in context.output_dir.glob("*.csv")}
            self.assertTrue(any(name.endswith(".status.csv") for name in files))
            self.assertEqual((context.output_dir / "diagnostics").exists(), enabled)
            self.assertEqual("Detail row diagnostics:" in console.getvalue(), enabled)
            self.assertEqual("Observed calculation diagnostics:" in console.getvalue(), enabled)
            runs.append((files, repr(result.load_case_results), random.getstate(), np.random.get_state()))
        self.assertEqual(runs[0][:3], runs[1][:3])
        np.testing.assert_array_equal(runs[0][3][1], runs[1][3][1])
        self.assertEqual(runs[0][3][2:], runs[1][3][2:])

    def test_failure_output_switch_and_write_outputs_precedence(self) -> None:
        for enabled, writing in ((False, True), (True, True), (True, False)):
            for error in (WeightFunctionDomainError("outside", at=0.2), ValueError("invalid")):
                with self.subTest(enabled=enabled, writing=writing, error=type(error).__name__):
                    context = replace(self.context, output_dir=self.context.output_dir / f"{enabled}_{writing}_{type(error).__name__}")

                    def fail(data, **kwargs):
                        raise error

                    console = StringIO()
                    with redirect_stdout(console), self.assertRaises(type(error)) as raised:
                        run_simulation(
                            self.input_data, output_context=context, write_outputs=writing,
                            write_diagnostics=enabled, element_life_calculator=fail,
                        )
                    self.assertIs(raised.exception, error)
                    self.assertEqual((context.output_dir / "diagnostics/failure.csv").exists(), enabled and writing)
                    self.assertEqual("Failure diagnostic:" in console.getvalue(), enabled and writing)
        context = replace(self.context, output_dir=self.context.output_dir / "no_output")
        run_simulation(self.input_data, output_context=context, write_outputs=False, write_diagnostics=True)
        self.assertFalse(context.output_dir.exists())

    def test_cli_switch_reaches_input_failure_and_runner(self) -> None:
        for enabled in (False, True):
            directory = self.context.output_dir / f"cli_{enabled}"
            args = ["run", "--preset", "smoke", "--output-dir", str(directory)]
            if enabled:
                args.append("--write-diagnostics")
            error = ValueError("input preparation failed")
            console = StringIO()
            with patch.object(cli, "build_context", side_effect=error), redirect_stdout(console):
                with self.assertRaises(ValueError) as raised:
                    cli.main(args)
            self.assertIs(raised.exception, error)
            self.assertEqual((directory / "diagnostics/failure.csv").exists(), enabled)
            self.assertEqual("Failure diagnostic:" in console.getvalue(), enabled)
            if enabled:
                record = pd.read_csv(directory / "diagnostics/failure.csv").iloc[0]
                self.assertEqual(json.loads(record["context"])["phase"], "input_preparation")
            with patch.object(cli, "build_context", return_value=SimpleNamespace(
                model_files=SimpleNamespace(model_name="test"),
            )), patch.object(cli, "build_calculation_input_data", return_value=self.input_data), \
                    patch.object(cli, "build_output_context", return_value=self.context), \
                    patch.object(cli, "run_simulation") as run, redirect_stdout(StringIO()):
                cli.main(args)
            self.assertEqual(run.call_args.kwargs["write_diagnostics"], enabled)
        console = StringIO()
        with redirect_stdout(console), self.assertRaises(SystemExit) as raised:
            cli.main(["run", "--help"])
        self.assertEqual(raised.exception.code, 0)
        self.assertIn("--write-diagnostics", console.getvalue())
        self.assertIn("disabled by default", " ".join(console.getvalue().split()))

    def test_existing_diagnostics_are_kept_unless_deletion_is_requested(self) -> None:
        diagnostic = self.context.output_dir / "diagnostics/previous.csv"
        diagnostic.parent.mkdir()
        diagnostic.write_text("previous diagnostic", encoding="utf-8")
        config = SimulationConfig.smoke(repo_root=Path.cwd(), output_dir=self.context.output_dir)
        cli._prepare_output_dir(replace(config, delete_existing_output=False))
        run_simulation(self.input_data, output_context=self.context)
        self.assertEqual(diagnostic.read_text(encoding="utf-8"), "previous diagnostic")
        summary = next(self.context.output_dir.glob("*.csv"))
        cli._prepare_output_dir(replace(config, delete_existing_output=True))
        self.assertFalse(diagnostic.exists())
        self.assertFalse(summary.exists())

    def test_expected_zero_rows_have_direct_reason_and_no_problem_event(self) -> None:
        # Run the real element kernel, not a fake initial result.
        data = replace(self.input_data, material_strength=replace(
            self.input_data.material_strength, ferrite_friction_strength=100.0,
        ), evaluation_points=replace(self.input_data.evaluation_points, eval_num_total=4))
        random.seed(42)
        run_simulation(data, output_context=self.context, write_diagnostics=True)
        detail_path = next(self.context.output_dir.glob("*_0.-1.csv"))
        detail = pd.read_csv(detail_path)
        rows = pd.read_csv(self.context.output_dir / "diagnostics" / (detail_path.name + ".rows.csv"))
        self.assertTrue((detail["Crack depth"] == 0).all())
        self.assertTrue((detail["CTSD"] == 0).all())
        self.assertEqual(len(detail), 4)
        self.assertEqual(rows["data_row"].tolist(), list(range(1, len(detail) + 1)))
        self.assertEqual(rows["detail_file"].unique().tolist(), [detail_path.name])
        self.assertTrue((rows["history_state"] == "initial").all())
        self.assertTrue((rows["diagnostic_status"] == "expected_conditions").all())
        self.assertIn("Maximum shear stress", rows.iloc[0]["reason"])
        self.assertFalse(list((self.context.output_dir / "diagnostics").glob("*.events.csv")))

    def test_discarded_candidate_problem_remains_linked_to_each_result_row(self) -> None:
        data = replace(self.input_data, specimen=replace(self.input_data.specimen, n_symm=2))

        def element(data, **kwargs):
            result = _fake_element_life_result(kwargs, cycles=[20.0 if kwargs["symmetry_index"] == 0 else 10.0])
            result.history_state = "adopted"
            result.selected_grain_index = 0
            result.crack_depth = [0.0]
            result.ctsd = [0.0]
            if kwargs["symmetry_index"] == 0:
                result.diagnostics = [CalculationDiagnostic(
                    "grain_layers_exhausted",
                    {"grain_index": 0, "evaluation_index": 3},
                )]
            return result

        run_simulation(data, output_context=self.context, write_diagnostics=True, element_life_calculator=element)
        diagnostic_dir = self.context.output_dir / "diagnostics"
        row = pd.read_csv(next(diagnostic_dir.glob("*.rows.csv"))).iloc[0]
        self.assertEqual(row["diagnostic_status"], "issues_observed_in_same_iteration")
        event = pd.read_csv(diagnostic_dir / row["events_file"]).iloc[0]
        self.assertEqual(row["iteration_event_ids"], event["event_id"])
        self.assertTrue(pd.isna(row["selected_candidate_event_ids"]))
        self.assertEqual(json.loads(event["context"])["symmetry_index"], 0)
        self.assertIn("does not establish", row["reason"])

    def _crack(self, policy: str, *, ctsd_result=None):
        # Supply a small deterministic geometry; execute actual exception/policy handling.
        data = replace(self.input_data, weight_function_domain_policy=policy)
        with ExitStack() as stack:
            replacements = {
                "_initial_crack_dimensions": (0.05, 0.02),
                "_build_crack_aspect_function": lambda a: 1.0,
                "_generate_grain_boundaries": SimpleNamespace(boundary_depths=np.array([0.1, 0.2])),
                "_build_evaluation_points": ([0.0, 0.1], [0.0, 0.1], 2),
                "_surface_reference_principal_stress": 1.0,
            }
            for name, value in replacements.items():
                stack.enter_context(patch.object(crack_life, name, return_value=value))
            stress = stack.enter_context(patch.object(crack_life, "_calculate_stress_state_at_crack_depth"))
            if ctsd_result is None:
                stress.side_effect = WeightFunctionDomainError("Artificial outside-domain input", at=0.2)
            else:
                stress.return_value = (1.0,) * 6
                stack.enter_context(patch.object(crack_life, "_evaluate_ctsd_at_crack_depth", return_value=ctsd_result))
            return crack_life.calculate_crack_life(
                data, load_index=0, grain_size=0.1, orientation=[0, 0, 0],
                y=0.0, z=0.0, anai=lambda a: 1.0,
                field_values=data.stress_fields.by_load[0],
                cycles_result=[10**18, 10**18], crack_depth_result=[0.0, 1.0],
            )

    def test_domain_error_policy_reraises_and_truncate_retains_context(self) -> None:
        with self.assertRaises(WeightFunctionDomainError) as raised:
            self._crack("error")
        self.assertEqual(raised.exception.context["evaluation_index"], 0)
        result = self._crack("truncate_candidate")
        self.assertFalse(result.is_complete)
        self.assertTrue(np.isnan(result.crack_depth).all())
        self.assertEqual(result.diagnostics[0].reason, "WeightFunctionDomainError")
        self.assertEqual(result.diagnostics[0].context["at"], 0.2)

    def test_problem_in_discarded_grain_is_retained_by_real_element_kernel(self) -> None:
        partial = self._crack("truncate_candidate")
        complete = replace(
            partial, is_complete=True, stop_reason=None, diagnostics=[],
            cycles=[0.0, 10.0], crack_depth=[0.0, 0.1],
        )
        data = replace(self.input_data, microstructure=replace(
            self.input_data.microstructure,
            slip_plane_resolver=lambda *args: (2.0, np.ones(3), np.ones(3)),
        ))
        random.seed(42)
        with patch("multiscale_fatigue_model_ijf_2026.calculation.element_life.calculate_crack_life",
                   side_effect=[partial, complete]) as calculation:
            result = calculate_element_life(
                data, load_index=0, area_element_rank=0, symmetry_index=0,
                area_element_index=0, stress_tensor=np.eye(3), max_shear_stress=2.0,
                field_values=data.stress_fields.by_load[0],
                cycles_result=[10**18, 10**18], crack_depth_result=[0.0, 1.0],
            )
        self.assertEqual(calculation.call_count, 2)
        self.assertEqual(result.selected_grain_index, 1)
        self.assertEqual(result.diagnostics[0].context["grain_index"], 0)
        self.assertEqual(result.diagnostics[0].reason, "WeightFunctionDomainError")

    def test_initial_ctsd_stop_and_layer_exhaustion_return_calculation_facts(self) -> None:
        expected = self._crack("error", ctsd_result=(100.0, 0.0, False, True))
        self.assertEqual(expected.diagnostics, [])
        unconfirmed = self._crack("error", ctsd_result=(1.05, 0.0, True, True))
        self.assertEqual(unconfirmed.diagnostics[0].reason, "grain_layers_exhausted")
        self.assertTrue(unconfirmed.diagnostics[0].context["unstable_fracture"])
        self.assertIsNone(unconfirmed.diagnostics[0].message)
        self.assertEqual(expected.cycles, unconfirmed.cycles)

    def test_fatal_error_is_saved_and_original_exception_is_reraised(self) -> None:
        for error in (CrackLifeDiagnosticError("non-finite K", quantity="K"), ValueError("unexpected input")):
            with self.subTest(error=type(error).__name__):
                def fail(data, **kwargs):
                    raise error

                with self.assertRaises(type(error)) as raised:
                    run_simulation(self.input_data, output_context=self.context, write_diagnostics=True, element_life_calculator=fail)
                self.assertIs(raised.exception, error)
                record = pd.read_csv(self.context.output_dir / "diagnostics/failure.csv").iloc[0]
                self.assertEqual(record["classification"], "unexpected")
                self.assertEqual(json.loads(record["context"])["load_index"], 0)
                self.assertIn(type(error).__name__, record["traceback"])
                self.assertFalse(list(self.context.output_dir.glob("*.csv")))

    def test_diagnostic_checks_do_not_consume_random_numbers(self) -> None:
        random.seed(137)
        np.random.seed(137)
        python_state = random.getstate()
        numpy_state = np.random.get_state()
        with self.assertRaises(CrackLifeDiagnosticError):
            crack_life._assert_finite("test", np.nan, evaluation_index=0)
        self._crack("truncate_candidate")
        self.assertEqual(python_state, random.getstate())
        current = np.random.get_state()
        self.assertEqual(numpy_state[0], current[0])
        np.testing.assert_array_equal(numpy_state[1], current[1])
        self.assertEqual(numpy_state[2:], current[2:])

    def test_negative_integration_is_recorded_without_changing_legacy_result(self) -> None:
        args = dict(
            i=3, rnList=[0.1, 0.5], ai=[0.1, 0.2, 0.3, 0.4],
            nTemp=10**18, S_Δδ0=[1.0] * 4,
            LifeMin=lambda depth: 10**18,
            evaluation_points=self.input_data.evaluation_points,
            crack_growth=self.input_data.crack_growth,
        )
        original = crack_life._integrate_stage2_life_cycle_window(
            **args, S_cyc0=[-100.0, 0.0, 0.0, 0.0], dNdaList=[[0, 1.0], 1],
        )
        diagnostics = []
        observed = crack_life._integrate_stage2_life_cycle_window(
            **args, S_cyc0=[-100.0, 0.0, 0.0, 0.0], dNdaList=[[0, 1.0], 1],
            diagnostics=diagnostics,
        )
        self.assertEqual(original, observed)
        self.assertTrue(observed[-1])
        self.assertEqual(diagnostics[0].reason, "negative_integrated_cycles")
        self.assertLess(min(diagnostics[0].context["cycles"]), 0)
        self.assertIsNone(diagnostics[0].message)

    def test_nan_in_initiation_check_does_not_masquerade_as_expected_zero(self) -> None:
        def invalid_comparison(data, **kwargs):
            kwargs["max_shear_stress"] = np.nan
            return calculate_element_life(data, **kwargs)

        random.seed(42)
        run_simulation(self.input_data, output_context=self.context, write_diagnostics=True, element_life_calculator=invalid_comparison)
        directory = self.context.output_dir / "diagnostics"
        row = pd.read_csv(next(directory.glob("*.rows.csv"))).iloc[0]
        self.assertEqual(row["history_state"], "initial")
        self.assertEqual(row["diagnostic_status"], "issues_observed_in_same_iteration")
        self.assertTrue(pd.isna(row["selected_candidate_event_ids"]))
        event = pd.read_csv(directory / row["events_file"]).iloc[0]
        self.assertEqual(event["classification"], "unexpected")
        self.assertEqual(json.loads(event["context"])["quantity"], "initiation_conditions")

    def test_nonfinite_integration_is_observed_but_intentional_fracture_inf_is_not(self) -> None:
        diagnostics = []
        crack_life._integrate_stage1_life_cycle(
            i=1, ai=[0.0, 0.1], nTemp=10**18,
            S_Δδ0=[np.nan, 1.0], S_cyc0=[0.0, 10**18], dNdaList=[1],
            LifeMin=lambda depth: 10**18, crack_growth=self.input_data.crack_growth,
            diagnostics=diagnostics,
        )
        self.assertEqual(diagnostics[0].reason, "CrackLifeDiagnosticError")
        self.assertEqual(diagnostics[0].context["quantity"], "integrated_cycles")
        fracture = self._crack("error", ctsd_result=(1.05, np.inf, True, False))
        self.assertEqual(fracture.diagnostics, [])
        self.assertTrue(np.isinf(fracture.ctsd).any())

    def test_reporting_policy_can_change_without_changing_calculation_record(self) -> None:
        event = CalculationDiagnostic("grain_layers_exhausted", {"evaluation_index": 3})
        original = asdict(event)
        self.assertNotIn("classification", original)
        self.assertEqual(output._describe_diagnostic(event), (
            "unclassified",
            "CTSD evaluation exhausted grain layers; legacy stop retained, model meaning unconfirmed.",
        ))
        with patch.dict(output._DIAGNOSTIC_DESCRIPTIONS, {
            event.reason: ("example_reporting_category", "Example explanation."),
        }):
            self.assertEqual(output._describe_diagnostic(event), (
                "example_reporting_category", "Example explanation.",
            ))
        self.assertEqual(asdict(event), original)

    def test_exception_record_keeps_technical_detail_without_reporting_category(self) -> None:
        error = WeightFunctionDomainError("query outside table: at=0.2", at=0.2)
        event = error.diagnostic()
        self.assertEqual(event.reason, "WeightFunctionDomainError")
        self.assertEqual(event.message, str(error))
        self.assertEqual(event.context, {"at": 0.2})
        self.assertNotIn("classification", asdict(event))
        self.assertEqual(output._describe_diagnostic(event), ("outside_domain", str(error)))
        unknown = CalculationDiagnostic("new_calculation_event", {"evaluation_index": 2})
        self.assertEqual(output._describe_diagnostic(unknown), ("unclassified", "new_calculation_event"))

    def test_unsupplied_provenance_is_classified_only_in_output(self) -> None:
        def element(data, **kwargs):
            result = _fake_element_life_result(kwargs)
            result.crack_depth = [0.0]
            result.ctsd = [0.0]
            self.assertIsNone(result.history_state)
            return result

        run_simulation(self.input_data, output_context=self.context, write_diagnostics=True, element_life_calculator=element)
        row = pd.read_csv(next((self.context.output_dir / "diagnostics").glob("*.rows.csv"))).iloc[0]
        self.assertEqual(row["history_state"], "unclassified")
        self.assertIn("provenance was not supplied", row["reason"])

    def test_non_adoption_is_recorded_without_deferred_policy(self) -> None:
        stopped = self._crack("error", ctsd_result=(100.0, 0.0, False, True))
        data = replace(self.input_data, microstructure=replace(
            self.input_data.microstructure,
            slip_plane_resolver=lambda *args: (2.0, np.ones(3), np.ones(3)),
        ))
        random.seed(42)
        with patch("multiscale_fatigue_model_ijf_2026.calculation.element_life.calculate_crack_life",
                   return_value=stopped):
            result = run_simulation(data, output_context=self.context, write_diagnostics=True)
        element = result.load_case_results[0].iteration_results[0].best_element_result
        self.assertEqual(element.history_state, "initial")
        self.assertIn("no_candidate_adopted", element.initial_history_reasons)
        row = pd.read_csv(next((self.context.output_dir / "diagnostics").glob("*.rows.csv"))).iloc[0]
        self.assertEqual(row["diagnostic_status"], "unclassified")
        self.assertEqual(row["iteration_initial_history_reasons"], "no_candidate_adopted")
        self.assertIn("detailed cause unclassified", row["reason"])


if __name__ == "__main__":
    unittest.main()
