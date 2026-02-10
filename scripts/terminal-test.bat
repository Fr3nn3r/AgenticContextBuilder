@echo off
cd /d "%~dp0.."
set DIR=%CD%
set WT=C:\Users\fbrun\AppData\Local\Microsoft\WindowsApps\wt.exe

echo === Windows Terminal Diagnostic ===
echo Directory: %DIR%
echo.

echo Test 6: cmd /c with quoted command string...
cmd /c ""%WT%" new-tab -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%""
echo Result: %ERRORLEVEL%
timeout /t 3 /nobreak

echo.
echo Test 7: Direct call with no escaping...
"%WT%" -d "%DIR%" ; new-tab ; new-tab ; new-tab
echo Result: %ERRORLEVEL%
timeout /t 3 /nobreak

echo.
echo Test 8: Sequential tab addition to window 0...
start "" "%WT%" -d "%DIR%"
timeout /t 2 /nobreak
"%WT%" -w 0 nt -d "%DIR%"
timeout /t 1 /nobreak
"%WT%" -w 0 nt -d "%DIR%"
timeout /t 1 /nobreak
"%WT%" -w 0 nt -d "%DIR%"
echo Done adding tabs
timeout /t 2 /nobreak

echo === Tests complete ===
pause
