/**
 * SystemAgent usage example
 * 
 * This example demonstrates how to use the SystemAgent for comprehensive
 * system resource monitoring during test execution.
 */

import { SystemAgent, createSystemAgent, SystemAgentConfig } from '../SystemAgent';

async function basicSystemMonitoringExample() {
  console.log('=== Basic System Monitoring Example ===');
  
  // Create a SystemAgent with basic configuration
  const agent = createSystemAgent({
    monitoringInterval: 2000, // Monitor every 2 seconds
    cpuThreshold: 80,         // Alert if CPU > 80%
    memoryThreshold: 85,      // Alert if Memory > 85%
    diskThreshold: 90         // Alert if Disk > 90%
  });

  try {
    // Initialize the agent
    await agent.initialize();
    console.log('SystemAgent initialized successfully');

    // Capture a single metrics snapshot
    const metrics = await agent.captureMetrics();
    console.log('\n=== System Metrics Snapshot ===');
    console.log(`Timestamp: ${metrics.timestamp.toISOString()}`);
    console.log(`CPU Usage: ${metrics.cpu.usage.toFixed(1)}%`);
    console.log(`Memory Usage: ${metrics.memory.percentage.toFixed(1)}%`);
    console.log(`Memory Used: ${(metrics.memory.used / 1024 / 1024 / 1024).toFixed(2)} GB`);
    console.log(`Total Memory: ${(metrics.memory.total / 1024 / 1024 / 1024).toFixed(2)} GB`);
    console.log(`System Platform: ${metrics.system.platform}`);
    console.log(`System Architecture: ${metrics.system.arch}`);
    console.log(`Hostname: ${metrics.system.hostname}`);
    console.log(`Uptime: ${Math.floor(metrics.system.uptime / 3600)} hours`);
    console.log(`Process Count: ${metrics.processes.length}`);

    // Show top 5 processes by CPU usage
    const topCpuProcesses = metrics.processes
      .sort((a, b) => b.cpu - a.cpu)
      .slice(0, 5);
    
    console.log('\n=== Top 5 Processes by CPU Usage ===');
    topCpuProcesses.forEach(proc => {
      console.log(`${proc.name} (PID: ${proc.pid}): ${proc.cpu.toFixed(1)}% CPU, ${(proc.memory / 1024 / 1024).toFixed(1)} MB RAM`);
    });

    // Get current system health
    const health = await agent.getSystemHealth();
    console.log(`\nSystem Health: ${health.toUpperCase()}`);

  } catch (error) {
    console.error('Error in basic monitoring:', error);
  } finally {
    await agent.cleanup();
  }
}

async function continuousMonitoringExample() {
  console.log('\n\n=== Continuous Monitoring Example ===');
  
  const agent = createSystemAgent({
    monitoringInterval: 1000,
    cpuThreshold: 75,
    memoryThreshold: 80,
    performanceBaseline: {
      captureBaseline: true,
      baselineDuration: 5000,  // 5 seconds baseline
      comparisonThreshold: 15  // 15% deviation threshold
    }
  });

  try {
    await agent.initialize();
    console.log('Starting continuous monitoring for 10 seconds...');

    // Set up event listeners
    let metricsCount = 0;
    agent.on('metrics', (metrics) => {
      metricsCount++;
      console.log(`Metrics ${metricsCount}: CPU ${metrics.cpu.usage.toFixed(1)}%, Memory ${metrics.memory.percentage.toFixed(1)}%`);
    });

    agent.on('issues', (issues) => {
      console.log(`⚠️  Issues detected: ${issues.length}`);
      issues.forEach(issue => {
        console.log(`  - ${issue.type.toUpperCase()}: ${issue.message} (${issue.severity})`);
      });
    });

    // Start monitoring
    await agent.startMonitoring();
    
    // Let it run for 10 seconds
    await new Promise(resolve => setTimeout(resolve, 10000));
    
    // Stop monitoring
    await agent.stopMonitoring();
    
    // Get metrics history
    const history = agent.getMetricsHistory();
    console.log(`\nCollected ${history.length} metric samples`);
    
    if (history.length > 0) {
      const avgCpu = history.reduce((sum, m) => sum + m.cpu.usage, 0) / history.length;
      const avgMemory = history.reduce((sum, m) => sum + m.memory.percentage, 0) / history.length;
      console.log(`Average CPU Usage: ${avgCpu.toFixed(1)}%`);
      console.log(`Average Memory Usage: ${avgMemory.toFixed(1)}%`);
    }

    // Get performance baseline if captured
    const baseline = agent.getPerformanceBaseline();
    if (baseline) {
      console.log('\n=== Performance Baseline ===');
      console.log(`Baseline Duration: ${baseline.duration}ms`);
      console.log(`Baseline Average CPU: ${baseline.metrics.avgCPU.toFixed(1)}%`);
      console.log(`Baseline Average Memory: ${baseline.metrics.avgMemory.toFixed(1)}%`);
    }

  } catch (error) {
    console.error('Error in continuous monitoring:', error);
  } finally {
    await agent.cleanup();
  }
}

async function healthReportExample() {
  console.log('\n\n=== Health Report Example ===');
  
  const agent = createSystemAgent({
    monitoringInterval: 500,
    cpuThreshold: 70,
    memoryThreshold: 75,
    diskThreshold: 85,
    processCountThreshold: 300
  });

  try {
    await agent.initialize();
    
    // Start monitoring to collect some data
    await agent.startMonitoring();
    await new Promise(resolve => setTimeout(resolve, 3000));
    await agent.stopMonitoring();
    
    // Generate comprehensive health report
    const healthReport = await agent.generateHealthReport();
    
    console.log('=== System Health Report ===');
    console.log(`Report Time: ${healthReport.timestamp.toISOString()}`);
    console.log(`Overall Health: ${healthReport.overall.toUpperCase()}`);
    console.log(`Issues Found: ${healthReport.issues.length}`);
    console.log(`Resource Leaks: ${healthReport.resourceLeaks.length}`);
    console.log(`Performance Issues: ${healthReport.performanceIssues.length}`);
    console.log(`Recommendations: ${healthReport.recommendations.length}`);
    
    if (healthReport.issues.length > 0) {
      console.log('\n--- Issues ---');
      healthReport.issues.forEach((issue, index) => {
        console.log(`${index + 1}. [${issue.severity.toUpperCase()}] ${issue.type}: ${issue.message}`);
      });
    }
    
    if (healthReport.recommendations.length > 0) {
      console.log('\n--- Recommendations ---');
      healthReport.recommendations.forEach((rec, index) => {
        console.log(`${index + 1}. ${rec}`);
      });
    }
    
    if (healthReport.resourceLeaks.length > 0) {
      console.log('\n--- Resource Leaks ---');
      healthReport.resourceLeaks.forEach((leak, index) => {
        console.log(`${index + 1}. ${leak.type} leak in ${leak.source} (${leak.severity}): ${leak.recommendation}`);
      });
    }

  } catch (error) {
    console.error('Error generating health report:', error);
  } finally {
    await agent.cleanup();
  }
}

async function testIntegrationExample() {
  console.log('\n\n=== Test Integration Example ===');
  
  const agent = createSystemAgent({
    monitoringInterval: 1000,
    cpuThreshold: 80,
    memoryThreshold: 85,
    cleanup: {
      killZombieProcesses: true,
      cleanTempFiles: true,
      tempDirPatterns: ['./temp/*', '/tmp/test-*'],
      processNamePatterns: ['test-*', 'zombie-*']
    }
  });

  try {
    console.log('Initializing system monitoring for test...');
    await agent.initialize();
    
    // Simulate test preparation
    console.log('Pre-test system health check...');
    const preTestHealth = await agent.getSystemHealth();
    console.log(`Pre-test health: ${preTestHealth}`);
    
    // Start monitoring during test
    await agent.startMonitoring();
    console.log('Test monitoring started');
    
    // Simulate running a test scenario
    console.log('Simulating test execution...');
    
    // Create some CPU load to demonstrate monitoring
    const startTime = Date.now();
    while (Date.now() - startTime < 5000) {
      // Simulate some work
      Math.random() * Math.random();
    }
    
    console.log('Test execution completed');
    
    // Stop monitoring
    await agent.stopMonitoring();
    
    // Post-test health check
    console.log('Post-test system health check...');
    const postTestHealth = await agent.getSystemHealth();
    console.log(`Post-test health: ${postTestHealth}`);
    
    // Generate final report
    const finalReport = await agent.generateHealthReport();
    console.log('\n--- Test Execution Report ---');
    console.log(`System Status: ${finalReport.overall}`);
    console.log(`Metrics Collected: ${agent.getMetricsHistory().length} samples`);
    
    if (finalReport.issues.length > 0) {
      console.log(`Issues During Test: ${finalReport.issues.length}`);
      finalReport.issues.forEach(issue => {
        console.log(`  - ${issue.message}`);
      });
    }
    
    // Demonstrate cleanup functionality
    console.log('\nPerforming system cleanup...');
    await agent.cleanup();
    console.log('System cleanup completed');

  } catch (error) {
    console.error('Error in test integration:', error);
  }
}

async function dockerMonitoringExample() {
  console.log('\n\n=== Docker Monitoring Example ===');
  
  const agent = createSystemAgent({
    dockerMonitoring: {
      enabled: true,
      containerFilters: [] // Monitor all containers
    },
    monitoringInterval: 2000
  });

  try {
    await agent.initialize();
    
    const metrics = await agent.captureMetrics();
    
    if (metrics.docker && metrics.docker.length > 0) {
      console.log(`Found ${metrics.docker.length} Docker containers:`);
      
      metrics.docker.forEach(container => {
        console.log(`\n--- Container: ${container.name} ---`);
        console.log(`ID: ${container.id}`);
        console.log(`Image: ${container.image}`);
        console.log(`State: ${container.state}`);
        console.log(`CPU Usage: ${container.cpu.toFixed(1)}%`);
        console.log(`Memory Usage: ${container.memory.toFixed(1)}%`);
        console.log(`Ports: ${container.ports.join(', ') || 'None'}`);
        
        if (container.networkIO) {
          console.log(`Network I/O: ${container.networkIO.rx} RX, ${container.networkIO.tx} TX`);
        }
        
        if (container.blockIO) {
          console.log(`Block I/O: ${container.blockIO.read} reads, ${container.blockIO.write} writes`);
        }
      });
    } else {
      console.log('No Docker containers found or Docker not available');
    }

  } catch (error) {
    console.error('Error in Docker monitoring:', error);
  } finally {
    await agent.cleanup();
  }
}

// Advanced configuration example
async function advancedConfigurationExample() {
  console.log('\n\n=== Advanced Configuration Example ===');
  
  const advancedConfig: SystemAgentConfig = {
    monitoringInterval: 1000,
    cpuThreshold: 75,
    memoryThreshold: 80,
    diskThreshold: 85,
    processCountThreshold: 500,
    
    networkMonitoring: {
      enabled: true,
      interfaces: [], // Monitor all interfaces
      bandwidth: true
    },
    
    dockerMonitoring: {
      enabled: true,
      containerFilters: ['web', 'api', 'db'] // Monitor specific containers
    },
    
    fileSystemMonitoring: {
      enabled: true,
      watchPaths: ['./logs', './temp', './cache'],
      excludePatterns: [/node_modules/, /\.git/, /\.DS_Store/]
    },
    
    cleanup: {
      killZombieProcesses: true,
      cleanTempFiles: true,
      tempDirPatterns: [
        './temp/*',
        './logs/*.tmp',
        '/tmp/test-*',
        './cache/temp-*'
      ],
      processNamePatterns: [
        'zombie-*',
        'test-worker-*',
        'temp-process-*'
      ]
    },
    
    performanceBaseline: {
      captureBaseline: true,
      baselineDuration: 10000, // 10 seconds
      comparisonThreshold: 20   // 20% deviation
    }
  };

  const agent = createSystemAgent(advancedConfig);

  try {
    await agent.initialize();
    console.log('Advanced SystemAgent initialized with full configuration');
    
    // Demonstrate all features briefly
    await agent.startMonitoring();
    console.log('Monitoring started with advanced configuration...');
    
    // Let it run briefly
    await new Promise(resolve => setTimeout(resolve, 3000));
    
    await agent.stopMonitoring();
    
    const report = await agent.generateHealthReport();
    console.log(`\nAdvanced monitoring report: ${report.overall} status`);
    console.log(`File system changes tracked: ${agent.getFileSystemChanges().length}`);
    
    const baseline = agent.getPerformanceBaseline();
    if (baseline) {
      console.log(`Performance baseline captured over ${baseline.duration}ms`);
    }

  } catch (error) {
    console.error('Error in advanced configuration:', error);
  } finally {
    await agent.cleanup();
  }
}

// Main example runner
async function runAllExamples() {
  console.log('🚀 SystemAgent Examples Starting...\n');
  
  try {
    await basicSystemMonitoringExample();
    await continuousMonitoringExample();
    await healthReportExample();
    await testIntegrationExample();
    await dockerMonitoringExample();
    await advancedConfigurationExample();
    
    console.log('\n✅ All SystemAgent examples completed successfully!');
    
  } catch (error) {
    console.error('❌ Error running examples:', error);
    process.exit(1);
  }
}

// Export for use in other modules
export {
  basicSystemMonitoringExample,
  continuousMonitoringExample,
  healthReportExample,
  testIntegrationExample,
  dockerMonitoringExample,
  advancedConfigurationExample,
  runAllExamples
};

// Run examples if this file is executed directly
if (require.main === module) {
  runAllExamples();
}