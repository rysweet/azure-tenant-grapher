/**
 * PriorityAgent Usage Examples
 *
 * This file demonstrates various use cases for the PriorityAgent including:
 * - Basic priority analysis
 * - Custom priority rules
 * - Flaky test detection
 * - Pattern analysis
 * - Comprehensive reporting
 */

import {
  PriorityAgent,
  createPriorityAgent,
  PriorityAgentConfig,
  PriorityRule,
  PriorityFactors
} from '../PriorityAgent';
import {
  TestFailure,
  TestResult,
  TestStatus,
  Priority,
  TestInterface,
  TestScenario
} from '../../models/TestModels';
import { LogLevel } from '../../utils/logger';

/**
 * Example 1: Basic Priority Agent Usage
 */
export async function basicPriorityAnalysisExample(): Promise<void> {
  console.log('=== Basic Priority Analysis Example ===');

  // Create agent with default configuration
  const agent = createPriorityAgent();

  try {
    await agent.initialize();

    // Create sample test failures
    const failures: TestFailure[] = [
      {
        scenarioId: 'login-test',
        timestamp: new Date(),
        message: 'Login failed: Invalid credentials',
        category: 'authentication',
        failedStep: 2
      },
      {
        scenarioId: 'data-export',
        timestamp: new Date(),
        message: 'Export operation timed out after 30 seconds',
        category: 'performance',
        failedStep: 5
      },
      {
        scenarioId: 'ui-rendering',
        timestamp: new Date(),
        message: 'Component failed to render: React error',
        category: 'ui',
        failedStep: 1
      }
    ];

    // Analyze individual failure
    console.log('\n--- Individual Priority Analysis ---');
    for (const failure of failures) {
      const assignment = await agent.analyzePriority(failure);
      console.log(`${failure.scenarioId}: ${assignment.priority} (Score: ${assignment.impactScore.toFixed(1)})`);
      console.log(`  Reasoning: ${assignment.reasoning.join(', ')}`);
    }

    // Rank all failures
    console.log('\n--- Ranking All Failures ---');
    const rankings = await agent.rankFailures(failures);
    rankings.forEach((assignment, index) => {
      console.log(`${index + 1}. ${assignment.scenarioId}: ${assignment.priority} (${assignment.impactScore.toFixed(1)})`);
    });

    // Get suggested fix order
    console.log('\n--- Suggested Fix Order ---');
    const fixOrder = await agent.suggestFixOrder(failures);
    fixOrder.forEach((scenarioId, index) => {
      console.log(`${index + 1}. ${scenarioId}`);
    });

  } finally {
    await agent.cleanup();
  }
}

/**
 * Example 2: Custom Priority Rules
 */
export async function customRulesExample(): Promise<void> {
  console.log('\n=== Custom Rules Example ===');

  // Define custom priority rules
  const customRules: PriorityRule[] = [
    {
      name: 'Security Critical',
      condition: (failure) => {
        return failure.message.toLowerCase().includes('security') ||
               failure.message.toLowerCase().includes('auth') ||
               failure.category === 'authentication';
      },
      priorityModifier: 50, // +50 points for security issues
      description: 'Boost priority for security-related failures'
    },
    {
      name: 'Performance Degradation',
      condition: (failure) => {
        return failure.message.toLowerCase().includes('timeout') ||
               failure.message.toLowerCase().includes('slow') ||
               failure.category === 'performance';
      },
      priorityModifier: 30, // +30 points for performance issues
      description: 'Boost priority for performance-related failures'
    },
    {
      name: 'Known Issue Penalty',
      condition: (failure) => {
        return failure.isKnownIssue === true;
      },
      priorityModifier: -20, // -20 points for known issues
      description: 'Lower priority for known issues'
    }
  ];

  // Create agent with custom rules
  const config: PriorityAgentConfig = {
    customRules,
    logLevel: LogLevel.DEBUG
  };

  const agent = createPriorityAgent(config);

  try {
    await agent.initialize();

    // Test failures that will trigger custom rules
    const failures: TestFailure[] = [
      {
        scenarioId: 'auth-bypass',
        timestamp: new Date(),
        message: 'Security vulnerability: Authentication bypass detected',
        category: 'authentication'
      },
      {
        scenarioId: 'slow-query',
        timestamp: new Date(),
        message: 'Database query timeout after 60 seconds',
        category: 'performance'
      },
      {
        scenarioId: 'known-ui-bug',
        timestamp: new Date(),
        message: 'UI alignment issue in sidebar',
        category: 'ui',
        isKnownIssue: true
      }
    ];

    console.log('\n--- Priority Analysis with Custom Rules ---');
    for (const failure of failures) {
      const assignment = await agent.analyzePriority(failure);
      console.log(`${failure.scenarioId}:`);
      console.log(`  Priority: ${assignment.priority}`);
      console.log(`  Impact Score: ${assignment.impactScore.toFixed(1)}`);
      console.log(`  Confidence: ${assignment.confidence.toFixed(2)}`);
      console.log(`  Factors: ${JSON.stringify(assignment.factors, null, 2)}`);
    }

  } finally {
    await agent.cleanup();
  }
}

/**
 * Example 3: Flaky Test Detection
 */
export async function flakyTestDetectionExample(): Promise<void> {
  console.log('\n=== Flaky Test Detection Example ===');

  const agent = createPriorityAgent({
    flakyThreshold: 0.3, // 30% threshold for flaky detection
    minSamplesForTrends: 5
  });

  try {
    await agent.initialize();

    // Generate historical test results with flaky behavior
    const testResults: TestResult[] = [];
    const scenarios = ['stable-test', 'flaky-test', 'very-flaky-test'];

    // Generate 20 results for each scenario
    scenarios.forEach(scenarioId => {
      for (let i = 0; i < 20; i++) {
        let status = TestStatus.PASSED;

        // Make flaky-test fail 40% of the time randomly
        if (scenarioId === 'flaky-test' && Math.random() < 0.4) {
          status = TestStatus.FAILED;
        }

        // Make very-flaky-test alternate between pass and fail
        if (scenarioId === 'very-flaky-test') {
          status = i % 2 === 0 ? TestStatus.PASSED : TestStatus.FAILED;
        }

        testResults.push({
          scenarioId,
          status,
          duration: 1000 + Math.random() * 2000,
          startTime: new Date(Date.now() - (20 - i) * 60 * 60 * 1000), // Spread over 20 hours
          endTime: new Date(Date.now() - (20 - i - 1) * 60 * 60 * 1000),
          error: status === TestStatus.FAILED ? 'Random failure' : undefined
        });
      }
    });

    console.log('\n--- Flaky Test Analysis ---');
    const flakyTests = agent.identifyFlaky(testResults);

    flakyTests.forEach(flakyTest => {
      console.log(`${flakyTest.scenarioId}:`);
      console.log(`  Flakiness Score: ${flakyTest.flakinessScore.toFixed(3)}`);
      console.log(`  Failure Rate: ${(flakyTest.failureRate * 100).toFixed(1)}%`);
      console.log(`  Flip Count: ${flakyTest.flipCount}`);
      console.log(`  Recommended Action: ${flakyTest.recommendedAction}`);
      console.log(`  Analysis Window: ${flakyTest.analysisWindow.totalRuns} runs`);
    });

  } finally {
    await agent.cleanup();
  }
}

/**
 * Example 4: Pattern Analysis
 */
export async function patternAnalysisExample(): Promise<void> {
  console.log('\n=== Pattern Analysis Example ===');

  const agent = createPriorityAgent();

  try {
    await agent.initialize();

    // Create failures with patterns
    const failures: TestFailure[] = [
      // Database connection pattern
      {
        scenarioId: 'user-login',
        timestamp: new Date(),
        message: 'Connection timeout to database server 192.168.1.100',
        category: 'database'
      },
      {
        scenarioId: 'data-fetch',
        timestamp: new Date(),
        message: 'Connection timeout to database server 192.168.1.200',
        category: 'database'
      },
      {
        scenarioId: 'user-profile',
        timestamp: new Date(),
        message: 'Connection timeout to database server 192.168.1.150',
        category: 'database'
      },

      // Permission pattern
      {
        scenarioId: 'admin-panel',
        timestamp: new Date(),
        message: 'Access denied: Insufficient permissions for operation',
        category: 'authorization'
      },
      {
        scenarioId: 'user-settings',
        timestamp: new Date(),
        message: 'Access denied: Insufficient permissions for update',
        category: 'authorization'
      },

      // Timing pattern (all happening at 2 AM)
      {
        scenarioId: 'backup-job',
        timestamp: new Date(new Date().setHours(2, 15, 0, 0)),
        message: 'Backup operation failed: Disk space insufficient',
        category: 'maintenance'
      },
      {
        scenarioId: 'cleanup-job',
        timestamp: new Date(new Date().setHours(2, 30, 0, 0)),
        message: 'Cleanup operation failed: Lock timeout',
        category: 'maintenance'
      },
      {
        scenarioId: 'report-gen',
        timestamp: new Date(new Date().setHours(2, 45, 0, 0)),
        message: 'Report generation failed: Resource unavailable',
        category: 'maintenance'
      }
    ];

    console.log('\n--- Pattern Analysis ---');
    const patterns = agent.analyzeFailurePatterns(failures);

    patterns.forEach(pattern => {
      console.log(`Pattern: ${pattern.description}`);
      console.log(`  ID: ${pattern.id}`);
      console.log(`  Frequency: ${pattern.frequency}`);
      console.log(`  Affected Scenarios: ${pattern.affectedScenarios.join(', ')}`);
      console.log(`  Confidence: ${pattern.confidence.toFixed(2)}`);
      console.log(`  Suggested Root Cause: ${pattern.suggestedRootCause}`);
      console.log(`  First Seen: ${pattern.firstSeen.toISOString()}`);
      console.log(`  Last Seen: ${pattern.lastSeen.toISOString()}`);
      console.log('');
    });

  } finally {
    await agent.cleanup();
  }
}

/**
 * Example 5: Comprehensive Priority Report
 */
export async function comprehensiveReportExample(): Promise<void> {
  console.log('\n=== Comprehensive Priority Report Example ===');

  // Custom priority factors favoring security and user impact
  const priorityFactors: PriorityFactors = {
    errorSeverity: 0.20,
    userImpact: 0.25,
    testStability: 0.10,
    businessPriority: 0.15,
    securityImplications: 0.20,
    performanceImpact: 0.05,
    regressionDetection: 0.05
  };

  const agent = createPriorityAgent({
    priorityFactors,
    flakyThreshold: 0.25
  });

  try {
    await agent.initialize();

    // Create comprehensive test scenario
    const scenarios = new Map<string, TestScenario>();
    scenarios.set('critical-login', {
      id: 'critical-login',
      name: 'User Login Flow',
      description: 'Critical user authentication flow',
      priority: Priority.CRITICAL,
      interface: TestInterface.GUI,
      prerequisites: ['Database running', 'Auth service available'],
      steps: [],
      verifications: [],
      expectedOutcome: 'User successfully logged in',
      estimatedDuration: 30,
      tags: ['security', 'authentication', 'critical-path'],
      enabled: true
    });

    const failures: TestFailure[] = [
      {
        scenarioId: 'critical-login',
        timestamp: new Date(),
        message: 'Authentication bypass vulnerability detected',
        category: 'security',
        failedStep: 3,
        stackTrace: 'SecurityError: Invalid token validation'
      }
    ];

    // Generate historical data for context
    const testResults: TestResult[] = [];
    for (let i = 0; i < 10; i++) {
      testResults.push({
        scenarioId: 'critical-login',
        status: i < 8 ? TestStatus.PASSED : TestStatus.FAILED, // Recent failures
        duration: 2000 + Math.random() * 1000,
        startTime: new Date(Date.now() - i * 24 * 60 * 60 * 1000),
        endTime: new Date(Date.now() - i * 24 * 60 * 60 * 1000 + 2500),
        error: i >= 8 ? 'Authentication error' : undefined
      });
    }

    console.log('\n--- Generating Comprehensive Report ---');
    const report = await agent.generatePriorityReport(failures, testResults);

    console.log(`Report Generated: ${report.timestamp.toISOString()}`);
    console.log(`Total Failures Analyzed: ${report.totalFailures}`);

    console.log('\nPriority Summary:');
    console.log(`  Critical: ${report.summary.criticalCount}`);
    console.log(`  High: ${report.summary.highCount}`);
    console.log(`  Medium: ${report.summary.mediumCount}`);
    console.log(`  Low: ${report.summary.lowCount}`);
    console.log(`  Average Impact Score: ${report.summary.averageImpactScore.toFixed(1)}`);
    console.log(`  Average Confidence: ${report.summary.averageConfidence.toFixed(2)}`);

    console.log('\nDetailed Assignments:');
    report.assignments.forEach(assignment => {
      console.log(`  ${assignment.scenarioId}: ${assignment.priority} (${assignment.impactScore.toFixed(1)})`);
      console.log(`    Estimated Fix Effort: ${assignment.estimatedFixEffort} hours`);
      console.log(`    Key Factors: ${Object.entries(assignment.factors)
        .sort(([,a], [,b]) => b - a)
        .slice(0, 3)
        .map(([factor, score]) => `${factor}: ${score.toFixed(2)}`)
        .join(', ')}`);
    });

    console.log('\nRecommendations:');
    report.recommendations.forEach((rec, index) => {
      console.log(`  ${index + 1}. ${rec}`);
    });

    console.log('\nSuggested Fix Order:');
    report.fixOrder.forEach((scenarioId, index) => {
      const assignment = report.assignments.find(a => a.scenarioId === scenarioId);
      console.log(`  ${index + 1}. ${scenarioId} (${assignment?.priority}, ${assignment?.estimatedFixEffort}h)`);
    });

  } finally {
    await agent.cleanup();
  }
}

/**
 * Example 6: Real-time Priority Monitoring
 */
export async function realTimeMonitoringExample(): Promise<void> {
  console.log('\n=== Real-time Priority Monitoring Example ===');

  const agent = createPriorityAgent();

  try {
    await agent.initialize();

    // Set up event listeners
    agent.on('reportGenerated', (report) => {
      console.log(`📊 New priority report generated with ${report.totalFailures} failures`);
    });

    agent.on('initialized', () => {
      console.log('🚀 PriorityAgent is ready for monitoring');
    });

    // Simulate continuous monitoring
    console.log('\n--- Simulating Real-time Monitoring ---');
    console.log('(This would typically run continuously in a real system)');

    // Simulate receiving new failures over time
    const newFailures = [
      {
        scenarioId: 'payment-processing',
        timestamp: new Date(),
        message: 'Payment gateway timeout - critical business impact',
        category: 'payment'
      }
    ];

    for (const failure of newFailures) {
      const assignment = await agent.analyzePriority(failure);
      console.log(`🔥 New failure detected: ${failure.scenarioId}`);
      console.log(`   Priority: ${assignment.priority}`);
      console.log(`   Impact Score: ${assignment.impactScore.toFixed(1)}`);

      if (assignment.priority === Priority.CRITICAL) {
        console.log('   🚨 CRITICAL PRIORITY - Immediate attention required!');
      }
    }

  } finally {
    await agent.cleanup();
  }
}

/**
 * Run all examples
 */
export async function runAllExamples(): Promise<void> {
  console.log('🧪 Running PriorityAgent Examples\n');

  try {
    await basicPriorityAnalysisExample();
    await customRulesExample();
    await flakyTestDetectionExample();
    await patternAnalysisExample();
    await comprehensiveReportExample();
    await realTimeMonitoringExample();

    console.log('\n✅ All PriorityAgent examples completed successfully!');
  } catch (error) {
    console.error('❌ Error running examples:', error);
    throw error;
  }
}

// Individual examples are already exported above
