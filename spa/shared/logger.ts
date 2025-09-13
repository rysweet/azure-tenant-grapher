/**
 * Core Logger Module
 * Provides centralized logging with multiple transports and levels
 */

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3,
}

export interface LogEntry {
  timestamp: string;
  level: LogLevel;
  message: string;
  component?: string;
  metadata?: Record<string, any>;
  id: string;
}

export interface LogTransport {
  log(entry: LogEntry): void | Promise<void>;
  flush?(): Promise<void>;
}

export class Logger {
  private static instance: Logger;
  private transports: LogTransport[] = [];
  private minLevel: LogLevel = LogLevel.INFO;
  private buffer: LogEntry[] = [];
  private maxBufferSize = 1000;
  private component?: string;

  private constructor() {}

  static getInstance(): Logger {
    if (!Logger.instance) {
      Logger.instance = new Logger();
    }
    return Logger.instance;
  }

  /**
   * Create a child logger with a specific component name
   */
  child(component: string): Logger {
    const childLogger = Object.create(this);
    childLogger.component = component;
    return childLogger;
  }

  /**
   * Add a transport for log output
   */
  addTransport(transport: LogTransport): void {
    this.transports.push(transport);
  }

  /**
   * Set minimum log level
   */
  setLevel(level: LogLevel): void {
    this.minLevel = level;
  }

  /**
   * Get buffered logs (for UI display)
   */
  getBuffer(): LogEntry[] {
    return [...this.buffer];
  }

  /**
   * Clear log buffer
   */
  clearBuffer(): void {
    this.buffer = [];
  }

  /**
   * Core logging method
   */
  private log(level: LogLevel, message: string, metadata?: Record<string, any>): void {
    if (level < this.minLevel) return;

    const entry: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      level,
      message: this.sanitizeMessage(message),
      component: this.component,
      metadata: metadata ? this.sanitizeMetadata(metadata) : undefined,
    };

    // Add to buffer for UI
    this.buffer.push(entry);
    if (this.buffer.length > this.maxBufferSize) {
      this.buffer.shift();
    }

    // Send to all transports
    for (const transport of this.transports) {
      try {
        const result = transport.log(entry);
        if (result instanceof Promise) {
          result.catch(err => {
            // Avoid infinite loop by using console directly for transport errors
            console.error('Log transport error:', err);
          });
        }
      } catch (err) {
        console.error('Log transport error:', err);
      }
    }
  }

  /**
   * Sanitize message to prevent sensitive data leakage
   */
  private sanitizeMessage(message: string): string {
    // Remove potential secrets (basic patterns)
    return message
      .replace(/password["\s]*[:=]["\s]*["']?[^"'\s,}]+/gi, 'password=***')
      .replace(/api[_-]?key["\s]*[:=]["\s]*["']?[^"'\s,}]+/gi, 'api_key=***')
      .replace(/token["\s]*[:=]["\s]*["']?[^"'\s,}]+/gi, 'token=***')
      .replace(/secret["\s]*[:=]["\s]*["']?[^"'\s,}]+/gi, 'secret=***');
  }

  /**
   * Sanitize metadata object
   */
  private sanitizeMetadata(metadata: Record<string, any>): Record<string, any> {
    const sanitized: Record<string, any> = {};
    const sensitiveKeys = ['password', 'token', 'secret', 'key', 'auth'];
    
    for (const [key, value] of Object.entries(metadata)) {
      if (sensitiveKeys.some(sensitive => key.toLowerCase().includes(sensitive))) {
        sanitized[key] = '***';
      } else if (typeof value === 'string') {
        sanitized[key] = this.sanitizeMessage(value);
      } else {
        sanitized[key] = value;
      }
    }
    
    return sanitized;
  }

  /**
   * Public logging methods
   */
  debug(message: string, metadata?: Record<string, any>): void {
    this.log(LogLevel.DEBUG, message, metadata);
  }

  info(message: string, metadata?: Record<string, any>): void {
    this.log(LogLevel.INFO, message, metadata);
  }

  warn(message: string, metadata?: Record<string, any>): void {
    this.log(LogLevel.WARN, message, metadata);
  }

  error(message: string, metadata?: Record<string, any>): void {
    this.log(LogLevel.ERROR, message, metadata);
  }

  /**
   * Flush all transports
   */
  async flush(): Promise<void> {
    const flushPromises = this.transports
      .filter(t => t.flush)
      .map(t => t.flush!());
    await Promise.all(flushPromises);
  }
}

// Export singleton instance
export const logger = Logger.getInstance();