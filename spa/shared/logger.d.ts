/**
 * Core Logger Module
 * Provides centralized logging with multiple transports and levels
 */
export declare enum LogLevel {
    DEBUG = 0,
    INFO = 1,
    WARN = 2,
    ERROR = 3
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
export declare class Logger {
    private static instance;
    private transports;
    private minLevel;
    private buffer;
    private maxBufferSize;
    private component?;
    private constructor();
    static getInstance(): Logger;
    /**
     * Create a child logger with a specific component name
     */
    child(component: string): Logger;
    /**
     * Add a transport for log output
     */
    addTransport(transport: LogTransport): void;
    /**
     * Set minimum log level
     */
    setLevel(level: LogLevel): void;
    /**
     * Get buffered logs (for UI display)
     */
    getBuffer(): LogEntry[];
    /**
     * Clear log buffer
     */
    clearBuffer(): void;
    /**
     * Core logging method
     */
    private log;
    /**
     * Sanitize message to prevent sensitive data leakage
     */
    private sanitizeMessage;
    /**
     * Sanitize metadata object
     */
    private sanitizeMetadata;
    /**
     * Public logging methods
     */
    debug(message: string, metadata?: Record<string, any>): void;
    info(message: string, metadata?: Record<string, any>): void;
    warn(message: string, metadata?: Record<string, any>): void;
    error(message: string, metadata?: Record<string, any>): void;
    /**
     * Flush all transports
     */
    flush(): Promise<void>;
}
export declare const logger: Logger;
//# sourceMappingURL=logger.d.ts.map