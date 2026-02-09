@echo off
cd /d "%~dp0.."
set DIR=%CD%
set WT=C:\Users\fbrun\AppData\Local\Microsoft\WindowsApps\wt.exe
set LOG=%DIR%\scripts\terminal-log.txt

echo Starting at %DATE% %TIME% > "%LOG%"
echo Directory: %DIR% >> "%LOG%"

REM Open first window with first tab
echo Opening first window... >> "%LOG%"
start "" "%WT%" --window new -d "%DIR%"
echo Waiting 3 seconds... >> "%LOG%"
timeout /t 3 /nobreak >nul

REM Add tabs to the most recent window
echo Adding tab 2... >> "%LOG%"
"%WT%" --window 0 new-tab -d "%DIR%" >> "%LOG%" 2>&1
echo Exit code: %ERRORLEVEL% >> "%LOG%"

echo Adding tab 3... >> "%LOG%"
"%WT%" --window 0 new-tab -d "%DIR%" >> "%LOG%" 2>&1
echo Exit code: %ERRORLEVEL% >> "%LOG%"

echo Adding tab 4... >> "%LOG%"
"%WT%" --window 0 new-tab -d "%DIR%" >> "%LOG%" 2>&1
echo Exit code: %ERRORLEVEL% >> "%LOG%"

echo Done at %TIME% >> "%LOG%"
