@echo off
set DIR=%CD%
set WT=C:\Users\fbrun\AppData\Local\Microsoft\WindowsApps\wt.exe

start "" "%WT%" -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%"
timeout /t 2 /nobreak >nul
start "" "%WT%" -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%"
timeout /t 2 /nobreak >nul
start "" "%WT%" -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%"
timeout /t 2 /nobreak >nul
start "" "%WT%" -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%" ; new-tab -d "%DIR%"
