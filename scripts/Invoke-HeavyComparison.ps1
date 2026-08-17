param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$ConfigFile = "",
    [string]$LegacyDir = "",
    [string]$RefactoredDir = "",
    [double]$Rtol = 0.0,
    [double]$Atol = 0.0
)

$ErrorActionPreference = "Stop"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if ([string]::IsNullOrWhiteSpace($ConfigFile)) {
    $ConfigFile = Join-Path $RepoRoot "verification\configs\heavy_seed42.json"
}

$simulationConfig = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
$Seed = [int]$simulationConfig.random_seed

if ([string]::IsNullOrWhiteSpace($LegacyDir)) {
    $LegacyDir = Join-Path $RepoRoot "outputs\heavy_conditions_legacy_seed$Seed"
}
if ([string]::IsNullOrWhiteSpace($RefactoredDir)) {
    $RefactoredDir = Join-Path $RepoRoot "outputs\heavy_conditions_refactored_seed$Seed"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

Write-Host "Running heavy-condition comparison."
Write-Host "Condition source: verification\configs\heavy_seed42.json"
Write-Host "Legacy script: multiscale-fatigue-model\Multiscale_fatigue_model.py"
Write-Host "Refactored script: src CLI"
Write-Host "Config: $ConfigFile"
Write-Host "Legacy output: $LegacyDir"
Write-Host "Refactored output: $RefactoredDir"

New-Item -ItemType Directory -Force $LegacyDir, $RefactoredDir | Out-Null
foreach ($csv in Get-ChildItem -Path $LegacyDir -Filter "*.csv" -File -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $csv.FullName -Force
}
foreach ($csv in Get-ChildItem -Path $RefactoredDir -Filter "*.csv" -File -ErrorAction SilentlyContinue) {
    Remove-Item -LiteralPath $csv.FullName -Force
}

$env:MFM_RANDOM_SEED = "$Seed"
$env:MFM_OUTPUT_DIR = $LegacyDir
$env:MFM_SIGMA_NOM = ($simulationConfig.sigma_nom -join ",")
$iterationIndices = 0..([int]$simulationConfig.iteration_count - 1)
$env:MFM_ITERATIONS = ($iterationIndices -join ",")
$env:MFM_N_SYMM = "$($simulationConfig.n_symm)"
if ($simulationConfig.PSObject.Properties.Name -contains "max_active_elements") {
    $env:MFM_MAX_ACTIVE_ELEMENTS = "$($simulationConfig.max_active_elements)"
}

try {
    $legacyStart = Get-Date
    Push-Location (Join-Path $RepoRoot "multiscale-fatigue-model")
    & $python ".\Multiscale_fatigue_model.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    $legacyElapsed = (Get-Date) - $legacyStart
    Write-Host ("Legacy elapsed: {0}" -f $legacyElapsed)
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

$refactoredStart = Get-Date
& $python -m multiscale_fatigue_model_ijf_2026.cli run `
    --config-file $ConfigFile `
    --base-dir (Join-Path $RepoRoot "multiscale-fatigue-model") `
    --output-dir $RefactoredDir `
    --delete-existing-output
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$refactoredElapsed = (Get-Date) - $refactoredStart
Write-Host ("Refactored elapsed: {0}" -f $refactoredElapsed)

& $python -m verification.compare_csv_outputs $LegacyDir $RefactoredDir --rtol $Rtol --atol $Atol
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "Heavy comparison passed."
