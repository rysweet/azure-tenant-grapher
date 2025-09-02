// Test setup file for Jest
import '@testing-library/jest-dom';

// Mock window.electronAPI for React component tests
(global as any).window = {
  electronAPI: {
    cli: {
      execute: jest.fn(),
      cancel: jest.fn(),
      status: jest.fn(),
    },
    file: {
      read: jest.fn(),
      write: jest.fn(),
      exists: jest.fn(),
    },
    dialog: {
      openFile: jest.fn(),
      saveFile: jest.fn(),
      openDirectory: jest.fn(),
    },
    config: {
      get: jest.fn(),
      set: jest.fn(),
      delete: jest.fn(),
      clear: jest.fn(),
    },
    env: {
      get: jest.fn(),
      getAll: jest.fn(),
    },
    system: {
      openExternal: jest.fn(),
      showItemInFolder: jest.fn(),
      platform: jest.fn(),
    },
    process: {
      list: jest.fn(),
      cleanup: jest.fn(),
    },
    window: {
      minimize: jest.fn(),
      maximize: jest.fn(),
      close: jest.fn(),
    },
    on: jest.fn(),
    off: jest.fn(),
  },
};
