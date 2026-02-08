@echo off
setlocal

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0open-terminals.ps1"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Failed to open Windows Terminal tabs. Exit code: %EXIT_CODE%
  echo See log: "%~dp0terminal-launch.log"
  pause
  exit /b %EXIT_CODE%
)
