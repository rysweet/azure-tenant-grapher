/**
 * TypeScript Agentic Testing System
 * Main entry point for the testing framework
 */

// Export core modules - with specific exports to avoid conflicts
export * from './models';

// Agent exports with specific naming
export { 
  IAgent, 
  AgentType, 
  ElectronUIAgent, 
  createElectronUIAgent,
  CLIAgent,
  createCLIAgent,
  ComprehensionAgent,
  createComprehensionAgent
} from './agents';
export type { 
  ElectronUIAgentConfig, 
  WebSocketEvent, 
  PerformanceSample,
  CLIAgentConfig,
  CLIProcessInfo,
  ExecutionContext,
  StreamData,
  ComprehensionAgentConfig,
  LLMConfig,
  FeatureSpec,
  DiscoveredFeature
} from './agents';

export * from './orchestrator';
export * from './scenarios';
export * from './utils';

// Version information
export const VERSION = '1.0.0';
export const SYSTEM_NAME = 'TypeScript Agentic Testing System';

// Default export for the main orchestrator
export { AgenticOrchestrator as default } from './orchestrator';

/**
 * Quick start function for common use cases
 */
export async function quickStart(scenarioPath: string): Promise<void> {
  const { AgenticOrchestrator } = await import('./orchestrator');
  const { ScenarioLoader } = await import('./scenarios');
  
  const orchestrator = new AgenticOrchestrator({
    logLevel: 'info',
    maxConcurrentAgents: 3,
    retryAttempts: 2
  });
  
  const scenarios = await ScenarioLoader.loadFromFile(scenarioPath);
  await orchestrator.executeScenarios([scenarios]);
}