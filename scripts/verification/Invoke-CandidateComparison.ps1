param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$ConfigFile = "",
    [string]$BaselineDir = "",
    [string]$CandidateDir = "",
    [double]$Rtol = 0.0,
    [double]$Atol = 0.0
)

$ErrorActionPreference = "Stop"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if ([string]::IsNullOrWhiteSpace($ConfigFile)) {
    $ConfigFile = Join-Path $RepoRoot "verification\configs\lightweight_seed42.json"
}
$simulationConfig = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
$Seed = [int]$simulationConfig.random_seed

if ([string]::IsNullOrWhiteSpace($BaselineDir)) {
    $BaselineDir = Join-Path $RepoRoot "outputs\baseline_seed$Seed"
}
if ([string]::IsNullOrWhiteSpace($CandidateDir)) {
    $CandidateDir = Join-Path $RepoRoot "outputs\candidate_reuse_seed$Seed"
}

if (-not (Test-Path $BaselineDir)) {
    throw "BaselineDir does not exist: $BaselineDir. Run scripts\verification\Invoke-BaselineComparison.ps1 once to create it."
}
if (-not (Get-ChildItem -Path $BaselineDir -Filter "*.csv" -File -ErrorAction SilentlyContinue)) {
    throw "BaselineDir has no CSV files: $BaselineDir. Run scripts\verification\Invoke-BaselineComparison.ps1 once to create it."
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

Write-Host "Running candidate comparison with reused baseline CSV."
Write-Host "Baseline: $BaselineDir"
Write-Host "Candidate: $CandidateDir"

New-Item -ItemType Directory -Force $CandidateDir | Out-Null
foreach ($csv in Get-ChildItem -Path $CandidateDir -Filter "*.csv" -File -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $csv.FullName -Force
}

$candidateStart = Get-Date
& $python -m multiscale_fatigue_model_ijf_2026.cli run `
    --config-file $ConfigFile `
    --base-dir (Join-Path $RepoRoot "multiscale-fatigue-model") `
    --output-dir $CandidateDir `
    --delete-existing-output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$candidateElapsed = (Get-Date) - $candidateStart
Write-Host ("Candidate elapsed: {0}" -f $candidateElapsed)

& $python -m verification.compare_csv_outputs $BaselineDir $CandidateDir --rtol $Rtol --atol $Atol
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Candidate comparison passed."
