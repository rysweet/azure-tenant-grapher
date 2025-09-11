/**
 * Winston-based logging system for the Agentic Testing System
 * Provides configurable logging with different levels, formats, and outputs
 */

import winston from 'winston';
import path from 'path';
import fs from 'fs';

/**
 * Log levels enumeration
 */
export enum LogLevel {
  ERROR = 'error',
  WARN = 'warn',
  INFO = 'info',
  HTTP = 'http',
  DEBUG = 'debug'
}

/**
 * Log context interface for structured logging
 */
export interface LogContext {
  /** Test scenario ID */
  scenarioId?: string;
  /** Test step index */
  stepIndex?: number;
  /** Component or module name */
  component?: string;
  /** Session or run ID */
  sessionId?: string;
  /** Additional metadata */
  metadata?: Record<string, any>;
}

/**
 * Logger configuration options
 */
export interface LoggerConfig {
  /** Log level threshold */
  level: LogLevel;
  /** Output directory for log files */
  logDir: string;
  /** Whether to log to console */
  enableConsole: boolean;
  /** Whether to log to file */
  enableFile: boolean;
  /** Maximum size of each log file in bytes */
  maxFileSize: number;
  /** Maximum number of log files to keep */
  maxFiles: number;
  /** Whether to compress rotated log files */
  compress: boolean;
  /** Custom log format */
  format?: string;
  /** Whether to include timestamps */
  includeTimestamp: boolean;
  /** Whether to include stack traces for errors */
  includeStackTrace: boolean;
}

/**
 * Default logger configuration
 */
const DEFAULT_CONFIG: LoggerConfig = {
  level: LogLevel.INFO,
  logDir: './logs',
  enableConsole: true,
  enableFile: true,
  maxFileSize: 10 * 1024 * 1024, // 10MB
  maxFiles: 5,
  compress: true,
  includeTimestamp: true,
  includeStackTrace: true
};

/**
 * Enhanced Winston logger with testing-specific features
 */
export class TestLogger {
  private logger: winston.Logger;
  private config: LoggerConfig;
  private context: LogContext = {};

  constructor(config: Partial<LoggerConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = this.createLogger();
  }

  /**
   * Create the Winston logger instance with configured transports
   */
  private createLogger(): winston.Logger {
    // Ensure log directory exists
    if (this.config.enableFile && !fs.existsSync(this.config.logDir)) {
      fs.mkdirSync(this.config.logDir, { recursive: true });
    }

    const transports: winston.transport[] = [];

    // Console transport
    if (this.config.enableConsole) {
      transports.push(
        new winston.transports.Console({
          level: this.config.level,
          format: winston.format.combine(
            winston.format.colorize({ all: true }),
            winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
            winston.format.printf(({ timestamp, level, message, ...meta }) => {
              let output = `${timestamp} [${level}]`;

              // Add context information
              if (this.context.scenarioId) {
                output += ` [${this.context.scenarioId}]`;
              }
              if (this.context.component) {
                output += ` [${this.context.component}]`;
              }

              output += `: ${message}`;

              // Add metadata if present
              if (Object.keys(meta).length > 0) {
                output += ` ${JSON.stringify(meta)}`;
              }

              return output;
            })
          )
        })
      );
    }

    // File transports
    if (this.config.enableFile) {
      // Combined log file
      transports.push(
        new winston.transports.File({
          filename: path.join(this.config.logDir, 'combined.log'),
          level: this.config.level,
          maxsize: this.config.maxFileSize,
          maxFiles: this.config.maxFiles,
          format: winston.format.combine(
            winston.format.timestamp(),
            winston.format.errors({ stack: this.config.includeStackTrace }),
            winston.format.json()
          )
        })
      );

      // Error-only log file
      transports.push(
        new winston.transports.File({
          filename: path.join(this.config.logDir, 'error.log'),
          level: LogLevel.ERROR,
          maxsize: this.config.maxFileSize,
          maxFiles: this.config.maxFiles,
          format: winston.format.combine(
            winston.format.timestamp(),
            winston.format.errors({ stack: true }),
            winston.format.json()
          )
        })
      );

      // Test-specific log file
      transports.push(
        new winston.transports.File({
          filename: path.join(this.config.logDir, 'test-execution.log'),
          level: this.config.level,
          maxsize: this.config.maxFileSize,
          maxFiles: this.config.maxFiles,
          format: winston.format.combine(
            winston.format.timestamp(),
            winston.format.errors({ stack: this.config.includeStackTrace }),
            winston.format.json()
          )
        })
      );
    }

    return winston.createLogger({
      level: this.config.level,
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.errors({ stack: this.config.includeStackTrace }),
        winston.format.json()
      ),
      defaultMeta: { service: 'agentic-testing' },
      transports
    });
  }

  /**
   * Set the logging context for structured logging
   */
  setContext(context: LogContext): void {
    this.context = { ...this.context, ...context };
  }

  /**
   * Clear the current logging context
   */
  clearContext(): void {
    this.context = {};
  }

  /**
   * Get the current logging context
   */
  getContext(): LogContext {
    return { ...this.context };
  }

  /**
   * Log an error message
   */
  error(message: string, meta?: any): void {
    this.logger.error(message, { ...this.context, ...meta });
  }

  /**
   * Log a warning message
   */
  warn(message: string, meta?: any): void {
    this.logger.warn(message, { ...this.context, ...meta });
  }

  /**
   * Log an info message
   */
  info(message: string, meta?: any): void {
    this.logger.info(message, { ...this.context, ...meta });
  }

  /**
   * Log an HTTP message
   */
  http(message: string, meta?: any): void {
    this.logger.http(message, { ...this.context, ...meta });
  }

  /**
   * Log a debug message
   */
  debug(message: string, meta?: any): void {
    this.logger.debug(message, { ...this.context, ...meta });
  }

  /**
   * Log test scenario start
   */
  scenarioStart(scenarioId: string, scenarioName: string): void {
    this.setContext({ scenarioId });
    this.info(`Starting test scenario: ${scenarioName}`, {
      event: 'scenario_start',
      scenarioId,
      scenarioName
    });
  }

  /**
   * Log test scenario completion
   */
  scenarioEnd(scenarioId: string, status: string, duration: number): void {
    this.info(`Test scenario completed: ${status}`, {
      event: 'scenario_end',
      scenarioId,
      status,
      duration
    });
    this.clearContext();
  }

  /**
   * Log test step execution
   */
  stepExecution(stepIndex: number, action: string, target: string): void {
    this.debug(`Executing step ${stepIndex + 1}: ${action}`, {
      event: 'step_execution',
      stepIndex,
      action,
      target
    });
  }

  /**
   * Log test step completion
   */
  stepComplete(stepIndex: number, status: string, duration: number): void {
    this.debug(`Step ${stepIndex + 1} completed: ${status}`, {
      event: 'step_complete',
      stepIndex,
      status,
      duration
    });
  }

  /**
   * Log performance metrics
   */
  performance(operation: string, duration: number, metadata?: Record<string, any>): void {
    this.info(`Performance: ${operation} took ${duration}ms`, {
      event: 'performance',
      operation,
      duration,
      ...metadata
    });
  }

  /**
   * Log screenshot capture
   */
  screenshot(filename: string, stepIndex?: number): void {
    this.debug(`Screenshot captured: ${filename}`, {
      event: 'screenshot',
      filename,
      stepIndex
    });
  }

  /**
   * Log command execution
   */
  commandExecution(command: string, workingDir?: string): void {
    this.debug(`Executing command: ${command}`, {
      event: 'command_execution',
      command,
      workingDir
    });
  }

  /**
   * Log command completion
   */
  commandComplete(command: string, exitCode: number, duration: number): void {
    const level = exitCode === 0 ? 'info' : 'warn';
    this.logger[level](`Command completed with exit code ${exitCode}`, {
      event: 'command_complete',
      command,
      exitCode,
      duration
    });
  }

  /**
   * Create a child logger with additional context
   */
  child(context: LogContext): TestLogger {
    const childLogger = new TestLogger(this.config);
    childLogger.setContext({ ...this.context, ...context });
    return childLogger;
  }

  /**
   * Change the log level at runtime
   */
  setLevel(level: LogLevel): void {
    this.config.level = level;
    this.logger.level = level;

    // Update all transports
    this.logger.transports.forEach(transport => {
      transport.level = level;
    });
  }

  /**
   * Get current log level
   */
  getLevel(): LogLevel {
    return this.config.level;
  }

  /**
   * Flush all log transports
   */
  async flush(): Promise<void> {
    return new Promise((resolve) => {
      // Winston doesn't have a built-in flush method, so we use a workaround
      let pendingTransports = this.logger.transports.length;

      if (pendingTransports === 0) {
        resolve();
        return;
      }

      this.logger.transports.forEach((transport) => {
        if ('close' in transport && typeof transport.close === 'function') {
          transport.close(() => {
            pendingTransports--;
            if (pendingTransports === 0) {
              resolve();
            }
          });
        } else {
          pendingTransports--;
          if (pendingTransports === 0) {
            resolve();
          }
        }
      });
    });
  }

  /**
   * Close the logger and clean up resources
   */
  async close(): Promise<void> {
    await this.flush();
    this.logger.close();
  }
}

/**
 * Create a logger instance with the specified configuration
 */
export function createLogger(config?: Partial<LoggerConfig>): TestLogger {
  return new TestLogger(config);
}

/**
 * Default logger instance for the application
 */
export const defaultLogger = new TestLogger();

/**
 * Convenience methods using the default logger
 */
export const logger = {
  error: (message: string, meta?: any) => defaultLogger.error(message, meta),
  warn: (message: string, meta?: any) => defaultLogger.warn(message, meta),
  info: (message: string, meta?: any) => defaultLogger.info(message, meta),
  debug: (message: string, meta?: any) => defaultLogger.debug(message, meta),
  setContext: (context: LogContext) => defaultLogger.setContext(context),
  clearContext: () => defaultLogger.clearContext(),
  setLevel: (level: LogLevel) => defaultLogger.setLevel(level),
  child: (context: LogContext) => defaultLogger.child(context)
};
