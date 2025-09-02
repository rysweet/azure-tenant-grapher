import { ProcessManager } from '../main/process-manager';
import { spawn } from 'child_process';
import { EventEmitter } from 'events';

// Mock child_process
jest.mock('child_process');

describe('ProcessManager', () => {
  let processManager: ProcessManager;
  let mockProcess: any;

  beforeEach(() => {
    processManager = new ProcessManager();

    // Create mock process
    mockProcess = new EventEmitter();
    mockProcess.stdout = new EventEmitter();
    mockProcess.stderr = new EventEmitter();
    mockProcess.kill = jest.fn();
    mockProcess.killed = false;
    mockProcess.pid = 12345;

    // Mock spawn
    (spawn as jest.Mock).mockReturnValue(mockProcess);
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  describe('execute', () => {
    it('should execute a command successfully', async () => {
      const executePromise = processManager.execute('build', ['--tenant-id', 'test']);

      // Simulate successful execution
      setTimeout(() => {
        mockProcess.stdout.emit('data', Buffer.from('Building graph...\n'));
        mockProcess.emit('exit', 0);
      }, 10);

      const result = await executePromise;

      expect(result).toHaveProperty('id');
      expect(result.output).toContain('Building graph...');
      expect(result.exitCode).toBe(0);
      expect(spawn).toHaveBeenCalledWith(
        expect.any(String),
        expect.arrayContaining(['build', '--tenant-id', 'test']),
        expect.objectContaining({
          cwd: expect.any(String),
          env: expect.objectContaining({
            PYTHONPATH: expect.any(String),
          }),
        })
      );
    });

    it('should handle command failure', async () => {
      const executePromise = processManager.execute('build', ['--invalid']);

      // Simulate failure
      setTimeout(() => {
        mockProcess.stderr.emit('data', Buffer.from('Error: Invalid argument\n'));
        mockProcess.emit('exit', 1);
      }, 10);

      await expect(executePromise).rejects.toThrow('Process failed with exit code 1');
    });

    it('should emit output events', (done) => {
      const outputData: any[] = [];

      processManager.on('output', (data) => {
        outputData.push(data);

        if (outputData.length === 2) {
          expect(outputData[0]).toMatchObject({
            type: 'stdout',
            data: ['stdout line'],
          });
          expect(outputData[1]).toMatchObject({
            type: 'stderr',
            data: ['stderr line'],
          });
          done();
        }
      });

      processManager.execute('test', []);

      // Emit test data
      mockProcess.stdout.emit('data', Buffer.from('stdout line\n'));
      mockProcess.stderr.emit('data', Buffer.from('stderr line\n'));
    });
  });

  describe('cancel', () => {
    it('should cancel a running process', async () => {
      const executePromise = processManager.execute('build', []);

      // Get process ID from the execute call
      setTimeout(async () => {
        const processes = processManager.listProcesses();
        expect(processes).toHaveLength(1);

        await processManager.cancel(processes[0].id);
        expect(mockProcess.kill).toHaveBeenCalledWith('SIGTERM');
      }, 10);

      // Simulate process termination after cancel
      setTimeout(() => {
        mockProcess.emit('exit', -1);
      }, 20);

      await expect(executePromise).rejects.toThrow();
    });

    it('should throw error for non-existent process', async () => {
      await expect(processManager.cancel('non-existent')).rejects.toThrow('Process non-existent not found');
    });

    it('should throw error for non-running process', async () => {
      const executePromise = processManager.execute('test', []);

      // Complete the process
      setTimeout(() => {
        mockProcess.emit('exit', 0);
      }, 10);

      await executePromise;

      const processes = processManager.listProcesses();
      await expect(processManager.cancel(processes[0].id)).rejects.toThrow('is not running');
    });
  });

  describe('cleanup', () => {
    it('should cleanup all running processes', async () => {
      // Start multiple processes
      processManager.execute('test1', []);
      processManager.execute('test2', []);

      // Allow processes to start
      await new Promise(resolve => setTimeout(resolve, 10));

      expect(processManager.listProcesses()).toHaveLength(2);

      await processManager.cleanup();

      expect(mockProcess.kill).toHaveBeenCalledWith('SIGTERM');
      expect(processManager.isCleanedUp()).toBe(true);
      expect(processManager.listProcesses()).toHaveLength(0);
    });

    it('should force kill stubborn processes', async () => {
      processManager.execute('test', []);

      // Mock process that doesn't die
      mockProcess.killed = false;

      await processManager.cleanup();

      expect(mockProcess.kill).toHaveBeenCalledWith('SIGTERM');
      // Should attempt SIGKILL after timeout
      expect(mockProcess.kill).toHaveBeenCalledWith('SIGKILL');
    });
  });

  describe('streamOutput', () => {
    it('should stream output for specific process', (done) => {
      processManager.execute('test', []).then(id => {
        const processId = id.id;

        let callCount = 0;
        const unsubscribe = processManager.streamOutput(processId, (data) => {
          callCount++;
          expect(data.id).toBe(processId);

          if (callCount === 2) {
            unsubscribe();
            done();
          }
        });
      });

      // Emit output events
      setTimeout(() => {
        mockProcess.stdout.emit('data', Buffer.from('line1\n'));
        mockProcess.stdout.emit('data', Buffer.from('line2\n'));
        mockProcess.stdout.emit('data', Buffer.from('line3\n')); // Should not be received
      }, 10);
    });
  });

  describe('getStatus', () => {
    it('should return process status', async () => {
      const executePromise = processManager.execute('test', ['--arg']);

      // Allow process to start
      await new Promise(resolve => setTimeout(resolve, 10));

      const processes = processManager.listProcesses();
      const status = processManager.getStatus(processes[0].id);

      expect(status).toMatchObject({
        command: 'test',
        args: ['--arg'],
        status: 'running',
      });

      // Complete the process
      mockProcess.emit('exit', 0);
      await executePromise;

      const finalStatus = processManager.getStatus(processes[0].id);
      expect(finalStatus?.status).toBe('completed');
      expect(finalStatus?.exitCode).toBe(0);
    });

    it('should return undefined for non-existent process', () => {
      expect(processManager.getStatus('non-existent')).toBeUndefined();
    });
  });
});
