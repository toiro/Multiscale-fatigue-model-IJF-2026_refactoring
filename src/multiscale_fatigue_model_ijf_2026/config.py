from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

# JSON config contains simulation conditions only. Directories and destructive
# output cleanup are execution controls and stay as CLI/script parameters.
SIMULATION_CONFIG_KEYS = {
    # Specimen and material selection.
    "steel",
    "specimen_type",
    "thickness_sign",
    "crystal",
    # Crack-growth model constants.
    "r_ratio",
    "c_paris",
    "n_paris",
    "delta_delta_th",
    # Reproducibility and load-case loops.
    "random_seed",
    "sigma_nom",
    "iteration_count",
    "n_symm",
    # Lightweight verification limiter.
    "max_active_elements",
}


@dataclass(frozen=True)
class SimulationConfig:
    """Execution-independent simulation conditions plus explicit I/O directories."""

    base_dir: Path
    output_dir: Path
    cache_dir: Path | None = None
    steel: str | None = None
    specimen_type: str | None = None
    thickness_sign: str | None = None
    crystal: str | None = None
    r_ratio: float | None = None
    c_paris: float | None = None
    n_paris: float | None = None
    delta_delta_th: float | None = None
    random_seed: int | None = None
    sigma_nom: tuple[float, ...] | None = None
    iteration_count: int | None = None
    n_symm: int | None = None
    max_active_elements: int | None = None
    delete_existing_output: bool = False

    @classmethod
    def smoke(cls, repo_root: Path, output_dir: Path | None = None) -> "SimulationConfig":
        return cls(
            base_dir=repo_root / "multiscale-fatigue-model",
            output_dir=output_dir or repo_root / "outputs" / "smoke_seed42",
            cache_dir=repo_root / "multiscale-fatigue-model",
            random_seed=42,
            sigma_nom=(150.0,),
            iteration_count=1,
            n_symm=1,
            max_active_elements=1,
            delete_existing_output=True,
        )


def load_simulation_config(
    config_path: Path,
    *,
    base_dir: Path,
    output_dir: Path,
) -> SimulationConfig:
    """Load simulation conditions from JSON while keeping directories explicit."""

    with Path(config_path).open(encoding="utf-8") as file:
        data = json.load(file)

    unknown_keys = sorted(set(data) - SIMULATION_CONFIG_KEYS)
    if unknown_keys:
        raise ValueError(f"Unknown simulation config key(s): {', '.join(unknown_keys)}")

    if "sigma_nom" in data and data["sigma_nom"] is not None:
        data["sigma_nom"] = tuple(data["sigma_nom"])
    return SimulationConfig(base_dir=base_dir, output_dir=output_dir, **data)
