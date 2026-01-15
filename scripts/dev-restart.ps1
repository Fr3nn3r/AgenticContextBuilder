# dev-restart.ps1 - Kill all uvicorn processes and restart cleanly
# Usage: .\scripts\dev-restart.ps1

Write-Host "Killing all uvicorn processes..." -ForegroundColor Yellow

$uvicornProcesses = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*' }

if ($uvicornProcesses) {
    $count = ($uvicornProcesses | Measure-Object).Count
    $uvicornProcesses | ForEach-Object {
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Write-Host "Killed $count uvicorn process(es)" -ForegroundColor Green
} else {
    Write-Host "No uvicorn processes found" -ForegroundColor Cyan
}

# Wait for port to be released
Start-Sleep -Seconds 1

# Check if port 8000 is still bound
$portCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "Warning: Port 8000 still in use by PID $($portCheck.OwningProcess)" -ForegroundColor Red
    Write-Host "Attempting to kill..." -ForegroundColor Yellow
    Stop-Process -Id $portCheck.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Starting uvicorn..." -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

# Start uvicorn fresh
uvicorn context_builder.api.main:app --reload --port 8000
