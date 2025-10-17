/**
 * Logger Setup for Renderer Process
 * Initializes the logging system for the frontend
 */

import { logger, LogLevel, type LogEntry } from '../../../shared/logger';

// Memory transport to store logs for the LogsTab component
class MemoryTransport {
  private logs: LogEntry[] = [];
  private maxSize: number;

  constructor(maxSize: number = 10000) {
    this.maxSize = maxSize;
  }

  log(entry: LogEntry): void {
    this.logs.push(entry);
    if (this.logs.length > this.maxSize) {
      this.logs.shift();
    }
  }

  getLogs(): LogEntry[] {
    return [...this.logs];
  }

  clear(): void {
    this.logs = [];
  }
}

const memoryTransport = new MemoryTransport(5000);

// Browser console transport
class BrowserConsoleTransport {
  private styles = {
    [LogLevel.DEBUG]: 'color: #6B7280',
    [LogLevel.INFO]: 'color: #10B981',
    [LogLevel.WARN]: 'color: #F59E0B',
    [LogLevel.ERROR]: 'color: #EF4444',
  };

  log(entry: LogEntry): void {
    const levelName = LogLevel[entry.level];
    const style = this.styles[entry.level];
    const component = entry.component ? `[${entry.component}]` : '';

    const prefix = `%c[${entry.timestamp}] ${levelName} ${component}`;

    if (entry.metadata) {
      console.log(`${prefix} ${entry.message}`, style, entry.metadata);
    } else {
      console.log(`${prefix} ${entry.message}`, style);
    }
  }
}

// WebSocket transport for receiving logs from backend
export interface LogBatchMessage {
  type: 'log-batch';
  entries: LogEntry[];
}

export class FrontendWebSocketTransport {
  private ws: WebSocket | null = null;
  private url: string;
  private reconnectTimer: NodeJS.Timeout | null = null;
  private reconnectDelay = 1000;
  private maxReconnectDelay = 30000;
  private listeners: Set<(entries: LogEntry[]) => void> = new Set();

  constructor(url: string = 'ws://localhost:3001/logs') {
    this.url = url;
    this.connect();
  }

  private connect(): void {
    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        console.log('Connected to log WebSocket');
        this.reconnectDelay = 1000;
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data.type === 'log-batch' && Array.isArray(data.entries)) {
            // Notify all listeners
            this.listeners.forEach(listener => {
              listener(data.entries);
            });
          }
        } catch (err) {
          console.error('Failed to parse log message:', err);
        }
      };

      this.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
      };

      this.ws.onclose = () => {
        console.log('Disconnected from log WebSocket');
        this.ws = null;
        this.scheduleReconnect();
      };
    } catch (err) {
      console.error('Failed to connect to log WebSocket:', err);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimer) return;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  }

  onLogBatch(listener: (entries: LogEntry[]) => void): () => void {
    this.listeners.add(listener);
    // Return unsubscribe function
    return () => {
      this.listeners.delete(listener);
    };
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  close(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.listeners.clear();
  }
}

let wsTransport: FrontendWebSocketTransport | null = null;

/**
 * Initialize logger for renderer process with WebSocket support
 */
export function initializeFrontendLogger(): FrontendWebSocketTransport {
  // Create WebSocket transport for receiving backend logs
  if (!wsTransport) {
    wsTransport = new FrontendWebSocketTransport();
  }

  return wsTransport;
}

/**
 * Get WebSocket transport instance
 */
export function getLogWebSocket(): FrontendWebSocketTransport | null {
  return wsTransport;
}

/**
 * Initialize logger for renderer process
 */
export function initializeRendererLogger(): void {
  // Set log level based on environment or localStorage
  const savedLevel = localStorage.getItem('logLevel');
  const logLevel = savedLevel || (process.env.NODE_ENV === 'development' ? 'debug' : 'info');

  switch (logLevel.toLowerCase()) {
    case 'debug':
      logger.setLevel(LogLevel.DEBUG);
      break;
    case 'warn':
      logger.setLevel(LogLevel.WARN);
      break;
    case 'error':
      logger.setLevel(LogLevel.ERROR);
      break;
    default:
      logger.setLevel(LogLevel.INFO);
  }

  // Add browser console transport with styling
  logger.addTransport(new BrowserConsoleTransport());

  // Add memory transport for UI display
  logger.addTransport(memoryTransport);

  // Log initialization
  logger.info('Renderer logger initialized', {
    level: logLevel,
    transports: ['browser-console', 'memory'],
  });

  // Handle unhandled errors
  window.addEventListener('error', (event) => {
    logger.error('Unhandled error', {
      message: event.message,
      filename: event.filename,
      lineno: event.lineno,
      colno: event.colno,
      error: event.error?.stack,
    });
  });

  window.addEventListener('unhandledrejection', (event) => {
    logger.error('Unhandled promise rejection', {
      reason: event.reason,
    });
  });
}

/**
 * Get logs from memory for display
 */
export function getLogs() {
  return memoryTransport.getLogs();
}

/**
 * Clear memory logs
 */
export function clearLogs() {
  memoryTransport.clear();
}

/**
 * Create a specialized logger for a component
 */
export function createLogger(component: string) {
  return logger.child(component);
}

/**
 * Create a component logger (alias for createLogger)
 */
export function createComponentLogger(component: string) {
  return logger.child(component);
}

/**
 * Replace console methods with logger
 */
export function replaceConsole(): void {
  const originalConsole = {
    log: console.log,
    error: console.error,
    warn: console.warn,
    debug: console.debug,
    info: console.info,
  };

  // Store originals for emergency use
  (window as any).__originalConsole = originalConsole;

  // Replace console methods
  console.log = (...args: any[]) => {
    logger.info(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' '));
  };

  console.info = (...args: any[]) => {
    logger.info(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' '));
  };

  console.warn = (...args: any[]) => {
    logger.warn(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' '));
  };

  console.error = (...args: any[]) => {
    logger.error(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' '));
  };

  console.debug = (...args: any[]) => {
    logger.debug(args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' '));
  };
}

// Export the main logger instance and types
export { logger, LogLevel, type LogEntry };

// Also export as SystemLogEntry and SystemLogLevel for compatibility
export type SystemLogEntry = LogEntry;
export { LogLevel as SystemLogLevel };
