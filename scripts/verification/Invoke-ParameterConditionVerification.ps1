param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

& $python -m verification.check_parameter_conditions
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m verification.check_resources (Join-Path $RepoRoot "resources")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m verification.check_context_boundaries $RepoRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Parameter condition verification passed."
