@echo off
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
    echo uv was not found. Install uv from https://docs.astral.sh/uv/getting-started/installation/
    echo Or run dist\MingImperialDesk\MingImperialDesk.exe
    pause
    exit /b 1
)
uv run --locked dynasty
if errorlevel 1 pause
