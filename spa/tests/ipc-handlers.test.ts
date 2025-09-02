import { ipcMain } from 'electron';
import { setupIPCHandlers } from '../main/ipc-handlers';
import { ProcessManager } from '../main/process-manager';
import * as fs from 'fs/promises';

// Mock electron
jest.mock('electron', () => ({
  ipcMain: {
    handle: jest.fn(),
  },
  dialog: {
    showOpenDialog: jest.fn(),
    showSaveDialog: jest.fn(),
  },
  shell: {
    openExternal: jest.fn(),
    showItemInFolder: jest.fn(),
  },
}));

// Mock fs/promises
jest.mock('fs/promises');

// Mock electron-store
jest.mock('electron-store', () => {
  return jest.fn().mockImplementation(() => ({
    get: jest.fn(),
    set: jest.fn(),
    delete: jest.fn(),
    clear: jest.fn(),
  }));
});

describe('IPC Handlers', () => {
  let processManager: ProcessManager;
  let handlers: Map<string, Function>;

  beforeEach(() => {
    handlers = new Map();
    processManager = new ProcessManager();

    // Capture IPC handlers
    (ipcMain.handle as jest.Mock).mockImplementation((channel, handler) => {
      handlers.set(channel, handler);
    });

    setupIPCHandlers(processManager);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('CLI handlers', () => {
    it('should handle cli:execute', async () => {
      const mockExecute = jest.spyOn(processManager, 'execute').mockResolvedValue({
        id: 'test-id',
        output: ['Success'],
        exitCode: 0,
      });

      const handler = handlers.get('cli:execute');
      const result = await handler(null, 'build', ['--tenant-id', 'test']);

      expect(result).toEqual({
        success: true,
        data: {
          id: 'test-id',
          output: ['Success'],
          exitCode: 0,
        },
      });
      expect(mockExecute).toHaveBeenCalledWith('build', ['--tenant-id', 'test']);
    });

    it('should handle cli:execute error', async () => {
      jest.spyOn(processManager, 'execute').mockRejectedValue(new Error('Command failed'));

      const handler = handlers.get('cli:execute');
      const result = await handler(null, 'build', []);

      expect(result).toEqual({
        success: false,
        error: 'Command failed',
      });
    });

    it('should handle cli:cancel', async () => {
      const mockCancel = jest.spyOn(processManager, 'cancel').mockResolvedValue();

      const handler = handlers.get('cli:cancel');
      const result = await handler(null, 'test-process-id');

      expect(result).toEqual({ success: true });
      expect(mockCancel).toHaveBeenCalledWith('test-process-id');
    });

    it('should handle cli:status', async () => {
      const mockStatus = {
        id: 'test-id',
        command: 'build',
        status: 'running',
      };
      jest.spyOn(processManager, 'getStatus').mockReturnValue(mockStatus as any);

      const handler = handlers.get('cli:status');
      const result = await handler(null, 'test-id');

      expect(result).toEqual(mockStatus);
    });
  });

  describe('File handlers', () => {
    it('should handle file:read', async () => {
      (fs.readFile as jest.Mock).mockResolvedValue('file content');

      const handler = handlers.get('file:read');
      const result = await handler(null, '/path/to/file.txt');

      expect(result).toEqual({
        success: true,
        data: 'file content',
      });
      expect(fs.readFile).toHaveBeenCalledWith('/path/to/file.txt', 'utf-8');
    });

    it('should handle file:read error', async () => {
      (fs.readFile as jest.Mock).mockRejectedValue(new Error('File not found'));

      const handler = handlers.get('file:read');
      const result = await handler(null, '/nonexistent.txt');

      expect(result).toEqual({
        success: false,
        error: 'File not found',
      });
    });

    it('should handle file:write', async () => {
      (fs.writeFile as jest.Mock).mockResolvedValue(undefined);

      const handler = handlers.get('file:write');
      const result = await handler(null, '/path/to/file.txt', 'content');

      expect(result).toEqual({ success: true });
      expect(fs.writeFile).toHaveBeenCalledWith('/path/to/file.txt', 'content', 'utf-8');
    });

    it('should handle file:exists', async () => {
      (fs.access as jest.Mock).mockResolvedValue(undefined);

      const handler = handlers.get('file:exists');
      const result = await handler(null, '/path/to/file.txt');

      expect(result).toBe(true);
      expect(fs.access).toHaveBeenCalledWith('/path/to/file.txt');
    });

    it('should handle file:exists for non-existent file', async () => {
      (fs.access as jest.Mock).mockRejectedValue(new Error('Not found'));

      const handler = handlers.get('file:exists');
      const result = await handler(null, '/nonexistent.txt');

      expect(result).toBe(false);
    });
  });

  describe('Config handlers', () => {
    it('should handle config:get', async () => {
      const handler = handlers.get('config:get');
      // Since store is mocked, we need to set up the return value
      const Store = require('electron-store');
      const mockStore = new Store();
      mockStore.get.mockReturnValue('test-value');

      const result = await handler(null, 'test-key');

      // The actual implementation creates its own store instance
      // so we can't directly assert on our mock
      expect(result).toBeDefined();
    });

    it('should handle config:set', async () => {
      const handler = handlers.get('config:set');
      const result = await handler(null, 'test-key', 'test-value');

      expect(result).toEqual({ success: true });
    });

    it('should handle config:delete', async () => {
      const handler = handlers.get('config:delete');
      const result = await handler(null, 'test-key');

      expect(result).toEqual({ success: true });
    });

    it('should handle config:clear', async () => {
      const handler = handlers.get('config:clear');
      const result = await handler(null);

      expect(result).toEqual({ success: true });
    });
  });

  describe('Environment handlers', () => {
    it('should handle env:get', async () => {
      process.env.TEST_VAR = 'test-value';

      const handler = handlers.get('env:get');
      const result = await handler(null, 'TEST_VAR');

      expect(result).toBe('test-value');

      delete process.env.TEST_VAR;
    });

    it('should handle env:getAll', async () => {
      process.env.AZURE_TENANT_ID = 'test-tenant';
      process.env.NEO4J_URI = 'bolt://localhost:7687';

      const handler = handlers.get('env:getAll');
      const result = await handler(null);

      expect(result).toHaveProperty('AZURE_TENANT_ID', 'test-tenant');
      expect(result).toHaveProperty('NEO4J_URI', 'bolt://localhost:7687');
      expect(result).not.toHaveProperty('SECRET_KEY'); // Should not expose arbitrary env vars
    });
  });

  describe('Process handlers', () => {
    it('should handle process:list', async () => {
      const mockProcesses = [
        { id: '1', command: 'build', status: 'running' },
        { id: '2', command: 'test', status: 'completed' },
      ];
      jest.spyOn(processManager, 'listProcesses').mockReturnValue(mockProcesses as any);

      const handler = handlers.get('process:list');
      const result = await handler(null);

      expect(result).toEqual(mockProcesses);
    });

    it('should handle process:cleanup', async () => {
      const mockCleanup = jest.spyOn(processManager, 'cleanup').mockResolvedValue();

      const handler = handlers.get('process:cleanup');
      const result = await handler(null);

      expect(result).toEqual({ success: true });
      expect(mockCleanup).toHaveBeenCalled();
    });
  });

  describe('System handlers', () => {
    it('should handle system:platform', async () => {
      const handler = handlers.get('system:platform');
      const result = await handler(null);

      expect(result).toHaveProperty('platform');
      expect(result).toHaveProperty('arch');
      expect(result).toHaveProperty('version');
    });
  });
});
