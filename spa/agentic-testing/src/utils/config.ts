/**
 * Configuration loader for the Agentic Testing System
 * Handles loading from environment variables, config files, and provides validation
 */

import fs from 'fs/promises';
import path from 'path';
import * as yaml from 'js-yaml';
import { TestConfig, LoggingConfig, ExecutionConfig, CLIConfig, UIConfig } from '../models/Config';

/**
 * Configuration loading error
 */
export class ConfigError extends Error {
  constructor(message: string, public configPath?: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

/**
 * Configuration source types
 */
export enum ConfigSource {
  ENVIRONMENT = 'environment',
  FILE = 'file',
  DEFAULT = 'default'
}

/**
 * Configuration validation result
 */
export interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

/**
 * Configuration metadata
 */
export interface ConfigMetadata {
  source: ConfigSource;
  loadedAt: Date;
  filePath?: string;
  environment: Record<string, string>;
}

/**
 * Default configuration values
 */
const DEFAULT_CONFIG: TestConfig = {
  execution: {
    maxParallel: 3,
    defaultTimeout: 30000,
    continueOnFailure: true,
    maxRetries: 2,
    retryDelay: 1000,
    randomizeOrder: false,
    resourceLimits: {
      maxMemory: 1024 * 1024 * 1024, // 1GB
      maxCpuUsage: 80,
      maxDiskUsage: 10 * 1024 * 1024 * 1024, // 10GB
      maxExecutionTime: 600000, // 10 minutes
      maxOpenFiles: 1024
    },
    cleanup: {
      cleanupAfterEach: true,
      cleanupAfterAll: true,
      cleanupDirectories: ['temp', 'screenshots'],
      cleanupFiles: ['*.tmp', '*.temp'],
      terminateProcesses: [],
      stopServices: [],
      customCleanupScripts: []
    }
  },
  cli: {
    executablePath: 'atg',
    workingDirectory: process.cwd(),
    defaultTimeout: 30000,
    environment: {},
    captureOutput: true,
    maxRetries: 2,
    retryDelay: 1000
  },
  ui: {
    browser: 'chromium',
    headless: false,
    viewport: { width: 1280, height: 720 },
    baseUrl: 'http://localhost:3000',
    defaultTimeout: 30000,
    screenshotDir: './screenshots',
    recordVideo: false
  },
  priority: {
    enabled: true,
    executionOrder: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'],
    failFastOnCritical: true,
    maxParallelByPriority: {
      CRITICAL: 1,
      HIGH: 2,
      MEDIUM: 3,
      LOW: 4
    },
    timeoutMultipliers: {
      CRITICAL: 2.0,
      HIGH: 1.5,
      MEDIUM: 1.0,
      LOW: 0.8
    },
    retryCountsByPriority: {
      CRITICAL: 3,
      HIGH: 2,
      MEDIUM: 1,
      LOW: 0
    }
  },
  logging: {
    level: 'info',
    console: true,
    format: 'structured',
    includeTimestamp: true,
    maxFileSize: 10 * 1024 * 1024,
    maxFiles: 5,
    compress: true
  },
  reporting: {
    outputDir: './reports',
    formats: ['html', 'json'],
    includeScreenshots: true,
    includeLogs: true,
    customTemplates: {},
    generationTimeout: 30000
  },
  notifications: {
    enabled: false,
    channels: [],
    triggers: [],
    templates: {}
  },
  plugins: {}
};

/**
 * Environment variable mappings
 */
const ENV_MAPPINGS: Record<string, string> = {
  'AGENTIC_LOG_LEVEL': 'logging.level',
  'AGENTIC_MAX_PARALLEL': 'execution.maxParallel',
  'AGENTIC_TIMEOUT': 'execution.defaultTimeout',
  'AGENTIC_HEADLESS': 'ui.headless',
  'AGENTIC_BROWSER': 'ui.browser',
  'AGENTIC_BASE_URL': 'ui.baseUrl',
  'AGENTIC_CLI_PATH': 'cli.executablePath',
  'AGENTIC_WORKING_DIR': 'cli.workingDirectory',
  'AGENTIC_SCREENSHOT_DIR': 'ui.screenshotDir',
  'AGENTIC_REPORT_DIR': 'reporting.outputDir',
  'GITHUB_TOKEN': 'github.token',
  'GITHUB_OWNER': 'github.owner',
  'GITHUB_REPO': 'github.repository'
};

/**
 * Configuration manager class
 */
export class ConfigManager {
  private config: TestConfig;
  private metadata: ConfigMetadata;
  private watchers: Array<(config: TestConfig) => void> = [];

  constructor(initialConfig?: Partial<TestConfig>) {
    this.config = this.mergeConfigs(DEFAULT_CONFIG, initialConfig || {});
    this.metadata = {
      source: ConfigSource.DEFAULT,
      loadedAt: new Date(),
      environment: { ...process.env } as Record<string, string>
    };
  }

  /**
   * Load configuration from a file
   */
  async loadFromFile(filePath: string): Promise<void> {
    try {
      const absolutePath = path.resolve(filePath);
      const fileContent = await fs.readFile(absolutePath, 'utf-8');
      const extension = path.extname(absolutePath).toLowerCase();

      let fileConfig: any;

      if (extension === '.json') {
        fileConfig = JSON.parse(fileContent);
      } else if (extension === '.yaml' || extension === '.yml') {
        fileConfig = yaml.load(fileContent);
      } else {
        throw new ConfigError(`Unsupported config file format: ${extension}`, filePath);
      }

      // Validate the loaded configuration
      const validation = this.validateConfig(fileConfig);
      if (!validation.valid) {
        throw new ConfigError(`Configuration validation failed: ${validation.errors.join(', ')}`, filePath);
      }

      // Merge with existing config
      this.config = this.mergeConfigs(this.config, fileConfig);
      this.metadata = {
        source: ConfigSource.FILE,
        loadedAt: new Date(),
        filePath: absolutePath,
        environment: { ...process.env } as Record<string, string>
      };

      // Notify watchers
      this.notifyWatchers();

    } catch (error) {
      if (error instanceof ConfigError) {
        throw error;
      }
      throw new ConfigError(`Failed to load config from ${filePath}: ${error.message}`, filePath);
    }
  }

  /**
   * Load configuration from environment variables
   */
  loadFromEnvironment(): void {
    const envConfig: any = {};

    Object.entries(ENV_MAPPINGS).forEach(([envVar, configPath]) => {
      const envValue = process.env[envVar];
      if (envValue !== undefined) {
        this.setNestedValue(envConfig, configPath, this.parseEnvValue(envValue));
      }
    });

    // Load additional environment variables for CLI config
    const cliEnvVars = Object.keys(process.env).reduce((acc, key) => {
      if (key.startsWith('AGENTIC_CLI_ENV_')) {
        const envKey = key.replace('AGENTIC_CLI_ENV_', '');
        acc[envKey] = process.env[key]!;
      }
      return acc;
    }, {} as Record<string, string>);

    if (Object.keys(cliEnvVars).length > 0) {
      this.setNestedValue(envConfig, 'cli.environment', cliEnvVars);
    }

    // Merge environment config
    if (Object.keys(envConfig).length > 0) {
      this.config = this.mergeConfigs(this.config, envConfig);
      this.metadata.source = ConfigSource.ENVIRONMENT;
      this.metadata.loadedAt = new Date();
      this.notifyWatchers();
    }
  }

  /**
   * Get the current configuration
   */
  getConfig(): TestConfig {
    return { ...this.config }; // Return a copy to prevent mutations
  }

  /**
   * Get configuration metadata
   */
  getMetadata(): ConfigMetadata {
    return { ...this.metadata };
  }

  /**
   * Update configuration at runtime
   */
  updateConfig(updates: Partial<TestConfig>): void {
    const validation = this.validateConfig(updates);
    if (!validation.valid) {
      throw new ConfigError(`Configuration update validation failed: ${validation.errors.join(', ')}`);
    }

    this.config = this.mergeConfigs(this.config, updates);
    this.notifyWatchers();
  }

  /**
   * Get a specific configuration value by path
   */
  get<T = any>(path: string, defaultValue?: T): T {
    return this.getNestedValue(this.config, path) ?? defaultValue;
  }

  /**
   * Set a specific configuration value by path
   */
  set(path: string, value: any): void {
    const updates = {};
    this.setNestedValue(updates, path, value);
    this.updateConfig(updates);
  }

  /**
   * Watch for configuration changes
   */
  watch(callback: (config: TestConfig) => void): () => void {
    this.watchers.push(callback);

    // Return unwatch function
    return () => {
      const index = this.watchers.indexOf(callback);
      if (index > -1) {
        this.watchers.splice(index, 1);
      }
    };
  }

  /**
   * Validate configuration object
   */
  validateConfig(config: any): ValidationResult {
    const errors: string[] = [];
    const warnings: string[] = [];

    try {
      // Basic type checks
      if (config.execution) {
        if (typeof config.execution.maxParallel === 'number' && config.execution.maxParallel < 1) {
          errors.push('execution.maxParallel must be at least 1');
        }
        if (typeof config.execution.defaultTimeout === 'number' && config.execution.defaultTimeout < 1000) {
          warnings.push('execution.defaultTimeout is less than 1 second');
        }
      }

      if (config.ui) {
        if (config.ui.browser && !['chromium', 'firefox', 'webkit'].includes(config.ui.browser)) {
          errors.push('ui.browser must be one of: chromium, firefox, webkit');
        }
        if (config.ui.viewport) {
          if (config.ui.viewport.width < 100 || config.ui.viewport.height < 100) {
            errors.push('ui.viewport dimensions must be at least 100x100');
          }
        }
      }

      if (config.logging) {
        if (config.logging.level && !['debug', 'info', 'warn', 'error'].includes(config.logging.level)) {
          errors.push('logging.level must be one of: debug, info, warn, error');
        }
      }

      if (config.priority) {
        if (config.priority.executionOrder && !Array.isArray(config.priority.executionOrder)) {
          errors.push('priority.executionOrder must be an array');
        }
      }

      // Check for required CLI executable
      if (config.cli?.executablePath) {
        // Note: We can't check file existence here as it might not be available during config loading
        // This should be done during runtime validation
      }

    } catch (error) {
      errors.push(`Configuration validation error: ${error.message}`);
    }

    return {
      valid: errors.length === 0,
      errors,
      warnings
    };
  }

  /**
   * Create a configuration for a specific environment
   */
  createEnvironmentConfig(environment: 'development' | 'testing' | 'production'): TestConfig {
    const baseConfig = { ...this.config };

    switch (environment) {
      case 'development':
        return this.mergeConfigs(baseConfig, {
          logging: { level: 'debug' as const },
          ui: { headless: false },
          execution: { continueOnFailure: true }
        });

      case 'testing':
        return this.mergeConfigs(baseConfig, {
          logging: { level: 'info' as const },
          ui: { headless: true },
          execution: { continueOnFailure: false, maxRetries: 0 }
        });

      case 'production':
        return this.mergeConfigs(baseConfig, {
          logging: { level: 'warn' as const },
          ui: { headless: true },
          execution: { continueOnFailure: false },
          notifications: { enabled: true }
        });

      default:
        return baseConfig;
    }
  }

  /**
   * Export configuration to file
   */
  async exportToFile(filePath: string, format: 'json' | 'yaml' = 'yaml'): Promise<void> {
    const config = this.getConfig();
    let content: string;

    if (format === 'json') {
      content = JSON.stringify(config, null, 2);
    } else {
      content = yaml.dump(config, {
        indent: 2,
        lineWidth: 120,
        noRefs: true,
        sortKeys: false
      });
    }

    await fs.writeFile(filePath, content, 'utf-8');
  }

  /**
   * Deep merge two configuration objects
   */
  private mergeConfigs<T extends Record<string, any>>(target: T, source: Partial<T>): T {
    const result = { ...target };

    Object.keys(source).forEach(key => {
      const sourceValue = source[key as keyof T];
      const targetValue = result[key as keyof T];

      if (sourceValue !== undefined) {
        if (typeof sourceValue === 'object' && !Array.isArray(sourceValue) && sourceValue !== null &&
            typeof targetValue === 'object' && !Array.isArray(targetValue) && targetValue !== null) {
          (result as any)[key] = this.mergeConfigs(targetValue, sourceValue);
        } else {
          (result as any)[key] = sourceValue;
        }
      }
    });

    return result;
  }

  /**
   * Get nested value from object using dot notation
   */
  private getNestedValue(obj: any, path: string): any {
    return path.split('.').reduce((current, key) => current?.[key], obj);
  }

  /**
   * Set nested value in object using dot notation
   */
  private setNestedValue(obj: any, path: string, value: any): void {
    const keys = path.split('.');
    const lastKey = keys.pop()!;

    const target = keys.reduce((current, key) => {
      if (!(key in current) || typeof current[key] !== 'object') {
        current[key] = {};
      }
      return current[key];
    }, obj);

    target[lastKey] = value;
  }

  /**
   * Parse environment variable value to appropriate type
   */
  private parseEnvValue(value: string): any {
    // Boolean values
    if (value.toLowerCase() === 'true') return true;
    if (value.toLowerCase() === 'false') return false;

    // Number values
    if (/^\d+$/.test(value)) return parseInt(value, 10);
    if (/^\d+\.\d+$/.test(value)) return parseFloat(value);

    // JSON values
    if ((value.startsWith('{') && value.endsWith('}')) ||
        (value.startsWith('[') && value.endsWith(']'))) {
      try {
        return JSON.parse(value);
      } catch {
        // If JSON parsing fails, return as string
      }
    }

    // Array values (comma-separated)
    if (value.includes(',')) {
      return value.split(',').map(v => v.trim());
    }

    return value;
  }

  /**
   * Notify configuration watchers
   */
  private notifyWatchers(): void {
    this.watchers.forEach(callback => {
      try {
        callback(this.getConfig());
      } catch (error) {
        console.error('Error in configuration watcher:', error);
      }
    });
  }
}

/**
 * Global configuration manager instance
 */
export const globalConfigManager = new ConfigManager();

/**
 * Load configuration from default locations
 */
export async function loadDefaultConfig(): Promise<TestConfig> {
  // Try to load from various default locations
  const configFiles = [
    'agentic-test.config.yaml',
    'agentic-test.config.yml',
    'agentic-test.config.json',
    '.agentic-testrc.yaml',
    '.agentic-testrc.yml',
    '.agentic-testrc.json'
  ];

  for (const configFile of configFiles) {
    try {
      await fs.access(configFile);
      await globalConfigManager.loadFromFile(configFile);
      break;
    } catch {
      // File doesn't exist, try next one
    }
  }

  // Load environment variables
  globalConfigManager.loadFromEnvironment();

  return globalConfigManager.getConfig();
}

/**
 * Create a new configuration manager with the provided config
 */
export function createConfigManager(config?: Partial<TestConfig>): ConfigManager {
  return new ConfigManager(config);
}

/**
 * Convenience function to get current configuration
 */
export function getConfig(): TestConfig {
  return globalConfigManager.getConfig();
}

/**
 * Convenience function to update configuration
 */
export function updateConfig(updates: Partial<TestConfig>): void {
  globalConfigManager.updateConfig(updates);
}
