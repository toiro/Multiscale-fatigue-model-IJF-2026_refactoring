param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [string]$ReferenceCachePath = "",
    [string]$CandidateCachePath = "",
    [string]$CacheFileName = "N50R_CS_FieldValues.pkl",
    [ValidateSet("SHA1", "SHA256", "SHA384", "SHA512", "MD5")]
    [string]$Algorithm = "SHA256"
)

$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"

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
if (-not (Test-Path $ReferenceCachePath)) {
    throw "Reference cache does not exist: $ReferenceCachePath"
}
if (-not (Test-Path $CandidateCachePath)) {
    throw "Candidate cache does not exist: $CandidateCachePath"
}

$referenceItem = Get-Item -LiteralPath $ReferenceCachePath
$candidateItem = Get-Item -LiteralPath $CandidateCachePath
$referenceHash = Get-FileHash -LiteralPath $ReferenceCachePath -Algorithm $Algorithm
$candidateHash = Get-FileHash -LiteralPath $CandidateCachePath -Algorithm $Algorithm

Write-Host "Abaqus cache hash comparison"
Write-Host "Algorithm: $Algorithm"
Write-Host "Reference: $($referenceItem.FullName)"
Write-Host "  Length: $($referenceItem.Length)"
Write-Host "  Hash:   $($referenceHash.Hash)"
Write-Host "Candidate: $($candidateItem.FullName)"
Write-Host "  Length: $($candidateItem.Length)"
Write-Host "  Hash:   $($candidateHash.Hash)"

if ($referenceItem.Length -ne $candidateItem.Length) {
    Write-Host "Length comparison failed."
    exit 1
}

if ($referenceHash.Hash -ne $candidateHash.Hash) {
    Write-Host "Hash comparison failed."
    exit 1
}

Write-Host "Abaqus cache hash comparison passed."
