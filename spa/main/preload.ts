import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // CLI operations
  cli: {
    execute: (command: string, args: string[]) =>
      ipcRenderer.invoke('cli:execute', command, args),
    cancel: (processId: string) =>
      ipcRenderer.invoke('cli:cancel', processId),
    status: (processId: string) =>
      ipcRenderer.invoke('cli:status', processId),
  },

  // File operations
  file: {
    read: (filePath: string) =>
      ipcRenderer.invoke('file:read', filePath),
    write: (filePath: string, content: string) =>
      ipcRenderer.invoke('file:write', filePath, content),
    exists: (filePath: string) =>
      ipcRenderer.invoke('file:exists', filePath),
  },

  // Dialog operations
  dialog: {
    openFile: (options?: any) =>
      ipcRenderer.invoke('dialog:openFile', options),
    saveFile: (options?: any) =>
      ipcRenderer.invoke('dialog:saveFile', options),
    openDirectory: (options?: any) =>
      ipcRenderer.invoke('dialog:openDirectory', options),
    showOpenDialog: (options?: any) =>
      ipcRenderer.invoke('dialog:showOpenDialog', options),
  },

  // Configuration
  config: {
    get: (key: string) =>
      ipcRenderer.invoke('config:get', key),
    set: (key: string, value: any) =>
      ipcRenderer.invoke('config:set', key, value),
    delete: (key: string) =>
      ipcRenderer.invoke('config:delete', key),
    clear: () =>
      ipcRenderer.invoke('config:clear'),
  },

  // Environment
  env: {
    get: (key: string) =>
      ipcRenderer.invoke('env:get', key),
    getAll: () =>
      ipcRenderer.invoke('env:getAll'),
  },

  // System operations
  system: {
    openExternal: (url: string) =>
      ipcRenderer.invoke('system:openExternal', url),
    showItemInFolder: (filePath: string) =>
      ipcRenderer.invoke('system:showItemInFolder', filePath),
    platform: () =>
      ipcRenderer.invoke('system:platform'),
  },

  // Shell operations (for opening folders)
  shell: {
    openPath: (path: string) =>
      ipcRenderer.invoke('shell:openPath', path),
  },

  // Process management
  process: {
    list: () =>
      ipcRenderer.invoke('process:list'),
    cleanup: () =>
      ipcRenderer.invoke('process:cleanup'),
  },

  // Window controls
  window: {
    minimize: () => ipcRenderer.send('window:minimize'),
    maximize: () => ipcRenderer.send('window:maximize'),
    close: () => ipcRenderer.send('window:close'),
    resize: (width: number, height: number) =>
      ipcRenderer.invoke('window:resize', width, height),
  },

  // Event listeners
  on: (channel: string, callback: (...args: any[]) => void) => {
    const validChannels = [
      'menu:new-build',
      'menu:open-spec',
      'menu:export-results',
      'menu:navigate',
      'menu:view-logs',
      'menu:run-diagnostics',
      'process:output',
      'process:exit',
      'process:error',
    ];

    if (validChannels.includes(channel)) {
      ipcRenderer.on(channel, (event, ...args) => callback(...args));
    }
  },

  off: (channel: string, callback: (...args: any[]) => void) => {
    ipcRenderer.removeListener(channel, callback);
  },
});

// Type definitions for TypeScript
export interface ElectronAPI {
  cli: {
    execute: (command: string, args: string[]) => Promise<any>;
    cancel: (processId: string) => Promise<any>;
    status: (processId: string) => Promise<any>;
  };
  file: {
    read: (filePath: string) => Promise<any>;
    write: (filePath: string, content: string) => Promise<any>;
    exists: (filePath: string) => Promise<boolean>;
  };
  dialog: {
    openFile: (options?: any) => Promise<string | null>;
    saveFile: (options?: any) => Promise<string | null>;
    openDirectory: (options?: any) => Promise<string | null>;
    showOpenDialog: (options?: any) => Promise<any>;
  };
  config: {
    get: (key: string) => Promise<any>;
    set: (key: string, value: any) => Promise<any>;
    delete: (key: string) => Promise<any>;
    clear: () => Promise<any>;
  };
  env: {
    get: (key: string) => Promise<string | undefined>;
    getAll: () => Promise<Record<string, string>>;
  };
  system: {
    openExternal: (url: string) => Promise<any>;
    showItemInFolder: (filePath: string) => Promise<any>;
    platform: () => Promise<any>;
  };
  shell: {
    openPath: (path: string) => Promise<any>;
  };
  process: {
    list: () => Promise<any[]>;
    cleanup: () => Promise<any>;
  };
  window: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    resize: (width: number, height: number) => Promise<any>;
  };
  on: (channel: string, callback: (...args: any[]) => void) => void;
  off: (channel: string, callback: (...args: any[]) => void) => void;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}
