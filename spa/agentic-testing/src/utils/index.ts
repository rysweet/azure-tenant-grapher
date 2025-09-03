/**
 * Utilities module - Comprehensive utilities and helpers for the Agentic Testing System
 */

// Re-export all utility modules
export * from './logger';
export * from './yamlParser';
export * from './config';
export * from './retry';
export * from './screenshot';
export * from './fileUtils';

// Legacy exports for backward compatibility
import winston from 'winston';

// Logger configuration (legacy)
export const createLegacyLogger = (level: string = 'info'): winston.Logger => {
  return winston.createLogger({
    level,
    format: winston.format.combine(
      winston.format.timestamp(),
      winston.format.errors({ stack: true }),
      winston.format.json()
    ),
    defaultMeta: { service: 'agentic-testing' },
    transports: [
      new winston.transports.File({ filename: 'error.log', level: 'error' }),
      new winston.transports.File({ filename: 'combined.log' }),
      new winston.transports.Console({
        format: winston.format.simple()
      })
    ]
  });
};

// Default legacy logger instance
export const legacyLogger = createLegacyLogger(process.env.LOG_LEVEL || 'info');

// Legacy configuration utilities (kept for backward compatibility)
export class LegacyConfigManager {
  private static config: Record<string, any> = {};
  
  static set(key: string, value: any): void {
    this.config[key] = value;
  }
  
  static get<T = any>(key: string, defaultValue?: T): T {
    return this.config[key] ?? defaultValue;
  }
  
  static has(key: string): boolean {
    return key in this.config;
  }
  
  static loadFromEnv(): void {
    const envVars = [
      'GITHUB_TOKEN',
      'ELECTRON_APP_PATH',
      'TEST_DATA_DIR',
      'LOG_LEVEL',
      'WEBSOCKET_URL',
      'AZURE_TENANT_ID'
    ];
    
    envVars.forEach(envVar => {
      if (process.env[envVar]) {
        this.set(envVar, process.env[envVar]);
      }
    });
  }
}

// Timing utilities
export class TimeUtils {
  static delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
  
  static timeout<T>(promise: Promise<T>, ms: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error(`Operation timed out after ${ms}ms`)), ms)
      )
    ]);
  }
  
  static measureTime<T>(fn: () => Promise<T>): Promise<{ result: T; duration: number }> {
    const start = Date.now();
    return fn().then(result => ({
      result,
      duration: Date.now() - start
    }));
  }
}

// String utilities
export class StringUtils {
  static interpolate(template: string, variables: Record<string, string>): string {
    return template.replace(/\${(\w+)}/g, (match, key) => {
      return variables[key] ?? match;
    });
  }
  
  static slugify(text: string): string {
    return text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-|-$/g, '');
  }
}

// Initialize legacy config from environment
LegacyConfigManager.loadFromEnv();