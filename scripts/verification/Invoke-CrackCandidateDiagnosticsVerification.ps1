param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$BaselineDir = "",
    [string]$CandidateDir = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

if ([string]::IsNullOrWhiteSpace($BaselineDir) -ne [string]::IsNullOrWhiteSpace($CandidateDir)) {
    throw "BaselineDir and CandidateDir must be specified together."
}

& $python -m verification.check_crack_candidate_diagnostics
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not [string]::IsNullOrWhiteSpace($BaselineDir)) {
    # Compare recorded results without repeating the fatigue calculation.
    & $python -m verification.compare_csv_outputs $BaselineDir $CandidateDir --rtol 0 --atol 0
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Crack candidate diagnostics verification passed."
