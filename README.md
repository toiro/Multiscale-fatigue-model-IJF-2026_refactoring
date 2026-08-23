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

Run the refactored implementation against the legacy input directory with:

```bash
python -m multiscale_fatigue_model_ijf_2026.cli run --config-file verification/configs/original_defaults.json --base-dir multiscale-fatigue-model --output-dir outputs/run --delete-existing-output
```

Default simulation parameters follow `multiscale-fatigue-model/Multiscale_fatigue_model.org.py`: `sigma_nom` is `[150, 160, 170, 180, 190]`, `iteration_count` is `4`, and `n_symm` is `4`. These values are written explicitly in `verification/configs/original_defaults.json`; no random seed is set for the default run.

Simulation parameters such as material, stress, and iteration settings are written in the JSON config file. CLI options are kept to systematic execution parameters such as input/output/cache directories. Use seed-fixed configs such as `verification/configs/heavy_seed42.json` and `verification/configs/lightweight_seed42.json` only for reproducible comparison and lightweight verification.

`resources/` groups input files by simulation condition. Each condition directory
uses the model name `<steel>_<specimen_type>_<thickness_sign>`, for example
`resources/N50R_CS_T50/`. When `--base-dir resources` is used, the runner selects
the matching condition directory if it exists. Every input file needed for that
condition should be placed in that directory.

Condition names are compact labels from the paper implementation. `steel` is the
material label (`B`, `G`, or `N50R` in the supported resources), `specimen_type`
is the specimen or loading geometry (`Smooth`, `R008`, `R100`, or `CS`), and
`thickness_sign` is the paper's thickness label (`T16`, `T24`, or `T50`). The
resolved values used by the code, including actual thickness, width, active
zone, evaluation points, cache key, weight-function family, and Abaqus nominal
stress extraction mode, are assembled in `parameters.resolve_parameter_condition()`.

Normal calculation configs for the supported `resources/` conditions live under
`resources/configs/`. Run one condition with:

```powershell
scripts\Invoke-ConditionResourcesRun.ps1 -ConfigFile resources\configs\N50R_CS_T50.json
```

These normal configs use the original default calculation settings and do not set
`random_seed` or `max_active_elements`. Seed-fixed lightweight configs under
`verification/configs/conditions/` are for development verification only.

`resources/sample_simulation.json` remains as a single `N50R_CS_T50` sample
settings file for reference. Use `resources/configs/` as the normal
multi-condition entry point. The current `N50R_CS_T50` data lives under
`resources/N50R_CS_T50/`:

- `N50R_CS_T50.inp` and `N50R_CS_T50.dat` or `N50R_CS_T50.dat.zip`: FEM mesh and field output.
- `N50R_*.csv`: measured microstructure and material-property inputs.
- `CombinedData_Ellipse_WF_CF.json`: weight-function constants.

Generated cache files such as `*.pkl` and output CSV files are kept outside `resources/`.
If a run must rebuild the Abaqus field cache from resources, provide the expanded
`.dat` file in the condition directory.

Cache files keep the legacy filename rule: FieldValues and generated
microstructure caches use `steel + specimen_type`, not `thickness_sign`. When
`--cache-dir` is provided explicitly, the runner writes and reads caches under
`<cache-dir>/<steel>_<specimen_type>_<thickness_sign>/` so that the supported
conditions can be kept parallel without relying on implicit shared files.

Before running added conditions, use the condition preflight:

```powershell
scripts\verification\Invoke-ConditionPreflight.ps1
```

This checks the supported condition table, condition-specific resource
directories, normal resource configs, lightweight verification configs, and
context boundary resolution without parsing Abaqus output or generating
calculation caches.

To run a specific lightweight verification config against `resources/`, pass the
verification config to the same condition resources runner:

```powershell
scripts\Invoke-ConditionResourcesRun.ps1 -ConfigFile verification\configs\conditions\lightweight_N50R_R008_T24.json
```

For a light verification run, use the smoke preset:

```bash
python -m multiscale_fatigue_model_ijf_2026.cli run --preset smoke
```

Comparison commands live under `scripts/verification/`; the normal CLI does not run the old implementation. To compare the refactored implementation against `Multiscale_fatigue_model.py` under a heavier seed-fixed condition, use `scripts\verification\Invoke-HeavyComparison.ps1`.

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
