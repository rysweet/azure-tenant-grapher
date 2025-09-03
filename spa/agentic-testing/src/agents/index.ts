/**
 * Agents module - Autonomous testing agents
 */

// Base agent interface
export interface IAgent {
  name: string;
  type: string;
  initialize(): Promise<void>;
  execute(scenario: any): Promise<any>;
  cleanup(): Promise<void>;
}

// Agent types
export enum AgentType {
  UI = 'ui',
  CLI = 'cli',
  API = 'api',
  WEBSOCKET = 'websocket',
  GITHUB = 'github',
  SYSTEM = 'system',
  COMPREHENSION = 'comprehension'
}

// Re-export all agent implementations
export { ElectronUIAgent, createElectronUIAgent } from './ElectronUIAgent';
export type { ElectronUIAgentConfig, WebSocketEvent, PerformanceSample } from './ElectronUIAgent';
export { CLIAgent, createCLIAgent } from './CLIAgent';
export type { CLIAgentConfig, CLIProcessInfo, ExecutionContext, StreamData } from './CLIAgent';
export { IssueReporter, createIssueReporter, defaultIssueReporterConfig } from './IssueReporter';
export type { 
  IssueReporterConfig, 
  RateLimitInfo, 
  IssueFingerprint, 
  CreateIssueOptions, 
  UpdateIssueOptions, 
  CreatePullRequestOptions,
  IssueTemplateVars,
  SystemInfo
} from './IssueReporter';
export { PriorityAgent, createPriorityAgent, defaultPriorityAgentConfig } from './PriorityAgent';
export type {
  PriorityAgentConfig,
  PriorityFactors,
  PriorityRule,
  AnalysisContext,
  PriorityAssignment,
  FailurePattern,
  FlakyTestResult,
  PriorityReport
} from './PriorityAgent';
export { ComprehensionAgent, createComprehensionAgent, defaultComprehensionAgentConfig } from './ComprehensionAgent';
export type {
  ComprehensionAgentConfig,
  LLMConfig,
  LLMProvider,
  FeatureSpec,
  FeatureInput,
  FeatureOutput,
  DiscoveredFeature
} from './ComprehensionAgent';
export { APIAgent, createAPIAgent } from './APIAgent';
export type {
  APIAgentConfig,
  HTTPMethod,
  AuthConfig,
  RequestInterceptor,
  ResponseInterceptor,
  SchemaValidation,
  PerformanceMeasurement,
  RetryConfig,
  APIRequest,
  APIResponse,
  RequestPerformance
} from './APIAgent';
export { WebSocketAgent, createWebSocketAgent } from './WebSocketAgent';
export type {
  WebSocketAgentConfig,
  ConnectionState,
  WebSocketMessage,
  ConnectionMetrics,
  LatencyMeasurement,
  EventListener,
  ReconnectionConfig,
  WebSocketAuth,
  ConnectionInfo
} from './WebSocketAgent';
export { SystemAgent, createSystemAgent, defaultSystemAgentConfig } from './SystemAgent';
export type {
  SystemAgentConfig,
  SystemMetrics,
  DiskUsage,
  DiskIO,
  NetworkInterface,
  ProcessInfo,
  DockerInfo,
  SystemHealthReport,
  SystemIssue,
  ResourceLeak,
  PerformanceIssue,
  FileSystemChange,
  PerformanceBaseline
} from './SystemAgent';