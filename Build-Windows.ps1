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
$archive = Join-Path $releaseRoot "BlachCalc-Installer.zip"
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
$buildId = [Guid]::NewGuid().ToString("N")
$packageStage = Join-Path $releaseRoot ("BlachCalc-Installer.staging-" + $buildId)
$archiveStage = Join-Path $releaseRoot ("BlachCalc-Installer.staging-" + $buildId + ".zip")
$packageBackup = Join-Path $releaseRoot ("BlachCalc-Installer.previous-" + $buildId)
$archiveBackup = Join-Path $releaseRoot ("BlachCalc-Installer.previous-" + $buildId + ".zip")
$packageMoved = $false
$archiveMoved = $false
$packagePublished = $false
$archivePublished = $false

try {
    New-Item -ItemType Directory -Path $packageStage -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root "dist\BlachCalc") -Destination (Join-Path $packageStage "App") -Recurse
    Copy-Item -LiteralPath (Join-Path $root "Install-BlachCalc.bat") -Destination $packageStage
    Copy-Item -LiteralPath (Join-Path $root "Install-BlachCalc.ps1") -Destination $packageStage
    Copy-Item -LiteralPath (Join-Path $root "Uninstall-BlachCalc.bat") -Destination $packageStage
    Copy-Item -LiteralPath (Join-Path $root "Uninstall-BlachCalc.ps1") -Destination $packageStage
    Copy-Item -LiteralPath (Join-Path $root "README.md") -Destination $packageStage

    if (-not (Test-Path -LiteralPath (Join-Path $packageStage "App\BlachCalc.exe") -PathType Leaf)) {
        throw "Nie znaleziono gotowego pliku App\BlachCalc.exe."
    }

    Compress-Archive -Path (Join-Path $packageStage "*") -DestinationPath $archiveStage -CompressionLevel Optimal
    if (-not (Test-Path -LiteralPath $archiveStage -PathType Leaf)) {
        throw "Nie udało się utworzyć archiwum instalacyjnego."
    }

    if (Test-Path -LiteralPath $packageRoot) {
        Move-Item -LiteralPath $packageRoot -Destination $packageBackup
        $packageMoved = $true
    }
    if (Test-Path -LiteralPath $archive) {
        Move-Item -LiteralPath $archive -Destination $archiveBackup
        $archiveMoved = $true
    }

    Move-Item -LiteralPath $packageStage -Destination $packageRoot
    $packagePublished = $true
    Move-Item -LiteralPath $archiveStage -Destination $archive
    $archivePublished = $true
} catch {
    if ($archivePublished -and (Test-Path -LiteralPath $archive)) {
        Remove-Item -LiteralPath $archive -Force
    }
    if ($packagePublished -and (Test-Path -LiteralPath $packageRoot)) {
        Remove-Item -LiteralPath $packageRoot -Recurse -Force
    }
    if ($packageMoved -and
        (Test-Path -LiteralPath $packageBackup) -and
        -not (Test-Path -LiteralPath $packageRoot)) {
        Move-Item -LiteralPath $packageBackup -Destination $packageRoot
    }
    if ($archiveMoved -and
        (Test-Path -LiteralPath $archiveBackup) -and
        -not (Test-Path -LiteralPath $archive)) {
        Move-Item -LiteralPath $archiveBackup -Destination $archive
    }
    throw
} finally {
    foreach ($temporaryPath in @($packageStage, $archiveStage)) {
        if (Test-Path -LiteralPath $temporaryPath) {
            Remove-Item -LiteralPath $temporaryPath -Recurse -Force
        }
    }
}

foreach ($backupPath in @($packageBackup, $archiveBackup)) {
    if (Test-Path -LiteralPath $backupPath) {
        try {
            Remove-Item -LiteralPath $backupPath -Recurse -Force
        } catch {
            Write-Warning "Nowa paczka jest gotowa, ale pozostała kopia poprzedniej wersji: $backupPath"
        }
    }
}
Write-Host "Gotowa paczka instalacyjna: $archive" -ForegroundColor Green
