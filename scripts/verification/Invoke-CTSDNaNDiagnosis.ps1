param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [int]$Seed = 42,
    [switch]$ReplayOnly
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$report = Join-Path $RepoRoot "outputs\troubleshooting\B_Smooth_T16_ctsd_nan_seed$Seed.json"
if (-not $ReplayOnly) {
    & $python -m verification.diagnose_ctsd_nan `
        --config-file (Join-Path $RepoRoot "resources\configs\B_Smooth_T16_report.json") `
        --base-dir (Join-Path $RepoRoot "resources") `
        --cache-dir (Join-Path $RepoRoot "outputs\condition_cache") `
        --report $report `
        --seed $Seed
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
elseif (-not (Test-Path -LiteralPath $report) -and $Seed -eq 42) {
    $report = Join-Path $RepoRoot "verification\fixtures\B_Smooth_T16_ctsd_nan_seed42.json"
    Write-Host "Replaying the recorded seed42 input fixture: $report"
}

& $python -m verification.replay_ctsd_nan $report --repo-root $RepoRoot `
    --analysis-file (Join-Path $RepoRoot "outputs\troubleshooting\B_Smooth_T16_ctsd_nan_seed$Seed.analysis.json")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
