$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

$compilerCommand = Get-Command ISCC.exe -ErrorAction SilentlyContinue
$compiler = if ($compilerCommand) { $compilerCommand.Source }
$programFilesRoots = @(${env:ProgramFiles(x86)}, $env:ProgramFiles) |
    Where-Object { $_ } |
    Select-Object -Unique
if (-not $compiler) {
    foreach ($version in @("7", "6")) {
        foreach ($programFiles in $programFilesRoots) {
            $candidate = Join-Path $programFiles "Inno Setup $version\ISCC.exe"
            if (Test-Path -LiteralPath $candidate -PathType Leaf) {
                $compiler = $candidate
                break
            }
        }
        if ($compiler) { break }
    }
}
if (-not $compiler) {
    throw "Nie znaleziono kompilatora Inno Setup 6 lub 7 (ISCC.exe). Zainstaluj Inno Setup i uruchom ten skrypt ponownie."
}

python -m unittest discover -p "test_*.py"
if ($LASTEXITCODE -ne 0) {
    throw "Testy projektu nie przeszły. Wydanie nie zostało zbudowane."
}

python -c "import PyInstaller, pymupdf, reportlab, PIL"
if ($LASTEXITCODE -ne 0) {
    throw "Brakuje zależności budowania. Zainstaluj je poleceniem: python -m pip install -r requirements-build.txt"
}

# Zamknij uruchomioną aplikację łagodnie przed nadpisaniem jej plików.
$distExecutable = Join-Path $root "dist\BlachCalc\BlachCalc.exe"
Get-CimInstance Win32_Process -Filter "Name = 'BlachCalc.exe'" |
    Where-Object { $_.ExecutablePath -and ($_.ExecutablePath -ieq $distExecutable) } |
    ForEach-Object {
        $runningApp = Get-Process -Id $_.ProcessId -ErrorAction Stop
        if (-not $runningApp.CloseMainWindow()) {
            throw "Nie udało się łagodnie zamknąć BlachCalc (PID $($_.ProcessId))."
        }
        if (-not $runningApp.WaitForExit(10000)) {
            throw "BlachCalc (PID $($_.ProcessId)) nie zamknął się. Zapisz pracę i zamknij aplikację ręcznie."
        }
    }

python create_icon.py
if ($LASTEXITCODE -ne 0) {
    throw "Nie udalo sie utworzyc ikony BlachCalc.ico."
}

python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --noupx `
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
$installer = Join-Path $releaseRoot "BlachCalc-Setup.exe"
New-Item -ItemType Directory -Path $releaseRoot -Force | Out-Null
$buildId = [Guid]::NewGuid().ToString("N")
$installerStage = Join-Path $releaseRoot ("BlachCalc-Setup.staging-" + $buildId)
$installerStageFile = Join-Path $installerStage "BlachCalc-Setup.exe"
$installerBackup = Join-Path $releaseRoot ("BlachCalc-Setup.previous-" + $buildId + ".exe")
$installerMoved = $false
$installerPublished = $false

try {
    New-Item -ItemType Directory -Path $installerStage -Force | Out-Null
    & $compiler "/O$installerStage" (Join-Path $root "BlachCalc-Setup.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Kompilowanie instalatora Inno Setup nie powiodło się."
    }
    if (-not (Test-Path -LiteralPath $installerStageFile -PathType Leaf)) {
        throw "Inno Setup nie utworzył pliku BlachCalc-Setup.exe."
    }

    if (Test-Path -LiteralPath $installer) {
        Move-Item -LiteralPath $installer -Destination $installerBackup
        $installerMoved = $true
    }
    Move-Item -LiteralPath $installerStageFile -Destination $installer
    $installerPublished = $true
} catch {
    if ($installerPublished -and (Test-Path -LiteralPath $installer)) {
        Remove-Item -LiteralPath $installer -Force
    }
    if ($installerMoved -and
        (Test-Path -LiteralPath $installerBackup) -and
        -not (Test-Path -LiteralPath $installer)) {
        Move-Item -LiteralPath $installerBackup -Destination $installer
    }
    throw
} finally {
    if (Test-Path -LiteralPath $installerStage) {
        Remove-Item -LiteralPath $installerStage -Recurse -Force
    }
}

if ($installerMoved -and (Test-Path -LiteralPath $installerBackup)) {
    try {
        Remove-Item -LiteralPath $installerBackup -Force
    } catch {
        Write-Warning "Nowy instalator jest gotowy, ale pozostała kopia poprzedniej wersji: $installerBackup"
    }
}
Write-Host "Gotowy instalator: $installer" -ForegroundColor Green

$packageId = [Guid]::NewGuid().ToString("N")
$packageStage = Join-Path $releaseRoot ("BlachCalc-Package.staging-" + $packageId)
$packageZipStage = Join-Path $releaseRoot ("BlachCalc-Package.staging-" + $packageId + ".zip")
$packageZip = Join-Path $root "BlachCalc-Package.zip"
$packageZipBackup = Join-Path $releaseRoot ("BlachCalc-Package.previous-" + $packageId + ".zip")
$packageMoved = $false
$packagePublished = $false

try {
    $sourceStage = Join-Path $packageStage "BlachCalc"
    New-Item -ItemType Directory -Path $sourceStage -Force | Out-Null
    $sourceFiles = @(
        ".gitignore",
        "BlachCalc-Setup.iss",
        "BlachCalc.spec",
        "Build-Windows.ps1",
        "LICENSE",
        "README.md",
        "Rebuild-And-Run.bat",
        "Rebuild-And-Run.ps1",
        "requirements-build.txt",
        "requirements.txt",
        "applogo.png",
        "BlachCalc.ico",
        "logo.png"
    )
    foreach ($file in $sourceFiles) {
        $source = Join-Path $root $file
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            throw "Brakuje pliku wymaganego w paczce źródeł: $source"
        }
        Copy-Item -LiteralPath $source -Destination $sourceStage
    }
    Get-ChildItem -LiteralPath $root -Filter "*.py" -File |
        Copy-Item -Destination $sourceStage

    $vscodeTasks = Join-Path $root ".vscode\tasks.json"
    if (Test-Path -LiteralPath $vscodeTasks -PathType Leaf) {
        $vscodeStage = Join-Path $sourceStage ".vscode"
        New-Item -ItemType Directory -Path $vscodeStage -Force | Out-Null
        Copy-Item -LiteralPath $vscodeTasks -Destination $vscodeStage
    }
    Copy-Item -LiteralPath $installer -Destination $packageStage
    Copy-Item -LiteralPath (Join-Path $root "INSTRUKCJA-URUCHOMIENIA.txt") -Destination $packageStage

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $packageStage,
        $packageZipStage,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $false
    )

    if (Test-Path -LiteralPath $packageZip) {
        Move-Item -LiteralPath $packageZip -Destination $packageZipBackup
        $packageMoved = $true
    }
    Move-Item -LiteralPath $packageZipStage -Destination $packageZip
    $packagePublished = $true
} catch {
    if ($packagePublished -and (Test-Path -LiteralPath $packageZip)) {
        Remove-Item -LiteralPath $packageZip -Force
    }
    if ($packageMoved -and
        (Test-Path -LiteralPath $packageZipBackup) -and
        -not (Test-Path -LiteralPath $packageZip)) {
        Move-Item -LiteralPath $packageZipBackup -Destination $packageZip
    }
    throw
} finally {
    if (Test-Path -LiteralPath $packageStage) {
        Remove-Item -LiteralPath $packageStage -Recurse -Force
    }
    if (Test-Path -LiteralPath $packageZipStage) {
        Remove-Item -LiteralPath $packageZipStage -Force
    }
}

if ($packageMoved -and (Test-Path -LiteralPath $packageZipBackup)) {
    Remove-Item -LiteralPath $packageZipBackup -Force
}

$rootInstaller = Join-Path $root "BlachCalc-Setup.exe"
$rootInstallerStage = Join-Path $root ("BlachCalc-Setup.staging-" + $packageId + ".exe")
$rootInstallerBackup = Join-Path $root ("BlachCalc-Setup.previous-" + $packageId + ".exe")
Copy-Item -LiteralPath $installer -Destination $rootInstallerStage
try {
    if (Test-Path -LiteralPath $rootInstaller) {
        Move-Item -LiteralPath $rootInstaller -Destination $rootInstallerBackup
    }
    Move-Item -LiteralPath $rootInstallerStage -Destination $rootInstaller
} catch {
    if ((Test-Path -LiteralPath $rootInstallerBackup) -and
        -not (Test-Path -LiteralPath $rootInstaller)) {
        Move-Item -LiteralPath $rootInstallerBackup -Destination $rootInstaller
    }
    throw
} finally {
    if (Test-Path -LiteralPath $rootInstallerStage) {
        Remove-Item -LiteralPath $rootInstallerStage -Force
    }
}
if (Test-Path -LiteralPath $rootInstallerBackup) {
    Remove-Item -LiteralPath $rootInstallerBackup -Force
}
Write-Host "Gotowy instalator: $installer" -ForegroundColor Green
Write-Host "Kopia instalatora: $rootInstaller" -ForegroundColor Green
Write-Host "Paczka projektu: $packageZip" -ForegroundColor Green
