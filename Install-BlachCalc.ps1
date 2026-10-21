$ErrorActionPreference = "Stop"

$source = Join-Path $PSScriptRoot "App"
$installRoot = Join-Path $env:LOCALAPPDATA "Programs\BlachCalc"
$expectedParent = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs"))
$resolvedInstallRoot = [IO.Path]::GetFullPath($installRoot)
$executable = Join-Path $source "BlachCalc.exe"

if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Nie znaleziono pliku App\BlachCalc.exe. Rozpakuj kompletne archiwum instalacyjne."
}
if (-not $resolvedInstallRoot.StartsWith(
    $expectedParent + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Nieprawidlowy folder docelowy instalacji."
}

New-Item -ItemType Directory -Path $expectedParent -Force | Out-Null
$stagingRoot = Join-Path $expectedParent ("BlachCalc.staging-" + [Guid]::NewGuid().ToString("N"))
$backupRoot = Join-Path $expectedParent ("BlachCalc.previous-" + [Guid]::NewGuid().ToString("N"))
$previousInstallMoved = $false

try {
    New-Item -ItemType Directory -Path $stagingRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $source -Force |
        Copy-Item -Destination $stagingRoot -Recurse -Force

    if (-not (Test-Path -LiteralPath (Join-Path $stagingRoot "BlachCalc.exe") -PathType Leaf)) {
        throw "Skopiowana aplikacja jest niekompletna. Istniejąca instalacja nie została zmieniona."
    }

    if (Test-Path -LiteralPath $resolvedInstallRoot) {
        Move-Item -LiteralPath $resolvedInstallRoot -Destination $backupRoot
        $previousInstallMoved = $true
    }

    try {
        Move-Item -LiteralPath $stagingRoot -Destination $resolvedInstallRoot
    } catch {
        if ($previousInstallMoved -and -not (Test-Path -LiteralPath $resolvedInstallRoot)) {
            Move-Item -LiteralPath $backupRoot -Destination $resolvedInstallRoot
            $previousInstallMoved = $false
        }
        throw
    }
} catch {
    if ($previousInstallMoved -and
        (Test-Path -LiteralPath $backupRoot) -and
        -not (Test-Path -LiteralPath $resolvedInstallRoot)) {
        Move-Item -LiteralPath $backupRoot -Destination $resolvedInstallRoot
    }
    throw
} finally {
    if (Test-Path -LiteralPath $stagingRoot) {
        Remove-Item -LiteralPath $stagingRoot -Recurse -Force
    }
}

if ($previousInstallMoved -and (Test-Path -LiteralPath $backupRoot)) {
    try {
        Remove-Item -LiteralPath $backupRoot -Recurse -Force
    } catch {
        Write-Warning "Nowa wersja działa, ale poprzednia instalacja pozostała w: $backupRoot"
    }
}

$installedExecutable = Join-Path $resolvedInstallRoot "BlachCalc.exe"
$icon = Join-Path $resolvedInstallRoot "BlachCalc.ico"
$desktop = [Environment]::GetFolderPath("DesktopDirectory")
$startMenu = Join-Path ([Environment]::GetFolderPath("Programs")) "BlachCalc"
New-Item -ItemType Directory -Path $startMenu -Force | Out-Null

$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @(
    (Join-Path $desktop "BlachCalc.lnk"),
    (Join-Path $startMenu "BlachCalc.lnk")
)) {
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $installedExecutable
    $shortcut.WorkingDirectory = $resolvedInstallRoot
    $shortcut.IconLocation = "$icon,0"
    $shortcut.Description = "BlachCalc - wyceny Izo-Technika"
    $shortcut.Save()
}

Write-Host "BlachCalc zostal zainstalowany." -ForegroundColor Green
Write-Host "Ikona na pulpicie: $(Join-Path $desktop 'BlachCalc.lnk')"
Start-Process -FilePath $installedExecutable -WorkingDirectory $resolvedInstallRoot
