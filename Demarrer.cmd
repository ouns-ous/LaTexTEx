@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 "%~dp0project_studio.py"
) else (
    python "%~dp0project_studio.py"
)
if errorlevel 1 pause
