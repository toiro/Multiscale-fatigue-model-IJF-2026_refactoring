param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$ConfigFile = "",
    [double]$Rtol = 0.0,
    [double]$Atol = 0.0
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if ([string]::IsNullOrWhiteSpace($ConfigFile)) {
    $ConfigFile = Join-Path $RepoRoot "verification\configs\lightweight_seed42.json"
}
$simulationConfig = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
$Seed = [int]$simulationConfig.random_seed

$baselineDir = Join-Path $RepoRoot "outputs\baseline_seed$Seed"
$candidateDir = Join-Path $RepoRoot "outputs\refactored_seed$Seed"
$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

Write-Host "Running deterministic baseline comparison."
Write-Host "Baseline: original script with env overrides. Candidate: src CLI."

$originalDir = Join-Path $RepoRoot "multiscale-fatigue-model"
New-Item -ItemType Directory -Force $baselineDir, $candidateDir | Out-Null
foreach ($csv in Get-ChildItem -Path $baselineDir -Filter "*.csv" -File -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $csv.FullName -Force
}
foreach ($csv in Get-ChildItem -Path $candidateDir -Filter "*.csv" -File -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $csv.FullName -Force
}

$env:MFM_RANDOM_SEED = "$Seed"
$env:MFM_OUTPUT_DIR = $baselineDir
$env:MFM_SIGMA_NOM = ($simulationConfig.sigma_nom -join ",")
$iterationIndices = 0..([int]$simulationConfig.iteration_count - 1)
$env:MFM_ITERATIONS = ($iterationIndices -join ",")
$env:MFM_N_SYMM = "$($simulationConfig.n_symm)"
$env:MFM_MAX_ACTIVE_ELEMENTS = "$($simulationConfig.max_active_elements)"
try {
    $originalStart = Get-Date
    Push-Location $originalDir
    & $python ".\Multiscale_fatigue_model.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $originalElapsed = (Get-Date) - $originalStart
    Write-Host ("Original elapsed: {0}" -f $originalElapsed)
}
finally {
    Pop-Location
    Remove-Item Env:\MFM_RANDOM_SEED -ErrorAction SilentlyContinue
    Remove-Item Env:\MFM_OUTPUT_DIR -ErrorAction SilentlyContinue
    Remove-Item Env:\MFM_SIGMA_NOM -ErrorAction SilentlyContinue
    Remove-Item Env:\MFM_ITERATIONS -ErrorAction SilentlyContinue
    Remove-Item Env:\MFM_N_SYMM -ErrorAction SilentlyContinue
    Remove-Item Env:\MFM_MAX_ACTIVE_ELEMENTS -ErrorAction SilentlyContinue
}

$candidateStart = Get-Date
& $python -m multiscale_fatigue_model_ijf_2026.cli run `
    --config-file $ConfigFile `
    --base-dir (Join-Path $RepoRoot "multiscale-fatigue-model") `
    --output-dir $candidateDir `
    --delete-existing-output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$candidateElapsed = (Get-Date) - $candidateStart
Write-Host ("Candidate elapsed: {0}" -f $candidateElapsed)

& $python -m verification.compare_csv_outputs $baselineDir $candidateDir --rtol $Rtol --atol $Atol
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Baseline comparison passed."
