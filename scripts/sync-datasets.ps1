<#
.SYNOPSIS
    Sync datasets between local and Azure Blob Storage.

.DESCRIPTION
    Uses azcopy to sync data/datasets/ with the claimsevidenceprod storage account.
    Requires: azcopy installed and logged in (azcopy login --tenant-id <tenant-id>)

.PARAMETER Direction
    "up" (local -> Azure) or "down" (Azure -> local). Default: up

.PARAMETER DryRun
    Preview what would be transferred without actually syncing.

.EXAMPLE
    .\scripts\sync-datasets.ps1              # Upload local changes to Azure
    .\scripts\sync-datasets.ps1 -Direction down   # Download from Azure to local
    .\scripts\sync-datasets.ps1 -DryRun           # Preview upload without syncing
#>

param(
    [ValidateSet("up", "down")]
    [string]$Direction = "up",
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$localPath = Join-Path $repoRoot "data\datasets"
$remotePath = "https://claimsevidenceprod.blob.core.windows.net/datasets/"
$tenantId = "2d629a45-763e-4606-8b91-ec016cbc0f0b"

# Check azcopy is available
if (-not (Get-Command azcopy -ErrorAction SilentlyContinue)) {
    Write-Error "azcopy not found. Install with: winget install Microsoft.Azure.AZCopy.10"
    exit 1
}

# Check local path exists
if (-not (Test-Path $localPath)) {
    Write-Error "Local datasets path not found: $localPath"
    exit 1
}

$syncArgs = @("sync")

if ($Direction -eq "up") {
    $syncArgs += $localPath, $remotePath
    Write-Host "Syncing LOCAL -> AZURE" -ForegroundColor Cyan
    Write-Host "  From: $localPath"
    Write-Host "  To:   $remotePath"
} else {
    $syncArgs += $remotePath, $localPath
    Write-Host "Syncing AZURE -> LOCAL" -ForegroundColor Cyan
    Write-Host "  From: $remotePath"
    Write-Host "  To:   $localPath"
}

$syncArgs += "--recursive"

if ($DryRun) {
    $syncArgs += "--dry-run"
    Write-Host "  Mode: DRY RUN (no files transferred)" -ForegroundColor Yellow
}

Write-Host ""

& azcopy @args

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Sync completed successfully." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Error "Sync failed with exit code $LASTEXITCODE. Run 'azcopy login --tenant-id $tenantId' if authentication expired."
}
