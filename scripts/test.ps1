# test.ps1 - Run pytest with Windows-compatible flags
# Usage: .\scripts\test.ps1 [optional pytest args]
#
# Examples:
#   .\scripts\test.ps1                    # Run all tests
#   .\scripts\test.ps1 tests/unit/        # Run unit tests only
#   .\scripts\test.ps1 -k "test_quality"  # Run tests matching pattern

$pytestArgs = $args -join " "

Write-Host "Running pytest with Windows-safe flags..." -ForegroundColor Cyan
Write-Host ""

if ($pytestArgs) {
    python -m pytest -v -p no:tmpdir -o cache_dir=output/.pytest_cache $args
} else {
    python -m pytest -v -p no:tmpdir -o cache_dir=output/.pytest_cache
}
