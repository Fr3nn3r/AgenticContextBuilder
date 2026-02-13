<#
.SYNOPSIS
    Selective sync of NSA workspace to Azure File Share.

.DESCRIPTION
    Syncs only the latest claim_run and latest extraction run per claim,
    plus all docs, ground_truth, context, config, registry, and global runs.
    Skips logs/, eval/, version_bundles/, .pending/, .input/, and old runs.
    Dramatically reduces transfer size compared to full sync.

    Uses azcopy sync with --include-regex to filter which paths get synced.
    Old runs on Azure (from previous full syncs) are not deleted -- the app
    reads newest-first so they are harmless, just unused.

    Requires: azcopy installed, az CLI logged in.

.PARAMETER DryRun
    Preview what would be transferred without actually syncing.

.PARAMETER FullSync
    Fall back to syncing everything (like sync-workspace.ps1), excluding
    logs/, eval/, version_bundles/, .pending/, .input/.

.EXAMPLE
    .\scripts\sync-workspace-selective.ps1 -DryRun     # Preview selective sync
    .\scripts\sync-workspace-selective.ps1              # Run selective sync
    .\scripts\sync-workspace-selective.ps1 -FullSync    # Full sync fallback
#>

param(
    [switch]$DryRun,
    [switch]$FullSync
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$localPath = Join-Path $repoRoot "workspaces\nsa"
$storageAccount = "claimsevidenceprod"
$shareName = "workspace"
$baseUrl = "https://$storageAccount.file.core.windows.net/$shareName"

# ---------- Prerequisites ----------

if (-not (Get-Command azcopy -ErrorAction SilentlyContinue)) {
    Write-Error "azcopy not found. Install with: winget install Microsoft.Azure.AZCopy.10"
    exit 1
}

if (-not (Test-Path $localPath)) {
    Write-Error "Local workspace path not found: $localPath"
    exit 1
}

# ---------- SAS token ----------

Write-Host "Generating SAS token..." -ForegroundColor DarkGray
$azCmd = Get-Command az -ErrorAction SilentlyContinue
if (-not $azCmd) {
    $azCmd = Get-Command "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" -ErrorAction SilentlyContinue
}
if (-not $azCmd) {
    Write-Error "Azure CLI (az) not found. Install with: winget install Microsoft.AzureCLI"
    exit 1
}

$accountKey = & $azCmd storage account keys list `
    --account-name $storageAccount --query "[0].value" -o tsv 2>$null
if (-not $accountKey) {
    Write-Error "Failed to get storage account key. Run 'az login' first."
    exit 1
}

$expiry = (Get-Date).AddDays(1).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$sas = & $azCmd storage share generate-sas `
    --name $shareName --account-name $storageAccount `
    --account-key $accountKey --permissions rwdl --expiry $expiry -o tsv 2>$null
if (-not $sas) {
    Write-Error "Failed to generate SAS token."
    exit 1
}

$remotePath = "${baseUrl}?${sas}"

# ---------- Full sync fallback ----------

if ($FullSync) {
    Write-Host "FULL SYNC mode (syncs everything except logs, eval, version_bundles, staging)" -ForegroundColor Yellow
    Write-Host "  From: $localPath"
    Write-Host "  To:   $baseUrl"

    $syncArgs = @(
        "sync", $localPath, $remotePath, "--recursive",
        "--delete-destination=true",
        "--exclude-path", "logs;eval;version_bundles;.pending;.input"
    )

    if ($DryRun) {
        $syncArgs += "--dry-run"
        Write-Host "  Mode: DRY RUN" -ForegroundColor Yellow
    }

    Write-Host ""
    & azcopy @syncArgs

    if ($LASTEXITCODE -eq 0) {
        Write-Host "`nFull sync completed successfully." -ForegroundColor Green
    } else {
        Write-Error "Sync failed with exit code $LASTEXITCODE."
    }
    exit $LASTEXITCODE
}

# ---------- Selective sync: build include-regex patterns ----------

Write-Host "SELECTIVE SYNC: latest claim_run + latest extraction run per claim" -ForegroundColor Cyan
Write-Host "  From: $localPath"
Write-Host "  To:   $baseUrl"

$claimsDir = Join-Path $localPath "claims"
if (-not (Test-Path $claimsDir)) {
    Write-Error "Claims directory not found: $claimsDir"
    exit 1
}

$claimDirs = Get-ChildItem -Path $claimsDir -Directory | Sort-Object Name
$regexPatterns = [System.Collections.Generic.List[string]]::new()

$totalClaimRuns = 0
$skippedClaimRuns = 0
$totalExtRuns = 0
$skippedExtRuns = 0

foreach ($claim in $claimDirs) {
    $claimId = $claim.Name
    $rel = "claims/$claimId"

    # docs/ -- ALL (source PDFs, text, meta, images)
    $regexPatterns.Add("^$rel/docs")

    # ground_truth/ -- ALL (if exists)
    if (Test-Path (Join-Path $claim.FullName "ground_truth")) {
        $regexPatterns.Add("^$rel/ground_truth")
    }

    # context/ -- ALL (legacy fallback, if exists)
    if (Test-Path (Join-Path $claim.FullName "context")) {
        $regexPatterns.Add("^$rel/context")
    }

    # claim_runs/ -- LATEST only (sorted descending by name; names encode timestamps)
    $crPath = Join-Path $claim.FullName "claim_runs"
    if (Test-Path $crPath) {
        $crEntries = Get-ChildItem -Path $crPath -Directory | Sort-Object Name -Descending
        $totalClaimRuns += $crEntries.Count
        if ($crEntries.Count -gt 0) {
            $regexPatterns.Add("^$rel/claim_runs/$($crEntries[0].Name)")
            $skippedClaimRuns += ($crEntries.Count - 1)
        }
    }

    # runs/ (extraction runs) -- LATEST only
    $erPath = Join-Path $claim.FullName "runs"
    if (Test-Path $erPath) {
        $erEntries = Get-ChildItem -Path $erPath -Directory | Sort-Object Name -Descending
        $totalExtRuns += $erEntries.Count
        if ($erEntries.Count -gt 0) {
            $regexPatterns.Add("^$rel/runs/$($erEntries[0].Name)")
            $skippedExtRuns += ($erEntries.Count - 1)
        }
    }
}

# Top-level directories -- ALL
$regexPatterns.Add("^config")
$regexPatterns.Add("^registry")
$regexPatterns.Add("^runs")
$regexPatterns.Add("^\.auth")

$regexStr = $regexPatterns -join ";"

# ---------- Summary ----------

Write-Host ""
Write-Host "  Claims:            $($claimDirs.Count)" -ForegroundColor White
Write-Host "  Claim runs:        $totalClaimRuns total, $skippedClaimRuns skipped (keeping 1 latest per claim)" -ForegroundColor White
Write-Host "  Extraction runs:   $totalExtRuns total, $skippedExtRuns skipped (keeping 1 latest per claim)" -ForegroundColor White
Write-Host "  Regex patterns:    $($regexPatterns.Count) entries ($([math]::Round($regexStr.Length / 1024, 1)) KB)" -ForegroundColor White
Write-Host "  Skipping:          logs/, eval/, version_bundles/, .pending/, .input/, claim_runs/ (top-level), old runs" -ForegroundColor DarkGray
Write-Host ""

# ---------- azcopy sync with include-regex ----------

$syncArgs = @(
    "sync", $localPath, $remotePath, "--recursive",
    "--delete-destination=true",
    "--include-regex", $regexStr
)

if ($DryRun) {
    $syncArgs += "--dry-run"
    Write-Host "  Mode: DRY RUN (no files transferred)" -ForegroundColor Yellow
    Write-Host ""
}

& azcopy @syncArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Selective sync completed successfully." -ForegroundColor Green
    Write-Host "  Synced $($claimDirs.Count) claims (latest runs only) + top-level dirs" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Error "Sync failed with exit code $LASTEXITCODE."
}
