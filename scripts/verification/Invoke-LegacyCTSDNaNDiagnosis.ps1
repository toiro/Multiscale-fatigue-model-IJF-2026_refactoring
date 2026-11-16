param(
    [string]$RepoRoot = (Resolve-Path "$PSScriptRoot\..\..").Path,
    [int]$Seed = 42,
    [int]$Iterations = 1,
    [int]$Symmetries = 1,
    [int]$MaxElements = 1,
    [string]$OutputDir = "",
    [switch]$NoObserve,
    [switch]$ContinueAfterCapture,
    [string]$ReplayFile = "",
    [string]$AnalysisFile = ""
)

$ErrorActionPreference = "Stop"
$python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { throw "Project .venv Python is required." }
$module = Join-Path $RepoRoot "verification\legacy_ctsd_nan.py"
if ($ReplayFile) {
    if (-not $AnalysisFile) {
        $analysisName = [System.IO.Path]::GetFileNameWithoutExtension($ReplayFile) + ".analysis.json"
        $AnalysisFile = Join-Path $RepoRoot "outputs\troubleshooting\N50R_CS_T50_legacy_ctsd_nan\replays\$analysisName"
    }
    & $python $module --repo-root $RepoRoot --replay $ReplayFile --analysis-file $AnalysisFile
    if ($LASTEXITCODE -ne 0) { throw "Legacy replay failed ($LASTEXITCODE)." }
    return
}
if (-not $OutputDir) {
    $runName = "seed${Seed}_" + (Get-Date -Format "yyyyMMdd_HHmmss_fff")
    $OutputDir = Join-Path $RepoRoot "outputs\troubleshooting\N50R_CS_T50_legacy_ctsd_nan\$runName"
}
if (Test-Path -LiteralPath $OutputDir) { throw "Output directory already exists: $OutputDir" }
$logDir = Split-Path -Parent $OutputDir
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$arguments = @($module, "--repo-root", $RepoRoot, "--output-dir", $OutputDir,
    "--seed", $Seed, "--iterations", $Iterations, "--symmetries", $Symmetries, "--max-elements", $MaxElements)
if ($NoObserve) { $arguments += "--no-observe" }
if ($ContinueAfterCapture) { $arguments += "--continue-after-capture" }
& $python -u @arguments 2>&1 | Tee-Object -FilePath "$OutputDir.log"
if ($LASTEXITCODE -ne 0) { throw "Legacy diagnosis failed ($LASTEXITCODE). See $OutputDir.log" }
