param(
    [string]$ConfigFile = "",
    [string]$OutputDir = "",
    [string]$CacheDir = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $Python = if (Test-Path $venvPython) { $venvPython } else { "py" }
}

if ([string]::IsNullOrWhiteSpace($ConfigFile)) {
    $ConfigFile = Join-Path $RepoRoot "resources\sample_simulation.json"
}
$simulationConfig = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    if ($null -ne $simulationConfig.random_seed) {
        $OutputDir = Join-Path $RepoRoot "outputs\sample_resources_seed$($simulationConfig.random_seed)"
    }
    else {
        $OutputDir = Join-Path $RepoRoot "outputs\sample_resources"
    }
}

if ([string]::IsNullOrWhiteSpace($CacheDir)) {
    $CacheDir = Join-Path $RepoRoot "multiscale-fatigue-model"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

& $Python -m multiscale_fatigue_model_ijf_2026.cli run `
    --config-file $ConfigFile `
    --base-dir (Join-Path $RepoRoot "resources") `
    --cache-dir $CacheDir `
    --output-dir $OutputDir `
    --delete-existing-output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $Python -m verification.validate_output_csv $OutputDir --require-summary --require-detail
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Sample resources run passed."
