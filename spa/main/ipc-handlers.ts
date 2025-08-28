import { ipcMain, dialog, shell } from 'electron';
import * as fs from 'fs/promises';
import * as path from 'path';
import { ProcessManager } from './process-manager';
import Store from 'electron-store';

const store = new Store();

export function setupIPCHandlers(processManager: ProcessManager) {
  // CLI command execution
  ipcMain.handle('cli:execute', async (event, command: string, args: string[]) => {
    try {
      const result = await processManager.execute(command, args);
      return { success: true, data: result };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('cli:cancel', async (event, processId: string) => {
    try {
      await processManager.cancel(processId);
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('cli:status', async (event, processId: string) => {
    return processManager.getStatus(processId);
  });

  // File operations
  ipcMain.handle('file:read', async (event, filePath: string) => {
    try {
      const content = await fs.readFile(filePath, 'utf-8');
      return { success: true, data: content };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('file:write', async (event, filePath: string, content: string) => {
    try {
      await fs.writeFile(filePath, content, 'utf-8');
      return { success: true };
    } catch (error) {
      return { success: false, error: error.message };
    }
  });

  ipcMain.handle('file:exists', async (event, filePath: string) => {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  });

  // Dialog operations
  ipcMain.handle('dialog:openFile', async (event, options: any) => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile'],
      ...options,
    });
    return result.canceled ? null : result.filePaths[0];
  });

  ipcMain.handle('dialog:saveFile', async (event, options: any) => {
    const result = await dialog.showSaveDialog(options);
    return result.canceled ? null : result.filePath;
  });

  ipcMain.handle('dialog:openDirectory', async (event, options: any) => {
    const result = await dialog.showOpenDialog({
      properties: ['openDirectory'],
      ...options,
    });
    return result.canceled ? null : result.filePaths[0];
  });

  // Configuration management
  ipcMain.handle('config:get', async (event, key: string) => {
    return store.get(key);
  });

  ipcMain.handle('config:set', async (event, key: string, value: any) => {
    store.set(key, value);
    return { success: true };
  });

  ipcMain.handle('config:delete', async (event, key: string) => {
    store.delete(key);
    return { success: true };
  });

  ipcMain.handle('config:clear', async () => {
    store.clear();
    return { success: true };
  });

  // Environment variables
  ipcMain.handle('env:get', async (event, key: string) => {
    return process.env[key];
  });

  ipcMain.handle('env:getAll', async () => {
    // Return only safe environment variables
    const safeEnvVars = {
      AZURE_TENANT_ID: process.env.AZURE_TENANT_ID,
      NEO4J_URI: process.env.NEO4J_URI,
      NODE_ENV: process.env.NODE_ENV,
    };
    return safeEnvVars;
  });

  // System operations
  ipcMain.handle('system:openExternal', async (event, url: string) => {
    await shell.openExternal(url);
    return { success: true };
  });

  ipcMain.handle('system:showItemInFolder', async (event, filePath: string) => {
    shell.showItemInFolder(filePath);
    return { success: true };
  });

  ipcMain.handle('system:platform', async () => {
    return {
      platform: process.platform,
      arch: process.arch,
      version: process.version,
    };
  });

  // Process information
  ipcMain.handle('process:list', async () => {
    return processManager.listProcesses();
  });

  ipcMain.handle('process:cleanup', async () => {
    await processManager.cleanup();
    return { success: true };
  });
}