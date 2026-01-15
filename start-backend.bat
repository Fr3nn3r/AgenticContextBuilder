@echo off
cd /d "%~dp0src\context_builder"
uvicorn api.main:app --reload --port 8000 --limit-concurrency 50 --timeout-keep-alive 5
