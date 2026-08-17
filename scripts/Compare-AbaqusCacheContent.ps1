param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path,
    [string]$ReferenceCachePath = "",
    [string]$CandidateCachePath = "",
    [string]$CacheFileName = "N50R_CS_FieldValues.pkl",
    [double]$Rtol = 0.0,
    [double]$Atol = 0.0
)

$ErrorActionPreference = "Stop"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if ([string]::IsNullOrWhiteSpace($ReferenceCachePath)) {
    $ReferenceCachePath = Join-Path $RepoRoot "multiscale-fatigue-model\$CacheFileName"
}

if ([string]::IsNullOrWhiteSpace($CandidateCachePath)) {
    $candidateDirs = Get-ChildItem -Path (Join-Path $RepoRoot "outputs") `
        -Directory `
        -Filter "abaqus_cache_regen_*" `
        -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending

    foreach ($dir in $candidateDirs) {
        $candidate = Join-Path $dir.FullName $CacheFileName
        if (Test-Path $candidate) {
            $CandidateCachePath = $candidate
            break
        }
    }
}

if ([string]::IsNullOrWhiteSpace($CandidateCachePath)) {
    throw "CandidateCachePath was not specified and no regenerated cache was found under outputs\abaqus_cache_regen_*."
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

& $python -m verification.compare_abaqus_cache `
    $ReferenceCachePath `
    $CandidateCachePath `
    --rtol $Rtol `
    --atol $Atol
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
