const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
let mainWindow = null;
let pythonProcess = null;
function findPython() {
  const candidates = ['python', 'python3', 'py'];
  return candidates[0]; 
}
function killProcessOnPort(port) {
  if (process.platform === 'win32') {
    try {
      const result = execSync(`netstat -ano | findstr :${port} | findstr LISTENING`, { encoding: 'utf8' });
      const lines = result.trim().split('\n');
      for (const line of lines) {
        const parts = line.trim().split(/\s+/);
        const pid = parts[parts.length - 1];
        if (pid && pid !== '0') {
          try {
            execSync(`taskkill /F /PID ${pid}`);
            console.log(`[Main] Killed stale process on port ${port} (PID ${pid})`);
          } catch (e) {
          }
        }
      }
    } catch (e) {
    }
  }
}
function startPythonBackend() {
  killProcessOnPort(8765);
  const pythonExe = process.env.PYTHON_PATH || findPython();
  const serverScript = path.join(__dirname, 'backend', 'server.py');
  const modelPath = process.env.YOLO_MODEL || path.join(__dirname, 'backend', 'best.pt');
  const args = [
    serverScript,
    '--model', modelPath,
    '--port', '8765',
    '--camera', process.env.CAMERA_INDEX || '0',
  ];
  console.log(`[Main] Starting Python backend: ${pythonExe} ${args.join(' ')}`);
  pythonProcess = spawn(pythonExe, args, {
    cwd: path.join(__dirname, 'backend'),
    stdio: ['pipe', 'pipe', 'pipe'],
  });
  pythonProcess.stdout.on('data', (data) => {
    const msg = data.toString().trim();
    console.log(`[Python] ${msg}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('python-log', msg);
    }
  });
  pythonProcess.stderr.on('data', (data) => {
    const msg = data.toString().trim();
    console.error(`[Python:ERR] ${msg}`);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('python-error', msg);
    }
  });
  pythonProcess.on('exit', (code) => {
    console.log(`[Main] Python process exited with code ${code}`);
    pythonProcess = null;
  });
  pythonProcess.on('error', (err) => {
    console.error(`[Main] Failed to start Python:`, err.message);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('python-error', `Failed to start Python: ${err.message}`);
    }
  });
}
function stopPythonBackend() {
  if (pythonProcess) {
    console.log('[Main] Stopping Python backend...');
    if (process.platform === 'win32') {
      const { exec } = require('child_process');
      exec(`taskkill /pid ${pythonProcess.pid} /T /F`);
    } else {
      pythonProcess.kill('SIGTERM');
    }
    pythonProcess = null;
  }
}
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 700,
    backgroundColor: '#0a0a0f',
    frame: false,
    titleBarStyle: 'hidden',
    titleBarOverlay: {
      color: '#0a0a0f',
      symbolColor: '#8888aa',
      height: 36,
    },
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    icon: path.join(__dirname, 'renderer', 'icon.png'),
    show: false,
  });
  mainWindow.loadFile(path.join(__dirname, 'renderer', 'index.html'));
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });
  setTimeout(() => {
    if (mainWindow && !mainWindow.isDestroyed() && !mainWindow.isVisible()) {
      console.log('[Main] Forcing window visible (ready-to-show timeout)');
      mainWindow.show();
    }
  }, 3000);
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}
ipcMain.handle('restart-python', () => {
  stopPythonBackend();
  setTimeout(() => startPythonBackend(), 1000);
  return { success: true };
});
ipcMain.handle('get-app-info', () => {
  return {
    version: app.getVersion(),
    pythonRunning: pythonProcess !== null,
    platform: process.platform,
  };
});
ipcMain.on('minimize-window', () => {
  mainWindow?.minimize();
});
ipcMain.on('maximize-window', () => {
  if (mainWindow?.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow?.maximize();
  }
});
ipcMain.on('close-window', () => {
  mainWindow?.close();
});
app.whenReady().then(() => {
  createWindow();
  startPythonBackend();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});
app.on('window-all-closed', () => {
  stopPythonBackend();
  app.quit();
});
app.on('before-quit', () => {
  stopPythonBackend();
});