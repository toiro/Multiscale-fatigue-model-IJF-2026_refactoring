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

Create and activate a virtual environment if needed, then install the package in
editable mode before using `python -m ...` commands:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

Run the refactored implementation against the resource input directory with:

```powershell
python -X utf8 -m multiscale_fatigue_model_ijf_2026.cli run `
  --config-file resources\configs\N50R_CS_T50.json `
  --base-dir resources `
  --cache-dir outputs\condition_cache `
  --output-dir outputs\conditions\N50R_CS_T50 `
  --delete-existing-output
```

### Input specification

The normal calculation has three input layers. Paths in the examples below are
relative to the repository root; run the commands from that directory.

| Layer | Where to specify it | Responsibility |
| --- | --- | --- |
| Execution controls | CLI arguments, or `scripts/Invoke-ConditionResourcesRun.ps1` parameters | Select config, input/cache/output directories, cleanup, and diagnostic output. |
| Simulation conditions | `resources/configs/<model_name>.json` | Select material/specimen, crack-growth constants, loads, repetitions, and random seed. |
| Measured and numerical resources | `resources/<model_name>/` | Supply microstructure distributions, measured strengths, FEM fields, and weight-function tables. |

`config.py` reads the simulation JSON; `context.py` combines it with the defaults
and condition tables in `parameters.py`, resolves directories, and prepares the
material and field data before passing calculation inputs to `calculation/`.
The weight-function JSON is a numerical resource, separate from the simulation
config JSON.

#### Command-line arguments

The entry point is `.\.venv\Scripts\python.exe -m multiscale_fatigue_model_ijf_2026.cli run`.
Use `run --help` to inspect the available arguments.

| Argument | Required / default | Meaning |
| --- | --- | --- |
| `--config-file PATH` | Required for a normal run | UTF-8 simulation JSON. |
| `--base-dir PATH` | Required for a normal run | Input root. If `<base-dir>/<model_name>/` exists, use it; otherwise use `base-dir` itself. Once resolved, files are read only from that directory. |
| `--output-dir PATH` | Required for a normal run | Directory for result CSVs; created if absent. |
| `--cache-dir PATH` | Optional; defaults to the resolved input directory | When supplied, caches are read/written under `<cache-dir>/<model_name>/`. Specify this to keep generated files outside `resources/`. |
| `--write-diagnostics` | Off | Write diagnostic CSVs and diagnostic console notices; see the example below. |
| `--delete-existing-output` | Off | Before input preparation, delete `*.csv` directly under the output directory and `diagnostics/*.csv`. Caches are retained. |
| `--preset smoke` | Optional; no preset by default | Use the built-in lightweight condition instead of loading `--config-file`. |
| `-h`, `--help` | Optional | Show help and exit. |

CLI paths are resolved against the current working directory, not the JSON file's
directory. Material, stress, seed, and iteration overrides belong in JSON; there
are no corresponding CLI flags.

The smoke preset uses the default `N50R_CS_T50` condition with seed `42`,
`sigma_nom=[150]`, `iteration_count=1`, `n_symm=1`, and `max_active_elements=1`.
Its input root and cache root are `multiscale-fatigue-model/`; its output is
`outputs/smoke_seed42/`. It enables output cleanup. Directory arguments can
override these paths; `--config-file` is ignored when the preset is selected.

The convenience script `scripts/Invoke-ConditionResourcesRun.ps1` accepts:

| PowerShell parameter | Required / default | Meaning |
| --- | --- | --- |
| `-ConfigFile PATH` | Required | Config containing explicit `steel`, `specimen_type`, and `thickness_sign` values, used to form the model name. |
| `-OutputDir PATH` | `outputs/conditions/<model_name>` under the repository root | If `random_seed` is present and non-null, the default name ends with `_seed<seed>`. |
| `-CacheDir PATH` | `outputs/condition_cache` under the repository root | Cache root; the CLI appends the model name. |
| `-Python PATH` | Repository `.venv/Scripts/python.exe` if present; otherwise `py` | Python executable. Use the repository virtual environment for project work. |

The script fixes the input root to the repository's `resources/`, always passes
`--delete-existing-output`, and validates summary/detail CSVs after calculation.
It does not expose the diagnostic flag; use the CLI directly for diagnostics.
Explicit relative script paths are relative to the current working directory.

#### Simulation JSON: all supported keys

The file is a JSON object. Unknown keys are rejected, including directory,
cleanup, and diagnostic settings. Except for `weight_function_domain_policy`,
omitting a key or setting it to `null` leaves the default below in effect.
For normal resource runs, explicitly specify the three condition labels.

| Key | Expected value | Default | Meaning |
| --- | --- | --- | --- |
| `steel` | String | `"N50R"` | Material label; supported combinations are listed below. |
| `specimen_type` | String | `"CS"` | Specimen/loading geometry label. |
| `thickness_sign` | String | `"T50"` | Thickness label, not a thickness in mm. |
| `crystal` | `"BCC"` or `"FCC"` | `"BCC"` | Crystal structure used to resolve slip planes. |
| `r_ratio` | Number | `-1` | Stress ratio R. |
| `c_paris` | Number | `18` | CTSD crack-growth-law coefficient; retain the model's mm/cycle unit convention. |
| `n_paris` | Number | `1.8` | CTSD crack-growth-law exponent. |
| `delta_delta_th` | Number, mm | `0.000063` | Stage II CTSD-range threshold. |
| `sigma_nom` | Array of numbers, MPa | `[150, 160, 170, 180, 190]` | Nominal stresses, evaluated in array order. |
| `iteration_count` | Integer, at least 1 | `4` | Number of stochastic repetitions per stress. |
| `n_symm` | Positive integer | `4` | Number of symmetry positions evaluated per element. |
| `random_seed` | Integer or `null` | `null` | Seed both Python and NumPy generators; `null` leaves them unseeded. |
| `max_active_elements` | Integer, at least 1, or `null` | `null` | Verification limiter. Overrides the normal active-element fraction with `min(1, limit / total_elements)`; the loop uses the resulting rounded count, capped by available ranked elements. |
| `weight_function_domain_policy` | `"error"` or `"truncate_candidate"` | `"error"` | Stop on unsupported interpolation domains, or retain only the candidate's calculated portion; see below. `null` is rejected. |

These types describe intended inputs. The loader checks unknown keys and domain
policy; it does not provide complete type/range validation for every field.
`iteration_count` and `max_active_elements` are checked against the lower bound
during context preparation.

For a complete normal example, see
[`resources/configs/N50R_CS_T50.json`](resources/configs/N50R_CS_T50.json).
To make a reproducible lightweight run, copy a normal config and set, for example:

```json
{
  "steel": "N50R",
  "specimen_type": "CS",
  "thickness_sign": "T50",
  "random_seed": 42,
  "sigma_nom": [150],
  "iteration_count": 1,
  "n_symm": 1,
  "max_active_elements": 1
}
```

This reduced condition is for verification; it changes the sampling extent.

#### Condition labels and values derived in code

`<model_name>` is `<steel>_<specimen_type>_<thickness_sign>`. Only these ten
combinations are supported; the labels cannot be combined arbitrarily.

| `steel` | `specimen_type` | `thickness_sign` | Resolved thickness / width (mm) | Weight-function family |
| --- | --- | --- | --- | --- |
| `B`, `G`, or `N50R` | `Smooth` | `T16` | 1.35 / 5.0 | Smooth |
| `B`, `G`, or `N50R` | `R008` | `T24` | 1.9 / 5.0 | Three-point bending |
| `B`, `G`, or `N50R` | `R100` | `T24` | 1.9 / 5.0 | Three-point bending |
| `N50R` | `CS` | `T50` | 4.5 / 1.5 | Compact specimen |

Dimensions, active-zone extent and element size, normal active-element fraction,
Stage I/II evaluation points, weight-function family, and Abaqus nominal-stress
extraction mode come from `parameters.resolve_parameter_condition()`.
They are not independent JSON fields. Phase names (`Ferrite`, `Pearlite`),
closure/remote-stress model switches, grain-boundary treatment, and transition
constant are also defined in `parameters.py`. Thus the config JSON alone does
not contain every physical/model parameter.

#### Material and FEM resources

Each resolved input directory must contain the following resources for the
selected condition. Filenames, including spaces, matter. Material CSVs are read
by column position, not by header name.

| Filename | Format / units | Role |
| --- | --- | --- |
| `<model_name>.inp` | Abaqus input text | Mesh and elastic constants, including E and Poisson ratio, used to build the field cache. |
| `<model_name>.dat` | Abaqus output text in the layout expected by `abaqus.py` | FEM stress/strain fields and load information used to build the field cache. ZIP files are not read directly. |
| `<steel>_Ferrite grain size.csv` | No header; columns: size (mm), distribution fraction | Ferrite size distribution. |
| `<steel>_Ferrite grain aspect ratio.csv` | No header; columns: aspect-ratio value, distribution fraction | Ferrite shape distribution; the reader uses the square root of the first column. |
| `<steel>_Ferrite grain angle.csv` | No header; columns: angle (degrees), distribution fraction | Grain-angle distribution; converted to radians during microstructure generation. Required by the supported material-loading path. |
| `<steel>_Pearlite thickness_C=<value>.csv` | No header; columns: thickness (mm), distribution fraction | Pearlite thickness distribution. The decimal value in the filename supplies `CRate`; the code sets the phase-fraction proxy to `1.5 * CRate`. |
| `<steel>_Monotonic tensile test.csv` | Header, then first data row: yield strength (MPa), tensile strength (MPa), reduction in area (fraction) | Mechanical properties; reference stress is the mean of the two strengths. Example header: `YS,TS,RA`. |
| `<steel>_Friction strength.csv` | Header, then first data row: ferrite strength (MPa), pearlite strength (MPa) | Phase friction strengths. Example header: `f,p`. |
| `CombinedData_Ellipse_WF_CF.json` | Numerical tables | `ldh` plus `WFCsmooth`, `WFC3PBT`, `WFCCS` weight-function tables and `CFsmooth`, `CF3PBT`, `CFCS` remote-stress tables. The condition selects the family. |

Distribution second columns are bin fractions, not cumulative probabilities;
the reader forms cumulative sums and interpolators. Preserve the supplied row
order and fraction convention. For Pearlite input, keep one matching
`<steel>_Pearlite thickness*.csv`: the current reader uses the first matching
filename from directory enumeration and extracts the decimal fraction proxy
from matching filenames. Duplicate matching files make selection ambiguous.
There is no automatic unit conversion for material lengths or strengths.
See [`resources/README.md`](resources/README.md) for the directory manifest.

#### Cache inputs and reproducibility

The runner reuses `<steel>_<specimen_type>_FieldValues.pkl` if present; otherwise
it builds it from `.inp` and expanded `.dat` files. It also loads a valid
`<steel>_<specimen_type>_gData.pkl` or generates stochastic microstructure data.
These are generated inputs to later runs, separate from the measured resources.
Cache filenames omit thickness and seed; the explicit `--cache-dir` condition
subdirectory prevents sharing across thickness labels, but not across seeds or
resource revisions of the same condition.

Existing caches are not automatically invalidated when source resources change.
Use a separate cache root when regenerating data for changed inputs. A fixed seed
alone does not guarantee identical results between runs that generate and reuse
`gData.pkl`, because generation consumes random numbers. For comparisons, retain
the config, resource versions, and cache contents/generation state as well as the
seed. `--delete-existing-output` does not rebuild caches.

### Run examples and verification

Default simulation parameters follow `multiscale-fatigue-model/Multiscale_fatigue_model.org.py`: `sigma_nom` is `[150, 160, 170, 180, 190]`, `iteration_count` is `4`, and `n_symm` is `4`. These values are written explicitly in `verification/configs/original_defaults.json`; no random seed is set for the default run.

Simulation parameters such as material, stress, and iteration settings are written in the JSON config file. CLI options control execution settings such as input/output/cache directories and diagnostic output. Use seed-fixed configs such as `verification/configs/heavy_seed42.json` and `verification/configs/lightweight_seed42.json` only for reproducible comparison and lightweight verification.

Diagnostic output is disabled by default. For investigation, add `--write-diagnostics`:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m multiscale_fatigue_model_ijf_2026.cli run `
  --config-file resources\configs\N50R_CS_T50.json `
  --base-dir resources `
  --cache-dir outputs\condition_cache `
  --output-dir outputs\conditions\N50R_CS_T50 `
  --write-diagnostics
```

This writes detail-row correspondence tables (`*.rows.csv`), event records when
present (`*.events.csv`), and a failure record (`failure.csv`) if input preparation
or calculation fails, under `<output-dir>/diagnostics/`. Diagnostic notices also
appear on the console. This option preserves calculation results, checks,
exception behavior, ordinary progress messages, and summary/detail/status CSVs.
Omitting it leaves existing diagnostic files in place; `--delete-existing-output`
explicitly removes existing result CSVs and `diagnostics/*.csv` before running.

`weight_function_domain_policy` controls what happens when a crack candidate
reaches outside the supported weight-function or remote-stress interpolation
domain. The default `error` preserves the diagnostic stop used for comparison
and reproducibility checks. For report-oriented runs, `truncate_candidate`
keeps values calculated before the domain limit, does not extrapolate beyond
the table, and records the domain-limit status in an additional status CSV only
when such an incomplete candidate occurs.

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
Input files larger than GitHub's 100 MB file size limit are stored as `.zip`
files in this repository.
If a run must rebuild the Abaqus field cache from resources, provide the expanded
`.dat` file in the condition directory. If only the zipped `.dat` file is present,
extract it before a fresh run:

```powershell
Expand-Archive resources\N50R_CS_T50\N50R_CS_T50.dat.zip -DestinationPath resources\N50R_CS_T50
```

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

```powershell
python -X utf8 -m multiscale_fatigue_model_ijf_2026.cli run --preset smoke
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

```powershell
python -m pip install -e .
```
