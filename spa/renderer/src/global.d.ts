/// <reference types="electron" />

/**
 * Global type definitions for Electron API exposed to renderer process
 */

interface ProcessResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
  success?: boolean;
  data?: any;
  error?: string;
}

interface ElectronAPI {
  // Window controls
  window: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    resize?: (width: number, height: number) => void;
  };
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  closeWindow: () => void;

  // Process execution
  process: {
    execute: (command: string, args: string[], options?: any) => Promise<{ id: string }>;
    kill: (id: string) => Promise<void>;
    list?: () => Promise<any[]>; // Optional list method
  };
  executeCommand: (command: string, args: string[], options?: any) => Promise<{ id: string }>;
  killProcess: (id: string) => Promise<void>;
  onProcessOutput: (callback: (data: any) => void) => void;
  onProcessError: (callback: (data: any) => void) => void;
  onProcessExit: (callback: (data: any) => void) => void;
  removeProcessListeners: () => void;

  // File system
  selectFile: () => Promise<string | null>;
  selectDirectory: () => Promise<string | null>;
  readFile: (path: string) => Promise<string>;
  writeFile: (path: string, content: string) => Promise<void>;
  
  // Configuration
  config: {
    get: (key?: string) => Promise<any>;
    set: (key: string, value?: any) => Promise<void>;
  };
  getConfig: () => Promise<any>;
  setConfig: (config: any) => Promise<void>;
  
  // System info
  system: {
    getInfo: () => Promise<{
      platform: string;
      arch: string;
      version: string;
    }>;
    platform?: string; // Optional direct platform property
  };
  getSystemInfo: () => Promise<{
    platform: string;
    arch: string;
    version: string;
  }>;

  // CLI
  cli: {
    execute: (command: string, args: string[], options?: any) => Promise<ProcessResult>;
    cancel?: (id: string) => Promise<void>;
  };

  // Environment
  env: {
    get: (key: string) => Promise<string | undefined>;
    getAll?: () => Promise<Record<string, string>>;
  };

  // IPC communication
  send: (channel: string, ...args: any[]) => void;
  on: (channel: string, callback: (...args: any[]) => void) => void;
  once: (channel: string, callback: (...args: any[]) => void) => void;
  off?: (channel: string, callback?: (...args: any[]) => void) => void;
  removeAllListeners: (channel: string) => void;
  
  // Dialog
  dialog?: {
    showOpenDialog: (options: any) => Promise<any>;
    showSaveDialog: (options: any) => Promise<any>;
    openFile?: (options: any) => Promise<any>;
    saveFile?: (options: any) => Promise<any>;
  };
  
  // File operations
  file?: {
    read: (path: string) => Promise<string>;
    write: (path: string, content: string) => Promise<void>;
    exists: (path: string) => Promise<boolean>;
  };
  
  // Shell operations
  shell?: {
    openExternal: (url: string) => Promise<void>;
    openPath: (path: string) => Promise<void>;
  };
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};