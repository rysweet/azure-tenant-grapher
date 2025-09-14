"use strict";
/**
 * Logger Transports
 * Various transports for outputting logs
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.MemoryTransport = exports.BrowserConsoleTransport = exports.WebSocketTransport = exports.FileTransport = exports.ConsoleTransport = void 0;
const logger_1 = require("./logger");
const fs = __importStar(require("fs"));
const path = __importStar(require("path"));
/**
 * Console Transport - outputs to console
 */
class ConsoleTransport {
    colors = {
        [logger_1.LogLevel.DEBUG]: '\x1b[36m', // Cyan
        [logger_1.LogLevel.INFO]: '\x1b[32m', // Green
        [logger_1.LogLevel.WARN]: '\x1b[33m', // Yellow
        [logger_1.LogLevel.ERROR]: '\x1b[31m', // Red
    };
    reset = '\x1b[0m';
    log(entry) {
        const levelName = logger_1.LogLevel[entry.level];
        const color = this.colors[entry.level];
        const component = entry.component ? `[${entry.component}]` : '';
        const message = `${color}[${entry.timestamp}] ${levelName}${this.reset} ${component} ${entry.message}`;
        if (entry.metadata) {
            console.log(message, entry.metadata);
        }
        else {
            console.log(message);
        }
    }
}
exports.ConsoleTransport = ConsoleTransport;
/**
 * File Transport - writes logs to file
 */
class FileTransport {
    fileStream;
    logPath;
    writeQueue = [];
    isWriting = false;
    constructor(logDir = './logs') {
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
    log(entry) {
        const logLine = JSON.stringify({
            ...entry,
            levelName: logger_1.LogLevel[entry.level],
        }) + '\n';
        this.writeQueue.push(logLine);
        this.processQueue();
    }
    async processQueue() {
        if (this.isWriting || this.writeQueue.length === 0)
            return;
        this.isWriting = true;
        const batch = this.writeQueue.splice(0, 100); // Process in batches
        try {
            for (const line of batch) {
                await this.write(line);
            }
        }
        catch (err) {
            console.error('Failed to write logs to file:', err);
        }
        finally {
            this.isWriting = false;
            if (this.writeQueue.length > 0) {
                setImmediate(() => this.processQueue());
            }
        }
    }
    write(data) {
        return new Promise((resolve, reject) => {
            if (!this.fileStream) {
                reject(new Error('File stream not initialized'));
                return;
            }
            this.fileStream.write(data, (err) => {
                if (err)
                    reject(err);
                else
                    resolve();
            });
        });
    }
    async flush() {
        while (this.writeQueue.length > 0) {
            await this.processQueue();
        }
        return new Promise((resolve) => {
            if (this.fileStream) {
                this.fileStream.end(() => resolve());
            }
            else {
                resolve();
            }
        });
    }
}
exports.FileTransport = FileTransport;
/**
 * WebSocket Transport - streams logs to connected clients
 */
class WebSocketTransport {
    connections = new Set();
    wss; // WebSocketServer instance
    batchBuffer = [];
    batchTimer;
    batchInterval = 100; // ms
    setWebSocketServer(wss) {
        this.wss = wss;
        // Handle new connections
        wss.on('connection', (ws) => {
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
    sendInitialLogs(ws) {
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
            }
            catch (err) {
                console.error('Failed to send initial logs:', err);
            }
        }
    }
    log(entry) {
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
    sendBatch() {
        if (this.batchBuffer.length === 0)
            return;
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
                }
                catch (err) {
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
    async flush() {
        this.sendBatch();
    }
}
exports.WebSocketTransport = WebSocketTransport;
/**
 * Browser Console Transport - for renderer process
 */
class BrowserConsoleTransport {
    styles = {
        [logger_1.LogLevel.DEBUG]: 'color: #6B7280',
        [logger_1.LogLevel.INFO]: 'color: #10B981',
        [logger_1.LogLevel.WARN]: 'color: #F59E0B',
        [logger_1.LogLevel.ERROR]: 'color: #EF4444',
    };
    log(entry) {
        const levelName = logger_1.LogLevel[entry.level];
        const style = this.styles[entry.level];
        const component = entry.component ? `[${entry.component}]` : '';
        const prefix = `%c[${entry.timestamp}] ${levelName} ${component}`;
        if (entry.metadata) {
            console.log(`${prefix} ${entry.message}`, style, entry.metadata);
        }
        else {
            console.log(`${prefix} ${entry.message}`, style);
        }
    }
}
exports.BrowserConsoleTransport = BrowserConsoleTransport;
/**
 * Memory Transport - stores logs in memory for retrieval
 */
class MemoryTransport {
    logs = [];
    maxSize;
    constructor(maxSize = 10000) {
        this.maxSize = maxSize;
    }
    log(entry) {
        this.logs.push(entry);
        if (this.logs.length > this.maxSize) {
            this.logs.shift();
        }
    }
    getLogs() {
        return [...this.logs];
    }
    clear() {
        this.logs = [];
    }
}
exports.MemoryTransport = MemoryTransport;
//# sourceMappingURL=logger-transports.js.map