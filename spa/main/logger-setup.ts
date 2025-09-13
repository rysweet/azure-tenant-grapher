/**
 * Logger Setup for Electron Main Process
 * Initializes the logging system with appropriate transports
 */

import { logger, LogLevel } from '../shared/logger';
import { ConsoleTransport, FileTransport } from '../shared/logger-transports';
import * as path from 'path';

/**
 * Initialize logger for Electron main process
 */
export function initializeMainLogger(): void {
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
  const logDir = process.env.LOG_DIR || path.join(process.cwd(), 'logs');
  logger.addTransport(new FileTransport(logDir));

  // Log initialization
  logger.info('Main process logger initialized', {
    level: logLevel,
    logDir,
    transports: ['console', 'file'],
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