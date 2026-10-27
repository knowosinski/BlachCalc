@echo off
cd /d "%~dp0"
python run_tests.py
if errorlevel 1 pause
