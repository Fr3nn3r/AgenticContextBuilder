# Sync workspace config to a customer repo and optionally commit
#
# Usage:
#   .\scripts\sync-customer.ps1                          # Copy + show status (default: nsa)
#   .\scripts\sync-customer.ps1 -Customer nsa            # Explicit customer
#   .\scripts\sync-customer.ps1 -Commit "feat: update"   # Copy + commit with message
#   .\scripts\sync-customer.ps1 -Diff                    # Copy + show full diff
#   .\scripts\sync-customer.ps1 -DryRun                  # Show what would be copied
#
# Prerequisites:
#   - Customer repo must be cloned as a sibling directory
#   - Customer repo must have a copy-from-workspace.ps1 script

param(
    [string]$Customer = "nsa",
    [string]$Commit = "",
    [switch]$Diff,
    [switch]$DryRun
)

# --- Customer registry ---
# Add new customers here: name -> repo folder name
$CustomerRepos = @{
    "nsa" = "context-builder-nsa"
}

if (-not $CustomerRepos.ContainsKey($Customer)) {
    $valid = ($CustomerRepos.Keys | Sort-Object) -join ", "
    Write-Error "Unknown customer '$Customer'. Valid customers: $valid"
    exit 1
}

# Resolve paths
$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$CustomerRepoName = $CustomerRepos[$Customer]
$CustomerRepoDir = Join-Path (Split-Path -Parent $RepoRoot) $CustomerRepoName
$CopyScript = Join-Path $CustomerRepoDir "copy-from-workspace.ps1"

# Validate
if (-not (Test-Path $CustomerRepoDir)) {
    Write-Error "Customer repo not found: $CustomerRepoDir"
    Write-Host "  Clone it with: git clone <url> `"$CustomerRepoDir`"" -ForegroundColor Gray
    exit 1
}

if (-not (Test-Path $CopyScript)) {
    Write-Error "Copy script not found: $CopyScript"
    exit 1
}

Write-Host ""
Write-Host "=== Sync customer config: $Customer ===" -ForegroundColor Cyan
Write-Host "  Main repo:     $RepoRoot" -ForegroundColor Gray
Write-Host "  Customer repo: $CustomerRepoDir" -ForegroundColor Gray
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN] Would run: $CopyScript" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Files that would be copied:" -ForegroundColor Yellow

    $WorkspaceConfig = Join-Path $RepoRoot "workspaces\$Customer\config"
    if (Test-Path $WorkspaceConfig) {
        $files = Get-ChildItem -Path $WorkspaceConfig -Recurse -File |
            Where-Object { $_.FullName -notlike "*__pycache__*" -and $_.Name -ne "sessions.json" -and $_.Name -ne "users.json" -and $_.Name -ne "audit.jsonl" -and $_.Name -ne "prompt_configs_history.jsonl" }
        foreach ($f in $files) {
            $rel = $f.FullName.Substring($WorkspaceConfig.Length + 1)
            Write-Host "  $rel" -ForegroundColor Gray
        }
        Write-Host ""
        Write-Host "Total: $($files.Count) files" -ForegroundColor Yellow
    } else {
        Write-Host "  Workspace config not found: $WorkspaceConfig" -ForegroundColor Red
    }
    exit 0
}

# Step 1: Run the copy script
Write-Host "Copying workspace config to customer repo..." -ForegroundColor Yellow
$WorkspaceConfig = Join-Path $RepoRoot "workspaces\$Customer\config"
# The copy script joins its own $ScriptDir + param with Resolve-Path,
# so we need to pass a relative path from the customer repo directory.
Push-Location $CustomerRepoDir
try {
    $RelativePath = Resolve-Path -Relative $WorkspaceConfig
} finally {
    Pop-Location
}
& $CopyScript -WorkspaceConfigDir $RelativePath

if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    Write-Error "Copy script failed with exit code $LASTEXITCODE"
    exit 1
}

# Step 2: Show status
Write-Host ""
Write-Host "--- Customer repo status ---" -ForegroundColor Cyan
Push-Location $CustomerRepoDir
try {
    git status --short

    $changes = git status --porcelain
    if (-not $changes) {
        Write-Host "  No changes detected." -ForegroundColor Green
        exit 0
    }

    # Show diff summary
    Write-Host ""
    Write-Host "--- Changed files ---" -ForegroundColor Cyan
    git diff --stat
    git diff --stat --cached

    # Show full diff if requested
    if ($Diff) {
        Write-Host ""
        Write-Host "--- Full diff ---" -ForegroundColor Cyan
        git diff
        git diff --cached
    }

    # Step 3: Commit if requested
    if ($Commit) {
        Write-Host ""
        Write-Host "Committing changes..." -ForegroundColor Yellow
        git add -A
        git commit -m $Commit

        if ($LASTEXITCODE -eq 0) {
            Write-Host ""
            Write-Host "Committed successfully." -ForegroundColor Green
            Write-Host "  Push with: git -C `"$CustomerRepoDir`" push" -ForegroundColor Gray
        } else {
            Write-Error "Commit failed."
            exit 1
        }
    } else {
        Write-Host ""
        Write-Host "Next steps:" -ForegroundColor Yellow
        Write-Host "  Commit:  .\scripts\sync-customer.ps1 -Commit `"feat: description`"" -ForegroundColor Gray
        Write-Host "  Or manually:" -ForegroundColor Gray
        Write-Host "    git -C `"$CustomerRepoDir`" add -A" -ForegroundColor Gray
        Write-Host "    git -C `"$CustomerRepoDir`" commit -m `"feat: description`"" -ForegroundColor Gray
        Write-Host "    git -C `"$CustomerRepoDir`" push" -ForegroundColor Gray
    }
} finally {
    Pop-Location
}
