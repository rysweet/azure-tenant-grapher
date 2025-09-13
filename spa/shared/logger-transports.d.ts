/**
 * Logger Transports
 * Various transports for outputting logs
 */
import { LogEntry, LogTransport } from './logger';
/**
 * Console Transport - outputs to console
 */
export declare class ConsoleTransport implements LogTransport {
    private colors;
    private reset;
    log(entry: LogEntry): void;
}
/**
 * File Transport - writes logs to file
 */
export declare class FileTransport implements LogTransport {
    private fileStream?;
    private logPath;
    private writeQueue;
    private isWriting;
    constructor(logDir?: string);
    log(entry: LogEntry): void;
    private processQueue;
    private write;
    flush(): Promise<void>;
}
/**
 * WebSocket Transport - streams logs to connected clients
 */
export declare class WebSocketTransport implements LogTransport {
    private connections;
    private wss?;
    private batchBuffer;
    private batchTimer?;
    private batchInterval;
    setWebSocketServer(wss: any): void;
    private sendInitialLogs;
    log(entry: LogEntry): void;
    private sendBatch;
    flush(): Promise<void>;
}
/**
 * Browser Console Transport - for renderer process
 */
export declare class BrowserConsoleTransport implements LogTransport {
    private styles;
    log(entry: LogEntry): void;
}
/**
 * Memory Transport - stores logs in memory for retrieval
 */
export declare class MemoryTransport implements LogTransport {
    private logs;
    private maxSize;
    constructor(maxSize?: number);
    log(entry: LogEntry): void;
    getLogs(): LogEntry[];
    clear(): void;
}
//# sourceMappingURL=logger-transports.d.ts.map