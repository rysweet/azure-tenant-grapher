/**
 * Configuration interfaces for the Agentic Testing System
 */

/**
 * CLI testing configuration
 */
export interface CLIConfig {
  /** Path to the CLI executable */
  executablePath: string;
  
  /** Default working directory for CLI commands */
  workingDirectory: string;
  
  /** Default timeout for CLI commands in milliseconds */
  defaultTimeout: number;
  
  /** Environment variables to set for CLI execution */
  environment: Record<string, string>;
  
  /** Whether to capture stdout/stderr */
  captureOutput: boolean;
  
  /** Shell to use for command execution */
  shell?: string;
  
  /** Path to log file for CLI output */
  logFile?: string;
  
  /** Maximum number of retries for failed commands */
  maxRetries: number;
  
  /** Delay between retries in milliseconds */
  retryDelay: number;
}

/**
 * UI/GUI testing configuration
 */
export interface UIConfig {
  /** Browser type for web UI testing */
  browser: 'chromium' | 'firefox' | 'webkit';
  
  /** Whether to run browser in headless mode */
  headless: boolean;
  
  /** Browser viewport size */
  viewport: {
    width: number;
    height: number;
  };
  
  /** Base URL for web application */
  baseUrl: string;
  
  /** Default timeout for UI operations in milliseconds */
  defaultTimeout: number;
  
  /** Directory for storing screenshots */
  screenshotDir: string;
  
  /** Directory for storing videos */
  videoDir?: string;
  
  /** Whether to record videos of test execution */
  recordVideo: boolean;
  
  /** Slow motion delay for actions in milliseconds */
  slowMo?: number;
  
  /** Custom user agent string */
  userAgent?: string;
  
  /** Device emulation settings */
  device?: string;
  
  /** Geolocation settings */
  geolocation?: {
    latitude: number;
    longitude: number;
  };
  
  /** Timezone setting */
  timezone?: string;
  
  /** Locale setting */
  locale?: string;
}

/**
 * GitHub integration configuration
 */
export interface GitHubConfig {
  /** GitHub personal access token */
  token: string;
  
  /** Repository owner */
  owner: string;
  
  /** Repository name */
  repository: string;
  
  /** Base branch for pull requests */
  baseBranch: string;
  
  /** Whether to create issues for test failures */
  createIssuesOnFailure: boolean;
  
  /** Labels to apply to created issues */
  issueLabels: string[];
  
  /** Template for issue titles */
  issueTitleTemplate: string;
  
  /** Template for issue bodies */
  issueBodyTemplate: string;
  
  /** Whether to create pull requests for fixes */
  createPullRequestsForFixes: boolean;
  
  /** Auto-assign issues to users */
  autoAssignUsers: string[];
  
  /** Milestone to assign to issues */
  milestone?: string;
}

/**
 * Priority-based execution configuration
 */
export interface PriorityConfig {
  /** Whether to enable priority-based execution */
  enabled: boolean;
  
  /** Execution order for priorities */
  executionOrder: string[];
  
  /** Whether to fail fast on critical test failures */
  failFastOnCritical: boolean;
  
  /** Maximum parallel executions per priority level */
  maxParallelByPriority: Record<string, number>;
  
  /** Timeout multipliers by priority */
  timeoutMultipliers: Record<string, number>;
  
  /** Retry counts by priority */
  retryCountsByPriority: Record<string, number>;
}

/**
 * Test execution configuration
 */
export interface ExecutionConfig {
  /** Maximum number of parallel test executions */
  maxParallel: number;
  
  /** Default timeout for test scenarios in milliseconds */
  defaultTimeout: number;
  
  /** Whether to continue execution after failures */
  continueOnFailure: boolean;
  
  /** Maximum number of retries for failed tests */
  maxRetries: number;
  
  /** Delay between retries in milliseconds */
  retryDelay: number;
  
  /** Whether to randomize test execution order */
  randomizeOrder: boolean;
  
  /** Seed for randomization */
  randomSeed?: number;
  
  /** Resource limits */
  resourceLimits: ResourceLimits;
  
  /** Cleanup configuration */
  cleanup: CleanupConfig;
}

/**
 * Resource limits for test execution
 */
export interface ResourceLimits {
  /** Maximum memory usage in bytes */
  maxMemory: number;
  
  /** Maximum CPU usage percentage */
  maxCpuUsage: number;
  
  /** Maximum disk space usage in bytes */
  maxDiskUsage: number;
  
  /** Maximum execution time per test in milliseconds */
  maxExecutionTime: number;
  
  /** Maximum number of open files */
  maxOpenFiles: number;
}

/**
 * Cleanup configuration
 */
export interface CleanupConfig {
  /** Whether to clean up after each test */
  cleanupAfterEach: boolean;
  
  /** Whether to clean up after all tests */
  cleanupAfterAll: boolean;
  
  /** Directories to clean up */
  cleanupDirectories: string[];
  
  /** Files to clean up (glob patterns) */
  cleanupFiles: string[];
  
  /** Processes to terminate */
  terminateProcesses: string[];
  
  /** Services to stop */
  stopServices: string[];
  
  /** Custom cleanup scripts */
  customCleanupScripts: string[];
}

/**
 * Main test configuration
 */
export interface TestConfig {
  /** Test execution settings */
  execution: ExecutionConfig;
  
  /** CLI testing configuration */
  cli: CLIConfig;
  
  /** UI testing configuration */
  ui: UIConfig;
  
  /** GitHub integration settings */
  github?: GitHubConfig;
  
  /** Priority-based execution settings */
  priority: PriorityConfig;
  
  /** Logging configuration */
  logging: LoggingConfig;
  
  /** Reporting configuration */
  reporting: ReportingConfig;
  
  /** Notification settings */
  notifications: NotificationConfig;
  
  /** Custom plugin configurations */
  plugins: Record<string, any>;
}

/**
 * Logging configuration
 */
export interface LoggingConfig {
  /** Log level */
  level: 'debug' | 'info' | 'warn' | 'error';
  
  /** Log file path */
  file?: string;
  
  /** Whether to log to console */
  console: boolean;
  
  /** Log format */
  format: 'json' | 'text' | 'structured';
  
  /** Whether to include timestamps */
  includeTimestamp: boolean;
  
  /** Maximum log file size in bytes */
  maxFileSize: number;
  
  /** Maximum number of log files to keep */
  maxFiles: number;
  
  /** Whether to compress old log files */
  compress: boolean;
}

/**
 * Test reporting configuration
 */
export interface ReportingConfig {
  /** Output directory for reports */
  outputDir: string;
  
  /** Report formats to generate */
  formats: ('html' | 'json' | 'xml' | 'csv')[];
  
  /** Whether to include screenshots in reports */
  includeScreenshots: boolean;
  
  /** Whether to include logs in reports */
  includeLogs: boolean;
  
  /** Custom report templates */
  customTemplates: Record<string, string>;
  
  /** Report generation timeout in milliseconds */
  generationTimeout: number;
}

/**
 * Notification configuration
 */
export interface NotificationConfig {
  /** Whether notifications are enabled */
  enabled: boolean;
  
  /** Notification channels */
  channels: NotificationChannel[];
  
  /** When to send notifications */
  triggers: NotificationTrigger[];
  
  /** Message templates */
  templates: Record<string, string>;
}

/**
 * Notification channel configuration
 */
export interface NotificationChannel {
  /** Channel type */
  type: 'email' | 'slack' | 'teams' | 'webhook';
  
  /** Channel name */
  name: string;
  
  /** Channel configuration */
  config: Record<string, any>;
  
  /** Whether channel is enabled */
  enabled: boolean;
}

/**
 * Notification trigger configuration
 */
export interface NotificationTrigger {
  /** Trigger event */
  event: 'test_start' | 'test_complete' | 'test_failure' | 'test_error';
  
  /** Conditions for triggering */
  conditions: Record<string, any>;
  
  /** Channels to notify */
  channels: string[];
  
  /** Whether trigger is enabled */
  enabled: boolean;
}