/**
 * PriorityAgent - Test priority analysis and ranking agent
 *
 * This agent analyzes test failures to determine priority levels, calculates impact scores,
 * ranks failures by importance, and provides actionable recommendations for fixing order.
 * It includes pattern recognition, trend analysis, and machine learning-ready scoring.
 */

import { EventEmitter } from 'events';
import { IAgent, AgentType } from './index';
import {
  TestFailure,
  TestResult,
  TestStatus,
  Priority,
  TestInterface,
  TestScenario
} from '../models/TestModels';
import { TestLogger, createLogger, LogLevel } from '../utils/logger';

/**
 * Priority scoring factors
 */
export interface PriorityFactors {
  /** Error severity weight (0-1) */
  errorSeverity: number;
  /** User impact weight (0-1) */
  userImpact: number;
  /** Test stability weight (0-1) */
  testStability: number;
  /** Business priority weight (0-1) */
  businessPriority: number;
  /** Security implications weight (0-1) */
  securityImplications: number;
  /** Performance impact weight (0-1) */
  performanceImpact: number;
  /** Regression detection weight (0-1) */
  regressionDetection: number;
}

/**
 * Priority analysis configuration
 */
export interface PriorityAgentConfig {
  /** Custom priority scoring factors */
  priorityFactors?: Partial<PriorityFactors>;
  /** Historical data retention period in days */
  historyRetentionDays?: number;
  /** Flaky test detection threshold (failure rate 0-1) */
  flakyThreshold?: number;
  /** Pattern recognition sensitivity */
  patternSensitivity?: number;
  /** Minimum samples required for trend analysis */
  minSamplesForTrends?: number;
  /** Custom priority rules */
  customRules?: PriorityRule[];
  /** Logging configuration */
  logLevel?: LogLevel;
}

/**
 * Custom priority rule interface
 */
export interface PriorityRule {
  /** Rule name */
  name: string;
  /** Rule condition function */
  condition: (failure: TestFailure, context: AnalysisContext) => boolean;
  /** Priority modifier (-100 to +100) */
  priorityModifier: number;
  /** Rule description */
  description: string;
}

/**
 * Analysis context for priority calculations
 */
export interface AnalysisContext {
  /** Historical test results */
  history: TestResult[];
  /** Test scenario information */
  scenarios: Map<string, TestScenario>;
  /** Previous priority assignments */
  previousPriorities: Map<string, PriorityAssignment>;
  /** System metadata */
  systemInfo?: Record<string, any>;
}

/**
 * Priority assignment result
 */
export interface PriorityAssignment {
  /** Test scenario ID */
  scenarioId: string;
  /** Assigned priority level */
  priority: Priority;
  /** Calculated impact score (0-100) */
  impactScore: number;
  /** Confidence level (0-1) */
  confidence: number;
  /** Assignment timestamp */
  timestamp: Date;
  /** Reasoning for the assignment */
  reasoning: string[];
  /** Contributing factors breakdown */
  factors: Record<string, number>;
  /** Recommended fix effort (hours) */
  estimatedFixEffort?: number;
}

/**
 * Failure pattern information
 */
export interface FailurePattern {
  /** Pattern ID */
  id: string;
  /** Pattern description */
  description: string;
  /** Affected scenarios */
  affectedScenarios: string[];
  /** Pattern frequency */
  frequency: number;
  /** First occurrence */
  firstSeen: Date;
  /** Last occurrence */
  lastSeen: Date;
  /** Pattern confidence (0-1) */
  confidence: number;
  /** Suggested root cause */
  suggestedRootCause?: string;
}

/**
 * Flaky test detection result
 */
export interface FlakyTestResult {
  /** Test scenario ID */
  scenarioId: string;
  /** Flakiness score (0-1) */
  flakinessScore: number;
  /** Failure rate over time */
  failureRate: number;
  /** Number of flips (pass->fail or fail->pass) */
  flipCount: number;
  /** Analysis window */
  analysisWindow: {
    startDate: Date;
    endDate: Date;
    totalRuns: number;
  };
  /** Recommended action */
  recommendedAction: 'stabilize' | 'quarantine' | 'investigate' | 'monitor';
}

/**
 * Priority analysis report
 */
export interface PriorityReport {
  /** Report generation timestamp */
  timestamp: Date;
  /** Total failures analyzed */
  totalFailures: number;
  /** Priority assignments */
  assignments: PriorityAssignment[];
  /** Identified patterns */
  patterns: FailurePattern[];
  /** Flaky tests */
  flakyTests: FlakyTestResult[];
  /** Recommended fix order */
  fixOrder: string[];
  /** Summary statistics */
  summary: {
    criticalCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
    averageImpactScore: number;
    averageConfidence: number;
  };
  /** Recommendations */
  recommendations: string[];
}

/**
 * Default priority factors
 */
const DEFAULT_PRIORITY_FACTORS: PriorityFactors = {
  errorSeverity: 0.25,
  userImpact: 0.20,
  testStability: 0.15,
  businessPriority: 0.15,
  securityImplications: 0.10,
  performanceImpact: 0.10,
  regressionDetection: 0.05
};

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<PriorityAgentConfig> = {
  priorityFactors: DEFAULT_PRIORITY_FACTORS,
  historyRetentionDays: 30,
  flakyThreshold: 0.3,
  patternSensitivity: 0.7,
  minSamplesForTrends: 5,
  customRules: [],
  logLevel: LogLevel.INFO
};

/**
 * PriorityAgent implementation
 */
export class PriorityAgent extends EventEmitter implements IAgent {
  public readonly name = 'PriorityAgent';
  public readonly type = AgentType.SYSTEM;

  private config: Required<PriorityAgentConfig>;
  private logger: TestLogger;
  private analysisHistory: Map<string, PriorityAssignment[]> = new Map();
  private patternCache: Map<string, FailurePattern> = new Map();
  private isInitialized = false;

  constructor(config: PriorityAgentConfig = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = createLogger({ level: this.config.logLevel });
    this.logger.setContext({ component: 'PriorityAgent' });
  }

  /**
   * Initialize the priority agent
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing PriorityAgent');

    try {
      // Validate configuration
      this.validateConfiguration();

      // Initialize analysis history
      await this.loadAnalysisHistory();

      // Initialize pattern cache
      await this.loadPatternCache();

      this.isInitialized = true;
      this.logger.info('PriorityAgent initialized successfully');
      this.emit('initialized');
    } catch (error) {
      this.logger.error('Failed to initialize PriorityAgent', { error });
      throw error;
    }
  }

  /**
   * Execute priority analysis on a scenario (implements IAgent interface)
   */
  async execute(scenario: TestScenario): Promise<PriorityAssignment | null> {
    if (!this.isInitialized) {
      throw new Error('PriorityAgent not initialized. Call initialize() first.');
    }

    this.logger.info(`Executing priority analysis for scenario: ${scenario.id}`);

    // For the IAgent interface, we need a test failure to analyze
    // This is a simplified implementation that would need actual failure data
    const mockFailure: TestFailure = {
      scenarioId: scenario.id,
      timestamp: new Date(),
      message: 'Mock failure for priority analysis',
      category: 'execution'
    };

    return this.analyzePriority(mockFailure);
  }

  /**
   * Analyze and assign priority to a test failure
   */
  async analyzePriority(
    failure: TestFailure,
    context?: Partial<AnalysisContext>
  ): Promise<PriorityAssignment> {
    this.logger.debug(`Analyzing priority for failure: ${failure.scenarioId}`, {
      failureMessage: failure.message,
      category: failure.category
    });

    const fullContext = await this.buildAnalysisContext(failure, context);
    const impactScore = this.calculateImpactScore(failure, fullContext);
    const priority = this.determinePriorityLevel(impactScore);
    const reasoning = this.generateReasoning(failure, fullContext, impactScore);
    const factors = this.calculateFactorBreakdown(failure, fullContext);
    const confidence = this.calculateConfidence(failure, fullContext);
    const estimatedFixEffort = this.estimateFixEffort(failure, fullContext);

    const assignment: PriorityAssignment = {
      scenarioId: failure.scenarioId,
      priority,
      impactScore,
      confidence,
      timestamp: new Date(),
      reasoning,
      factors,
      estimatedFixEffort
    };

    // Store in history
    this.storeAssignment(assignment);

    this.logger.info(`Priority assigned: ${priority} (score: ${impactScore})`, {
      scenarioId: failure.scenarioId,
      assignment
    });

    return assignment;
  }

  /**
   * Calculate impact score for a test failure
   */
  calculateImpactScore(
    failure: TestFailure,
    context: AnalysisContext
  ): number {
    const factors = this.config.priorityFactors;
    let score = 0;

    // Error severity scoring
    const severityScore = this.scoreSeverity(failure);
    score += severityScore * (factors.errorSeverity || 0);

    // User impact scoring
    const userImpactScore = this.scoreUserImpact(failure, context);
    score += userImpactScore * (factors.userImpact || 0);

    // Test stability scoring
    const stabilityScore = this.scoreStability(failure, context);
    score += stabilityScore * (factors.testStability || 0);

    // Business priority scoring
    const businessScore = this.scoreBusinessPriority(failure, context);
    score += businessScore * (factors.businessPriority || 0);

    // Security implications scoring
    const securityScore = this.scoreSecurityImplications(failure, context);
    score += securityScore * (factors.securityImplications || 0);

    // Performance impact scoring
    const performanceScore = this.scorePerformanceImpact(failure, context);
    score += performanceScore * (factors.performanceImpact || 0);

    // Regression detection scoring
    const regressionScore = this.scoreRegressionDetection(failure, context);
    score += regressionScore * (factors.regressionDetection || 0);

    // Apply custom rules
    score += this.applyCustomRules(failure, context);

    // Normalize to 0-100 scale
    return Math.max(0, Math.min(100, score * 100));
  }

  /**
   * Rank multiple failures by priority
   */
  rankFailures(failures: TestFailure[]): Promise<PriorityAssignment[]> {
    this.logger.info(`Ranking ${failures.length} failures by priority`);

    return Promise.all(
      failures.map(failure => this.analyzePriority(failure))
    ).then(assignments => {
      // Sort by impact score (descending) and confidence (descending)
      const ranked = assignments.sort((a, b) => {
        if (a.impactScore !== b.impactScore) {
          return b.impactScore - a.impactScore;
        }
        return b.confidence - a.confidence;
      });

      this.logger.info('Failures ranked by priority', {
        totalFailures: failures.length,
        ranking: ranked.map((a, index) => ({
          rank: index + 1,
          scenarioId: a.scenarioId,
          priority: a.priority,
          score: a.impactScore
        }))
      });

      return ranked;
    });
  }

  /**
   * Suggest order for fixing failures
   */
  async suggestFixOrder(failures: TestFailure[]): Promise<string[]> {
    this.logger.info(`Suggesting fix order for ${failures.length} failures`);

    const rankedAssignments = await this.rankFailures(failures);

    // Group by priority and consider fix effort
    const groups: Record<Priority, PriorityAssignment[]> = {
      [Priority.CRITICAL]: [],
      [Priority.HIGH]: [],
      [Priority.MEDIUM]: [],
      [Priority.LOW]: []
    };

    rankedAssignments.forEach(assignment => {
      groups[assignment.priority].push(assignment);
    });

    // Within each priority group, sort by fix effort (ascending)
    Object.values(groups).forEach(group => {
      group.sort((a, b) => {
        const effortA = a.estimatedFixEffort || 0;
        const effortB = b.estimatedFixEffort || 0;
        return effortA - effortB;
      });
    });

    // Build final fix order
    const fixOrder = [
      ...groups[Priority.CRITICAL],
      ...groups[Priority.HIGH],
      ...groups[Priority.MEDIUM],
      ...groups[Priority.LOW]
    ].map(assignment => assignment.scenarioId);

    this.logger.info('Fix order generated', {
      fixOrder: fixOrder.map((scenarioId, index) => ({
        order: index + 1,
        scenarioId,
        priority: rankedAssignments.find(a => a.scenarioId === scenarioId)?.priority
      }))
    });

    return fixOrder;
  }

  /**
   * Identify flaky tests from historical results
   */
  identifyFlaky(results: TestResult[]): FlakyTestResult[] {
    this.logger.info(`Analyzing ${results.length} results for flaky tests`);

    const scenarioGroups = new Map<string, TestResult[]>();

    // Group results by scenario
    results.forEach(result => {
      if (!scenarioGroups.has(result.scenarioId)) {
        scenarioGroups.set(result.scenarioId, []);
      }
      scenarioGroups.get(result.scenarioId)!.push(result);
    });

    const flakyTests: FlakyTestResult[] = [];

    scenarioGroups.forEach((scenarioResults, scenarioId) => {
      if (scenarioResults.length < this.config.minSamplesForTrends) {
        return; // Not enough data
      }

      const flakyResult = this.analyzeFlakyBehavior(scenarioId, scenarioResults);
      if (flakyResult.flakinessScore >= this.config.flakyThreshold) {
        flakyTests.push(flakyResult);
      }
    });

    this.logger.info(`Found ${flakyTests.length} flaky tests`, {
      flakyTests: flakyTests.map(test => ({
        scenarioId: test.scenarioId,
        flakinessScore: test.flakinessScore,
        failureRate: test.failureRate,
        recommendedAction: test.recommendedAction
      }))
    });

    return flakyTests;
  }

  /**
   * Analyze failure patterns across multiple failures
   */
  analyzeFailurePatterns(failures: TestFailure[]): FailurePattern[] {
    this.logger.info(`Analyzing patterns in ${failures.length} failures`);

    const patterns: FailurePattern[] = [];

    // Group failures by error message similarity
    const messagePatterns = this.groupByMessagePatterns(failures);
    patterns.push(...messagePatterns);

    // Group failures by stack trace similarity
    const stackPatterns = this.groupByStackTracePatterns(failures);
    patterns.push(...stackPatterns);

    // Group failures by timing patterns
    const timingPatterns = this.groupByTimingPatterns(failures);
    patterns.push(...timingPatterns);

    // Group failures by category
    const categoryPatterns = this.groupByCategoryPatterns(failures);
    patterns.push(...categoryPatterns);

    // Update pattern cache
    patterns.forEach(pattern => {
      this.patternCache.set(pattern.id, pattern);
    });

    this.logger.info(`Found ${patterns.length} failure patterns`, {
      patterns: patterns.map(pattern => ({
        id: pattern.id,
        description: pattern.description,
        affectedScenarios: pattern.affectedScenarios.length,
        frequency: pattern.frequency,
        confidence: pattern.confidence
      }))
    });

    return patterns;
  }

  /**
   * Generate comprehensive priority report
   */
  async generatePriorityReport(
    failures: TestFailure[],
    results: TestResult[] = []
  ): Promise<PriorityReport> {
    this.logger.info('Generating comprehensive priority report');

    const assignments = await this.rankFailures(failures);
    const patterns = this.analyzeFailurePatterns(failures);
    const flakyTests = this.identifyFlaky(results);
    const fixOrder = await this.suggestFixOrder(failures);

    const summary = {
      criticalCount: assignments.filter(a => a.priority === Priority.CRITICAL).length,
      highCount: assignments.filter(a => a.priority === Priority.HIGH).length,
      mediumCount: assignments.filter(a => a.priority === Priority.MEDIUM).length,
      lowCount: assignments.filter(a => a.priority === Priority.LOW).length,
      averageImpactScore: assignments.reduce((sum, a) => sum + a.impactScore, 0) / assignments.length,
      averageConfidence: assignments.reduce((sum, a) => sum + a.confidence, 0) / assignments.length
    };

    const recommendations = this.generateRecommendations(assignments, patterns, flakyTests);

    const report: PriorityReport = {
      timestamp: new Date(),
      totalFailures: failures.length,
      assignments,
      patterns,
      flakyTests,
      fixOrder,
      summary,
      recommendations
    };

    this.logger.info('Priority report generated', { summary });
    this.emit('reportGenerated', report);

    return report;
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up PriorityAgent');

    try {
      // Save analysis history
      await this.saveAnalysisHistory();

      // Save pattern cache
      await this.savePatternCache();

      // Close logger
      await this.logger.close();

      this.emit('cleanup');
      this.logger.info('PriorityAgent cleanup completed');
    } catch (error) {
      this.logger.error('Error during PriorityAgent cleanup', { error });
      throw error;
    }
  }

  // Private helper methods

  private validateConfiguration(): void {
    const factors = this.config.priorityFactors;
    const totalWeight = Object.values(factors).reduce((sum, weight) => sum + weight, 0);

    if (Math.abs(totalWeight - 1.0) > 0.01) {
      this.logger.warn('Priority factor weights do not sum to 1.0', {
        totalWeight,
        factors
      });
    }

    if (this.config.flakyThreshold < 0 || this.config.flakyThreshold > 1) {
      throw new Error('Flaky threshold must be between 0 and 1');
    }
  }

  private async buildAnalysisContext(
    failure: TestFailure,
    partialContext?: Partial<AnalysisContext>
  ): Promise<AnalysisContext> {
    return {
      history: partialContext?.history || [],
      scenarios: partialContext?.scenarios || new Map(),
      previousPriorities: partialContext?.previousPriorities || new Map(),
      systemInfo: partialContext?.systemInfo || {}
    };
  }

  private scoreSeverity(failure: TestFailure): number {
    const message = failure.message.toLowerCase();
    const stackTrace = failure.stackTrace?.toLowerCase() || '';

    // Critical severity indicators
    if (message.includes('crash') || message.includes('segfault') ||
        message.includes('fatal') || message.includes('abort')) {
      return 1.0;
    }

    // High severity indicators
    if (message.includes('error') || message.includes('exception') ||
        message.includes('failed') || stackTrace.includes('error')) {
      return 0.8;
    }

    // Medium severity indicators
    if (message.includes('warning') || message.includes('timeout') ||
        message.includes('assertion')) {
      return 0.6;
    }

    // Low severity (default)
    return 0.4;
  }

  private scoreUserImpact(failure: TestFailure, context: AnalysisContext): number {
    const scenario = context.scenarios.get(failure.scenarioId);
    if (!scenario) return 0.5;

    // High impact for GUI tests (user-facing)
    if (scenario.interface === TestInterface.GUI) {
      return 0.9;
    }

    // Medium-high impact for mixed interfaces
    if (scenario.interface === TestInterface.MIXED) {
      return 0.7;
    }

    // Medium impact for CLI tests
    if (scenario.interface === TestInterface.CLI) {
      return 0.6;
    }

    // Lower impact for API tests (internal)
    return 0.4;
  }

  private scoreStability(failure: TestFailure, context: AnalysisContext): number {
    const history = context.history.filter(r => r.scenarioId === failure.scenarioId);
    if (history.length === 0) return 0.5;

    const recentFailures = history
      .filter(r => r.status === TestStatus.FAILED)
      .filter(r => {
        const daysSinceFailure = (Date.now() - r.startTime.getTime()) / (1000 * 60 * 60 * 24);
        return daysSinceFailure <= 7; // Last 7 days
      });

    const failureRate = recentFailures.length / Math.min(history.length, 10);
    return Math.min(1.0, failureRate * 2); // Double weight for instability
  }

  private scoreBusinessPriority(failure: TestFailure, context: AnalysisContext): number {
    const scenario = context.scenarios.get(failure.scenarioId);
    if (!scenario) return 0.5;

    // Use scenario priority as business priority indicator
    switch (scenario.priority) {
      case Priority.CRITICAL:
        return 1.0;
      case Priority.HIGH:
        return 0.8;
      case Priority.MEDIUM:
        return 0.6;
      case Priority.LOW:
        return 0.4;
      default:
        return 0.5;
    }
  }

  private scoreSecurityImplications(failure: TestFailure, context: AnalysisContext): number {
    const message = failure.message.toLowerCase();
    const scenario = context.scenarios.get(failure.scenarioId);
    const tags = scenario?.tags || [];

    // Security-related keywords
    const securityKeywords = [
      'security', 'auth', 'login', 'credential', 'token', 'permission',
      'access', 'admin', 'privilege', 'encrypt', 'decrypt', 'certificate'
    ];

    const hasSecurityKeywords = securityKeywords.some(keyword =>
      message.includes(keyword) || tags.some(tag => tag.toLowerCase().includes(keyword))
    );

    return hasSecurityKeywords ? 1.0 : 0.2;
  }

  private scorePerformanceImpact(failure: TestFailure, context: AnalysisContext): number {
    const message = failure.message.toLowerCase();

    // Performance-related keywords
    if (message.includes('timeout') || message.includes('slow') ||
        message.includes('performance') || message.includes('memory') ||
        message.includes('cpu')) {
      return 0.9;
    }

    // Check if scenario has performance tags
    const scenario = context.scenarios.get(failure.scenarioId);
    const tags = scenario?.tags || [];
    const hasPerformanceTags = tags.some(tag =>
      tag.toLowerCase().includes('performance') ||
      tag.toLowerCase().includes('load') ||
      tag.toLowerCase().includes('stress')
    );

    return hasPerformanceTags ? 0.8 : 0.3;
  }

  private scoreRegressionDetection(failure: TestFailure, context: AnalysisContext): number {
    const history = context.history.filter(r => r.scenarioId === failure.scenarioId);
    if (history.length === 0) return 0.5;

    // Check if this was previously passing
    const recentPassing = history
      .filter(r => r.status === TestStatus.PASSED)
      .filter(r => {
        const daysSinceTest = (Date.now() - r.startTime.getTime()) / (1000 * 60 * 60 * 24);
        return daysSinceTest <= 30; // Last 30 days
      });

    // High regression score if recently passing tests are now failing
    return recentPassing.length > 0 ? 0.9 : 0.4;
  }

  private applyCustomRules(failure: TestFailure, context: AnalysisContext): number {
    let modifierSum = 0;

    this.config.customRules.forEach(rule => {
      if (rule.condition(failure, context)) {
        modifierSum += rule.priorityModifier;
        this.logger.debug(`Applied custom rule: ${rule.name}`, {
          scenarioId: failure.scenarioId,
          modifier: rule.priorityModifier
        });
      }
    });

    // Convert modifier (-100 to +100) to factor (-1 to +1)
    return modifierSum / 100;
  }

  private determinePriorityLevel(impactScore: number): Priority {
    if (impactScore >= 80) return Priority.CRITICAL;
    if (impactScore >= 60) return Priority.HIGH;
    if (impactScore >= 40) return Priority.MEDIUM;
    return Priority.LOW;
  }

  private generateReasoning(
    failure: TestFailure,
    context: AnalysisContext,
    impactScore: number
  ): string[] {
    const reasoning: string[] = [];

    reasoning.push(`Impact score: ${impactScore.toFixed(1)}/100`);

    if (impactScore >= 80) {
      reasoning.push('Critical priority due to high impact score');
    } else if (impactScore >= 60) {
      reasoning.push('High priority due to significant impact');
    } else if (impactScore >= 40) {
      reasoning.push('Medium priority with moderate impact');
    } else {
      reasoning.push('Low priority with minimal impact');
    }

    const scenario = context.scenarios.get(failure.scenarioId);
    if (scenario) {
      reasoning.push(`Test interface: ${scenario.interface}`);
      reasoning.push(`Scenario priority: ${scenario.priority}`);
    }

    return reasoning;
  }

  private calculateFactorBreakdown(
    failure: TestFailure,
    context: AnalysisContext
  ): Record<string, number> {
    return {
      severity: this.scoreSeverity(failure),
      userImpact: this.scoreUserImpact(failure, context),
      stability: this.scoreStability(failure, context),
      businessPriority: this.scoreBusinessPriority(failure, context),
      securityImplications: this.scoreSecurityImplications(failure, context),
      performanceImpact: this.scorePerformanceImpact(failure, context),
      regressionDetection: this.scoreRegressionDetection(failure, context)
    };
  }

  private calculateConfidence(failure: TestFailure, context: AnalysisContext): number {
    let confidence = 0.5; // Base confidence

    // Increase confidence with more historical data
    const history = context.history.filter(r => r.scenarioId === failure.scenarioId);
    const historyFactor = Math.min(1.0, history.length / 10);
    confidence += historyFactor * 0.3;

    // Increase confidence if scenario information is available
    if (context.scenarios.has(failure.scenarioId)) {
      confidence += 0.2;
    }

    return Math.min(1.0, confidence);
  }

  private estimateFixEffort(failure: TestFailure, context: AnalysisContext): number {
    const scenario = context.scenarios.get(failure.scenarioId);
    let baseEffort = 2; // 2 hours default

    // Adjust based on interface complexity
    if (scenario?.interface === TestInterface.GUI) {
      baseEffort *= 1.5; // GUI tests often more complex to fix
    } else if (scenario?.interface === TestInterface.MIXED) {
      baseEffort *= 1.3;
    }

    // Adjust based on severity
    const severityScore = this.scoreSeverity(failure);
    baseEffort *= (1 + severityScore);

    // Adjust based on stability (unstable tests harder to fix)
    const stabilityScore = this.scoreStability(failure, context);
    baseEffort *= (1 + stabilityScore);

    return Math.round(baseEffort * 10) / 10; // Round to 1 decimal place
  }

  private analyzeFlakyBehavior(scenarioId: string, results: TestResult[]): FlakyTestResult {
    const sortedResults = results.sort((a, b) => a.startTime.getTime() - b.startTime.getTime());

    let flipCount = 0;
    let failureCount = 0;

    for (let i = 0; i < sortedResults.length; i++) {
      const current = sortedResults[i];

      if (current.status === TestStatus.FAILED || current.status === TestStatus.ERROR) {
        failureCount++;
      }

      if (i > 0) {
        const previous = sortedResults[i - 1];
        const currentFailed = current.status === TestStatus.FAILED || current.status === TestStatus.ERROR;
        const previousFailed = previous.status === TestStatus.FAILED || previous.status === TestStatus.ERROR;

        if (currentFailed !== previousFailed) {
          flipCount++;
        }
      }
    }

    const failureRate = failureCount / results.length;
    const flipRate = flipCount / Math.max(1, results.length - 1);

    // Flakiness score combines failure rate and flip rate
    const flakinessScore = (failureRate * 0.6) + (flipRate * 0.4);

    let recommendedAction: FlakyTestResult['recommendedAction'] = 'monitor';
    if (flakinessScore >= 0.7) {
      recommendedAction = 'quarantine';
    } else if (flakinessScore >= 0.5) {
      recommendedAction = 'investigate';
    } else if (flakinessScore >= 0.3) {
      recommendedAction = 'stabilize';
    }

    return {
      scenarioId,
      flakinessScore,
      failureRate,
      flipCount,
      analysisWindow: {
        startDate: sortedResults[0].startTime,
        endDate: sortedResults[sortedResults.length - 1].endTime,
        totalRuns: results.length
      },
      recommendedAction
    };
  }

  private groupByMessagePatterns(failures: TestFailure[]): FailurePattern[] {
    const patterns: FailurePattern[] = [];
    const messageGroups = new Map<string, TestFailure[]>();

    failures.forEach(failure => {
      // Extract pattern from error message (simplified)
      const pattern = this.extractMessagePattern(failure.message);
      if (!messageGroups.has(pattern)) {
        messageGroups.set(pattern, []);
      }
      messageGroups.get(pattern)!.push(failure);
    });

    messageGroups.forEach((groupFailures, pattern) => {
      if (groupFailures.length >= 2) { // Pattern needs at least 2 occurrences
        const timestamps = groupFailures.map(f => f.timestamp);
        patterns.push({
          id: `msg-${this.generatePatternId(pattern)}`,
          description: `Error message pattern: "${pattern}"`,
          affectedScenarios: Array.from(new Set(groupFailures.map(f => f.scenarioId))),
          frequency: groupFailures.length,
          firstSeen: new Date(Math.min(...timestamps.map(t => t.getTime()))),
          lastSeen: new Date(Math.max(...timestamps.map(t => t.getTime()))),
          confidence: Math.min(1.0, groupFailures.length / failures.length * 2),
          suggestedRootCause: this.suggestRootCauseFromMessage(pattern)
        });
      }
    });

    return patterns;
  }

  private groupByStackTracePatterns(failures: TestFailure[]): FailurePattern[] {
    // Simplified implementation - would need more sophisticated stack trace analysis
    return [];
  }

  private groupByTimingPatterns(failures: TestFailure[]): FailurePattern[] {
    // Group failures that happen at similar times
    const hourGroups = new Map<number, TestFailure[]>();

    failures.forEach(failure => {
      const hour = failure.timestamp.getHours();
      if (!hourGroups.has(hour)) {
        hourGroups.set(hour, []);
      }
      hourGroups.get(hour)!.push(failure);
    });

    const patterns: FailurePattern[] = [];
    hourGroups.forEach((groupFailures, hour) => {
      if (groupFailures.length >= 3) { // Need significant clustering
        const timestamps = groupFailures.map(f => f.timestamp);
        patterns.push({
          id: `time-${hour}`,
          description: `Failures clustered around ${hour}:00 hour`,
          affectedScenarios: Array.from(new Set(groupFailures.map(f => f.scenarioId))),
          frequency: groupFailures.length,
          firstSeen: new Date(Math.min(...timestamps.map(t => t.getTime()))),
          lastSeen: new Date(Math.max(...timestamps.map(t => t.getTime()))),
          confidence: 0.7,
          suggestedRootCause: 'Possible scheduled task or resource contention'
        });
      }
    });

    return patterns;
  }

  private groupByCategoryPatterns(failures: TestFailure[]): FailurePattern[] {
    const categoryGroups = new Map<string, TestFailure[]>();

    failures.forEach(failure => {
      const category = failure.category || 'unknown';
      if (!categoryGroups.has(category)) {
        categoryGroups.set(category, []);
      }
      categoryGroups.get(category)!.push(failure);
    });

    const patterns: FailurePattern[] = [];
    categoryGroups.forEach((groupFailures, category) => {
      if (groupFailures.length >= 2) {
        const timestamps = groupFailures.map(f => f.timestamp);
        patterns.push({
          id: `cat-${category}`,
          description: `Category pattern: ${category}`,
          affectedScenarios: Array.from(new Set(groupFailures.map(f => f.scenarioId))),
          frequency: groupFailures.length,
          firstSeen: new Date(Math.min(...timestamps.map(t => t.getTime()))),
          lastSeen: new Date(Math.max(...timestamps.map(t => t.getTime()))),
          confidence: 0.8,
          suggestedRootCause: `Common issue in ${category} category`
        });
      }
    });

    return patterns;
  }

  private extractMessagePattern(message: string): string {
    // Simplified pattern extraction - replace numbers and IDs with placeholders
    return message
      .replace(/\d+/g, 'NUMBER')
      .replace(/[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}/gi, 'UUID')
      .replace(/\/[^\s]+/g, 'PATH')
      .toLowerCase()
      .trim();
  }

  private generatePatternId(pattern: string): string {
    // Simple hash function for pattern ID
    let hash = 0;
    for (let i = 0; i < pattern.length; i++) {
      const char = pattern.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(16);
  }

  private suggestRootCauseFromMessage(pattern: string): string {
    if (pattern.includes('timeout')) return 'Performance or network issues';
    if (pattern.includes('not found') || pattern.includes('missing')) return 'Missing resources or dependencies';
    if (pattern.includes('permission') || pattern.includes('access')) return 'Permission or authentication issues';
    if (pattern.includes('connection')) return 'Network connectivity issues';
    if (pattern.includes('memory') || pattern.includes('out of')) return 'Resource exhaustion';
    return 'Unknown root cause - requires investigation';
  }

  private generateRecommendations(
    assignments: PriorityAssignment[],
    patterns: FailurePattern[],
    flakyTests: FlakyTestResult[]
  ): string[] {
    const recommendations: string[] = [];

    const criticalCount = assignments.filter(a => a.priority === Priority.CRITICAL).length;
    if (criticalCount > 0) {
      recommendations.push(`Address ${criticalCount} critical priority failures immediately`);
    }

    const highCount = assignments.filter(a => a.priority === Priority.HIGH).length;
    if (highCount > 3) {
      recommendations.push(`${highCount} high priority failures detected - consider increasing team focus on testing`);
    }

    if (patterns.length > 0) {
      const topPattern = patterns.sort((a, b) => b.frequency - a.frequency)[0];
      recommendations.push(`Most frequent pattern: "${topPattern.description}" affects ${topPattern.affectedScenarios.length} scenarios`);
    }

    const quarantineCandidates = flakyTests.filter(t => t.recommendedAction === 'quarantine');
    if (quarantineCandidates.length > 0) {
      recommendations.push(`Consider quarantining ${quarantineCandidates.length} highly flaky tests until stabilized`);
    }

    const stabilizeCandidates = flakyTests.filter(t => t.recommendedAction === 'stabilize');
    if (stabilizeCandidates.length > 0) {
      recommendations.push(`${stabilizeCandidates.length} tests need stabilization work`);
    }

    return recommendations;
  }

  private storeAssignment(assignment: PriorityAssignment): void {
    if (!this.analysisHistory.has(assignment.scenarioId)) {
      this.analysisHistory.set(assignment.scenarioId, []);
    }
    this.analysisHistory.get(assignment.scenarioId)!.push(assignment);
  }

  private async loadAnalysisHistory(): Promise<void> {
    // In a real implementation, this would load from persistent storage
    this.logger.debug('Loading analysis history from storage');
  }

  private async saveAnalysisHistory(): Promise<void> {
    // In a real implementation, this would save to persistent storage
    this.logger.debug('Saving analysis history to storage');
  }

  private async loadPatternCache(): Promise<void> {
    // In a real implementation, this would load from persistent storage
    this.logger.debug('Loading pattern cache from storage');
  }

  private async savePatternCache(): Promise<void> {
    // In a real implementation, this would save to persistent storage
    this.logger.debug('Saving pattern cache to storage');
  }
}

/**
 * Create a new PriorityAgent instance with the specified configuration
 */
export function createPriorityAgent(config?: PriorityAgentConfig): PriorityAgent {
  return new PriorityAgent(config);
}

/**
 * Default configuration for PriorityAgent
 */
export const defaultPriorityAgentConfig: PriorityAgentConfig = {
  priorityFactors: DEFAULT_PRIORITY_FACTORS,
  historyRetentionDays: 30,
  flakyThreshold: 0.3,
  patternSensitivity: 0.7,
  minSamplesForTrends: 5,
  customRules: [],
  logLevel: LogLevel.INFO
};
