/**
 * Core test models and interfaces for the Agentic Testing System
 */

/**
 * Test execution status enumeration
 */
export enum TestStatus {
  PASSED = 'PASSED',
  FAILED = 'FAILED',
  SKIPPED = 'SKIPPED',
  ERROR = 'ERROR',
  RUNNING = 'RUNNING',
  PENDING = 'PENDING'
}

/**
 * Test priority levels
 */
export enum Priority {
  CRITICAL = 'CRITICAL',
  HIGH = 'HIGH',
  MEDIUM = 'MEDIUM',
  LOW = 'LOW'
}

/**
 * Test interface types
 */
export enum TestInterface {
  CLI = 'CLI',
  GUI = 'GUI',
  MIXED = 'MIXED',
  API = 'API'
}

/**
 * Individual test step within a scenario
 */
export interface TestStep {
  /** Action to perform (e.g., 'click', 'type', 'wait', 'execute') */
  action: string;
  /** Target element or command to interact with */
  target: string;
  /** Optional value to input or parameter to pass */
  value?: string;
  /** Optional condition to wait for */
  waitFor?: string;
  /** Optional timeout in milliseconds */
  timeout?: number;
  /** Human-readable description of the step */
  description?: string;
  /** Expected outcome or result */
  expected?: string;
}

/**
 * Verification step for validating test results
 */
export interface VerificationStep {
  /** Type of verification (e.g., 'text', 'element', 'attribute', 'count') */
  type: string;
  /** Target to verify */
  target: string;
  /** Expected value */
  expected: string;
  /** Comparison operator (e.g., 'equals', 'contains', 'greater_than') */
  operator: string;
  /** Description of what is being verified */
  description?: string;
}

/**
 * Complete test scenario definition
 */
export interface TestScenario {
  /** Unique identifier for the scenario */
  id: string;
  /** Human-readable name */
  name: string;
  /** Detailed description */
  description: string;
  /** Test priority level */
  priority: Priority;
  /** Interface type being tested */
  interface: TestInterface;
  /** Prerequisites or setup requirements */
  prerequisites: string[];
  /** Test execution steps */
  steps: TestStep[];
  /** Verification steps to validate results */
  verifications: VerificationStep[];
  /** Expected final outcome */
  expectedOutcome: string;
  /** Estimated execution time in seconds */
  estimatedDuration: number;
  /** Tags for categorization and filtering */
  tags: string[];
  /** Whether this test is currently enabled */
  enabled: boolean;
  /** Environment variables or configuration needed */
  environment?: Record<string, string>;
  /** Cleanup steps to run after test completion */
  cleanup?: TestStep[];
}

/**
 * Result of executing a test scenario
 */
export interface TestResult {
  /** ID of the scenario that was executed */
  scenarioId: string;
  /** Final execution status */
  status: TestStatus;
  /** Execution duration in milliseconds */
  duration: number;
  /** Start timestamp */
  startTime: Date;
  /** End timestamp */
  endTime: Date;
  /** Error message if test failed or errored */
  error?: string;
  /** Stack trace if applicable */
  stackTrace?: string;
  /** Paths to captured screenshots */
  screenshots?: string[];
  /** Captured log messages */
  logs?: string[];
  /** Step-by-step execution results */
  stepResults?: StepResult[];
  /** Additional metadata */
  metadata?: Record<string, any>;
}

/**
 * Result of executing an individual test step
 */
export interface StepResult {
  /** Index of the step in the scenario */
  stepIndex: number;
  /** Execution status */
  status: TestStatus;
  /** Execution duration in milliseconds */
  duration: number;
  /** Error message if step failed */
  error?: string;
  /** Actual result or output */
  actualResult?: string;
  /** Screenshot taken during this step */
  screenshot?: string;
}

/**
 * Detailed test failure information
 */
export interface TestFailure {
  /** ID of the failed scenario */
  scenarioId: string;
  /** Failure timestamp */
  timestamp: Date;
  /** Failure message */
  message: string;
  /** Stack trace */
  stackTrace?: string;
  /** Step where failure occurred */
  failedStep?: number;
  /** Screenshots at time of failure */
  screenshots?: string[];
  /** Relevant log entries */
  logs?: string[];
  /** Failure category */
  category?: string;
  /** Whether this is a known issue */
  isKnownIssue?: boolean;
}

/**
 * Test execution error information
 */
export interface TestError {
  /** Error type */
  type: string;
  /** Error message */
  message: string;
  /** Stack trace */
  stackTrace?: string;
  /** Timestamp when error occurred */
  timestamp: Date;
  /** Additional context */
  context?: Record<string, any>;
}

/**
 * Result of executing a CLI command
 */
export interface CommandResult {
  /** Command that was executed */
  command: string;
  /** Exit code */
  exitCode: number;
  /** Standard output */
  stdout: string;
  /** Standard error */
  stderr: string;
  /** Execution duration in milliseconds */
  duration: number;
  /** Working directory where command was executed */
  workingDirectory?: string;
  /** Environment variables used */
  environment?: Record<string, string>;
}

/**
 * Test execution summary statistics
 */
export interface TestSummary {
  /** Total number of scenarios */
  totalScenarios: number;
  /** Number of passed scenarios */
  passed: number;
  /** Number of failed scenarios */
  failed: number;
  /** Number of skipped scenarios */
  skipped: number;
  /** Number of error scenarios */
  errors: number;
  /** Total execution duration in milliseconds */
  totalDuration: number;
  /** Success rate as percentage */
  successRate: number;
  /** Test run timestamp */
  timestamp: Date;
}

/**
 * Test run configuration
 */
export interface TestRun {
  /** Unique run identifier */
  id: string;
  /** Run name or description */
  name: string;
  /** Timestamp when run started */
  startTime: Date;
  /** Timestamp when run completed */
  endTime?: Date;
  /** Overall run status */
  status: TestStatus;
  /** Scenarios included in this run */
  scenarios: string[];
  /** Run results */
  results: TestResult[];
  /** Run summary */
  summary?: TestSummary;
  /** Configuration used for this run */
  config?: Record<string, any>;
}
