/**
 * Application state models for capturing current state during testing
 */

/**
 * Current state of the application being tested
 */
export interface AppState {
  /** Timestamp when state was captured */
  timestamp: Date;

  /** Interface type currently being tested */
  interface: 'CLI' | 'GUI' | 'API';

  /** Path to screenshot of current state (for GUI testing) */
  screenshotPath?: string;

  /** Current URL (for web-based GUI testing) */
  url?: string;

  /** Current page or window title */
  title?: string;

  /** Active tab or section */
  activeTab?: string;

  /** Current working directory (for CLI testing) */
  workingDirectory?: string;

  /** Environment variables at time of capture */
  environment?: Record<string, string>;

  /** Current user or authentication state */
  user?: string;

  /** Application process information */
  processInfo?: ProcessInfo;

  /** Network state and connectivity */
  networkState?: NetworkState;

  /** Memory and performance metrics */
  performance?: PerformanceMetrics;

  /** Custom application-specific state data */
  customData?: Record<string, any>;
}

/**
 * Information about the application process
 */
export interface ProcessInfo {
  /** Process ID */
  pid: number;

  /** Process name */
  name: string;

  /** Process status */
  status: string;

  /** CPU usage percentage */
  cpuUsage?: number;

  /** Memory usage in bytes */
  memoryUsage?: number;

  /** Process start time */
  startTime?: Date;

  /** Child processes */
  children?: ProcessInfo[];
}

/**
 * Network connectivity state
 */
export interface NetworkState {
  /** Whether network is available */
  isOnline: boolean;

  /** Connection type */
  connectionType?: string;

  /** Network latency in milliseconds */
  latency?: number;

  /** Download speed in Mbps */
  downloadSpeed?: number;

  /** Upload speed in Mbps */
  uploadSpeed?: number;

  /** Active connections */
  activeConnections?: Connection[];
}

/**
 * Individual network connection
 */
export interface Connection {
  /** Local address */
  localAddress: string;

  /** Local port */
  localPort: number;

  /** Remote address */
  remoteAddress: string;

  /** Remote port */
  remotePort: number;

  /** Connection state */
  state: string;

  /** Protocol */
  protocol: string;
}

/**
 * Performance metrics
 */
export interface PerformanceMetrics {
  /** CPU usage percentage */
  cpuUsage: number;

  /** Memory usage in bytes */
  memoryUsage: number;

  /** Available memory in bytes */
  availableMemory: number;

  /** Disk usage percentage */
  diskUsage?: number;

  /** Response time for last action in milliseconds */
  responseTime?: number;

  /** Frame rate (for GUI applications) */
  frameRate?: number;

  /** Load average */
  loadAverage?: number[];
}

/**
 * State change event
 */
export interface StateChangeEvent {
  /** Timestamp of the change */
  timestamp: Date;

  /** Type of change */
  changeType: 'navigation' | 'interaction' | 'data' | 'error' | 'system';

  /** Previous state */
  previousState: Partial<AppState>;

  /** New state */
  newState: Partial<AppState>;

  /** Description of what changed */
  description: string;

  /** Action that triggered the change */
  trigger?: string;
}

/**
 * State snapshot for comparison
 */
export interface StateSnapshot {
  /** Unique identifier */
  id: string;

  /** Snapshot timestamp */
  timestamp: Date;

  /** Complete application state */
  state: AppState;

  /** Optional label or description */
  label?: string;

  /** Test scenario this snapshot belongs to */
  scenarioId?: string;

  /** Step index within the scenario */
  stepIndex?: number;
}

/**
 * State validation result
 */
export interface StateValidation {
  /** Whether state is valid */
  isValid: boolean;

  /** Validation errors */
  errors: string[];

  /** Validation warnings */
  warnings: string[];

  /** Expected state values */
  expected?: Partial<AppState>;

  /** Actual state values */
  actual?: Partial<AppState>;

  /** Validation timestamp */
  timestamp: Date;
}
