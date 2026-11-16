from __future__ import annotations

import argparse
import datetime
from dataclasses import replace
from pathlib import Path

from .config import SimulationConfig, load_simulation_config
from .context import build_calculation_input_data, build_context
from .output import build_output_context, write_failure_diagnostic
from .runner import run_simulation


def _add_run_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--preset", choices=("smoke",), default=None)
    parser.add_argument("--config-file", type=Path, default=None)
    parser.add_argument("--base-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument(
        "--write-diagnostics",
        action="store_true",
        help="Write diagnostic CSVs and diagnostic notices (disabled by default).",
    )
    parser.add_argument(
        "--delete-existing-output",
        action="store_true",
        help="Delete existing result CSVs and diagnostics/*.csv in --output-dir before running.",
    )


def _build_run_config(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> SimulationConfig:
    if args.preset == "smoke":
        config = SimulationConfig.smoke(
            repo_root=Path.cwd().resolve(),
            output_dir=args.output_dir.resolve() if args.output_dir else None,
        )
    else:
        if args.config_file is None:
            parser.error("--config-file is required unless --preset smoke is used")
        if args.base_dir is None:
            parser.error("--base-dir is required unless --preset smoke is used")
        if args.output_dir is None:
            parser.error("--output-dir is required unless --preset smoke is used")
        config = load_simulation_config(
            args.config_file.resolve(),
            base_dir=args.base_dir.resolve(),
            output_dir=args.output_dir.resolve(),
        )

    overrides: dict[str, object] = {}
    for arg_name, field_name in (
        ("base_dir", "base_dir"),
        ("cache_dir", "cache_dir"),
    ):
        value = getattr(args, arg_name)
        if value is not None:
            overrides[field_name] = (
                value.resolve() if isinstance(value, Path) else value
            )

    if args.delete_existing_output:
        overrides["delete_existing_output"] = True

    return replace(config, **overrides)


def _prepare_output_dir(config: SimulationConfig) -> None:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    if config.delete_existing_output:
        for path in config.output_dir.glob("*.csv"):
            path.unlink()
        for path in (config.output_dir / "diagnostics").glob("*.csv"):
            path.unlink()


def _run(config: SimulationConfig, *, write_diagnostics: bool = False) -> None:
    started_at = datetime.datetime.now()
    print(f"Run started: {started_at}")
    _prepare_output_dir(config)
    try:
        context = build_context(config)
    except Exception as exc:  # Save input failures when requested; no recovery is attempted.
        if write_diagnostics:
            write_failure_diagnostic(
                config.output_dir, exc, phase="input_preparation",
                steel=config.steel, specimen_type=config.specimen_type,
                thickness_sign=config.thickness_sign,
            )
        raise
    input_data = build_calculation_input_data(context)
    output_context = build_output_context(context)
    run_simulation(
        input_data, output_context=output_context, write_outputs=True,
        write_diagnostics=write_diagnostics,
    )
    completed_at = datetime.datetime.now()
    print(f"Run completed: {context.model_files.model_name}")
    print(f"Run elapsed: {completed_at - started_at}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="multiscale-fatigue-model-ijf-2026",
        description=(
            "Run the refactored reference implementation. "
            "Comparison commands live under scripts/verification/."
        ),
    )
    subparsers = parser.add_subparsers(dest="command")
    run_parser = subparsers.add_parser("run")
    _add_run_arguments(run_parser)

    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return

    if args.command == "run":
        _run(_build_run_config(args, run_parser), write_diagnostics=args.write_diagnostics)
        return

    raise ValueError(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
