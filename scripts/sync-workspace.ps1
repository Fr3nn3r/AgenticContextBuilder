<#
.SYNOPSIS
    Sync NSA workspace between local and Azure File Share.

.DESCRIPTION
    Uses azcopy to sync workspaces/nsa/ with the claimsevidenceprod Azure Files share.
    Requires: azcopy installed and logged in (azcopy login --tenant-id <tenant-id>)

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
$remotePath = "https://claimsevidenceprod.file.core.windows.net/workspace/"
$tenantId = "2d629a45-763e-4606-8b91-ec016cbc0f0b"

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

$syncArgs = @("sync")

if ($Direction -eq "up") {
    $syncArgs += $localPath, $remotePath
    Write-Host "Syncing LOCAL -> AZURE FILES" -ForegroundColor Cyan
    Write-Host "  From: $localPath"
    Write-Host "  To:   $remotePath"
} else {
    $syncArgs += $remotePath, $localPath
    Write-Host "Syncing AZURE FILES -> LOCAL" -ForegroundColor Cyan
    Write-Host "  From: $remotePath"
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
    Write-Error "Sync failed with exit code $LASTEXITCODE. Run 'azcopy login --tenant-id $tenantId' if authentication expired."
}
