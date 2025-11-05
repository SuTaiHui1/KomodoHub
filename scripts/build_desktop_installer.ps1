param(
    [int]$Port = 18555,
    [switch]$UseMirror = $true
)

$ErrorActionPreference = 'Stop'

function Run($cmd, $args) {
  Write-Host "> $cmd $args" -ForegroundColor Cyan
  & $cmd $args
}

# Check admin (symlink extraction may require it)
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($id)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
  Write-Warning "It's recommended to run this script in an Administrator PowerShell or enable Windows Developer Mode (Settings -> For developers) to avoid symlink extraction errors."
}

# Resolve paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot  = Split-Path -Parent $scriptDir
$electronDir = Join-Path $repoRoot 'desktop\electron'

Write-Host "[1/4] Build backend EXE (PyInstaller)" -ForegroundColor Yellow
Run powershell "`"$scriptDir\build_backend_exe.ps1`" -Port $Port"

Write-Host "[2/4] Prepare Electron environment" -ForegroundColor Yellow
Push-Location $electronDir
if ($UseMirror) {
  Write-Host "Configure registry and mirrors (npmmirror)" -ForegroundColor DarkYellow
  Run npm "config set registry https://registry.npmmirror.com"
  $env:ELECTRON_MIRROR = "https://npmmirror.com/mirrors/electron/"
  $env:ELECTRON_BUILDER_BINARIES_MIRROR = "https://npmmirror.com/mirrors/electron-builder-binaries/"
}
if (-not (Test-Path 'node_modules')) {
  Run npm "install"
}

Write-Host "[3/4] Build installer (NSIS)" -ForegroundColor Yellow
Run npm "run build"

Write-Host "[4/4] Result" -ForegroundColor Green
$installer = Join-Path $electronDir 'dist\KomodoHub-Setup-0.1.0.exe'
if (Test-Path $installer) {
  Write-Host "Installer created: $installer" -ForegroundColor Green
} else {
  Write-Warning "Installer not found in dist. Check the build logs above for errors (often symlink permissions)."
}
Pop-Location

