import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';
import { InputValidator } from '../backend/src/security/input-validator';

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

export class ProcessManager extends EventEmitter {
  private processes: Map<string, ProcessInfo> = new Map();
  private cleanedUp: boolean = false;

  execute(command: string, args: string[]): any {
    // Validate command and arguments
    const commandValidation = InputValidator.validateCommand(command);
    if (!commandValidation.isValid) {
      console.error('[ProcessManager] Invalid command:', commandValidation.error);
      throw new Error(commandValidation.error || 'Invalid command');
    }

    const argsValidation = InputValidator.validateArguments(args);
    if (!argsValidation.isValid) {
      console.error('[ProcessManager] Invalid arguments:', argsValidation.error);
      throw new Error(argsValidation.error || 'Invalid arguments');
    }

    const id = uuidv4();
    const projectRoot = path.resolve(__dirname, '../../../..');

    // Use virtual environment Python instead of system Python
    const pythonPath = process.env.PYTHON_PATH || (
      process.platform === 'win32'
        ? path.join(projectRoot, '.venv', 'Scripts', 'python.exe')
        : path.join(projectRoot, '.venv', 'bin', 'python')
    );

    const cliPath = path.resolve(__dirname, '../../../../scripts/cli.py');

    console.log('[ProcessManager] Executing command:', command, 'with args:', args);
    console.log('[ProcessManager] Python path:', pythonPath);
    console.log('[ProcessManager] CLI path:', cliPath);

    // Build the full command
    const fullArgs = [cliPath, command, ...args];

    // Never use shell: true to prevent command injection
    const childProcess = spawn(pythonPath, fullArgs, {
      cwd: projectRoot,
      shell: false, // Explicitly disable shell execution
      env: {
        ...process.env,
        PYTHONPATH: projectRoot,
        PYTHONUNBUFFERED: '1', // Force Python to flush output immediately
      },
    });

    const processInfo: ProcessInfo = {
      id,
      command,
      args,
      process: childProcess,
      status: 'running',
      output: [],
      error: [],
      startTime: new Date(),
      pid: typeof childProcess.pid === 'number' ? childProcess.pid : undefined,
    };

    this.processes.set(id, processInfo);

    // Handle stdout with output sanitization
    childProcess.stdout?.on('data', (data) => {
      const text = InputValidator.sanitizeOutput(data.toString());
      console.log('[ProcessManager] stdout received:', text);
      const lines = text.split('\n');
      // Keep all lines including empty ones, but remove the last empty line if text doesn't end with newline
      if (lines[lines.length - 1] === '' && !text.endsWith('\n')) {
        lines.pop();
      }
      processInfo.output.push(...lines);
      console.log('[ProcessManager] Emitting output event with', lines.length, 'lines');
      this.emit('output', { id, type: 'stdout', data: lines });
    });

    // Handle stderr with output sanitization
    childProcess.stderr?.on('data', (data) => {
      const text = InputValidator.sanitizeOutput(data.toString());
      console.log('[ProcessManager] stderr received:', text);
      const lines = text.split('\n');
      // Keep all lines including empty ones, but remove the last empty line if text doesn't end with newline
      if (lines[lines.length - 1] === '' && !text.endsWith('\n')) {
        lines.pop();
      }
      processInfo.error.push(...lines);
      console.log('[ProcessManager] Emitting stderr event with', lines.length, 'lines');
      this.emit('output', { id, type: 'stderr', data: lines });
    });

    // Handle process completion
    childProcess.on('exit', (code) => {
      processInfo.status = code === 0 ? 'completed' : 'failed';
      processInfo.exitCode = code !== null ? code : undefined;
      processInfo.endTime = new Date();

      this.emit('process:exit', { id, code });
    });

    childProcess.on('error', (error) => {
      processInfo.status = 'failed';
      processInfo.endTime = new Date();
      this.emit('process:error', { id, error });
    });

    // Return immediately with process info
    return {
      id,
      pid: processInfo.pid,
      command,
      args,
      startTime: processInfo.startTime
    };
  }

  async cancel(processId: string): Promise<void> {
    const processInfo = this.processes.get(processId);
    if (!processInfo) {
      throw new Error(`Process ${processId} not found`);
    }

    if (processInfo.status !== 'running') {
      throw new Error(`Process ${processId} is not running`);
    }

    processInfo.process.kill('SIGTERM');
    processInfo.status = 'cancelled';
    processInfo.endTime = new Date();

    this.emit('process:cancelled', { id: processId });
  }

  getStatus(processId: string): ProcessInfo | undefined {
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
        console.warn(`Process ${p.id} has invalid PID:`, p.pid);
      }

      return {
        ...rest,
        pid: validPid,
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
          console.error(`Failed to kill process ${id}:`, error);
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
    const outputHandler = (data: any) => {
      if (data.id === processId) {
        callback(data);
      }
    };

    this.on('output', outputHandler);

    // Return cleanup function
    return () => {
      this.off('output', outputHandler);
    };
  }
}
