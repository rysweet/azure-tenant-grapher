/// <reference types="electron" />

/**
 * Global type definitions for Electron API exposed to renderer process
 */

interface ProcessResult {
  stdout: string;
  stderr: string;
  exitCode: number | null;
}

interface ElectronAPI {
  // Window controls
  window: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
  };
  minimizeWindow: () => void;
  maximizeWindow: () => void;
  closeWindow: () => void;

  // Process execution
  process: {
    execute: (command: string, args: string[], options?: any) => Promise<{ id: string }>;
    kill: (id: string) => Promise<void>;
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
  getConfig: () => Promise<any>;
  setConfig: (config: any) => Promise<void>;
  
  // System info
  system: {
    getInfo: () => Promise<{
      platform: string;
      arch: string;
      version: string;
    }>;
  };
  getSystemInfo: () => Promise<{
    platform: string;
    arch: string;
    version: string;
  }>;

  // IPC communication
  send: (channel: string, ...args: any[]) => void;
  on: (channel: string, callback: (...args: any[]) => void) => void;
  once: (channel: string, callback: (...args: any[]) => void) => void;
  removeAllListeners: (channel: string) => void;
}

declare global {
  interface Window {
    electronAPI: ElectronAPI;
  }
}

export {};