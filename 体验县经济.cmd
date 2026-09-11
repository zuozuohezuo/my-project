@echo off
chcp 65001 >nul
cd /d "%~dp0"
if exist "%~dp0dist\MingImperialDesk-CountyV2\MingImperialDesk-CountyV2.exe" (
    start "" "%~dp0dist\MingImperialDesk-CountyV2\MingImperialDesk-CountyV2.exe" --county-demo normal
) else (
    uv run dynasty --county-demo normal
    if errorlevel 1 pause
)
