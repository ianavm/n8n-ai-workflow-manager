@echo off
REM n8n Agentic Workflows Manager - Launcher
REM Fixes Windows encoding issues

echo ============================================================
echo  N8N AGENTIC WORKFLOWS MANAGER
echo  AnyVision Media - Workflow Operations Center
echo ============================================================
echo.

REM Set UTF-8 encoding to handle Unicode characters
chcp 65001 > nul
set PYTHONIOENCODING=utf-8

REM Run the workflow manager
python tools\run_manager.py %*

pause
