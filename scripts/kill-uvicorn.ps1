# kill-uvicorn.ps1 - Quick script to kill all uvicorn processes
# Usage: .\scripts\kill-uvicorn.ps1
#
# Note: Avoids WMI (Get-CimInstance) which can hang when system has many connections

Write-Host "Checking port 8000..." -ForegroundColor Yellow

# Method 1: Kill by port using netstat (fast, no WMI)
$portResult = netstat -ano | Select-String ":8000\s+.*LISTENING"
if ($portResult) {
    foreach ($line in $portResult) {
        $pid = ($line -split '\s+')[-1]
        if ($pid -match '^\d+$') {
            Write-Host "  Killing PID $pid (listening on port 8000)" -ForegroundColor DarkGray
            Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
        }
    }
    Write-Host "Killed server process(es)" -ForegroundColor Green
} else {
    Write-Host "No process listening on port 8000" -ForegroundColor Cyan
}

# Method 2: Also kill any established connections' client processes
# This helps when browsers/tests have accumulated connections
$established = netstat -ano | Select-String "127.0.0.1:8000\s+.*ESTABLISHED"
if ($established) {
    $pids = @()
    foreach ($line in $established) {
        $pid = ($line -split '\s+')[-1]
        if ($pid -match '^\d+$' -and $pids -notcontains $pid) {
            $pids += $pid
        }
    }
    if ($pids.Count -gt 0) {
        Write-Host "Found $($pids.Count) client process(es) with established connections" -ForegroundColor Yellow
        Write-Host "  (Not killing clients - they will disconnect when server stops)" -ForegroundColor DarkGray
    }
}

# Verify port is free
Start-Sleep -Milliseconds 500
$portCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "Port 8000 still bound by PID $($portCheck.OwningProcess) - force killing..." -ForegroundColor Yellow
    Stop-Process -Id $portCheck.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "Done" -ForegroundColor Green
} else {
    Write-Host "Port 8000 is free" -ForegroundColor Cyan
}
