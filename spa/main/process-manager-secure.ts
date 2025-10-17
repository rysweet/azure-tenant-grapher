/**
 * SECURE VERSION OF PROCESS-MANAGER.TS
 * Implements input validation and command injection prevention
 */

import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';

// Import validation functions
import {
  validateCommand,
  validateArguments,
  sanitizeOutput
} from '../backend/src/security/input-validator';

interface ProcessInfo {
  id: string;
  command: string;
  args: string[];
  process: ChildProcess;
  status: 'running' | 'completed' | 'failed' | 'cancelled';
  output: string[];
  error: string[];
  startTime: Date;
  endTime?: Date;
  exitCode?: number;
  pid?: number;
}

export class SecureProcessManager extends EventEmitter {
  private processes: Map<string, ProcessInfo> = new Map();
  private cleanedUp: boolean = false;
  private readonly maxProcesses = 10; // Limit concurrent processes
  private readonly allowedCommands = new Set([
    'collect',
    'report',
    'analyze',
    'graph',
    'export',
    'import',
    'test',
    'validate',
    'status',
    'version'
  ]);

  execute(command: string, args: string[]): any {
    // Check process limit
    const runningProcesses = Array.from(this.processes.values())
      .filter(p => p.status === 'running').length;

    if (runningProcesses >= this.maxProcesses) {
      throw new Error('Maximum number of concurrent processes reached');
    }

    // Validate command
    const commandValidation = validateCommand(command);
    if (!commandValidation.isValid) {
      throw new Error('Invalid command: ' + commandValidation.error);
    }

    // Validate arguments
    const argsValidation = validateArguments(args);
    if (!argsValidation.isValid) {
      throw new Error('Invalid arguments: ' + argsValidation.error);
    }

    const id = uuidv4();
    const pythonPath = process.env.PYTHON_PATH || 'python3';
    const cliPath = path.resolve(__dirname, '../../../scripts/cli.py');

    // Verify CLI path is within project
    const projectRoot = path.resolve(__dirname, '../../..');
    if (!cliPath.startsWith(projectRoot)) {
      throw new Error('CLI path outside project directory');
    }

    const sanitizedCommand = commandValidation.sanitized as string;
    const sanitizedArgs = argsValidation.sanitized as string[];

    console.log('[SecureProcessManager] Executing command:', sanitizedCommand, 'with args:', sanitizedArgs);
    console.log('[SecureProcessManager] Python path:', pythonPath);
    console.log('[SecureProcessManager] CLI path:', cliPath);

    // Build the full command with sanitized inputs
    const fullArgs = [cliPath, sanitizedCommand, ...sanitizedArgs];

    const childProcess = spawn(pythonPath, fullArgs, {
      cwd: projectRoot,
      env: {
        ...process.env,
        PYTHONPATH: projectRoot,
        PYTHONUNBUFFERED: '1',
      },
      shell: false, // Never use shell to prevent injection
      stdio: ['ignore', 'pipe', 'pipe'] // Ignore stdin, pipe stdout/stderr
    });

    const processInfo: ProcessInfo = {
      id,
      command: sanitizedCommand,
      args: sanitizedArgs,
      process: childProcess,
      status: 'running',
      output: [],
      error: [],
      startTime: new Date(),
      pid: typeof childProcess.pid === 'number' ? childProcess.pid : undefined,
    };

    this.processes.set(id, processInfo);

    // Handle stdout with sanitization
    childProcess.stdout?.on('data', (data) => {
      const text = sanitizeOutput(data.toString());
      console.log('[SecureProcessManager] stdout received:', text);
      const lines = text.split('\n');
      if (lines[lines.length - 1] === '' && !text.endsWith('\n')) {
        lines.pop();
      }
      processInfo.output.push(...lines);
      console.log('[SecureProcessManager] Emitting output event with', lines.length, 'lines');
      this.emit('output', { id, type: 'stdout', data: lines });
    });

    // Handle stderr with sanitization
    childProcess.stderr?.on('data', (data) => {
      const text = sanitizeOutput(data.toString());
      console.log('[SecureProcessManager] stderr received:', text);
      const lines = text.split('\n');
      if (lines[lines.length - 1] === '' && !text.endsWith('\n')) {
        lines.pop();
      }
      processInfo.error.push(...lines);
      console.log('[SecureProcessManager] Emitting stderr event with', lines.length, 'lines');
      this.emit('output', { id, type: 'stderr', data: lines });
    });

    // Handle process completion
    childProcess.on('exit', (code) => {
      processInfo.status = code === 0 ? 'completed' : 'failed';
      processInfo.exitCode = code !== null ? code : undefined;
      processInfo.endTime = new Date();

      this.emit('process:exit', { id, code });

      // Clean up old processes after completion
      setTimeout(() => {
        if (this.processes.has(id)) {
          const info = this.processes.get(id);
          if (info && info.status !== 'running') {
            this.processes.delete(id);
          }
        }
      }, 300000); // Clean up after 5 minutes
    });

    childProcess.on('error', (error) => {
      processInfo.status = 'failed';
      processInfo.endTime = new Date();
      // Sanitize error message
      const sanitizedError = {
        ...error,
        message: sanitizeOutput(error.message)
      };
      this.emit('process:error', { id, error: sanitizedError });
    });

    // Set timeout for long-running processes
    const timeout = setTimeout(() => {
      if (processInfo.status === 'running') {
        console.warn('[SecureProcessManager] Process timeout:', id);
        childProcess.kill('SIGTERM');
        processInfo.status = 'cancelled';
        processInfo.endTime = new Date();
        this.emit('process:timeout', { id });
      }
    }, 600000); // 10 minute timeout

    childProcess.on('exit', () => {
      clearTimeout(timeout);
    });

    // Return immediately with process info
    return {
      id,
      pid: processInfo.pid,
      command: sanitizedCommand,
      args: sanitizedArgs,
      startTime: processInfo.startTime
    };
  }

  async cancel(processId: string): Promise<void> {
    // Validate process ID format (should be UUID)
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(processId)) {
      throw new Error('Invalid process ID format');
    }

    const processInfo = this.processes.get(processId);
    if (!processInfo) {
      throw new Error('Process ' + processId + ' not found');
    }

    if (processInfo.status !== 'running') {
      throw new Error('Process ' + processId + ' is not running');
    }

    processInfo.process.kill('SIGTERM');
    processInfo.status = 'cancelled';
    processInfo.endTime = new Date();

    this.emit('process:cancelled', { id: processId });

    // Give process time to clean up, then force kill if needed
    setTimeout(() => {
      if (!processInfo.process.killed) {
        processInfo.process.kill('SIGKILL');
      }
    }, 5000);
  }

  getStatus(processId: string): ProcessInfo | undefined {
    // Validate process ID
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(processId)) {
      return undefined;
    }

    return this.processes.get(processId);
  }

  listProcesses(): Omit<ProcessInfo, 'process'>[] {
    return Array.from(this.processes.values()).map(p => {
      const { process, ...rest } = p;

      // Validate PID with explicit type checking
      let validPid: number | undefined = undefined;
      if (typeof p.pid === 'number' && p.pid > 0) {
        validPid = p.pid;
      } else if (p.pid !== undefined) {
        console.warn('Process ' + p.id + ' has invalid PID:', p.pid);
      }

      return {
        ...rest,
        pid: validPid,
        // Sanitize output before returning
        output: rest.output.map(line => sanitizeOutput(line)),
        error: rest.error.map(line => sanitizeOutput(line))
      };
    });
  }

  async cleanup(): Promise<void> {
    if (this.cleanedUp) return;

    // Kill all running processes
    for (const [id, info] of this.processes) {
      if (info.status === 'running') {
        try {
          info.process.kill('SIGTERM');
          // Give process time to terminate gracefully
          await new Promise(resolve => setTimeout(resolve, 100));
          if (!info.process.killed) {
            info.process.kill('SIGKILL');
          }
        } catch (error) {
          console.error('Failed to kill process ' + id + ':', error);
        }
      }
    }

    this.cleanedUp = true;
    this.processes.clear();
  }

  isCleanedUp(): boolean {
    return this.cleanedUp;
  }

  // Stream output for WebSocket connections
  streamOutput(processId: string, callback: (data: any) => void): () => void {
    // Validate process ID
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    if (!uuidRegex.test(processId)) {
      throw new Error('Invalid process ID');
    }

    const outputHandler = (data: any) => {
      if (data.id === processId) {
        // Ensure output is sanitized before streaming
        const sanitizedData = {
          ...data,
          data: Array.isArray(data.data)
            ? data.data.map((line: string) => sanitizeOutput(line))
            : sanitizeOutput(data.data)
        };
        callback(sanitizedData);
      }
    };

    this.on('output', outputHandler);

    // Return cleanup function
    return () => {
      this.off('output', outputHandler);
    };
  }

  /**
   * Get process count for monitoring
   */
  getProcessCount(): { total: number; running: number } {
    const running = Array.from(this.processes.values())
      .filter(p => p.status === 'running').length;

    return {
      total: this.processes.size,
      running
    };
  }
}

// Export as default for compatibility
export default SecureProcessManager;
