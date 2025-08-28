import { app, BrowserWindow, ipcMain, Menu } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import { setupIPCHandlers } from './ipc-handlers';
import { ProcessManager } from './process-manager';
import { createApplicationMenu } from './menu';

let mainWindow: BrowserWindow | null = null;
let processManager: ProcessManager;
let backendProcess: ChildProcess | null = null;

async function createWindow() {
  const iconPath = path.join(__dirname, '../../assets/icon.png');
  const windowOptions: any = {
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 768,
    title: 'Azure Tenant Grapher',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#1e1e1e',
  };
  
  // Only set icon if it exists
  if (fs.existsSync(iconPath)) {
    windowOptions.icon = iconPath;
  }
  
  mainWindow = new BrowserWindow(windowOptions);

  // Set application menu
  const menu = createApplicationMenu(mainWindow);
  Menu.setApplicationMenu(menu);

  // Load the app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle window controls
  ipcMain.on('window:minimize', () => mainWindow?.minimize());
  ipcMain.on('window:maximize', () => {
    if (mainWindow?.isMaximized()) {
      mainWindow.unmaximize();
    } else {
      mainWindow?.maximize();
    }
  });
  ipcMain.on('window:close', () => mainWindow?.close());
}

// Start the backend server
function startBackendServer() {
  console.log('Starting backend server...');
  
  const backendPath = path.join(__dirname, '../backend/server.js');
  const tsxPath = path.join(__dirname, '../../node_modules/.bin/tsx');
  
  // Check if we're in development mode
  if (process.env.NODE_ENV === 'development' || !require('fs').existsSync(backendPath)) {
    // Use tsx to run TypeScript directly in development
    const backendTsPath = path.join(__dirname, '../../backend/src/server.ts');
    backendProcess = spawn('npx', ['tsx', backendTsPath], {
      cwd: path.join(__dirname, '../..'),
      env: {
        ...process.env,
        BACKEND_PORT: '3001',
        NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
        NEO4J_USER: process.env.NEO4J_USER || 'neo4j',
        NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || 'azure-grapher-2024'
      }
    });
  } else {
    // Use compiled JavaScript in production
    backendProcess = spawn('node', [backendPath], {
      env: {
        ...process.env,
        BACKEND_PORT: '3001',
        NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7687',
        NEO4J_USER: process.env.NEO4J_USER || 'neo4j',
        NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || 'azure-grapher-2024'
      }
    });
  }

  backendProcess.stdout?.on('data', (data) => {
    console.log(`Backend: ${data}`);
  });

  backendProcess.stderr?.on('data', (data) => {
    console.error(`Backend Error: ${data}`);
  });

  backendProcess.on('error', (error) => {
    console.error('Failed to start backend:', error);
  });

  backendProcess.on('close', (code) => {
    console.log(`Backend process exited with code ${code}`);
    backendProcess = null;
  });
}

// Set app name
app.setName('Azure Tenant Grapher');

// Set app ID for notifications and system integration
if (process.platform === 'darwin') {
  const iconPath = path.join(__dirname, '../../assets/icon.png');
  if (fs.existsSync(iconPath)) {
    try {
      app.dock.setIcon(iconPath);
    } catch (error) {
      console.warn('Failed to set dock icon:', error);
    }
  }
}

app.whenReady().then(async () => {
  // Start backend server
  startBackendServer();
  
  // Initialize process manager
  processManager = new ProcessManager();
  
  // Setup IPC handlers
  setupIPCHandlers(processManager);
  
  // Create the main window after a short delay to ensure backend is starting
  setTimeout(async () => {
    await createWindow();
  }, 1000);

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Cleanup all processes
  processManager.cleanup();
  
  // Stop backend server
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
  }
  
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('before-quit', (event) => {
  // Ensure all processes are terminated
  if (!processManager.isCleanedUp()) {
    event.preventDefault();
    processManager.cleanup().then(() => app.quit());
  }
  
  // Stop backend server
  if (backendProcess) {
    backendProcess.kill('SIGTERM');
  }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  processManager.cleanup();
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Handle process termination signals for clean shutdown
process.on('SIGINT', () => {
  processManager.cleanup().then(() => {
    app.quit();
  });
});

process.on('SIGTERM', () => {
  processManager.cleanup().then(() => {
    app.quit();
  });
});