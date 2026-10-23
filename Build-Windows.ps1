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

# Uruchomiona aplikacja blokuje pliki w dist\, co przerywa budowanie.
$distExecutable = Join-Path $root "dist\BlachCalc\BlachCalc.exe"
Get-CimInstance Win32_Process -Filter "Name = 'BlachCalc.exe'" |
    Where-Object { $_.ExecutablePath -and ($_.ExecutablePath -ieq $distExecutable) } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-Sleep -Milliseconds 800

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
