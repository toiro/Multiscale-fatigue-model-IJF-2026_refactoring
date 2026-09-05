param(
    [Parameter(Mandatory = $true)]
    [string]$ConfigFile,
    [Parameter(Mandatory = $true)]
    [int]$AreaElementRank,
    [int]$LoadIndex = 0,
    [int]$SymmetryIndex = 1,
    [string]$BaseDir = "",
    [string]$CacheDir = "",
    [string]$Python = ""
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

if ([string]::IsNullOrWhiteSpace($Python)) {
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $Python = if (Test-Path $venvPython) { $venvPython } else { "py" }
}

if ([string]::IsNullOrWhiteSpace($BaseDir)) {
    $BaseDir = Join-Path $RepoRoot "resources"
}

if ([string]::IsNullOrWhiteSpace($CacheDir)) {
    $CacheDir = Join-Path $RepoRoot "outputs\condition_cache"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

& $Python -m verification.diagnose_element_life `
    --config-file (Resolve-Path $ConfigFile).Path `
    --base-dir $BaseDir `
    --cache-dir $CacheDir `
    --load-index $LoadIndex `
    --area-element-rank $AreaElementRank `
    --symmetry-index $SymmetryIndex

if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
