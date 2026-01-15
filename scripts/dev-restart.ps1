# dev-restart.ps1 - Kill all uvicorn processes and restart cleanly
# Usage: .\scripts\dev-restart.ps1
#
# Note: Avoids WMI (Get-CimInstance) which can hang when system has many connections

Write-Host "Killing processes on port 8000..." -ForegroundColor Yellow

# Method 1: Kill by port (fast, no WMI)
$portResult = netstat -ano | Select-String ":8000\s+.*LISTENING"
if ($portResult) {
    foreach ($line in $portResult) {
        $pid = ($line -split '\s+')[-1]
        if ($pid -match '^\d+$') {
            Write-Host "  Killing PID $pid (bound to port 8000)" -ForegroundColor DarkGray
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Killed process(es) on port 8000" -ForegroundColor Green
} else {
    Write-Host "Port 8000 is free" -ForegroundColor Cyan
}

# Method 2: Kill any remaining python processes that might be uvicorn
$pythonProcs = Get-Process python -ErrorAction SilentlyContinue
if ($pythonProcs) {
    Write-Host "Found $($pythonProcs.Count) python process(es), cleaning up..." -ForegroundColor Yellow
    $pythonProcs | ForEach-Object {
        Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
    }
}

# Wait for port to be released
Start-Sleep -Seconds 1

# Verify port is free
$portCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "Warning: Port 8000 still in use by PID $($portCheck.OwningProcess)" -ForegroundColor Red
    Write-Host "Attempting force kill..." -ForegroundColor Yellow
    Stop-Process -Id $portCheck.OwningProcess -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
}

Write-Host ""
Write-Host "Starting uvicorn with connection limits..." -ForegroundColor Yellow
Write-Host "  --limit-concurrency 50  (max simultaneous connections)" -ForegroundColor DarkGray
Write-Host "  --timeout-keep-alive 5  (close idle connections after 5s)" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

# Start uvicorn with connection limits to prevent accumulation
uvicorn context_builder.api.main:app --reload --port 8000 --limit-concurrency 50 --timeout-keep-alive 5
