/**
 * Logger Transports
 * Various transports for outputting logs
 */

import { LogEntry, LogLevel, LogTransport } from './logger';
import * as fs from 'fs';
import * as path from 'path';
import { WebSocket } from 'ws';

/**
 * Console Transport - outputs to console
 */
export class ConsoleTransport implements LogTransport {
  private colors = {
    [LogLevel.DEBUG]: '\x1b[36m', // Cyan
    [LogLevel.INFO]: '\x1b[32m',  // Green
    [LogLevel.WARN]: '\x1b[33m',  // Yellow
    [LogLevel.ERROR]: '\x1b[31m', // Red
  };
  private reset = '\x1b[0m';

  log(entry: LogEntry): void {
    const levelName = LogLevel[entry.level];
    const color = this.colors[entry.level];
    const component = entry.component ? `[${entry.component}]` : '';

    const message = `${color}[${entry.timestamp}] ${levelName}${this.reset} ${component} ${entry.message}`;

    if (entry.metadata) {
      console.log(message, entry.metadata);
    } else {
      console.log(message);
    }
  }
}

/**
 * File Transport - writes logs to file
 */
export class FileTransport implements LogTransport {
  private fileStream?: fs.WriteStream;
  private logPath: string;
  private writeQueue: string[] = [];
  private isWriting = false;

  constructor(logDir: string = './logs') {
    // Ensure log directory exists
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }

    // Create log file with date
    const date = new Date().toISOString().split('T')[0];
    this.logPath = path.join(logDir, `app-${date}.log`);

    // Open file stream
    this.fileStream = fs.createWriteStream(this.logPath, { flags: 'a' });
  }

  log(entry: LogEntry): void {
    const logLine = JSON.stringify({
      ...entry,
      levelName: LogLevel[entry.level],
    }) + '\n';

    this.writeQueue.push(logLine);
    this.processQueue();
  }

  private async processQueue(): Promise<void> {
    if (this.isWriting || this.writeQueue.length === 0) return;

    this.isWriting = true;
    const batch = this.writeQueue.splice(0, 100); // Process in batches

    try {
      for (const line of batch) {
        await this.write(line);
      }
    } catch (err) {
      console.error('Failed to write logs to file:', err);
    } finally {
      this.isWriting = false;
      if (this.writeQueue.length > 0) {
        setImmediate(() => this.processQueue());
      }
    }
  }

  private write(data: string): Promise<void> {
    return new Promise((resolve, reject) => {
      if (!this.fileStream) {
        reject(new Error('File stream not initialized'));
        return;
      }

      this.fileStream.write(data, (err) => {
        if (err) reject(err);
        else resolve();
      });
    });
  }

  async flush(): Promise<void> {
    while (this.writeQueue.length > 0) {
      await this.processQueue();
    }

    return new Promise((resolve) => {
      if (this.fileStream) {
        this.fileStream.end(() => resolve());
      } else {
        resolve();
      }
    });
  }
}

/**
 * WebSocket Transport - streams logs to connected clients
 */
export class WebSocketTransport implements LogTransport {
  private connections: Set<WebSocket> = new Set();
  private wss?: any; // WebSocketServer instance
  private batchBuffer: LogEntry[] = [];
  private batchTimer?: NodeJS.Timeout;
  private batchInterval = 100; // ms

  setWebSocketServer(wss: any): void {
    this.wss = wss;

    // Handle new connections
    wss.on('connection', (ws: WebSocket) => {
      this.connections.add(ws);

      // Send initial buffer of recent logs
      this.sendInitialLogs(ws);

      ws.on('close', () => {
        this.connections.delete(ws);
      });

      ws.on('error', () => {
        this.connections.delete(ws);
      });
    });
  }

  private sendInitialLogs(ws: WebSocket): void {
    // Send last 100 logs from buffer if available
    const logger = require('./logger').logger;
    const buffer = logger.getBuffer();
    const recentLogs = buffer.slice(-100);

    if (recentLogs.length > 0) {
      try {
        ws.send(JSON.stringify({
          type: 'log-batch',
          entries: recentLogs,
        }));
      } catch (err) {
        console.error('Failed to send initial logs:', err);
      }
    }
  }

  log(entry: LogEntry): void {
    // Add to batch buffer
    this.batchBuffer.push(entry);

    // Start or reset batch timer
    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
    }

    this.batchTimer = setTimeout(() => {
      this.sendBatch();
    }, this.batchInterval);

    // Send immediately if buffer is large
    if (this.batchBuffer.length >= 20) {
      this.sendBatch();
    }
  }

  private sendBatch(): void {
    if (this.batchBuffer.length === 0) return;

    const batch = [...this.batchBuffer];
    this.batchBuffer = [];

    const message = JSON.stringify({
      type: 'log-batch',
      entries: batch,
    });

    // Send to all connected clients
    for (const ws of this.connections) {
      if (ws.readyState === WebSocket.OPEN) {
        try {
          ws.send(message);
        } catch (err) {
          console.error('Failed to send log to client:', err);
          this.connections.delete(ws);
        }
      }
    }

    if (this.batchTimer) {
      clearTimeout(this.batchTimer);
      this.batchTimer = undefined;
    }
  }

  async flush(): Promise<void> {
    this.sendBatch();
  }
}

/**
 * Browser Console Transport - for renderer process
 */
export class BrowserConsoleTransport implements LogTransport {
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

/**
 * Memory Transport - stores logs in memory for retrieval
 */
export class MemoryTransport implements LogTransport {
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
