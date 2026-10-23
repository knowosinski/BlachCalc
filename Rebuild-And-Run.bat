@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Rebuild-And-Run.ps1"
if errorlevel 1 pause
