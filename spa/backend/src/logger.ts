export interface Logger {
  debug(message: string, ...args: any[]): void;
  info(message: string, ...args: any[]): void;
  warn(message: string, ...args: any[]): void;
  error(message: string, ...args: any[]): void;
}

export enum LogLevel {
  DEBUG = 0,
  INFO = 1,
  WARN = 2,
  ERROR = 3
}

class SimpleLogger implements Logger {
  private level: LogLevel;

  constructor() {
    const envLevel = process.env.LOG_LEVEL?.toUpperCase();
    switch (envLevel) {
      case 'DEBUG':
        this.level = LogLevel.DEBUG;
        break;
      case 'INFO':
        this.level = LogLevel.INFO;
        break;
      case 'WARN':
        this.level = LogLevel.WARN;
        break;
      case 'ERROR':
        this.level = LogLevel.ERROR;
        break;
      default:
        this.level = process.env.NODE_ENV === 'production' ? LogLevel.INFO : LogLevel.DEBUG;
    }
  }

  private formatMessage(level: string, message: string): string {
    const timestamp = new Date().toISOString();
    return `[${timestamp}] ${level}: ${message}`;
  }

  private sanitizeArgs(args: any[]): any[] {
    return args.map(arg => {
      if (typeof arg === 'string') {
        // Remove any potential sensitive information from strings
        return arg.replace(/(password|secret|key|token)=[^\s]*/gi, '$1=***');
      }
      return arg;
    });
  }

  debug(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.DEBUG) {
      const sanitizedArgs = this.sanitizeArgs(args);
      console.log(this.formatMessage('DEBUG', message), ...sanitizedArgs);
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.INFO) {
      const sanitizedArgs = this.sanitizeArgs(args);
      console.log(this.formatMessage('INFO', message), ...sanitizedArgs);
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.WARN) {
      const sanitizedArgs = this.sanitizeArgs(args);
      console.warn(this.formatMessage('WARN', message), ...sanitizedArgs);
    }
  }

  error(message: string, ...args: any[]): void {
    if (this.level <= LogLevel.ERROR) {
      const sanitizedArgs = this.sanitizeArgs(args);
      console.error(this.formatMessage('ERROR', message), ...sanitizedArgs);
    }
  }
}

export const logger = new SimpleLogger();
