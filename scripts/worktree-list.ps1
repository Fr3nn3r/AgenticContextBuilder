<#
.SYNOPSIS
    List all git worktrees with their status.
#>

$ErrorActionPreference = "Stop"

Write-Host "Git Worktrees:" -ForegroundColor Cyan
Write-Host "==============" -ForegroundColor Cyan
Write-Host ""

$Worktrees = git worktree list --porcelain | Out-String
$Entries = $Worktrees -split "worktree " | Where-Object { $_ -ne "" }

foreach ($Entry in $Entries) {
    $Lines = $Entry -split "`n" | Where-Object { $_ -ne "" }
    $Path = $Lines[0].Trim()
    $Branch = ($Lines | Where-Object { $_ -match "^branch " }) -replace "^branch refs/heads/", ""

    if (-not $Branch) {
        $Branch = "(detached)"
    }

    # Check for uncommitted changes
    if (Test-Path $Path) {
        Push-Location $Path
        $Status = git status --porcelain 2>$null
        $Ahead = git rev-list --count "@{upstream}..HEAD" 2>$null
        Pop-Location

        $StatusIndicator = ""
        if ($Status) {
            $StatusIndicator = " [uncommitted changes]"
        }
        if ($Ahead -and $Ahead -gt 0) {
            $StatusIndicator += " [ahead $Ahead]"
        }

        $Color = if ($Status) { "Yellow" } else { "Green" }
        Write-Host "  $Branch" -ForegroundColor $Color -NoNewline
        Write-Host $StatusIndicator -ForegroundColor Yellow
        Write-Host "    $Path" -ForegroundColor Gray
    }
    Write-Host ""
}

Write-Host "Commands:" -ForegroundColor Gray
Write-Host "  Create:  ./scripts/worktree-new.ps1 <name>" -ForegroundColor Gray
Write-Host "  Remove:  ./scripts/worktree-remove.ps1 <name>" -ForegroundColor Gray
