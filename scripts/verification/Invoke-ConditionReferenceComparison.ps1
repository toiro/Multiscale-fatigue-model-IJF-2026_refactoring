param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$ReferenceRoot = "",
    [string]$CandidateRoot = "",
    [double]$Rtol = 0.0,
    [double]$Atol = 0.0
)

$ErrorActionPreference = "Stop"

$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

if ([string]::IsNullOrWhiteSpace($ReferenceRoot)) {
    $ReferenceRoot = Join-Path $RepoRoot "outputs\condition_reference"
}
if ([string]::IsNullOrWhiteSpace($CandidateRoot)) {
    $CandidateRoot = Join-Path $RepoRoot "outputs\conditions"
}

if (-not (Test-Path $ReferenceRoot)) {
    throw "ReferenceRoot does not exist: $ReferenceRoot"
}
if (-not (Test-Path $CandidateRoot)) {
    throw "CandidateRoot does not exist: $CandidateRoot"
}

$env:PYTHONPATH = (Join-Path $RepoRoot "src") + [System.IO.Path]::PathSeparator + $RepoRoot

$referenceDirs = Get-ChildItem -Path $ReferenceRoot -Directory | Sort-Object Name
if (-not $referenceDirs) {
    throw "ReferenceRoot has no condition reference directories: $ReferenceRoot"
}

foreach ($referenceDir in $referenceDirs) {
    $candidateDir = Join-Path $CandidateRoot $referenceDir.Name
    if (-not (Test-Path $candidateDir)) {
        throw "Candidate condition output does not exist: $candidateDir"
    }

    Write-Host "Comparing condition reference: $($referenceDir.Name)"
    & $python -m verification.compare_csv_outputs `
        $referenceDir.FullName `
        $candidateDir `
        --rtol $Rtol `
        --atol $Atol
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Write-Host "Condition reference comparison passed."
