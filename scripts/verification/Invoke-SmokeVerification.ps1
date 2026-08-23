param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [int]$Seed = 42
)

$ErrorActionPreference = "Stop"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

& $python -m multiscale_fatigue_model_ijf_2026.cli --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m multiscale_fatigue_model_ijf_2026.cli run --help | Out-Null
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -c "from pathlib import Path; from verification.smoke import run_import_smoke; run_import_smoke(Path(r'$RepoRoot'))"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -c "from pathlib import Path; from verification.smoke import run_mock_calculation_smoke; run_mock_calculation_smoke(Path(r'$RepoRoot'))"
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m verification.validate_output_csv (Join-Path $RepoRoot "tests\fixtures\csv") --require-summary --require-detail
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Smoke verification passed for import/config/CSV fixtures."
