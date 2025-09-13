"use strict";
/**
 * Core Logger Module
 * Provides centralized logging with multiple transports and levels
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.logger = exports.Logger = exports.LogLevel = void 0;
var LogLevel;
(function (LogLevel) {
    LogLevel[LogLevel["DEBUG"] = 0] = "DEBUG";
    LogLevel[LogLevel["INFO"] = 1] = "INFO";
    LogLevel[LogLevel["WARN"] = 2] = "WARN";
    LogLevel[LogLevel["ERROR"] = 3] = "ERROR";
})(LogLevel || (exports.LogLevel = LogLevel = {}));
class Logger {
    static instance;
    transports = [];
    minLevel = LogLevel.INFO;
    buffer = [];
    maxBufferSize = 1000;
    component;
    constructor() { }
    static getInstance() {
        if (!Logger.instance) {
            Logger.instance = new Logger();
        }
        return Logger.instance;
    }
    /**
     * Create a child logger with a specific component name
     */
    child(component) {
        const childLogger = Object.create(this);
        childLogger.component = component;
        return childLogger;
    }
    /**
     * Add a transport for log output
     */
    addTransport(transport) {
        this.transports.push(transport);
    }
    /**
     * Set minimum log level
     */
    setLevel(level) {
        this.minLevel = level;
    }
    /**
     * Get buffered logs (for UI display)
     */
    getBuffer() {
        return [...this.buffer];
    }
    /**
     * Clear log buffer
     */
    clearBuffer() {
        this.buffer = [];
    }
    /**
     * Core logging method
     */
    log(level, message, metadata) {
        if (level < this.minLevel)
            return;
        const entry = {
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
            }
            catch (err) {
                console.error('Log transport error:', err);
            }
        }
    }
    /**
     * Sanitize message to prevent sensitive data leakage
     */
    sanitizeMessage(message) {
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
    sanitizeMetadata(metadata) {
        const sanitized = {};
        const sensitiveKeys = ['password', 'token', 'secret', 'key', 'auth'];
        for (const [key, value] of Object.entries(metadata)) {
            if (sensitiveKeys.some(sensitive => key.toLowerCase().includes(sensitive))) {
                sanitized[key] = '***';
            }
            else if (typeof value === 'string') {
                sanitized[key] = this.sanitizeMessage(value);
            }
            else {
                sanitized[key] = value;
            }
        }
        return sanitized;
    }
    /**
     * Public logging methods
     */
    debug(message, metadata) {
        this.log(LogLevel.DEBUG, message, metadata);
    }
    info(message, metadata) {
        this.log(LogLevel.INFO, message, metadata);
    }
    warn(message, metadata) {
        this.log(LogLevel.WARN, message, metadata);
    }
    error(message, metadata) {
        this.log(LogLevel.ERROR, message, metadata);
    }
    /**
     * Flush all transports
     */
    async flush() {
        const flushPromises = this.transports
            .filter(t => t.flush)
            .map(t => t.flush());
        await Promise.all(flushPromises);
    }
}
exports.Logger = Logger;
// Export singleton instance
exports.logger = Logger.getInstance();
//# sourceMappingURL=logger.js.map