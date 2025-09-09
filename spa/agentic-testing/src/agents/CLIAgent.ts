/**
 * CLIAgent - Comprehensive CLI testing agent using Node.js child_process
 *
 * This agent provides complete automation capabilities for CLI applications
 * including command execution, output validation, timeout handling, and
 * comprehensive error handling with automatic recovery.
 */

import { spawn, exec, ChildProcess, SpawnOptions, ExecOptions } from 'child_process';
import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs/promises';
import { IAgent, AgentType } from './index';
import {
  TestStep,
  TestStatus,
  StepResult,
  CommandResult
} from '../models/TestModels';
import { TestLogger, createLogger, LogLevel } from '../utils/logger';

/**
 * Configuration options for the CLIAgent
 */
export interface CLIAgentConfig {
  /** Working directory for command execution */
  workingDirectory?: string;
  /** Default environment variables */
  environment?: Record<string, string>;
  /** Default timeout for commands in milliseconds */
  defaultTimeout?: number;
  /** Maximum buffer size for stdout/stderr */
  maxBufferSize?: number;
  /** Shell to use for command execution */
  shell?: string | boolean;
  /** Whether to capture output streams */
  captureOutput?: boolean;
  /** Command execution mode */
  executionMode?: 'spawn' | 'exec' | 'auto';
  /** Retry configuration */
  retryConfig?: {
    maxRetries: number;
    retryDelay: number;
    retryOnExitCodes: number[];
  };
  /** Input/Output configuration */
  ioConfig?: {
    encoding: BufferEncoding;
    handleInteractivePrompts: boolean;
    autoResponses: Record<string, string>;
  };
  /** Logging configuration */
  logConfig?: {
    logCommands: boolean;
    logOutput: boolean;
    logLevel: LogLevel;
  };
}

/**
 * Running process information
 */
export interface CLIProcessInfo {
  /** Process ID */
  pid: number;
  /** Command being executed */
  command: string;
  /** Process start time */
  startTime: Date;
  /** Process status */
  status: 'running' | 'completed' | 'failed' | 'killed';
  /** Child process reference */
  process: ChildProcess;
}

/**
 * Command execution context
 */
export interface ExecutionContext {
  /** Command to execute */
  command: string;
  /** Command arguments */
  args: string[];
  /** Working directory */
  cwd?: string;
  /** Environment variables */
  env?: Record<string, string>;
  /** Timeout in milliseconds */
  timeout?: number;
  /** Input data to send to process */
  input?: string;
  /** Expected exit codes (default: [0]) */
  expectedExitCodes?: number[];
}

/**
 * Output stream data
 */
export interface StreamData {
  /** Stream type */
  type: 'stdout' | 'stderr';
  /** Data content */
  data: string;
  /** Timestamp */
  timestamp: Date;
  /** Process ID */
  pid?: number;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<CLIAgentConfig> = {
  workingDirectory: process.cwd(),
  environment: {},
  defaultTimeout: 30000,
  maxBufferSize: 1024 * 1024, // 1MB
  shell: true,
  captureOutput: true,
  executionMode: 'auto',
  retryConfig: {
    maxRetries: 2,
    retryDelay: 1000,
    retryOnExitCodes: [1] // Retry on generic failures
  },
  ioConfig: {
    encoding: 'utf8',
    handleInteractivePrompts: true,
    autoResponses: {
      'Are you sure? (y/N)': 'y',
      'Continue? (y/N)': 'y',
      'Overwrite? (y/N)': 'y'
    }
  },
  logConfig: {
    logCommands: true,
    logOutput: true,
    logLevel: LogLevel.DEBUG
  }
};

/**
 * Comprehensive CLI testing agent
 */
export class CLIAgent extends EventEmitter implements IAgent {
  public readonly name = 'CLIAgent';
  public readonly type = AgentType.SYSTEM;

  private config: Required<CLIAgentConfig>;
  private logger: TestLogger;
  private isInitialized = false;
  private currentScenarioId?: string;
  private runningProcesses: Map<string, CLIProcessInfo> = new Map();
  private commandHistory: CommandResult[] = [];
  private outputBuffer: StreamData[] = [];
  private interactiveResponses: Map<string, string> = new Map();

  constructor(config: CLIAgentConfig = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = createLogger({
      level: this.config.logConfig.logLevel,
      logDir: './logs/cli-agent'
    });

    this.setupEventListeners();
  }

  /**
   * Initialize the agent
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing CLIAgent', { config: this.sanitizeConfig() });

    try {
      // Validate working directory
      await this.validateWorkingDirectory();

      // Set up interactive responses
      this.setupInteractiveResponses();

      this.isInitialized = true;
      this.logger.info('CLIAgent initialized successfully');
      this.emit('initialized');

    } catch (error: any) {
      this.logger.error('Failed to initialize CLIAgent', { error: error?.message });
      throw new Error(`Failed to initialize CLIAgent: ${error?.message}`);
    }
  }

  /**
   * Execute a test scenario
   */
  async execute(scenario: any): Promise<any> {
    if (!this.isInitialized) {
      throw new Error('Agent not initialized. Call initialize() first.');
    }

    this.currentScenarioId = scenario.id;
    this.logger.setContext({ scenarioId: scenario.id, component: 'CLIAgent' });
    this.logger.scenarioStart(scenario.id, scenario.name);

    const startTime = Date.now();
    let status = TestStatus.PASSED;
    let error: string | undefined;

    try {
      // Set environment variables if specified in scenario
      if (scenario.environment) {
        this.setEnvironmentVariables(scenario.environment);
      }

      // Execute scenario steps
      const stepResults: StepResult[] = [];

      for (let i = 0; i < scenario.steps.length; i++) {
        const step = scenario.steps[i];
        const stepResult = await this.executeStep(step, i);
        stepResults.push(stepResult);

        if (stepResult.status === TestStatus.FAILED || stepResult.status === TestStatus.ERROR) {
          status = stepResult.status;
          error = stepResult.error;
          break;
        }
      }

      return {
        scenarioId: scenario.id,
        status,
        duration: Date.now() - startTime,
        startTime: new Date(startTime),
        endTime: new Date(),
        error,
        stepResults,
        logs: this.getScenarioLogs(),
        commandHistory: this.getScenarioCommandHistory(),
        outputBuffer: [...this.outputBuffer]
      };

    } catch (executeError: any) {
      this.logger.error('Scenario execution failed', { error: executeError?.message });
      status = TestStatus.ERROR;
      error = executeError?.message;
      throw executeError;

    } finally {
      // Clean up any running processes
      await this.killAllProcesses();
      this.logger.scenarioEnd(scenario.id, status, Date.now() - startTime);
      this.currentScenarioId = undefined;
    }
  }

  /**
   * Execute a CLI command with full configuration
   */
  async executeCommand(command: string, args: string[] = [], options: Partial<ExecutionContext> = {}): Promise<CommandResult> {
    const context: ExecutionContext = {
      command,
      args,
      cwd: options.cwd || this.config.workingDirectory,
      env: { ...this.config.environment, ...options.env },
      timeout: options.timeout || this.config.defaultTimeout,
      expectedExitCodes: options.expectedExitCodes || [0],
      ...options
    };

    this.logger.commandExecution(command, context.cwd);
    const startTime = Date.now();

    let attempt = 0;
    const maxAttempts = this.config.retryConfig.maxRetries + 1;

    while (attempt < maxAttempts) {
      try {
        const result = await this.executeWithRetry(context, attempt);

        // Log command completion
        const duration = Date.now() - startTime;
        this.logger.commandComplete(command, result.exitCode, duration);

        // Store in command history
        this.commandHistory.push(result);

        return result;

      } catch (error: any) {
        attempt++;

        if (attempt >= maxAttempts) {
          const duration = Date.now() - startTime;
          const failedResult: CommandResult = {
            command: `${command} ${args.join(' ')}`.trim(),
            exitCode: -1,
            stdout: '',
            stderr: error?.message || 'Unknown error',
            duration,
            workingDirectory: context.cwd,
            environment: context.env
          };

          this.commandHistory.push(failedResult);
          throw error;
        }

        this.logger.warn(`Command attempt ${attempt} failed, retrying in ${this.config.retryConfig.retryDelay}ms`, {
          error: error?.message,
          attempt,
          maxAttempts
        });

        await this.delay(this.config.retryConfig.retryDelay);
      }
    }

    throw new Error('Unexpected end of retry loop');
  }

  /**
   * Execute a test step
   */
  async executeStep(step: TestStep, stepIndex: number): Promise<StepResult> {
    const startTime = Date.now();
    this.logger.stepExecution(stepIndex, step.action, step.target);

    try {
      let result: any;

      switch (step.action.toLowerCase()) {
        case 'execute':
        case 'run':
        case 'command':
          result = await this.handleExecuteAction(step);
          break;

        case 'execute_with_input':
          result = await this.handleExecuteWithInputAction(step);
          break;

        case 'wait_for_output':
          result = await this.waitForOutput(step.target, step.timeout || this.config.defaultTimeout);
          break;

        case 'validate_output':
          result = await this.validateOutput(this.getLatestOutput(), step.expected || step.value);
          break;

        case 'validate_exit_code':
          result = await this.validateExitCode(parseInt(step.expected || step.value || '0'));
          break;

        case 'capture_output':
          result = this.captureOutput();
          break;

        case 'kill':
        case 'kill_process':
          await this.killProcess(step.target);
          break;

        case 'wait':
          const waitTime = parseInt(step.value || '1000');
          await this.delay(waitTime);
          break;

        case 'set_environment':
          this.setEnvironmentVariable(step.target, step.value || '');
          break;

        case 'change_directory':
          this.changeWorkingDirectory(step.target);
          break;

        case 'file_exists':
          result = await this.fileExists(step.target);
          break;

        case 'directory_exists':
          result = await this.directoryExists(step.target);
          break;

        default:
          throw new Error(`Unsupported CLI action: ${step.action}`);
      }

      const duration = Date.now() - startTime;
      this.logger.stepComplete(stepIndex, TestStatus.PASSED, duration);

      return {
        stepIndex,
        status: TestStatus.PASSED,
        duration,
        actualResult: typeof result === 'string' ? result : JSON.stringify(result)
      };

    } catch (error: any) {
      const duration = Date.now() - startTime;
      this.logger.stepComplete(stepIndex, TestStatus.FAILED, duration);

      return {
        stepIndex,
        status: TestStatus.FAILED,
        duration,
        error: error?.message
      };
    }
  }

  /**
   * Validate command output against expected result
   */
  async validateOutput(output: string, expected: any): Promise<boolean> {
    if (typeof expected === 'string') {
      if (expected.startsWith('regex:')) {
        const pattern = expected.substring(6);
        const regex = new RegExp(pattern, 'i');
        return regex.test(output);
      } else if (expected.startsWith('contains:')) {
        const searchText = expected.substring(9);
        return output.includes(searchText);
      } else {
        return output.trim() === expected.trim();
      }
    }

    if (typeof expected === 'object' && expected.type) {
      switch (expected.type) {
        case 'json':
          try {
            const parsed = JSON.parse(output);
            return this.deepEqual(parsed, expected.value);
          } catch (error) {
            return false;
          }

        case 'contains':
          return output.includes(expected.value);

        case 'not_contains':
          return !output.includes(expected.value);

        case 'starts_with':
          return output.startsWith(expected.value);

        case 'ends_with':
          return output.endsWith(expected.value);

        case 'length':
          return output.length === expected.value;

        case 'empty':
          return output.trim().length === 0;

        case 'not_empty':
          return output.trim().length > 0;

        default:
          throw new Error(`Unsupported validation type: ${expected.type}`);
      }
    }

    return false;
  }

  /**
   * Wait for specific output pattern
   */
  async waitForOutput(pattern: string, timeout: number = this.config.defaultTimeout): Promise<string> {
    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      const regex = new RegExp(pattern, 'i');

      const checkOutput = () => {
        const currentOutput = this.getAllOutput();

        if (regex.test(currentOutput)) {
          resolve(currentOutput);
          return;
        }

        if (Date.now() - startTime > timeout) {
          reject(new Error(`Timeout waiting for output pattern: ${pattern}`));
          return;
        }

        setTimeout(checkOutput, 100);
      };

      checkOutput();
    });
  }

  /**
   * Capture current output buffer
   */
  captureOutput(): { stdout: string; stderr: string; combined: string } {
    const stdoutData = this.outputBuffer
      .filter(entry => entry.type === 'stdout')
      .map(entry => entry.data)
      .join('');

    const stderrData = this.outputBuffer
      .filter(entry => entry.type === 'stderr')
      .map(entry => entry.data)
      .join('');

    const combinedData = this.outputBuffer
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      .map(entry => entry.data)
      .join('');

    return {
      stdout: stdoutData,
      stderr: stderrData,
      combined: combinedData
    };
  }

  /**
   * Kill a specific process
   */
  async kill(processId?: string): Promise<void> {
    if (processId) {
      await this.killProcess(processId);
    } else {
      await this.killAllProcesses();
    }
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up CLIAgent resources');

    try {
      // Kill all running processes
      await this.killAllProcesses();

      // Clear buffers and history
      this.outputBuffer = [];
      this.commandHistory = [];
      this.runningProcesses.clear();

      this.logger.info('CLIAgent cleanup completed');
      this.emit('cleanup');

    } catch (error: any) {
      this.logger.error('Error during cleanup', { error: error?.message });
    }
  }

  // Private helper methods

  private async executeWithRetry(context: ExecutionContext, attempt: number): Promise<CommandResult> {
    const fullCommand = `${context.command} ${context.args.join(' ')}`.trim();
    const processId = `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;

    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      let stdout = '';
      let stderr = '';
      let timeoutHandle: NodeJS.Timeout;

      // Choose execution method
      let childProcess: ChildProcess;

      if (this.config.executionMode === 'exec' ||
          (this.config.executionMode === 'auto' && context.args.length === 0)) {
        // Use exec for simple commands or when explicitly requested
        const execOptions: ExecOptions = {
          cwd: context.cwd,
          env: context.env,
          maxBuffer: this.config.maxBufferSize,
          timeout: context.timeout,
          encoding: this.config.ioConfig.encoding
        };

        childProcess = exec(fullCommand, execOptions, (error, stdoutBuffer, stderrBuffer) => {
          clearTimeout(timeoutHandle);

          const duration = Date.now() - startTime;
          const exitCode = error ? (error as any).code || 1 : 0;

          const stdoutStr = typeof stdoutBuffer === 'string' ? stdoutBuffer : stdoutBuffer?.toString(this.config.ioConfig.encoding) || '';
          const stderrStr = typeof stderrBuffer === 'string' ? stderrBuffer : stderrBuffer?.toString(this.config.ioConfig.encoding) || '';

          const result: CommandResult = {
            command: fullCommand,
            exitCode,
            stdout: stdoutStr,
            stderr: stderrStr,
            duration,
            workingDirectory: context.cwd,
            environment: context.env
          };

          if (context.expectedExitCodes!.includes(exitCode)) {
            resolve(result);
          } else {
            reject(new Error(`Command failed with exit code ${exitCode}: ${stderr || error?.message}`));
          }
        });

      } else {
        // Use spawn for complex commands with arguments
        const spawnOptions: SpawnOptions = {
          cwd: context.cwd,
          env: context.env,
          shell: this.config.shell,
          stdio: ['pipe', 'pipe', 'pipe']
        };

        childProcess = spawn(context.command, context.args, spawnOptions);

        // Handle stdout
        childProcess.stdout?.on('data', (data: Buffer) => {
          const output = data.toString(this.config.ioConfig.encoding);
          stdout += output;

          if (this.config.captureOutput) {
            this.outputBuffer.push({
              type: 'stdout',
              data: output,
              timestamp: new Date(),
              pid: childProcess.pid
            });
          }

          // Handle interactive prompts
          this.handleInteractivePrompt(output, childProcess);

          if (this.config.logConfig.logOutput) {
            this.logger.debug(`[STDOUT] ${output.trim()}`);
          }
        });

        // Handle stderr
        childProcess.stderr?.on('data', (data: Buffer) => {
          const output = data.toString(this.config.ioConfig.encoding);
          stderr += output;

          if (this.config.captureOutput) {
            this.outputBuffer.push({
              type: 'stderr',
              data: output,
              timestamp: new Date(),
              pid: childProcess.pid
            });
          }

          if (this.config.logConfig.logOutput) {
            this.logger.debug(`[STDERR] ${output.trim()}`);
          }
        });

        // Handle process exit
        childProcess.on('close', (code: number | null) => {
          clearTimeout(timeoutHandle);
          this.runningProcesses.delete(processId);

          const duration = Date.now() - startTime;
          const exitCode = code ?? -1;

          const result: CommandResult = {
            command: fullCommand,
            exitCode,
            stdout,
            stderr,
            duration,
            workingDirectory: context.cwd,
            environment: context.env
          };

          if (context.expectedExitCodes!.includes(exitCode)) {
            resolve(result);
          } else {
            reject(new Error(`Command failed with exit code ${exitCode}: ${stderr}`));
          }
        });

        // Handle process errors
        childProcess.on('error', (error: Error) => {
          clearTimeout(timeoutHandle);
          this.runningProcesses.delete(processId);
          reject(new Error(`Process error: ${error.message}`));
        });

        // Send input if provided
        if (context.input && childProcess.stdin) {
          childProcess.stdin.write(context.input);
          childProcess.stdin.end();
        }
      }

      // Store process info
      this.runningProcesses.set(processId, {
        pid: childProcess.pid || 0,
        command: fullCommand,
        startTime: new Date(startTime),
        status: 'running',
        process: childProcess
      });

      // Set timeout
      if (context.timeout && context.timeout > 0) {
        timeoutHandle = setTimeout(() => {
          this.killProcess(processId);
          reject(new Error(`Command timeout after ${context.timeout}ms: ${fullCommand}`));
        }, context.timeout);
      }
    });
  }

  private handleInteractivePrompt(output: string, process: ChildProcess): void {
    if (!this.config.ioConfig.handleInteractivePrompts || !process.stdin) {
      return;
    }

    for (const [prompt, response] of Array.from(this.interactiveResponses.entries())) {
      if (output.includes(prompt)) {
        this.logger.debug(`Responding to interactive prompt: "${prompt}" with "${response}"`);
        process.stdin.write(`${response}\n`);
        break;
      }
    }
  }

  private async handleExecuteAction(step: TestStep): Promise<CommandResult> {
    const parts = step.target.split(' ');
    const command = parts[0];
    const args = parts.slice(1);

    const options: Partial<ExecutionContext> = {};

    if (step.timeout) {
      options.timeout = step.timeout;
    }

    if (step.value) {
      // Value can contain additional environment variables
      try {
        const envVars = JSON.parse(step.value);
        options.env = envVars;
      } catch {
        // If not JSON, treat as input
        options.input = step.value;
      }
    }

    return this.executeCommand(command, args, options);
  }

  private async handleExecuteWithInputAction(step: TestStep): Promise<CommandResult> {
    const parts = step.target.split(' ');
    const command = parts[0];
    const args = parts.slice(1);

    return this.executeCommand(command, args, {
      input: step.value || '',
      timeout: step.timeout
    });
  }

  private async validateExitCode(expectedCode: number): Promise<boolean> {
    if (this.commandHistory.length === 0) {
      throw new Error('No command history available for exit code validation');
    }

    const lastCommand = this.commandHistory[this.commandHistory.length - 1];
    return lastCommand.exitCode === expectedCode;
  }

  private async killProcess(processId: string): Promise<void> {
    const processInfo = this.runningProcesses.get(processId);
    if (!processInfo) {
      this.logger.warn(`Process not found: ${processId}`);
      return;
    }

    try {
      this.logger.info(`Killing process: ${processInfo.command} (PID: ${processInfo.pid})`);

      if (processInfo.process) {
        processInfo.process.kill('SIGTERM');

        // Wait for graceful shutdown
        await this.delay(1000);

        // Force kill if still running
        if (!processInfo.process.killed) {
          processInfo.process.kill('SIGKILL');
        }
      }

      processInfo.status = 'killed';
      this.runningProcesses.delete(processId);

    } catch (error: any) {
      this.logger.error(`Failed to kill process ${processId}`, { error: error?.message });
      throw error;
    }
  }

  private async killAllProcesses(): Promise<void> {
    const processes = Array.from(this.runningProcesses.keys());

    if (processes.length === 0) {
      return;
    }

    this.logger.info(`Killing ${processes.length} running processes`);

    const killPromises = processes.map(processId =>
      this.killProcess(processId).catch(error =>
        this.logger.warn(`Failed to kill process ${processId}`, { error: error?.message })
      )
    );

    await Promise.all(killPromises);
  }

  private setEnvironmentVariable(name: string, value: string): void {
    this.config.environment[name] = value;
    process.env[name] = value;
    this.logger.debug(`Set environment variable: ${name}=${value}`);
  }

  private setEnvironmentVariables(variables: Record<string, string>): void {
    for (const [name, value] of Object.entries(variables)) {
      this.setEnvironmentVariable(name, value);
    }
  }

  private changeWorkingDirectory(directory: string): void {
    const resolvedPath = path.resolve(directory);
    this.config.workingDirectory = resolvedPath;
    this.logger.debug(`Changed working directory to: ${resolvedPath}`);
  }

  private async fileExists(filePath: string): Promise<boolean> {
    try {
      const fullPath = path.resolve(this.config.workingDirectory, filePath);
      await fs.access(fullPath);
      return true;
    } catch {
      return false;
    }
  }

  private async directoryExists(dirPath: string): Promise<boolean> {
    try {
      const fullPath = path.resolve(this.config.workingDirectory, dirPath);
      const stats = await fs.stat(fullPath);
      return stats.isDirectory();
    } catch {
      return false;
    }
  }

  private getLatestOutput(): string {
    if (this.commandHistory.length === 0) {
      return this.getAllOutput();
    }

    const lastCommand = this.commandHistory[this.commandHistory.length - 1];
    return `${lastCommand.stdout}\n${lastCommand.stderr}`.trim();
  }

  private getAllOutput(): string {
    return this.outputBuffer
      .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime())
      .map(entry => entry.data)
      .join('');
  }

  private getScenarioLogs(): string[] {
    // Return recent logs related to the current scenario
    return this.outputBuffer
      .filter(entry => entry.timestamp.getTime() > Date.now() - 300000) // Last 5 minutes
      .map(entry => `[${entry.type.toUpperCase()}] ${entry.data.trim()}`)
      .filter(log => log.length > 0);
  }

  private getScenarioCommandHistory(): CommandResult[] {
    return [...this.commandHistory];
  }

  private setupEventListeners(): void {
    this.on('error', (error) => {
      this.logger.error('CLIAgent error', { error: error.message });
    });
  }

  private setupInteractiveResponses(): void {
    this.interactiveResponses.clear();

    for (const [prompt, response] of Object.entries(this.config.ioConfig.autoResponses)) {
      this.interactiveResponses.set(prompt, response);
    }
  }

  private async validateWorkingDirectory(): Promise<void> {
    try {
      await fs.access(this.config.workingDirectory);
      const stats = await fs.stat(this.config.workingDirectory);

      if (!stats.isDirectory()) {
        throw new Error(`Working directory is not a directory: ${this.config.workingDirectory}`);
      }
    } catch (error: any) {
      if (error.code === 'ENOENT') {
        throw new Error(`Working directory does not exist: ${this.config.workingDirectory}`);
      }
      throw error;
    }
  }

  private sanitizeConfig(): Record<string, any> {
    const { environment, ...safeConfig } = this.config;
    return {
      ...safeConfig,
      environment: environment ? Object.keys(environment) : undefined
    };
  }

  private deepEqual(obj1: any, obj2: any): boolean {
    if (obj1 === obj2) return true;

    if (obj1 == null || obj2 == null) return false;

    if (typeof obj1 !== typeof obj2) return false;

    if (typeof obj1 !== 'object') return obj1 === obj2;

    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);

    if (keys1.length !== keys2.length) return false;

    for (const key of keys1) {
      if (!keys2.includes(key)) return false;
      if (!this.deepEqual(obj1[key], obj2[key])) return false;
    }

    return true;
  }

  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Factory function to create CLIAgent instance
 */
export function createCLIAgent(config?: CLIAgentConfig): CLIAgent {
  return new CLIAgent(config);
}
