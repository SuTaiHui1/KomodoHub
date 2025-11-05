param(
    [int]$Port = 18555
)

# Ensure venv is active before running this script
# Install PyInstaller if not present
pip show pyinstaller *> $null
if ($LASTEXITCODE -ne 0) {
    pip install pyinstaller
}

# Build onefile EXE including app modules, templates, and data
pyinstaller --noconfirm --clean `
  --onefile --name KomodoHubBackend `
  --hidden-import app.main `
  --hidden-import app.models `
  --hidden-import app.db `
  --hidden-import app.utils `
  --hidden-import app.security `
  --add-data "app/templates;app/templates" `
  --add-data "data;data" `
  run_backend.py

# Copy EXE next to Electron main.js for dev/start
Copy-Item -Force dist\KomodoHubBackend.exe desktop\electron\KomodoHubBackend.exe
Write-Host "Built KomodoHubBackend.exe and copied to desktop\electron."

