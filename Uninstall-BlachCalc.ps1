$ErrorActionPreference = "Stop"

$programsRoot = [IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "Programs"))
$installRoot = [IO.Path]::GetFullPath((Join-Path $programsRoot "BlachCalc"))
if (-not $installRoot.StartsWith(
    $programsRoot + [IO.Path]::DirectorySeparatorChar,
    [StringComparison]::OrdinalIgnoreCase
)) {
    throw "Nieprawidlowy folder instalacji."
}

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "BlachCalc.lnk"
$startMenuRoot = Join-Path ([Environment]::GetFolderPath("Programs")) "BlachCalc"
foreach ($path in @($desktopShortcut, (Join-Path $startMenuRoot "BlachCalc.lnk"))) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Force
    }
}
if (Test-Path -LiteralPath $startMenuRoot) {
    Remove-Item -LiteralPath $startMenuRoot -Recurse -Force
}
if (Test-Path -LiteralPath $installRoot) {
    Remove-Item -LiteralPath $installRoot -Recurse -Force
}

Write-Host "Usunieto BlachCalc. Baza danych i oferty pozostaly na komputerze." -ForegroundColor Green
