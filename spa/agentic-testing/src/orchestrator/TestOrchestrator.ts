/**
 * Main orchestrator for the Agentic Testing System
 * Coordinates all testing agents and manages test execution flow
 */

import { EventEmitter } from 'events';
import * as path from 'path';
import * as fs from 'fs/promises';
import { v4 as uuidv4 } from 'uuid';
import {
  TestScenario,
  TestStep,
  TestResult,
  TestStatus,
  TestSession,
  TestFailure,
  TestInterface,
  TestError,
  Priority
} from '../models/TestModels';
import {
  TestConfig,
  ExecutionConfig,
  CLIConfig,
  UIConfig,
  GitHubConfig,
  PriorityConfig
} from '../models/Config';
import { ElectronUIAgent } from '../agents/ElectronUIAgent';
import { CLIAgent } from '../agents/CLIAgent';
import { IssueReporter } from '../agents/IssueReporter';
import { PriorityAgent } from '../agents/PriorityAgent';
import { logger } from '../utils/logger';
import { parseYamlScenarios } from '../utils/yamlParser';

/**
 * Test suite configuration
 */
export interface TestSuite {
  name: string;
  description?: string;
  patterns: string[];
  tags?: string[];
}

/**
 * Orchestrator events
 */
export interface OrchestratorEvents {
  'session:start': (session: TestSession) => void;
  'session:end': (session: TestSession) => void;
  'scenario:start': (scenario: TestScenario) => void;
  'scenario:end': (scenario: TestScenario, result: TestResult) => void;
  'phase:start': (phase: string) => void;
  'phase:end': (phase: string) => void;
  'error': (error: Error) => void;
}

/**
 * Main test orchestrator class
 */
export class TestOrchestrator extends EventEmitter {
  private config: TestConfig;
  private session: TestSession | null = null;
  private results: TestResult[] = [];
  private failures: TestFailure[] = [];

  // Agents
  private cliAgent: CLIAgent;
  private uiAgent: ElectronUIAgent | null = null;
  private issueReporter: IssueReporter;
  private priorityAgent: PriorityAgent;

  // Execution control
  private maxParallel: number;
  private retryCount: number;
  private failFast: boolean;
  private abortController: AbortController;

  constructor(config: TestConfig) {
    super();
    this.config = config;

    // Initialize agents
    this.cliAgent = new CLIAgent(config.cli);
    this.issueReporter = new IssueReporter(config.github);
    this.priorityAgent = new PriorityAgent(config.priority);

    // Initialize UI agent if configured
    if (config.ui && config.ui.browser) {
      this.uiAgent = new ElectronUIAgent(config.ui);
    }

    // Execution settings
    this.maxParallel = config.execution?.maxParallel || 3;
    this.retryCount = config.execution?.maxRetries || 2;
    this.failFast = config.execution?.continueOnFailure === false;
    this.abortController = new AbortController();

    // Setup event handlers
    this.setupEventHandlers();
  }

  /**
   * Setup internal event handlers
   */
  private setupEventHandlers(): void {
    this.on('error', (error) => {
      logger.error('Orchestrator error:', error);
    });
  }

  /**
   * Run a complete testing session
   */
  async run(suite: string = 'smoke', scenarioFiles?: string[]): Promise<TestSession> {
    logger.info(`Starting test session with suite: ${suite}`);

    // Create session
    this.session = {
      id: uuidv4(),
      startTime: new Date(),
      endTime: null,
      scenariosExecuted: [],
      results: [],
      failures: [],
      issuesCreated: [],
      metrics: {
        totalScenarios: 0,
        passed: 0,
        failed: 0,
        skipped: 0,
        duration: 0
      }
    };

    this.emit('session:start', this.session);

    try {
      // Phase 1: Discovery
      this.emit('phase:start', 'discovery');
      logger.info('Phase 1: Loading and discovering test scenarios');
      const scenarios = await this.loadScenarios(scenarioFiles);

      // Filter scenarios based on suite
      const filteredScenarios = this.filterScenariosForSuite(scenarios, suite);
      logger.info(`Selected ${filteredScenarios.length} scenarios for suite '${suite}'`);
      this.emit('phase:end', 'discovery');

      // Phase 2: Execution
      this.emit('phase:start', 'execution');
      logger.info('Phase 2: Executing test scenarios');
      await this.executeScenarios(filteredScenarios);
      this.emit('phase:end', 'execution');

      // Phase 3: Analysis
      this.emit('phase:start', 'analysis');
      logger.info('Phase 3: Analyzing results and prioritizing failures');
      await this.analyzeResults();
      this.emit('phase:end', 'analysis');

      // Phase 4: Reporting
      this.emit('phase:start', 'reporting');
      logger.info('Phase 4: Reporting failures to GitHub');
      await this.reportFailures();
      this.emit('phase:end', 'reporting');

    } catch (error) {
      logger.error('Test session failed:', error);
      this.emit('error', error as Error);
      throw error;
    } finally {
      // Finalize session
      this.session.endTime = new Date();
      this.calculateSessionMetrics();

      // Save session results
      await this.saveSessionResults();

      this.emit('session:end', this.session);
    }

    logger.info(`Test session completed: ${this.session.id}`);
    return this.session;
  }

  /**
   * Load test scenarios from files
   */
  private async loadScenarios(scenarioFiles?: string[]): Promise<TestScenario[]> {
    const scenarios: TestScenario[] = [];

    // Default scenario directory
    const scenarioDir = path.join(process.cwd(), 'scenarios');

    if (scenarioFiles && scenarioFiles.length > 0) {
      // Load specific files
      for (const file of scenarioFiles) {
        try {
          const content = await fs.readFile(file, 'utf-8');
          const fileScenarios = await parseYamlScenarios(content);
          scenarios.push(...fileScenarios);
          logger.debug(`Loaded ${fileScenarios.length} scenarios from ${file}`);
        } catch (error) {
          logger.error(`Failed to load scenarios from ${file}:`, error);
        }
      }
    } else {
      // Load all YAML files from scenario directory
      try {
        const files = await fs.readdir(scenarioDir);
        const yamlFiles = files.filter(f => f.endsWith('.yaml') || f.endsWith('.yml'));

        for (const file of yamlFiles) {
          const filePath = path.join(scenarioDir, file);
          const content = await fs.readFile(filePath, 'utf-8');
          const fileScenarios = await parseYamlScenarios(content);
          scenarios.push(...fileScenarios);
          logger.debug(`Loaded ${fileScenarios.length} scenarios from ${file}`);
        }
      } catch (error) {
        logger.error('Failed to load scenarios from directory:', error);
      }
    }

    logger.info(`Loaded ${scenarios.length} total test scenarios`);
    return scenarios;
  }

  /**
   * Filter scenarios based on test suite configuration
   */
  private filterScenariosForSuite(scenarios: TestScenario[], suite: string): TestScenario[] {
    // Default test suites
    const suiteConfig: Record<string, string[]> = {
      smoke: ['smoke:', 'critical:', 'auth:'],
      regression: ['*'],
      full: ['*'],
      ...this.config.execution?.suites
    };

    const patterns = suiteConfig[suite] || ['*'];

    if (patterns.includes('*')) {
      return scenarios;
    }

    const filtered: TestScenario[] = [];

    for (const scenario of scenarios) {
      for (const pattern of patterns) {
        if (pattern.endsWith(':')) {
          // Prefix match
          const prefix = pattern.slice(0, -1);
          if (scenario.id.startsWith(prefix) ||
              scenario.tags?.some(tag => tag.startsWith(prefix))) {
            filtered.push(scenario);
            break;
          }
        } else if (pattern.includes('*')) {
          // Glob pattern
          const regex = new RegExp(pattern.replace('*', '.*'));
          if (regex.test(scenario.id) ||
              scenario.tags?.some(tag => regex.test(tag))) {
            filtered.push(scenario);
            break;
          }
        } else {
          // Exact match
          if (scenario.id === pattern ||
              scenario.tags?.includes(pattern)) {
            filtered.push(scenario);
            break;
          }
        }
      }
    }

    return filtered;
  }

  /**
   * Execute test scenarios with parallel execution support
   */
  private async executeScenarios(scenarios: TestScenario[]): Promise<void> {
    // Group scenarios by interface type
    const cliScenarios = scenarios.filter(s => s.interface === TestInterface.CLI);
    const uiScenarios = scenarios.filter(s => s.interface === TestInterface.GUI);
    const mixedScenarios = scenarios.filter(s => s.interface === TestInterface.MIXED);

    // Execute CLI scenarios
    if (cliScenarios.length > 0) {
      logger.info(`Executing ${cliScenarios.length} CLI scenarios`);
      await this.executeCLIScenarios(cliScenarios);
    }

    // Execute UI scenarios
    if (uiScenarios.length > 0) {
      logger.info(`Executing ${uiScenarios.length} UI scenarios`);
      await this.executeUIScenarios(uiScenarios);
    }

    // Execute mixed scenarios
    if (mixedScenarios.length > 0) {
      logger.info(`Executing ${mixedScenarios.length} mixed scenarios`);
      await this.executeMixedScenarios(mixedScenarios);
    }
  }

  /**
   * Execute CLI test scenarios in parallel
   */
  private async executeCLIScenarios(scenarios: TestScenario[]): Promise<void> {
    const results = await this.executeParallel(scenarios, async (scenario) => {
      return await this.executeSingleScenario(scenario, this.cliAgent);
    });

    this.processResults(scenarios, results);
  }

  /**
   * Execute UI test scenarios
   */
  private async executeUIScenarios(scenarios: TestScenario[]): Promise<void> {
    if (!this.uiAgent) {
      logger.warn('UI agent not available');
      for (const scenario of scenarios) {
        this.recordFailure(scenario, 'UI testing unavailable - Electron agent not configured');
      }
      return;
    }

    // Initialize UI agent
    await this.uiAgent.initialize();

    try {
      // UI scenarios typically run sequentially
      for (const scenario of scenarios) {
        if (this.abortController.signal.aborted) {
          logger.info('Execution aborted');
          break;
        }

        const result = await this.executeSingleScenario(scenario, this.uiAgent);
        this.recordResult(result);

        if (this.failFast && result.status === TestStatus.FAILED) {
          logger.warn('Fail-fast enabled, stopping execution');
          break;
        }
      }
    } finally {
      await this.uiAgent.cleanup();
    }
  }

  /**
   * Execute mixed interface scenarios
   */
  private async executeMixedScenarios(scenarios: TestScenario[]): Promise<void> {
    for (const scenario of scenarios) {
      if (this.abortController.signal.aborted) {
        logger.info('Execution aborted');
        break;
      }

      const agent = this.selectAgentForScenario(scenario);
      const result = await this.executeSingleScenario(scenario, agent);
      this.recordResult(result);

      if (this.failFast && result.status === TestStatus.FAILED) {
        logger.warn('Fail-fast enabled, stopping execution');
        break;
      }
    }
  }

  /**
   * Execute scenarios in parallel with concurrency limit
   */
  private async executeParallel<T>(
    items: T[],
    handler: (item: T) => Promise<TestResult>
  ): Promise<(TestResult | Error)[]> {
    const results: (TestResult | Error)[] = [];
    const executing: Promise<void>[] = [];

    for (const item of items) {
      if (this.abortController.signal.aborted) {
        break;
      }

      const promise = handler(item).then(
        result => { results.push(result); },
        error => { results.push(error); }
      );

      executing.push(promise);

      if (executing.length >= this.maxParallel) {
        await Promise.race(executing);
        executing.splice(0, executing.findIndex(p => p));
      }
    }

    await Promise.all(executing);
    return results;
  }

  /**
   * Execute a single test scenario
   */
  private async executeSingleScenario(
    scenario: TestScenario,
    agent: CLIAgent | ElectronUIAgent
  ): Promise<TestResult> {
    logger.info(`Executing scenario: ${scenario.id} - ${scenario.name}`);
    this.emit('scenario:start', scenario);

    const startTime = Date.now();
    let retryCount = 0;

    while (retryCount <= this.retryCount) {
      try {
        const result = await agent.execute(scenario);

        const endResult: TestResult = {
          ...result,
          scenarioId: scenario.id,
          duration: Date.now() - startTime,
          retryCount
        };

        this.emit('scenario:end', scenario, endResult);
        return endResult;

      } catch (error) {
        logger.error(`Scenario ${scenario.id} failed (attempt ${retryCount + 1}):`, error);

        if (retryCount < this.retryCount && scenario.retryOnFailure !== false) {
          retryCount++;
          await new Promise(resolve => setTimeout(resolve, Math.pow(2, retryCount) * 1000));
          continue;
        }

        // Final failure
        const errorResult: TestResult = {
          scenarioId: scenario.id,
          status: TestStatus.FAILED,
          duration: Date.now() - startTime,
          error: {
            type: 'execution_error',
            message: error instanceof Error ? error.message : String(error),
            stackTrace: error instanceof Error ? error.stack : undefined
          },
          retryCount
        };

        this.emit('scenario:end', scenario, errorResult);
        return errorResult;
      }
    }

    // Should not reach here
    return {
      scenarioId: scenario.id,
      status: TestStatus.ERROR,
      duration: Date.now() - startTime,
      retryCount
    };
  }

  /**
   * Select appropriate agent for scenario
   */
  private selectAgentForScenario(scenario: TestScenario): CLIAgent | ElectronUIAgent {
    // Count step types
    const cliSteps = scenario.steps.filter(s =>
      s.action === 'execute' || s.action === 'runCommand'
    ).length;
    const uiSteps = scenario.steps.filter(s =>
      ['click', 'type', 'navigate', 'screenshot'].includes(s.action)
    ).length;

    if (uiSteps > cliSteps && this.uiAgent) {
      return this.uiAgent;
    }
    return this.cliAgent;
  }

  /**
   * Process execution results
   */
  private processResults(scenarios: TestScenario[], results: (TestResult | Error)[]): void {
    for (let i = 0; i < scenarios.length; i++) {
      const result = results[i];

      if (result instanceof Error) {
        logger.error(`Scenario ${scenarios[i].id} failed with exception:`, result);
        this.recordFailure(scenarios[i], result.message);
      } else {
        this.recordResult(result);
        if (this.failFast && result.status === TestStatus.FAILED) {
          logger.warn('Fail-fast enabled, stopping execution');
          this.abortController.abort();
          break;
        }
      }
    }
  }

  /**
   * Record test result
   */
  private recordResult(result: TestResult): void {
    this.results.push(result);
    this.session?.results.push(result);
    this.session?.scenariosExecuted.push(result.scenarioId);

    if (result.status === TestStatus.FAILED && result.error) {
      const failure: TestFailure = {
        scenarioId: result.scenarioId,
        timestamp: new Date(),
        message: result.error.message,
        stackTrace: result.error.stackTrace,
        category: result.error.type || 'execution',
        logs: result.logs
      };
      this.failures.push(failure);
      this.session?.failures.push(failure);
    }
  }

  /**
   * Record a scenario failure
   */
  private recordFailure(scenario: TestScenario, errorMsg: string): void {
    const failure: TestFailure = {
      scenarioId: scenario.id,
      timestamp: new Date(),
      message: errorMsg,
      category: 'execution'
    };

    this.failures.push(failure);
    this.session?.failures.push(failure);
  }

  /**
   * Analyze test results and prioritize failures
   */
  private async analyzeResults(): Promise<void> {
    if (this.failures.length === 0) {
      logger.info('No failures to analyze');
      return;
    }

    logger.info(`Analyzing ${this.failures.length} failures`);

    // Analyze each failure
    for (const failure of this.failures) {
      const priority = await this.priorityAgent.analyzePriority(failure);
      logger.debug(`Failure ${failure.scenarioId} priority: ${priority.priority} (score: ${priority.impactScore})`);
    }

    // Get priority report
    const report = await this.priorityAgent.generatePriorityReport(this.failures, this.results);

    logger.info('Priority summary:', {
      critical: report.summary.criticalCount,
      high: report.summary.highCount,
      medium: report.summary.mediumCount,
      low: report.summary.lowCount,
      average: report.summary.averageImpactScore.toFixed(2)
    });
  }

  /**
   * Report failures to GitHub
   */
  private async reportFailures(): Promise<void> {
    if (this.failures.length === 0) {
      logger.info('No failures to report');
      return;
    }

    if (!this.config.github?.createIssues) {
      logger.info('Issue creation disabled');
      return;
    }

    logger.info(`Reporting ${this.failures.length} failures to GitHub`);

    // Initialize issue reporter
    await this.issueReporter.initialize();

    try {
      // Report failures and get issue numbers
      const issueNumbers: number[] = [];

      for (const failure of this.failures) {
        try {
          const issueNumber = await this.issueReporter.reportFailure(failure);
          if (issueNumber) {
            issueNumbers.push(issueNumber);
          }
        } catch (error) {
          logger.error(`Failed to report failure ${failure.scenarioId}:`, error);
        }
      }

      // Track created issues
      this.session?.issuesCreated.push(...issueNumbers);
      logger.info(`Created ${issueNumbers.length} GitHub issues`);

    } finally {
      await this.issueReporter.cleanup();
    }
  }

  /**
   * Calculate session metrics
   */
  private calculateSessionMetrics(): void {
    if (!this.session) return;

    const metrics = this.session.metrics;
    metrics.totalScenarios = this.session.scenariosExecuted.length;
    metrics.passed = this.results.filter(r => r.status === TestStatus.PASSED).length;
    metrics.failed = this.results.filter(r => r.status === TestStatus.FAILED).length;
    metrics.skipped = this.results.filter(r => r.status === TestStatus.SKIPPED).length;

    if (this.session.startTime && this.session.endTime) {
      metrics.duration = this.session.endTime.getTime() - this.session.startTime.getTime();
    }
  }

  /**
   * Save session results to file
   */
  private async saveSessionResults(): Promise<void> {
    if (!this.session) return;

    const outputDir = path.join(process.cwd(), 'outputs', 'sessions');
    await fs.mkdir(outputDir, { recursive: true });

    const timestamp = this.session.startTime.toISOString().replace(/[:.]/g, '-');
    const filename = `session_${this.session.id}_${timestamp}.json`;
    const filepath = path.join(outputDir, filename);

    const sessionData = {
      ...this.session,
      results: this.results
    };

    await fs.writeFile(filepath, JSON.stringify(sessionData, null, 2));
    logger.info(`Session results saved to ${filepath}`);
  }

  /**
   * Abort the current test session
   */
  abort(): void {
    logger.warn('Aborting test session');
    this.abortController.abort();
  }

  /**
   * Get current session
   */
  getSession(): TestSession | null {
    return this.session;
  }

  /**
   * Get test results
   */
  getResults(): TestResult[] {
    return this.results;
  }

  /**
   * Get test failures
   */
  getFailures(): TestFailure[] {
    return this.failures;
  }
}

/**
 * Create a test orchestrator instance
 */
export function createTestOrchestrator(config: TestConfig): TestOrchestrator {
  return new TestOrchestrator(config);
}
