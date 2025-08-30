import { spawn, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';

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

  async execute(command: string, args: string[]): Promise<any> {
    const id = uuidv4();
    const pythonPath = process.env.PYTHON_PATH || 'python3';
    const cliPath = path.resolve(__dirname, '../../../scripts/cli.py');
    
    // Build the full command
    const fullArgs = [cliPath, command, ...args];
    
    const childProcess = spawn(pythonPath, fullArgs, {
      cwd: path.resolve(__dirname, '../../..'),
      env: {
        ...process.env,
        PYTHONPATH: path.resolve(__dirname, '../../..'),
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
      pid: childProcess.pid,
    };

    this.processes.set(id, processInfo);

    // Handle stdout
    childProcess.stdout?.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line);
      processInfo.output.push(...lines);
      this.emit('output', { id, type: 'stdout', data: lines });
    });

    // Handle stderr
    childProcess.stderr?.on('data', (data) => {
      const lines = data.toString().split('\n').filter((line: string) => line);
      processInfo.error.push(...lines);
      this.emit('output', { id, type: 'stderr', data: lines });
    });

    // Handle process completion
    return new Promise((resolve, reject) => {
      childProcess.on('exit', (code) => {
        processInfo.status = code === 0 ? 'completed' : 'failed';
        processInfo.exitCode = code ?? undefined;
        processInfo.endTime = new Date();
        
        this.emit('process:exit', { id, code });
        
        if (code === 0) {
          resolve({
            id,
            output: processInfo.output,
            exitCode: code,
          });
        } else {
          reject(new Error(`Process failed with exit code ${code}`));
        }
      });

      childProcess.on('error', (error) => {
        processInfo.status = 'failed';
        processInfo.endTime = new Date();
        this.emit('process:error', { id, error });
        reject(error);
      });
    });
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
      return {
        ...rest,
        // Ensure PID is included and valid
        pid: p.pid && p.pid > 0 ? p.pid : undefined,
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