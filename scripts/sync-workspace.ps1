<#
.SYNOPSIS
    Sync NSA workspace between local and Azure File Share.

.DESCRIPTION
    Uses azcopy to sync workspaces/nsa/ with the claimsevidenceprod Azure Files share.
    Authenticates via a SAS token generated from the storage account key (requires az CLI).
    Requires: azcopy installed, az CLI logged in.

.PARAMETER Direction
    "up" (local -> Azure, default) or "down" (Azure -> local).

.PARAMETER DryRun
    Preview what would be transferred without actually syncing.

.PARAMETER IncludeLogs
    Include the logs/ directory (709 MB). Excluded by default.

.EXAMPLE
    .\scripts\sync-workspace.ps1                       # Upload local -> Azure
    .\scripts\sync-workspace.ps1 -Direction down        # Download Azure -> local
    .\scripts\sync-workspace.ps1 -DryRun                # Preview upload
    .\scripts\sync-workspace.ps1 -IncludeLogs           # Include logs dir
#>

param(
    [ValidateSet("up", "down")]
    [string]$Direction = "up",
    [switch]$DryRun,
    [switch]$IncludeLogs
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$localPath = Join-Path $repoRoot "workspaces\nsa"
$storageAccount = "claimsevidenceprod"
$shareName = "workspace"
$baseUrl = "https://$storageAccount.file.core.windows.net/$shareName"

# Check azcopy is available
if (-not (Get-Command azcopy -ErrorAction SilentlyContinue)) {
    Write-Error "azcopy not found. Install with: winget install Microsoft.Azure.AZCopy.10"
    exit 1
}

# Check local path exists
if (-not (Test-Path $localPath)) {
    Write-Error "Local workspace path not found: $localPath"
    exit 1
}

# Generate SAS token using storage account key
Write-Host "Generating SAS token..." -ForegroundColor DarkGray
$azCmd = Get-Command az -ErrorAction SilentlyContinue
if (-not $azCmd) {
    $azCmd = Get-Command "C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd" -ErrorAction SilentlyContinue
}
if (-not $azCmd) {
    Write-Error "Azure CLI (az) not found. Install with: winget install Microsoft.AzureCLI"
    exit 1
}
$accountKey = & $azCmd storage account keys list --account-name $storageAccount --query "[0].value" -o tsv 2>$null
if (-not $accountKey) {
    Write-Error "Failed to get storage account key. Run 'az login' first."
    exit 1
}

$expiry = (Get-Date).AddDays(1).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$sas = & $azCmd storage share generate-sas --name $shareName --account-name $storageAccount --account-key $accountKey --permissions rwdl --expiry $expiry -o tsv 2>$null
if (-not $sas) {
    Write-Error "Failed to generate SAS token."
    exit 1
}

$remotePath = "${baseUrl}?${sas}"

$syncArgs = @("sync")

if ($Direction -eq "up") {
    $syncArgs += $localPath, $remotePath
    Write-Host "Syncing LOCAL -> AZURE FILES" -ForegroundColor Cyan
    Write-Host "  From: $localPath"
    Write-Host "  To:   $baseUrl"
} else {
    $syncArgs += $remotePath, $localPath
    Write-Host "Syncing AZURE FILES -> LOCAL" -ForegroundColor Cyan
    Write-Host "  From: $baseUrl"
    Write-Host "  To:   $localPath"
}

$syncArgs += "--recursive"

# Exclude logs by default (709 MB)
if (-not $IncludeLogs) {
    $syncArgs += "--exclude-path", "logs/"
    Write-Host "  Excluding: logs/ (use -IncludeLogs to include)" -ForegroundColor DarkGray
}

if ($DryRun) {
    $syncArgs += "--dry-run"
    Write-Host "  Mode: DRY RUN (no files transferred)" -ForegroundColor Yellow
}

Write-Host ""

& azcopy @syncArgs

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Sync completed successfully." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Error "Sync failed with exit code $LASTEXITCODE."
}
