<#
.SYNOPSIS
    Reset a workspace by clearing all data while preserving configuration.

.DESCRIPTION
    This is the equivalent of "DROP DATABASE" for a workspace.
    Clears all claims, runs, logs, indexes while keeping users and config.

    CLEARED (data):
      - claims/          All documents and extractions
      - runs/            Pipeline run results
      - logs/            Compliance logs
      - registry/        Indexes and labels
      - version_bundles/ Version snapshots
      - .pending/        Pending uploads
      - .input/          Input staging

    PRESERVED (config):
      - config/          Users, sessions, extractors, extraction_specs, prompts

.PARAMETER WorkspaceId
    Optional workspace ID. Defaults to the active workspace.

.PARAMETER DryRun
    Preview what would be deleted without actually deleting.

.PARAMETER Force
    Skip confirmation prompt.

.EXAMPLE
    .\workspace-reset.ps1 -DryRun
    Preview what would be deleted from the active workspace.

.EXAMPLE
    .\workspace-reset.ps1 -Force
    Reset the active workspace without confirmation.

.EXAMPLE
    .\workspace-reset.ps1 -WorkspaceId "nsa" -Force
    Reset a specific workspace without confirmation.
#>

param(
    [string]$WorkspaceId = "",
    [switch]$DryRun,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# Build command
$args = @("workspace", "reset")

if ($WorkspaceId) {
    $args += "--workspace-id"
    $args += $WorkspaceId
}

if ($DryRun) {
    $args += "--dry-run"
}

if ($Force) {
    $args += "--force"
}

# Run the CLI command
Write-Host "Running: python -m context_builder.cli $($args -join ' ')" -ForegroundColor Cyan
python -m context_builder.cli @args
