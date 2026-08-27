param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigFile,
    [string]$OutputDir = "",
    [string]$CacheDir = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $Python = if (Test-Path $venvPython) { $venvPython } else { "py" }
}

$ConfigFile = (Resolve-Path $ConfigFile).Path
$simulationConfig = Get-Content -LiteralPath $ConfigFile -Raw | ConvertFrom-Json
$modelName = "{0}_{1}_{2}" -f `
    $simulationConfig.steel, `
    $simulationConfig.specimen_type, `
    $simulationConfig.thickness_sign

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    if ($null -ne $simulationConfig.random_seed) {
        $OutputDir = Join-Path $RepoRoot "outputs\conditions\${modelName}_seed$($simulationConfig.random_seed)"
    }
    else {
        $OutputDir = Join-Path $RepoRoot "outputs\conditions\$modelName"
    }
}

if ([string]::IsNullOrWhiteSpace($CacheDir)) {
    $CacheDir = Join-Path $RepoRoot "outputs\condition_cache"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    & $Command
    $succeeded = $?
    $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    if (-not $succeeded -or $exitCode -ne 0) {
        exit $exitCode
    }
}

Invoke-NativeCommand {
    & $Python -m multiscale_fatigue_model_ijf_2026.cli run `
        --config-file $ConfigFile `
        --base-dir (Join-Path $RepoRoot "resources") `
        --cache-dir $CacheDir `
        --output-dir $OutputDir `
        --delete-existing-output
}

Invoke-NativeCommand {
    & $Python -m verification.validate_output_csv $OutputDir --require-summary --require-detail
}

Write-Host "Condition resources run passed: $modelName"
