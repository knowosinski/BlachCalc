$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Nie udalo sie zainstalowac zaleznosci budowania."
}

python create_icon.py
if ($LASTEXITCODE -ne 0) {
    throw "Nie udalo sie utworzyc ikony BlachCalc.ico."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name BlachCalc `
    --icon BlachCalc.ico `
    --add-data "logo.png;." `
    --add-data "BlachCalc.ico;." `
    --collect-all pymupdf `
    --distpath (Join-Path $root "dist") `
    --workpath (Join-Path $root "build\pyinstaller") `
    blachcalc.py
if ($LASTEXITCODE -ne 0) {
    throw "Budowanie aplikacji BlachCalc nie powiodlo sie."
}

$releaseRoot = Join-Path $root "release"
$packageRoot = Join-Path $releaseRoot "BlachCalc-Installer"
$appDirectory = Join-Path $packageRoot "App"
$archive = Join-Path $releaseRoot "BlachCalc-Installer.zip"
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
if (Test-Path -LiteralPath $packageRoot) {
    Remove-Item -LiteralPath $packageRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $packageRoot -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root "dist\BlachCalc") -Destination $appDirectory -Recurse
Copy-Item -LiteralPath (Join-Path $root "Install-BlachCalc.bat") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $root "Install-BlachCalc.ps1") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $root "Uninstall-BlachCalc.bat") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $root "Uninstall-BlachCalc.ps1") -Destination $packageRoot
Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $packageRoot
if (Test-Path -LiteralPath $archive) {
    Remove-Item -LiteralPath $archive -Force
}
Compress-Archive -Path (Join-Path $packageRoot "*") -DestinationPath $archive -CompressionLevel Optimal
Write-Host "Gotowa paczka instalacyjna: $archive" -ForegroundColor Green
