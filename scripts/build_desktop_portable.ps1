param(
    [int]$Port = 18555,
    [switch]$UseMirror = $true
)

$ErrorActionPreference = 'Stop'

function Run($cmd, $args) {
  Write-Host "> $cmd $args" -ForegroundColor Cyan
  & $cmd $args
}

# Resolve repo paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$electronDir = Join-Path $repoRoot 'desktop\electron'

Write-Host "[1/5] Build backend EXE (PyInstaller)" -ForegroundColor Yellow
Run powershell "`"$scriptDir\build_backend_exe.ps1`" -Port $Port"

Write-Host "[2/5] Prepare Electron environment" -ForegroundColor Yellow
Push-Location $electronDir

if ($UseMirror) {
  Write-Host "Configure registry and mirrors (npmmirror)" -ForegroundColor DarkYellow
  Run npm "config set registry https://registry.npmmirror.com"
  $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
  $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
}

if (-not (Test-Path 'node_modules')) {
  Write-Host "Install Electron deps" -ForegroundColor Yellow
  Run npm "install"
}

Write-Host "[3/5] Build win-unpacked directory" -ForegroundColor Yellow
Run npx "-y electron-builder --win --x64 --dir"

Write-Host "[4/5] Place backend EXE into resources" -ForegroundColor Yellow
$backendExe = Join-Path $electronDir 'KomodoHubBackend.exe'
if (-not (Test-Path $backendExe)) {
  throw "Backend EXE not found at $backendExe. Did build_backend_exe.ps1 succeed?"
}
$resourcesDir = Join-Path $electronDir 'dist\win-unpacked\resources'
New-Item -ItemType Directory -Force -Path $resourcesDir | Out-Null
Copy-Item -Force $backendExe (Join-Path $resourcesDir 'KomodoHubBackend.exe')

Write-Host "[5/5] Launch Komodo Hub (portable)" -ForegroundColor Yellow
$appPath = Join-Path $electronDir 'dist\win-unpacked\Komodo Hub.exe'
if (-not (Test-Path $appPath)) { throw "App not found: $appPath" }
Start-Process -FilePath $appPath -WorkingDirectory (Split-Path $appPath)

Pop-Location
Write-Host "Done. Portable app started from dist\\win-unpacked." -ForegroundColor Green

