# Multiscale-fatigue-model-IJF-2026

## Refactored Reference Implementation

`src/multiscale_fatigue_model_ijf_2026/` contains a staged refactoring of the original script. The goal is not to provide a general-purpose library API; it is to make the paper implementation easier to read, verify, and modify without changing the calculation results.

Recommended reading order:

1. `config.py` and `parameters.py`: input conditions, specimen setup, active zone, evaluation points, and model switches.
2. `material.py`: measured material data, Abaqus field cache, weight-function resources, and generated microstructure cache.
3. `field_values.py`: stress/strain field lookup used by the fatigue calculation.
4. `context.py` and `calculation/inputs.py`: preparation and shape of the calculation-only inputs.
5. `runner.py` and `calculation/load_case.py`: execution order across nominal stress, iterations, active area elements, and symmetry positions.
6. `calculation/element_life.py`: crack-initiation candidates inside one active area element.
7. `calculation/crack_life.py`: Stage I/II crack growth, grain boundaries, CTSD, K value, closure, and life integration.
8. Result dataclasses live next to the calculation that creates them; `output.py` writes legacy-compatible CSV output.

Execution hierarchy:

1. `runner.py`: loop over nominal stress cases.
2. `calculation/load_case.py`: loop over iterations, ranked active area elements, and symmetry positions.
3. `calculation/element_life.py`: sample candidate cracks inside one active area element and keep the shortest life.
4. `calculation/crack_life.py`: evaluate crack-growth points through Stage I/II, CTSD, K value, closure, and life integration.

Run the refactored implementation with:

```bash
python -m multiscale_fatigue_model_ijf_2026.cli run --config-file verification/configs/original_defaults.json --base-dir multiscale-fatigue-model --output-dir outputs/run --delete-existing-output
```

Default simulation parameters follow `multiscale-fatigue-model/Multiscale_fatigue_model.org.py`: `sigma_nom` is `[150, 160, 170, 180, 190]`, `iteration_count` is `4`, and `n_symm` is `4`. These values are written explicitly in `verification/configs/original_defaults.json`; no random seed is set for the default run.

Simulation parameters such as material, stress, and iteration settings are written in the JSON config file. CLI options are kept to systematic execution parameters such as input/output/cache directories. Use seed-fixed configs such as `verification/configs/heavy_seed42.json` and `verification/configs/lightweight_seed42.json` only for reproducible comparison and lightweight verification.

`resources/` contains the minimal files needed for a sample run with `--base-dir resources`:

- `sample_simulation.json`: sample simulation settings aligned with `Multiscale_fatigue_model.org.py` defaults.
- `N50R_CS_T50.inp` and `N50R_CS_T50.dat`: FEM mesh and field output.
- `N50R_*.csv`: measured microstructure and material-property inputs.
- `CombinedData_Ellipse_WF_CF.json`: weight-function constants.

Generated cache files such as `*.pkl` and output CSV files are kept outside `resources/`.

Run the sample resources setup with:

```powershell
scripts\Invoke-SampleResourcesRun.ps1
```

The script uses `resources/sample_simulation.json`, reads input files from `resources/`, reuses cache files from `multiscale-fatigue-model/` by default, and writes CSV output under `outputs/sample_resources/`.

For a light verification run, use the smoke preset:

```bash
python -m multiscale_fatigue_model_ijf_2026.cli run --preset smoke
```

Comparison commands live under `scripts/`; the normal CLI does not run the old implementation. To compare the refactored implementation against `Multiscale_fatigue_model.py` under a heavier seed-fixed condition, use `scripts\Invoke-HeavyComparison.ps1`.

### `multiscale-fatigue-model/` (Validation on Real Specimens)
- **Purpose**: Corresponds to **Section 3** of the manuscript. It validates the multiscale fatigue model's capability to reproduce small-crack growth behavior (non-monotonic da/dN curves) and predict fatigue life (S-N curves).
- **Contents**: 
  - Forward simulation scripts for real specimen geometries.
  - Required data files including finite element (FEM) mesh files (`.inp`), strain field data (`.dat`), weight functions, and microstructural information.
- **Usage**: Run the main life prediction script within this directory.

## Requirements
- Python 3.x
- Required libraries: `numpy`, `pandas`, `scipy`

Install the dependencies using:
```bash
pip install numpy pandas scipy
