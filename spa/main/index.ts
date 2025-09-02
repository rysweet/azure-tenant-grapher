import { app, BrowserWindow, ipcMain, Menu } from 'electron';
import * as path from 'path';
import * as fs from 'fs';
import { spawn, ChildProcess } from 'child_process';
import { setupIPCHandlers } from './ipc-handlers';
import { ProcessManager } from './process-manager';
import { createApplicationMenu } from './menu';
import * as dotenv from 'dotenv';

// Load .env file from the project root
const envPath = path.join(__dirname, '../../../.env');
dotenv.config({ path: envPath });

let mainWindow: BrowserWindow | null = null;
let processManager: ProcessManager;
let backendProcess: ChildProcess | null = null;
let mcpServerProcess: ChildProcess | null = null;

async function createWindow() {
  const iconPath = path.join(__dirname, '../../assets/icon.png');
  const windowOptions: any = {
    width: 1600,
    height: 1000,
    minWidth: 1200,
    minHeight: 800,
    resizable: true,
    maximizable: true,
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

// Start the MCP server
async function startMcpServer() {
  const projectRoot = path.join(__dirname, '../../..');
  const pythonPath = path.join(projectRoot, '.venv', 'bin', 'python');
  const scriptPath = path.join(projectRoot, 'scripts', 'cli.py');
  
  console.log('Starting MCP server from:', projectRoot);
  
  // Ensure outputs directory exists
  const pidFile = path.join(projectRoot, 'outputs', 'mcp_server.pid');
  const statusFile = path.join(projectRoot, 'outputs', 'mcp_server.status');
  const outputsDir = path.dirname(pidFile);
  
  try {
    fs.mkdirSync(outputsDir, { recursive: true });
    
    // Clean up any stale PID file
    if (fs.existsSync(pidFile)) {
      try {
        const oldPid = parseInt(fs.readFileSync(pidFile, 'utf-8').trim());
        // Try to kill old process if it exists
        try {
          process.kill(oldPid, 0); // Check if process exists
          process.kill(oldPid, 'SIGTERM'); // Kill it
          console.log(`Killed stale MCP server with PID ${oldPid}`);
        } catch (e) {
          // Process doesn't exist, which is fine
        }
      } catch (e) {
        // Ignore errors reading old PID
      }
      fs.unlinkSync(pidFile);
    }
    
    // Clean up status file
    if (fs.existsSync(statusFile)) {
      fs.unlinkSync(statusFile);
    }
  } catch (err) {
    console.error('Error preparing for MCP server:', err);
  }
  
  // Start MCP server as a persistent service with healthcheck
  // Use the mcp_service module that provides HTTP healthcheck
  mcpServerProcess = spawn(pythonPath, ['-m', 'src.mcp_service'], {
    cwd: projectRoot,
    env: {
      ...process.env,
      PYTHONPATH: projectRoot,
      NEO4J_URI: process.env.NEO4J_URI || 'bolt://localhost:7688',
      NEO4J_PORT: process.env.NEO4J_PORT || '7688',
      NEO4J_PASSWORD: process.env.NEO4J_PASSWORD || 'azure-grapher-2024'
    },
    detached: false,
    stdio: ['ignore', 'pipe', 'pipe']  // MCP service doesn't need stdin
  });

  if (!mcpServerProcess || !mcpServerProcess.pid) {
    console.error('Failed to spawn MCP server process');
    return;
  }

  console.log(`MCP server started with PID: ${mcpServerProcess.pid}`);
  
  // Write PID and initial status file
  try {
    fs.writeFileSync(pidFile, mcpServerProcess.pid.toString());
    fs.writeFileSync(statusFile, 'starting');
    console.log(`MCP PID file written to: ${pidFile}`);
  } catch (err) {
    console.error('Failed to write MCP files:', err);
  }

  let mcpReady = false;
  
  mcpServerProcess.stdout?.on('data', (data) => {
    const output = data.toString();
    console.log(`MCP Server: ${output}`);
    
    // Check for ready messages - MCP service or healthcheck
    if (!mcpReady && (output.includes('MCP service is ready') || 
                      output.includes('Healthcheck available') ||
                      output.includes('healthcheck server running'))) {
      mcpReady = true;
      const statusFile = path.join(projectRoot, 'outputs', 'mcp_server.status');
      try {
        fs.writeFileSync(statusFile, 'ready');
        console.log('MCP server is ready with healthcheck!');
      } catch (e) {
        console.error('Failed to update MCP status file:', e);
      }
    }
  });

  mcpServerProcess.stderr?.on('data', (data) => {
    const error = data.toString();
    // Log but don't treat all stderr as errors - some tools use stderr for info
    console.log(`MCP Server (stderr): ${error}`);
  });

  mcpServerProcess.on('error', (error) => {
    console.error('Failed to start MCP server:', error);
    // Clean up PID file on error
    const pidFile = path.join(projectRoot, 'outputs', 'mcp_server.pid');
    if (fs.existsSync(pidFile)) {
      fs.unlinkSync(pidFile);
    }
  });

  mcpServerProcess.on('close', (code) => {
    if (code !== 0) {
      console.error(`MCP server process exited with code ${code}`);
    }
    
    // Clean up PID and status files
    const pidFile = path.join(projectRoot, 'outputs', 'mcp_server.pid');
    const statusFile = path.join(projectRoot, 'outputs', 'mcp_server.status');
    
    try {
      if (fs.existsSync(pidFile)) {
        fs.unlinkSync(pidFile);
      }
      if (fs.existsSync(statusFile)) {
        fs.unlinkSync(statusFile);
      }
    } catch (e) {
      console.error('Error cleaning up MCP files:', e);
    }
    
    mcpServerProcess = null;
  });
}

// Start the backend server
function startBackendServer() {
  
  const backendPath = path.join(__dirname, '../backend/src/server.js');
  const tsxPath = path.join(__dirname, '../../node_modules/.bin/tsx');
  
  // Check if we're in development mode
  if (process.env.NODE_ENV === 'development' || !require('fs').existsSync(backendPath)) {
    // Use tsx to run TypeScript directly in development
    const backendTsPath = path.join(__dirname, '../backend/src/server.ts');
    
    backendProcess = spawn('npx', ['tsx', backendTsPath], {
      cwd: path.join(__dirname, '..'),
      env: {
        ...process.env,
        BACKEND_PORT: '3001'
        // Pass through all environment variables as-is from the parent process
      }
    });
  } else {
    // Use compiled JavaScript in production
    backendProcess = spawn('node', [backendPath], {
      env: {
        ...process.env,
        BACKEND_PORT: '3001'
        // Pass through all environment variables as-is from the parent process
      }
    });
  }

  if (!backendProcess) {
    console.error('Failed to spawn backend process');
    return;
  }

  backendProcess.stdout?.on('data', (data) => {
    // Backend output handled by backend logger
  });

  backendProcess.stderr?.on('data', (data) => {
    console.error(`Backend Error: ${data}`);
  });

  backendProcess.on('error', (error) => {
    console.error('Failed to start backend:', error);
  });

  backendProcess.on('close', (code) => {
    if (code !== 0) {
      console.error(`Backend process exited with code ${code}`);
    }
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
      // Silently handle dock icon errors
    }
  }
}

app.whenReady().then(async () => {
  // Start backend server
  startBackendServer();
  
  // Start MCP server
  await startMcpServer();
  
  // Wait for MCP server to be ready by checking status file
  const projectRoot = path.join(__dirname, '../../..');
  const statusFile = path.join(projectRoot, 'outputs', 'mcp_server.status');
  let mcpAttempts = 0;
  
  console.log('Waiting for MCP server to be ready...');
  while (mcpAttempts < 20) { // Wait up to 10 seconds
    if (fs.existsSync(statusFile)) {
      const status = fs.readFileSync(statusFile, 'utf-8').trim();
      if (status === 'ready') {
        console.log('MCP server confirmed ready');
        break;
      }
    }
    await new Promise(resolve => setTimeout(resolve, 500));
    mcpAttempts++;
  }
  
  if (mcpAttempts >= 20) {
    console.warn('MCP server may not be fully ready yet');
  }
  
  // Initialize process manager
  processManager = new ProcessManager();
  
  // Forward ProcessManager events to renderer
  processManager.on('output', (data) => {
    console.log('[Main] Forwarding output event:', data);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('process:output', data);
    }
  });
  
  processManager.on('process:exit', (data) => {
    console.log('[Main] Forwarding exit event:', data);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('process:exit', data);
    }
  });
  
  processManager.on('process:error', (data) => {
    console.log('[Main] Forwarding error event:', data);
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('process:error', data);
    }
  });
  
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
  
  // Stop MCP server
  if (mcpServerProcess) {
    mcpServerProcess.kill('SIGTERM');
    // Clean up PID file
    const pidFile = path.join(__dirname, '../../../outputs/mcp_server.pid');
    if (fs.existsSync(pidFile)) {
      fs.unlinkSync(pidFile);
    }
  }
  
  // Always quit the app when the window is closed
  // This is a single-window application, so we want it to fully quit
  app.quit();
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
  
  // Stop MCP server
  if (mcpServerProcess) {
    mcpServerProcess.kill('SIGTERM');
    // Clean up PID file
    const pidFile = path.join(__dirname, '../../../outputs/mcp_server.pid');
    if (fs.existsSync(pidFile)) {
      fs.unlinkSync(pidFile);
    }
  }
});

// Handle uncaught exceptions
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
  processManager.cleanup();
  if (mcpServerProcess) {
    mcpServerProcess.kill('SIGTERM');
  }
});

process.on('unhandledRejection', (reason, promise) => {
  console.error('Unhandled Rejection at:', promise, 'reason:', reason);
});

// Handle process termination signals for clean shutdown
process.on('SIGINT', () => {
  processManager.cleanup().then(() => {
    if (mcpServerProcess) {
      mcpServerProcess.kill('SIGTERM');
    }
    app.quit();
  });
});

process.on('SIGTERM', () => {
  processManager.cleanup().then(() => {
    if (mcpServerProcess) {
      mcpServerProcess.kill('SIGTERM');
    }
    app.quit();
  });
});