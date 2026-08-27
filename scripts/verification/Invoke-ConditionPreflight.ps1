param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

& (Join-Path $PSScriptRoot "Invoke-ParameterConditionVerification.ps1") `
    -RepoRoot $RepoRoot
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Condition preflight passed."
