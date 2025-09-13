/**
 * Logger Setup for Backend
 * Initializes the logging system with appropriate transports
 */

import { logger, LogLevel } from '../../shared/logger';
import { ConsoleTransport, FileTransport, WebSocketTransport } from '../../shared/logger-transports';
import { WebSocketServer } from 'ws';

let wsTransport: WebSocketTransport | null = null;

/**
 * Initialize logger for backend/main process
 */
export function initializeLogger(wss?: WebSocketServer): void {
  // Set log level based on environment
  const logLevel = process.env.LOG_LEVEL || 'info';
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

  // Add console transport
  logger.addTransport(new ConsoleTransport());

  // Add file transport for persistent logging
  const logDir = process.env.LOG_DIR || './logs';
  logger.addTransport(new FileTransport(logDir));

  // Add WebSocket transport if server provided
  if (wss) {
    wsTransport = new WebSocketTransport();
    wsTransport.setWebSocketServer(wss);
    logger.addTransport(wsTransport);
  }

  // Log initialization
  logger.info('Logger initialized', {
    level: logLevel,
    logDir,
    transports: ['console', 'file', wss ? 'websocket' : null].filter(Boolean),
  });

  // Handle process exit
  process.on('beforeExit', async () => {
    await logger.flush();
  });
}

/**
 * Create a specialized logger for a component
 */
export function createLogger(component: string) {
  return logger.child(component);
}

/**
 * Replace console.log/error/warn with logger
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
  (global as any).__originalConsole = originalConsole;

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