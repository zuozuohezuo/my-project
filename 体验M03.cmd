@echo off
setlocal
cd /d "%~dp0"
if exist "dist\MingImperialDesk-M03Stages\MingImperialDesk-M03Stages.exe" (
    start "" "dist\MingImperialDesk-M03Stages\MingImperialDesk-M03Stages.exe" --m03-demo
    exit /b
)
uv run --locked dynasty --m03-demo
