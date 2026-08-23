# Resources

Input files are grouped by simulation condition:

```text
resources/
  sample_simulation.json
  configs/
    B_Smooth_T16.json
    ...
  B_Smooth_T16/
  B_R008_T24/
  B_R100_T24/
  G_Smooth_T16/
  G_R008_T24/
  G_R100_T24/
  N50R_Smooth_T16/
  N50R_R008_T24/
  N50R_R100_T24/
  N50R_CS_T50/
    N50R_CS_T50.inp
    N50R_CS_T50.dat
    N50R_*.csv
    CombinedData_Ellipse_WF_CF.json
```

Directory names must match the model name assembled from the JSON config:
`<steel>_<specimen_type>_<thickness_sign>`.

Normal calculation configs for these directories live in `resources/configs/`.
They use the original default calculation
settings (`sigma_nom=[150,160,170,180,190]`, `iteration_count=4`, `n_symm=4`)
and do not set `random_seed` or `max_active_elements`.

Run a normal resource condition with:

```powershell
scripts\Invoke-ConditionResourcesRun.ps1 -ConfigFile resources\configs\N50R_CS_T50.json
```

Lightweight condition configs under `verification/configs/conditions/` are only
for development verification.

Supported condition directories:

- `B_Smooth_T16/`, `G_Smooth_T16/`, `N50R_Smooth_T16/`
- `B_R008_T24/`, `G_R008_T24/`, `N50R_R008_T24/`
- `B_R100_T24/`, `G_R100_T24/`, `N50R_R100_T24/`
- `N50R_CS_T50/`

Each condition directory should contain only normal run inputs:

- `<steel>_<specimen_type>_<thickness_sign>.inp`
- `<steel>_<specimen_type>_<thickness_sign>.dat` or an expanded `.dat` restored
  from the stored `.dat.zip`
- `<steel>_Ferrite grain size.csv`
- `<steel>_Ferrite grain aspect ratio.csv`
- `<steel>_Ferrite grain angle.csv`
- `<steel>_Pearlite thickness_*.csv`
- `<steel>_Monotonic tensile test.csv`
- `<steel>_Friction strength.csv`
- `CombinedData_Ellipse_WF_CF.json`

Files outside this manifest are not used by normal runs. Keep duplicate scratch
or copied CSV files out of condition directories.

`resources/sample_simulation.json` remains a representative `N50R_CS_T50` sample.
Use `resources/configs/` as the normal multi-condition entry point.

Generated cache files such as `*_FieldValues.pkl` and `*_gData.pkl` should stay
outside committed input resources unless a verification task explicitly needs a
cached fixture.

If only `*.dat.zip` is stored, expand it before running without a precomputed
field cache.

The runner reads only from the resolved condition directory. Put every file
needed for a condition, including `CombinedData_Ellipse_WF_CF.json`, inside that
condition directory.
