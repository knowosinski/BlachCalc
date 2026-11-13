@echo off
REM Build BlachCalc v1.4.1 with new local update system
REM Run as Administrator

setlocal enabledelayedexpansion

echo.
echo ╔════════════════════════════════════════════════════════════════╗
echo ║          BLACHCALC v1.4.1 BUILD & INSTALL                     ║
echo ║     Local Update System (bez GitHub - kompletny rewrite)      ║
echo ╚════════════════════════════════════════════════════════════════╝
echo.

REM Check if running as Administrator
openfiles >nul 2>&1
if errorlevel 1 (
    echo ⚠️  ERROR: Uruchom PowerShell/CMD jako Administrator!
    echo.
    pause
    exit /b 1
)

REM Get script directory
cd /d "%~dp0"

echo ✓ Folder: %cd%
echo.

REM Check if Build-Windows.ps1 exists
if not exist "Build-Windows.ps1" (
    echo ❌ ERROR: Build-Windows.ps1 nie znaleziony!
    echo.
    pause
    exit /b 1
)

echo 📦 Uruchamianie BUILD (może to potrwać 15-30 minut)...
echo.

REM Run PowerShell build script
powershell -ExecutionPolicy Bypass -File "Build-Windows.ps1"
set BUILD_RESULT=%errorlevel%

echo.
if %BUILD_RESULT% equ 0 (
    echo ✅ BUILD SUKCES!
    echo.
    echo 📍 Instalator: %cd%\release\BlachCalc-Setup.exe
    echo 📍 Aplikacja:  %cd%\dist\BlachCalc\BlachCalc.exe
    echo.
    echo Następne kroki:
    echo   1. Uruchom instalator: release\BlachCalc-Setup.exe
    echo   2. Lub uruchom aplikację: dist\BlachCalc\BlachCalc.exe
    echo.
) else (
    echo ❌ BUILD FAILED (exit code %BUILD_RESULT%)
    echo.
    echo Przyczyny:
    echo   • Brakuje zależności - uruchom: python -m pip install -r requirements-build.txt
    echo   • Inno Setup nie zainstalowany - pobierz: https://jrsoftware.org/isdl.php
    echo   • Testy nie przeszły - sprawdź komunikaty powyżej
    echo.
)

pause
exit /b %BUILD_RESULT%
