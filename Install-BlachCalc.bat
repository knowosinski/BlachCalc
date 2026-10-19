@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-BlachCalc.ps1"
if errorlevel 1 (
    echo.
    echo Instalacja nie powiodla sie. Szczegoly bledu znajduja sie powyzej.
    pause
    exit /b 1
)
exit /b 0
