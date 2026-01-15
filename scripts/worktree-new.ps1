<#
.SYNOPSIS
    Create a new git worktree for isolated parallel development.

.DESCRIPTION
    Creates a worktree in a sibling directory with a new branch.
    Example: ./scripts/worktree-new.ps1 feature-auth
    Creates: ../AgenticContextBuilder-feature-auth/ on branch feature/auth

.PARAMETER Name
    Short name for the worktree (e.g., "auth", "dashboard", "bugfix-123")

.PARAMETER BaseBranch
    Branch to base the new branch on (default: main)

.EXAMPLE
    ./scripts/worktree-new.ps1 auth
    ./scripts/worktree-new.ps1 dashboard -BaseBranch develop
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Name,

    [Parameter(Mandatory=$false)]
    [string]$BaseBranch = "main"
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

# Check if worktree already exists
if (Test-Path $WorktreePath) {
    Write-Error "Worktree already exists at: $WorktreePath"
    exit 1
}

# Check if branch exists
$BranchExists = git show-ref --verify --quiet "refs/heads/$BranchName" 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Branch '$BranchName' already exists, checking out existing branch..." -ForegroundColor Yellow
    git worktree add $WorktreePath $BranchName
} else {
    Write-Host "Creating new worktree with branch '$BranchName' based on '$BaseBranch'..." -ForegroundColor Cyan
    git worktree add -b $BranchName $WorktreePath $BaseBranch
}

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to create worktree"
    exit 1
}

# Copy node_modules symlink or .venv if they exist (for faster setup)
Write-Host ""
Write-Host "Worktree created successfully!" -ForegroundColor Green
Write-Host "  Path:   $WorktreePath" -ForegroundColor White
Write-Host "  Branch: $BranchName" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. cd `"$WorktreePath`""
Write-Host "  2. Open a new terminal/Claude Code window there"
Write-Host "  3. Run 'npm install' in ui/ if needed"
Write-Host ""
Write-Host "To list all worktrees: git worktree list" -ForegroundColor Gray
Write-Host "To remove when done:   ./scripts/worktree-remove.ps1 $Name" -ForegroundColor Gray
