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
if (Test-Path -LiteralPath $resolvedInstallRoot) {
    Remove-Item -LiteralPath $resolvedInstallRoot -Recurse -Force
}
New-Item -ItemType Directory -Path $resolvedInstallRoot -Force | Out-Null
Get-ChildItem -LiteralPath $source -Force |
    Copy-Item -Destination $resolvedInstallRoot -Recurse -Force

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
