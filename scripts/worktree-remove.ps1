<#
.SYNOPSIS
    Remove a git worktree and optionally delete its branch.

.PARAMETER Name
    Short name of the worktree (e.g., "auth", "dashboard")

.PARAMETER DeleteBranch
    Also delete the associated branch (default: false, prompts)

.EXAMPLE
    ./scripts/worktree-remove.ps1 auth
    ./scripts/worktree-remove.ps1 auth -DeleteBranch
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Name,

    [Parameter(Mandatory=$false)]
    [switch]$DeleteBranch
)

$ErrorActionPreference = "Stop"

# Determine paths
$RepoRoot = git rev-parse --show-toplevel 2>$null
if (-not $RepoRoot) {
    Write-Error "Not in a git repository"
    exit 1
}

$RepoName = Split-Path $RepoRoot -Leaf
$ParentDir = Split-Path $RepoRoot -Parent
$WorktreePath = Join-Path $ParentDir "$RepoName-$Name"
$BranchName = "feature/$Name"

# Check if worktree exists
if (-not (Test-Path $WorktreePath)) {
    Write-Error "Worktree not found at: $WorktreePath"
    Write-Host "Existing worktrees:" -ForegroundColor Yellow
    git worktree list
    exit 1
}

# Check for uncommitted changes
Push-Location $WorktreePath
$Status = git status --porcelain
Pop-Location

if ($Status) {
    Write-Host "WARNING: Worktree has uncommitted changes:" -ForegroundColor Red
    Write-Host $Status -ForegroundColor Yellow
    $Confirm = Read-Host "Continue anyway? (y/N)"
    if ($Confirm -ne "y") {
        Write-Host "Aborted."
        exit 0
    }
}

# Remove worktree
Write-Host "Removing worktree at $WorktreePath..." -ForegroundColor Cyan
git worktree remove $WorktreePath --force

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to remove worktree"
    exit 1
}

Write-Host "Worktree removed." -ForegroundColor Green

# Handle branch deletion
if (-not $DeleteBranch) {
    $DeleteBranch = (Read-Host "Delete branch '$BranchName'? (y/N)") -eq "y"
}

if ($DeleteBranch) {
    # Check if branch is merged
    $Merged = git branch --merged main | Select-String -Pattern "^\s*$BranchName$"
    if (-not $Merged) {
        Write-Host "WARNING: Branch '$BranchName' is not merged into main" -ForegroundColor Yellow
        $ForceDelete = Read-Host "Force delete? (y/N)"
        if ($ForceDelete -eq "y") {
            git branch -D $BranchName
        } else {
            Write-Host "Branch kept. Delete manually with: git branch -d $BranchName" -ForegroundColor Gray
        }
    } else {
        git branch -d $BranchName
        Write-Host "Branch '$BranchName' deleted." -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Remaining worktrees:" -ForegroundColor Cyan
git worktree list
