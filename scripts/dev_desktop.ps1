param(
    [int]$Port = 18555
)

# Start backend
Start-Process -FilePath python -ArgumentList "run_backend.py $Port" -WindowStyle Hidden
Start-Sleep -Seconds 2

# Start Electron (requires npm install in desktop/electron)
Push-Location desktop/electron
if (-Not (Test-Path node_modules)) { npm install }
npm run start
Pop-Location

