# PriorityAgent - Test Failure Priority Analysis

The PriorityAgent is a comprehensive test failure analysis and ranking system that helps development teams prioritize bug fixes and test improvements based on multiple factors including impact, severity, stability, and business importance.

## Features

### Core Capabilities
- **Priority Analysis**: Assigns priority levels (Critical, High, Medium, Low) to test failures
- **Impact Scoring**: Calculates numerical impact scores (0-100) based on multiple weighted factors
- **Failure Ranking**: Orders failures by importance for optimal fix prioritization
- **Pattern Recognition**: Identifies common failure patterns and root causes
- **Flaky Test Detection**: Detects and analyzes unstable tests with configurable thresholds
- **Historical Analysis**: Uses test history to improve priority accuracy over time
- **Comprehensive Reporting**: Generates detailed reports with actionable recommendations

### Priority Factors
The agent considers seven key factors when calculating priority:

1. **Error Severity** (25%): Crash/fatal errors vs warnings/minor issues
2. **User Impact** (20%): GUI tests vs internal API tests 
3. **Test Stability** (15%): Consistent failures vs flaky behavior
4. **Business Priority** (15%): Critical path vs nice-to-have features
5. **Security Implications** (10%): Security-related failures get priority boost
6. **Performance Impact** (10%): Timeouts and performance degradation
7. **Regression Detection** (5%): Previously passing tests now failing

*Percentages are configurable weights in the default configuration.*

## Usage Examples

### Basic Priority Analysis

```typescript
import { createPriorityAgent, TestFailure } from './PriorityAgent';

const agent = createPriorityAgent();
await agent.initialize();

const failure: TestFailure = {
  scenarioId: 'login-test',
  timestamp: new Date(),
  message: 'Authentication failed: Invalid credentials',
  category: 'authentication'
};

const assignment = await agent.analyzePriority(failure);
console.log(`Priority: ${assignment.priority}`);
console.log(`Impact Score: ${assignment.impactScore}`);
console.log(`Confidence: ${assignment.confidence}`);
```

### Custom Priority Rules

```typescript
import { PriorityRule, PriorityAgentConfig } from './PriorityAgent';

const customRules: PriorityRule[] = [
  {
    name: 'Security Critical',
    condition: (failure) => failure.message.toLowerCase().includes('security'),
    priorityModifier: 50, // +50 points
    description: 'Boost priority for security-related failures'
  }
];

const config: PriorityAgentConfig = {
  customRules,
  flakyThreshold: 0.3 // 30% failure rate threshold
};

const agent = createPriorityAgent(config);
```

### Ranking Multiple Failures

```typescript
const failures: TestFailure[] = [
  // ... array of test failures
];

// Get priority assignments ranked by importance
const rankings = await agent.rankFailures(failures);

// Get suggested fix order
const fixOrder = await agent.suggestFixOrder(failures);

console.log('Fix order:', fixOrder);
```

### Flaky Test Detection

```typescript
const testResults: TestResult[] = [
  // ... historical test results
];

const flakyTests = agent.identifyFlaky(testResults);

flakyTests.forEach(flaky => {
  console.log(`${flaky.scenarioId}: ${flaky.flakinessScore.toFixed(2)} flakiness`);
  console.log(`Recommended action: ${flaky.recommendedAction}`);
});
```

### Pattern Analysis

```typescript
const patterns = agent.analyzeFailurePatterns(failures);

patterns.forEach(pattern => {
  console.log(`Pattern: ${pattern.description}`);
  console.log(`Affects ${pattern.affectedScenarios.length} scenarios`);
  console.log(`Suggested cause: ${pattern.suggestedRootCause}`);
});
```

### Comprehensive Reporting

```typescript
const report = await agent.generatePriorityReport(failures, testResults);

console.log(`Report Summary:`);
console.log(`- Critical: ${report.summary.criticalCount}`);
console.log(`- High: ${report.summary.highCount}`);
console.log(`- Medium: ${report.summary.mediumCount}`);
console.log(`- Low: ${report.summary.lowCount}`);

report.recommendations.forEach(rec => {
  console.log(`📋 ${rec}`);
});
```

## Configuration Options

### PriorityAgentConfig

```typescript
interface PriorityAgentConfig {
  /** Custom priority scoring factors (weights must sum to ~1.0) */
  priorityFactors?: Partial<PriorityFactors>;
  
  /** Historical data retention period in days (default: 30) */
  historyRetentionDays?: number;
  
  /** Flaky test detection threshold 0-1 (default: 0.3) */
  flakyThreshold?: number;
  
  /** Pattern recognition sensitivity (default: 0.7) */
  patternSensitivity?: number;
  
  /** Minimum samples required for trend analysis (default: 5) */
  minSamplesForTrends?: number;
  
  /** Custom priority rules */
  customRules?: PriorityRule[];
  
  /** Logging level */
  logLevel?: LogLevel;
}
```

### Priority Factors

```typescript
interface PriorityFactors {
  errorSeverity: number;      // 0.25 (25%)
  userImpact: number;         // 0.20 (20%)
  testStability: number;      // 0.15 (15%)
  businessPriority: number;   // 0.15 (15%)
  securityImplications: number; // 0.10 (10%)
  performanceImpact: number;  // 0.10 (10%)
  regressionDetection: number; // 0.05 (5%)
}
```

## Output Types

### Priority Assignment

```typescript
interface PriorityAssignment {
  scenarioId: string;           // Test scenario identifier
  priority: Priority;           // CRITICAL | HIGH | MEDIUM | LOW
  impactScore: number;          // 0-100 numerical score
  confidence: number;           // 0-1 confidence in assignment
  timestamp: Date;              // When assignment was made
  reasoning: string[];          // Human-readable explanations
  factors: Record<string, number>; // Factor score breakdown
  estimatedFixEffort?: number;  // Hours estimated to fix
}
```

### Priority Report

```typescript
interface PriorityReport {
  timestamp: Date;
  totalFailures: number;
  assignments: PriorityAssignment[];
  patterns: FailurePattern[];
  flakyTests: FlakyTestResult[];
  fixOrder: string[];
  summary: {
    criticalCount: number;
    highCount: number;
    mediumCount: number;
    lowCount: number;
    averageImpactScore: number;
    averageConfidence: number;
  };
  recommendations: string[];
}
```

## Pattern Detection

The agent automatically detects several types of patterns:

- **Message Patterns**: Similar error messages across different tests
- **Stack Trace Patterns**: Common stack traces indicating shared root causes  
- **Timing Patterns**: Failures clustered around specific times (resource contention)
- **Category Patterns**: Failures grouped by error category

Pattern detection helps identify systemic issues that affect multiple tests.

## Flaky Test Analysis

Flaky tests are identified using multiple metrics:

- **Failure Rate**: Percentage of runs that fail
- **Flip Count**: Number of state changes (pass→fail, fail→pass)
- **Flakiness Score**: Combined metric weighing both factors

Recommended actions based on flakiness score:
- **0.7+**: Quarantine (disable until fixed)
- **0.5-0.7**: Investigate (requires attention)
- **0.3-0.5**: Stabilize (minor improvements needed)
- **<0.3**: Monitor (acceptable variability)

## Integration

### With Test Runners

```typescript
// Jest/Vitest/Mocha integration example
afterEach(async () => {
  if (this.currentTest.state === 'failed') {
    const failure: TestFailure = {
      scenarioId: this.currentTest.title,
      timestamp: new Date(),
      message: this.currentTest.err.message,
      stackTrace: this.currentTest.err.stack,
      category: 'execution'
    };
    
    const assignment = await priorityAgent.analyzePriority(failure);
    console.log(`Test failure priority: ${assignment.priority}`);
  }
});
```

### With CI/CD Pipelines

```typescript
// GitHub Actions / Jenkins integration
const report = await agent.generatePriorityReport(failures, historicalResults);

// Post as PR comment or issue
await github.issues.createComment({
  issue_number: pr.number,
  body: `## Test Failure Priority Report

**Critical:** ${report.summary.criticalCount}
**High:** ${report.summary.highCount}  
**Medium:** ${report.summary.mediumCount}
**Low:** ${report.summary.lowCount}

### Recommendations:
${report.recommendations.map(r => `- ${r}`).join('\n')}
  `
});
```

### Event-Driven Architecture

```typescript
agent.on('reportGenerated', (report) => {
  // Send notifications for critical failures
  if (report.summary.criticalCount > 0) {
    notificationService.sendAlert({
      severity: 'critical',
      message: `${report.summary.criticalCount} critical test failures detected`
    });
  }
});
```

## Best Practices

1. **Regular Analysis**: Run priority analysis on every test failure
2. **Historical Context**: Maintain test result history for accurate trend analysis
3. **Custom Rules**: Define project-specific priority rules for better accuracy
4. **Regular Reviews**: Periodically review and adjust priority factor weights
5. **Flaky Test Management**: Act on flaky test recommendations promptly
6. **Pattern Investigation**: Investigate recurring patterns for systemic fixes

## Machine Learning Integration

The PriorityAgent is designed to be ML-ready:

- **Structured Data**: All scoring factors are numerical and normalized
- **Feature Engineering**: Factor breakdowns provide ML training features  
- **Confidence Scoring**: Built-in confidence metrics for model validation
- **Historical Tracking**: Time-series data suitable for trend analysis
- **Pattern Recognition**: Pattern data can train clustering models

Future enhancements could include:
- ML-powered pattern detection
- Predictive failure analysis
- Automated priority weight optimization
- Anomaly detection for test stability

## Examples

See `/src/agents/examples/PriorityAgent.example.ts` for comprehensive usage examples including:

- Basic priority analysis
- Custom rules configuration  
- Flaky test detection
- Pattern analysis
- Real-time monitoring
- Comprehensive reporting

## Implementation Notes

- Thread-safe for concurrent failure analysis
- Configurable logging with structured output
- Event-driven architecture with custom event handlers
- Extensible through custom priority rules
- Persistent storage ready (implement loadAnalysisHistory/saveAnalysisHistory)
- Memory efficient with configurable history retention