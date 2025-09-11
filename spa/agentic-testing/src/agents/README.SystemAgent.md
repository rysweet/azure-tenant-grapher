# SystemAgent

The SystemAgent is a comprehensive system resource monitoring and management agent designed for testing environments. It provides real-time monitoring of CPU, memory, disk, network, and process metrics, along with performance analysis and system health reporting.

## Features

### Core Monitoring Capabilities

- **CPU Monitoring**: Real-time CPU usage, load averages, core count, and temperature (when available)
- **Memory Monitoring**: Total, used, free, and available memory with usage percentages
- **Disk Monitoring**: Disk usage by filesystem, I/O operations and throughput
- **Network Monitoring**: Interface statistics, bandwidth usage, and connection counts
- **Process Monitoring**: Process list with CPU/memory usage, state, and hierarchy information
- **Docker Monitoring**: Container metrics including CPU, memory, network, and block I/O

### Advanced Features

- **Health Assessment**: Automatic issue detection with configurable thresholds
- **Resource Leak Detection**: Trend analysis to identify memory leaks and process leaks
- **Performance Baseline**: Capture and compare against performance baselines
- **File System Monitoring**: Track file creation, modification, and deletion
- **System Cleanup**: Automated cleanup of zombie processes and temporary files
- **Event-Driven Architecture**: Real-time notifications via event emitters

## Installation

The SystemAgent is part of the agentic-testing package and requires the following dependencies:

```bash
npm install systeminformation pidusage chokidar
```

## Basic Usage

```typescript
import { SystemAgent, createSystemAgent } from './agents/SystemAgent';

// Create agent with default configuration
const agent = createSystemAgent();

// Initialize the agent
await agent.initialize();

// Capture system metrics
const metrics = await agent.captureMetrics();
console.log(`CPU Usage: ${metrics.cpu.usage}%`);
console.log(`Memory Usage: ${metrics.memory.percentage}%`);

// Cleanup
await agent.cleanup();
```

## Configuration

The SystemAgent accepts a comprehensive configuration object:

```typescript
import { SystemAgentConfig } from './agents/SystemAgent';

const config: SystemAgentConfig = {
  // Monitoring intervals and thresholds
  monitoringInterval: 5000,      // Monitor every 5 seconds
  cpuThreshold: 80,              // Alert if CPU > 80%
  memoryThreshold: 85,           // Alert if Memory > 85%
  diskThreshold: 90,             // Alert if Disk > 90%
  processCountThreshold: 500,    // Alert if > 500 processes

  // Network monitoring
  networkMonitoring: {
    enabled: true,
    interfaces: [],              // Monitor all interfaces
    bandwidth: true              // Include bandwidth metrics
  },

  // Docker container monitoring
  dockerMonitoring: {
    enabled: true,
    containerFilters: []         // Monitor all containers
  },

  // File system change tracking
  fileSystemMonitoring: {
    enabled: true,
    watchPaths: ['./logs', './temp'],
    excludePatterns: [/node_modules/, /\.git/]
  },

  // Automated cleanup
  cleanup: {
    killZombieProcesses: true,
    cleanTempFiles: true,
    tempDirPatterns: ['./temp/*', '/tmp/test-*'],
    processNamePatterns: ['zombie-*', 'test-*']
  },

  // Performance baseline
  performanceBaseline: {
    captureBaseline: true,
    baselineDuration: 30000,     // 30 seconds
    comparisonThreshold: 20      // 20% deviation threshold
  }
};

const agent = createSystemAgent(config);
```

## API Reference

### SystemAgent Class

#### Properties

- `name: string` - Agent name ("SystemAgent")
- `type: AgentType` - Agent type (AgentType.SYSTEM)

#### Methods

##### Core Methods

- `initialize(): Promise<void>` - Initialize the agent and set up monitoring
- `execute(scenario: any): Promise<SystemHealthReport>` - Execute monitoring for a scenario
- `cleanup(): Promise<void>` - Clean up resources and stop monitoring

##### Metrics Collection

- `captureMetrics(): Promise<SystemMetrics>` - Capture current system metrics
- `getMetricsHistory(): SystemMetrics[]` - Get historical metrics data
- `getSystemHealth(): Promise<'healthy' | 'warning' | 'critical'>` - Get current health status

##### Monitoring Control

- `startMonitoring(): Promise<void>` - Start continuous monitoring
- `stopMonitoring(): Promise<void>` - Stop continuous monitoring

##### Reports and Analysis

- `generateHealthReport(): Promise<SystemHealthReport>` - Generate comprehensive health report
- `getFileSystemChanges(): FileSystemChange[]` - Get tracked file system changes
- `getPerformanceBaseline(): PerformanceBaseline | undefined` - Get performance baseline data

### Data Structures

#### SystemMetrics

```typescript
interface SystemMetrics {
  timestamp: Date;
  cpu: {
    usage: number;           // CPU usage percentage
    loadAverage: number[];   // 1, 5, 15 minute load averages
    cores: number;           // Number of CPU cores
    temperature?: number;    // CPU temperature (if available)
  };
  memory: {
    total: number;          // Total memory in bytes
    free: number;           // Free memory in bytes
    used: number;           // Used memory in bytes
    percentage: number;     // Usage percentage
    available: number;      // Available memory in bytes
  };
  disk: {
    usage: DiskUsage[];     // Per-filesystem usage
    io?: DiskIO;           // I/O statistics
  };
  network: {
    interfaces: NetworkInterface[];  // Network interface stats
    connections?: number;            // Active connections
  };
  processes: ProcessInfo[];         // Running processes
  docker?: DockerInfo[];           // Docker containers (if enabled)
  system: {
    uptime: number;         // System uptime in seconds
    platform: string;      // Operating system platform
    arch: string;          // System architecture
    hostname: string;      // System hostname
  };
}
```

#### SystemHealthReport

```typescript
interface SystemHealthReport {
  timestamp: Date;
  overall: 'healthy' | 'warning' | 'critical';
  issues: SystemIssue[];
  metrics: SystemMetrics;
  recommendations: string[];
  resourceLeaks: ResourceLeak[];
  performanceIssues: PerformanceIssue[];
}
```

### Events

The SystemAgent emits the following events:

- `metrics` - Emitted when new metrics are captured during monitoring
- `issues` - Emitted when system issues are detected
- `fileSystemChange` - Emitted when file system changes are detected

```typescript
agent.on('metrics', (metrics: SystemMetrics) => {
  console.log(`CPU: ${metrics.cpu.usage}%`);
});

agent.on('issues', (issues: SystemIssue[]) => {
  console.log(`Issues detected: ${issues.length}`);
});

agent.on('fileSystemChange', (change) => {
  console.log(`File ${change.type}: ${change.path}`);
});
```

## Use Cases

### Test Environment Monitoring

Monitor system resources during test execution to detect performance issues:

```typescript
const agent = createSystemAgent({
  monitoringInterval: 1000,
  cpuThreshold: 75,
  memoryThreshold: 80
});

await agent.initialize();
await agent.startMonitoring();

// Run your tests here
await runTestSuite();

await agent.stopMonitoring();
const report = await agent.generateHealthReport();

if (report.overall !== 'healthy') {
  console.warn('System issues detected during test execution');
}
```

### Resource Leak Detection

Monitor for memory leaks and process leaks during long-running operations:

```typescript
const agent = createSystemAgent({
  monitoringInterval: 5000,
  performanceBaseline: {
    captureBaseline: true,
    baselineDuration: 30000,
    comparisonThreshold: 15
  }
});

await agent.initialize();
await agent.startMonitoring();

// Run long operation
await longRunningOperation();

const report = await agent.generateHealthReport();
if (report.resourceLeaks.length > 0) {
  console.warn('Resource leaks detected:', report.resourceLeaks);
}
```

### Docker Container Monitoring

Monitor Docker containers during test execution:

```typescript
const agent = createSystemAgent({
  dockerMonitoring: {
    enabled: true,
    containerFilters: ['web-server', 'database']
  }
});

await agent.initialize();
const metrics = await agent.captureMetrics();

metrics.docker?.forEach(container => {
  console.log(`${container.name}: CPU ${container.cpu}%, Memory ${container.memory}%`);
});
```

### System Cleanup

Automatically clean up zombie processes and temporary files:

```typescript
const agent = createSystemAgent({
  cleanup: {
    killZombieProcesses: true,
    cleanTempFiles: true,
    tempDirPatterns: ['./test-temp/*', '/tmp/test-*'],
    processNamePatterns: ['test-worker-*']
  }
});

await agent.initialize();
// Cleanup is performed during agent.cleanup()
await agent.cleanup();
```

## Error Handling

The SystemAgent is designed to be resilient and handle errors gracefully:

- Missing system information is handled with fallback values
- Failed process queries are skipped rather than causing crashes
- Docker monitoring gracefully degrades when Docker is unavailable
- File system monitoring handles permission errors and missing paths

```typescript
try {
  const agent = createSystemAgent();
  await agent.initialize();
  const metrics = await agent.captureMetrics();
  // Use metrics
} catch (error) {
  console.error('SystemAgent error:', error);
  // Agent continues to function with degraded capabilities
}
```

## Performance Considerations

- **Monitoring Interval**: Lower intervals provide more granular data but consume more resources
- **Process Monitoring**: Can be resource-intensive on systems with many processes
- **File System Monitoring**: Watching many paths can impact performance
- **Docker Monitoring**: Requires Docker CLI access and may add latency

Recommended settings for different scenarios:

- **Development**: 5000ms interval, basic monitoring
- **CI/CD**: 2000ms interval, full monitoring with cleanup
- **Production**: 10000ms interval, essential monitoring only

## Troubleshooting

### Common Issues

1. **Permission Errors**: Ensure the process has sufficient permissions to read system information
2. **Docker Access**: Verify Docker is installed and accessible for container monitoring
3. **File System Watching**: Check that watch paths exist and are readable
4. **Process Information**: Some process details may not be available on all platforms

### Debug Mode

Enable detailed logging for troubleshooting:

```typescript
const agent = createSystemAgent({
  // Configure with debug-friendly settings
  monitoringInterval: 10000, // Slower monitoring
  fileSystemMonitoring: { enabled: false }, // Disable if causing issues
  dockerMonitoring: { enabled: false } // Disable if Docker unavailable
});
```

## Integration Examples

### Jest Test Integration

```typescript
// In your test setup
let systemAgent: SystemAgent;

beforeAll(async () => {
  systemAgent = createSystemAgent();
  await systemAgent.initialize();
  await systemAgent.startMonitoring();
});

afterAll(async () => {
  await systemAgent.stopMonitoring();
  const report = await systemAgent.generateHealthReport();

  if (report.overall !== 'healthy') {
    console.warn('System issues detected during tests:', report.issues);
  }

  await systemAgent.cleanup();
});
```

### Playwright Test Integration

```typescript
import { test, Page } from '@playwright/test';
import { SystemAgent, createSystemAgent } from './agents/SystemAgent';

test.describe('System monitored tests', () => {
  let systemAgent: SystemAgent;

  test.beforeEach(async () => {
    systemAgent = createSystemAgent({
      monitoringInterval: 2000,
      cpuThreshold: 70,
      memoryThreshold: 75
    });

    await systemAgent.initialize();
    await systemAgent.startMonitoring();
  });

  test.afterEach(async () => {
    await systemAgent.stopMonitoring();
    const health = await systemAgent.getSystemHealth();

    if (health !== 'healthy') {
      console.warn(`Test completed with system health: ${health}`);
    }

    await systemAgent.cleanup();
  });

  test('monitored test case', async ({ page }: { page: Page }) => {
    // Your test implementation
    await page.goto('https://example.com');
    // Test continues...
  });
});
```

## Best Practices

1. **Always call cleanup()**: Ensure proper resource cleanup after agent use
2. **Configure appropriate thresholds**: Set realistic thresholds based on your system
3. **Use events for real-time monitoring**: Leverage event-driven architecture for responsiveness
4. **Capture baselines**: Use performance baselines for comparative analysis
5. **Handle errors gracefully**: Implement proper error handling for degraded scenarios
6. **Monitor selectively**: Enable only the monitoring features you need to minimize overhead

## License

This SystemAgent is part of the Azure Tenant Grapher project and follows the same licensing terms.
