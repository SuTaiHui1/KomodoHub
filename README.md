# Komodo Hub — Lite (FastAPI + Jinja2)

Minimal species reporting platform for learning purposes.

## Features
- Register, login, logout (cookie session)
- Submit species reports with up to 3 images
- Public page lists approved reports, search by title/species
- Admin review (approve/reject with note)
- SQLite storage, local media under `media/`

## Quickstart

1) Install dependencies
```
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2) Seed data (creates admin and sample reports)
```
python scripts/seed.py
```

3) Run
```
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

Admin login: `admin@example.com` / `admin123`

## Notes
- Media uploads stored under `media/uploads/YYYY/MM/`. Allowed: JPEG/PNG, max 5MB.
- This code autogenerates tables on startup; no migrations needed for the course demo.
- Keep `SessionMiddleware` secret in env for non-demo usage.

## Desktop App (Windows)

There are two ways to run the desktop version (Electron wrapper):

1) Portable (no installer, fastest to try)
- Build & run:
  - `scripts\build_desktop_portable.ps1`
- It produces `desktop\electron\dist\win-unpacked\Komodo Hub.exe` and launches the app.

2) Installer (NSIS)
- Pre-req: Node.js LTS (v20+) and Python deps installed.
- Build installer:
  - `scripts\build_desktop_installer.ps1`
- Result: `desktop\electron\dist\KomodoHub-Setup-0.1.0.exe`.

If Electron downloads are slow/failing, set mirrors (PowerShell):
```
cd desktop\electron
npm config set registry https://registry.npmmirror.com
$env:ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"
$env:ELECTRON_BUILDER_BINARIES_MIRROR="https://npmmirror.com/mirrors/electron-builder-binaries/"
npm install
```

## GitHub Releases (CI)

This repo includes a GitHub Actions workflow to build and attach Windows artifacts to a Release automatically.

- Trigger a release build:
  - Create a tag, e.g. `v0.1.0`, and push it:
    - `git tag v0.1.0 && git push origin v0.1.0`
  - The workflow `.github/workflows/build-desktop.yml` will:
    - Build the backend EXE via PyInstaller
    - Build the Electron installer (NSIS)
    - Zip a portable folder
    - Upload both as release assets

Users can then download the installer (`KomodoHub-Setup-*.exe`) or the portable zip from the Releases page and run directly, no local build required.

