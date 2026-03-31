const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let mainWindow;
let pythonProcess = null;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false
    },
    autoHideMenuBar: true
  });

  // Em modo DEV, carrega o Vite. Em PROD, carrega o arquivo buildado
  const isDev = !app.isPackaged;
  if (isDev) {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, 'dist', 'index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function startPythonBackend() {
  const env = { ...process.env, ELECTRON_RUN: '1', PYTHONIOENCODING: 'utf-8' };
  
  if (app.isPackaged) {
    // O electron-builder coloca o que está em extraResources dentro de process.resourcesPath
    // De acordo com seu package.json, o .exe está na raiz de resources
    const scriptPath = path.join(process.resourcesPath, 'backend_app.exe');
    
    pythonProcess = spawn(scriptPath, [], { 
      env,
      // CRITICAL: O CWD precisa ser a pasta onde o executável está para ele achar o banco de dados
      cwd: process.resourcesPath 
    });
  } else {
    const scriptPath = path.join(__dirname, '..', 'backend', 'app.py');
    const pythonExe = path.join(__dirname, '..', 'backend', 'venv', 'Scripts', 'python.exe');
    const cwdPath = path.join(__dirname, '..', 'backend');
    pythonProcess = spawn(pythonExe, [scriptPath], { env, cwd: cwdPath });
  }

pythonProcess.on('error', (err) => {
    console.error(`[Electron] ❌ ERRO CRÍTICO AO ABRIR O PYTHON:`, err);
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`[Python] ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`[Python Error] ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`[Python] Processo encerrado com código ${code}`);
  });
}
app.whenReady().then(() => {
  startPythonBackend();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Garante que o processo python feche quando o electron fechar
app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
  }
});
