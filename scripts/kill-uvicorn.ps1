# kill-uvicorn.ps1 - Quick script to kill all uvicorn processes
# Usage: .\scripts\kill-uvicorn.ps1

$uvicornProcesses = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*uvicorn*' }

if ($uvicornProcesses) {
    $count = ($uvicornProcesses | Measure-Object).Count
    Write-Host "Found $count uvicorn process(es):" -ForegroundColor Yellow

    $uvicornProcesses | ForEach-Object {
        Write-Host "  PID $($_.ProcessId)" -ForegroundColor DarkGray
        Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
    }

    Write-Host "All uvicorn processes killed" -ForegroundColor Green
} else {
    Write-Host "No uvicorn processes running" -ForegroundColor Cyan
}

# Also check port 8000
$portCheck = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
if ($portCheck) {
    Write-Host "Port 8000 still bound by PID $($portCheck.OwningProcess) - killing..." -ForegroundColor Yellow
    Stop-Process -Id $portCheck.OwningProcess -Force -ErrorAction SilentlyContinue
    Write-Host "Done" -ForegroundColor Green
} else {
    Write-Host "Port 8000 is free" -ForegroundColor Cyan
}
