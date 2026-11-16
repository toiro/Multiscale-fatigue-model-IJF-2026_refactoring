param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
& $python -m verification.audit_candidate_life `
    --config-file (Join-Path $RepoRoot "resources\configs\B_Smooth_T16_report.json") `
    --base-dir (Join-Path $RepoRoot "resources") `
    --cache-dir (Join-Path $RepoRoot "outputs\condition_cache") `
    --report (Join-Path $RepoRoot "outputs\troubleshooting\B_Smooth_T16_candidate_life_seed42.csv") `
    --reference (Join-Path $RepoRoot "verification\fixtures\B_Smooth_T16_ctsd_nan_seed42.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
