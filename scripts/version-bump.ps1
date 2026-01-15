<#
.SYNOPSIS
    Bumps the version in pyproject.toml and ui/package.json

.DESCRIPTION
    Updates version numbers following semantic versioning (SemVer).
    Both backend and frontend versions are kept in sync.

.PARAMETER Type
    The type of version bump: patch, minor, or major

.PARAMETER DryRun
    Show what would be changed without making changes

.EXAMPLE
    .\scripts\version-bump.ps1 patch    # 0.2.0 -> 0.2.1
    .\scripts\version-bump.ps1 minor    # 0.2.0 -> 0.3.0
    .\scripts\version-bump.ps1 major    # 0.2.0 -> 1.0.0
    .\scripts\version-bump.ps1 patch -DryRun  # Preview changes
#>

param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("patch", "minor", "major")]
    [string]$Type,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$PyProjectPath = Join-Path $RepoRoot "pyproject.toml"
$PackageJsonPath = Join-Path $RepoRoot "ui\package.json"

# Read current version from pyproject.toml
$pyContent = Get-Content $PyProjectPath -Raw
if ($pyContent -match 'version\s*=\s*"(\d+)\.(\d+)\.(\d+)"') {
    $major = [int]$Matches[1]
    $minor = [int]$Matches[2]
    $patch = [int]$Matches[3]
    $currentVersion = "$major.$minor.$patch"
} else {
    Write-Error "Could not parse version from pyproject.toml"
    exit 1
}

# Calculate new version
switch ($Type) {
    "patch" { $patch++ }
    "minor" { $minor++; $patch = 0 }
    "major" { $major++; $minor = 0; $patch = 0 }
}
$newVersion = "$major.$minor.$patch"

Write-Host ""
Write-Host "Version bump: " -NoNewline
Write-Host "$currentVersion" -ForegroundColor Yellow -NoNewline
Write-Host " -> " -NoNewline
Write-Host "$newVersion" -ForegroundColor Green
Write-Host ""

if ($DryRun) {
    Write-Host "[DRY RUN] Would update:" -ForegroundColor Cyan
    Write-Host "  - $PyProjectPath"
    Write-Host "  - $PackageJsonPath"
    Write-Host ""
    exit 0
}

# Update pyproject.toml
$pyContent = $pyContent -replace 'version\s*=\s*"\d+\.\d+\.\d+"', "version = `"$newVersion`""
Set-Content $PyProjectPath $pyContent -NoNewline

# Update package.json
$pkgContent = Get-Content $PackageJsonPath -Raw
$pkgContent = $pkgContent -replace '"version"\s*:\s*"\d+\.\d+\.\d+"', "`"version`": `"$newVersion`""
Set-Content $PackageJsonPath $pkgContent -NoNewline

Write-Host "Updated files:" -ForegroundColor Green
Write-Host "  - $PyProjectPath"
Write-Host "  - $PackageJsonPath"
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  git add pyproject.toml ui/package.json"
Write-Host "  git commit -m `"chore: bump version to $newVersion`""
Write-Host ""
