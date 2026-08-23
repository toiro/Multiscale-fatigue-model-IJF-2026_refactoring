param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path
)

$ErrorActionPreference = "Stop"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m ruff check `
    (Join-Path $RepoRoot "src") `
    (Join-Path $RepoRoot "verification")
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Static analysis passed."
