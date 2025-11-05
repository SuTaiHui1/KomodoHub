const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let pythonProc = null;
const PORT = process.env.KOMODO_PORT || '18555';

function startBackend() {
  // Prefer packaged EXE
  const useExe = true;
  if (useExe) {
    // In packaged app: exe copied to resourcesPath; in dev: place exe next to this file
    const exePath = app.isPackaged
      ? path.join(process.resourcesPath, 'KomodoHubBackend.exe')
      : path.join(__dirname, 'KomodoHubBackend.exe');
    pythonProc = spawn(exePath, [PORT], { stdio: 'inherit' });
  } else {
    const py = process.platform === 'win32' ? 'python' : 'python3';
    // Run backend from repo root
    const backendCwd = path.resolve(__dirname, '..', '..');
    pythonProc = spawn(py, ['run_backend.py', PORT], { cwd: backendCwd, stdio: 'inherit' });
  }
}

function waitForServer(retries = 50) {
  return new Promise((resolve, reject) => {
    const http = require('http');
    const check = () => {
      const req = http.get(`http://127.0.0.1:${PORT}/`, res => {
        resolve();
      });
      req.on('error', () => {
        if (retries-- > 0) setTimeout(check, 200);
        else reject(new Error('Backend not responding'));
      });
    };
    check();
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js')
    }
  });
  win.loadURL(`http://127.0.0.1:${PORT}/`);
}

app.whenReady().then(async () => {
  startBackend();
  try {
    await waitForServer();
  } catch (e) {
    console.error(e);
  }
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('quit', () => {
  if (pythonProc) {
    try { pythonProc.kill(); } catch {}
  }
});
