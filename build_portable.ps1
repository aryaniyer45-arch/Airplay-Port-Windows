<#
Build the portable AirPlay Mirror package.

PREREQUISITES (one time):
  1. You already built UxPlay in MSYS2 (yesterday's steps).
  2. In the "MSYS2 UCRT64" terminal, run:  bash collect_runtime.sh
     -> that creates AirPlayMirror-portable\runtime\
  3. Python 3.10+ installed (python.org, "Add to PATH" ticked).

THEN run this in normal PowerShell, from this folder:
     powershell -ExecutionPolicy Bypass -File .\build_portable.ps1

Result: AirPlayMirror-portable\  (a ready-to-zip folder) and AirPlayMirror-portable.zip
#>
$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Out  = Join-Path $Root 'AirPlayMirror-portable'
$Runtime = Join-Path $Out 'runtime'

if (-not (Test-Path (Join-Path $Runtime 'bin\uxplay.exe'))) {
    throw "runtime\bin\uxplay.exe is missing. Run 'bash collect_runtime.sh' in MSYS2 UCRT64 first."
}

Write-Host '== Installing build deps ==' -ForegroundColor Cyan
python -m pip install --quiet --upgrade pyinstaller pywebview pillow zeroconf

Write-Host '== Building the app into a standalone exe ==' -ForegroundColor Cyan
# --onedir is more reliable than --onefile for a bundle that ships extra folders.
# --collect-all webview bundles pywebview's backends; --add-data packs the web UI.
$iconArg = @()
if (Test-Path (Join-Path $Root 'icon.ico')) { $iconArg = @('--icon', (Join-Path $Root 'icon.ico')) }
python -m PyInstaller --noconfirm --windowed --onedir --name AirPlayMirror `
    --collect-all webview `
    --add-data "web;web" `
    @iconArg `
    --distpath (Join-Path $Root '_dist') --workpath (Join-Path $Root '_work') `
    (Join-Path $Root 'airplay_web.py')

$AppDir = Join-Path $Root '_dist\AirPlayMirror'
if (-not (Test-Path (Join-Path $AppDir 'AirPlayMirror.exe'))) {
    throw 'PyInstaller did not produce AirPlayMirror.exe - check the output above.'
}

Write-Host '== Assembling the package ==' -ForegroundColor Cyan
# Put the built app's files into the output folder, keeping runtime\ in place.
Copy-Item -Recurse -Force (Join-Path $AppDir '*') $Out
foreach ($f in 'README.txt','LICENSE') {
    if (Test-Path (Join-Path $Root $f)) { Copy-Item -Force (Join-Path $Root $f) $Out }
}
if (Test-Path (Join-Path $Root 'licenses')) {
    Copy-Item -Recurse -Force (Join-Path $Root 'licenses') $Out
}

Write-Host '== Zipping ==' -ForegroundColor Cyan
$Zip = Join-Path $Root 'AirPlayMirror-portable.zip'
if (Test-Path $Zip) { Remove-Item $Zip }
Compress-Archive -Path $Out -DestinationPath $Zip

# Tidy build scratch.
Remove-Item -Recurse -Force (Join-Path $Root '_dist'),(Join-Path $Root '_work') -ErrorAction SilentlyContinue
Remove-Item -Force (Join-Path $Root 'AirPlayMirror.spec') -ErrorAction SilentlyContinue

Write-Host "`nDone. Share:  $Zip" -ForegroundColor Green
Write-Host "Users extract it and run AirPlayMirror.exe - nothing to install." -ForegroundColor Green
