$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $root

& (Join-Path $root "Build-Windows.ps1")

$executable = Join-Path $root "dist\BlachCalc\BlachCalc.exe"
if (-not (Test-Path -LiteralPath $executable -PathType Leaf)) {
    throw "Nie znaleziono $executable."
}
$process = Start-Process -FilePath $executable -PassThru
Start-Sleep -Seconds 3
if ($process.HasExited) {
    throw "BlachCalc zakonczyl dzialanie zaraz po uruchomieniu."
}
Write-Host "BlachCalc uruchomiony (PID $($process.Id))." -ForegroundColor Green
