@echo off
setlocal
chcp 65001 >nul
set "APPDIR=%LOCALAPPDATA%\Programs\BlachCalc"
set "UNINS=%APPDIR%\unins000.exe"

if not exist "%UNINS%" (
    echo BlachCalc nie jest zainstalowany w: %APPDIR%
    echo Jesli instalowales w innym miejscu, uzyj Ustawienia Windows ^> Aplikacje.
    pause
    exit /b 1
)

start "" "%UNINS%"
endlocal
