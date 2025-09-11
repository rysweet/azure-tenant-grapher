/**
 * SystemAgent basic test suite - focuses on core functionality
 */

// Mock the problematic screenshot utility
jest.mock('../../utils/screenshot', () => ({
  ScreenshotManager: jest.fn().mockImplementation(() => ({
    capture: jest.fn(),
    compare: jest.fn(),
    cleanup: jest.fn()
  }))
}));

import { SystemAgent, createSystemAgent, SystemAgentConfig } from '../SystemAgent';
import { AgentType } from '../index';

describe('SystemAgent - Basic Tests', () => {
  let agent: SystemAgent;

  beforeEach(() => {
    agent = createSystemAgent({
      monitoringInterval: 1000,
      performanceBaseline: {
        captureBaseline: false,
        baselineDuration: 1000,
        comparisonThreshold: 20
      },
      fileSystemMonitoring: {
        enabled: false, // Disable for basic tests
        watchPaths: [],
        excludePatterns: []
      }
    });
  });

  afterEach(async () => {
    try {
      await agent.cleanup();
    } catch (error) {
      // Ignore cleanup errors in tests
    }
  });

  describe('Agent Properties', () => {
    it('should have correct type and name', () => {
      expect(agent.type).toBe(AgentType.SYSTEM);
      expect(agent.name).toBe('SystemAgent');
    });

    it('should be an instance of SystemAgent', () => {
      expect(agent).toBeInstanceOf(SystemAgent);
    });
  });

  describe('Factory Function', () => {
    it('should create SystemAgent with default config', () => {
      const defaultAgent = createSystemAgent();
      expect(defaultAgent).toBeInstanceOf(SystemAgent);
      expect(defaultAgent.type).toBe(AgentType.SYSTEM);
    });

    it('should create SystemAgent with custom config', () => {
      const customConfig: Partial<SystemAgentConfig> = {
        monitoringInterval: 10000,
        cpuThreshold: 90,
        memoryThreshold: 95
      };

      const customAgent = createSystemAgent(customConfig);
      expect(customAgent).toBeInstanceOf(SystemAgent);
    });
  });

  describe('Initialization', () => {
    it('should initialize without throwing', async () => {
      await expect(agent.initialize()).resolves.not.toThrow();
    });

    it('should handle initialization errors gracefully', async () => {
      // Test with potentially problematic configuration
      const problematicAgent = createSystemAgent({
        fileSystemMonitoring: {
          enabled: true,
          watchPaths: ['/nonexistent/path'],
          excludePatterns: []
        }
      });

      // Should not throw, but may log warnings
      await expect(problematicAgent.initialize()).resolves.not.toThrow();
      await problematicAgent.cleanup();
    });
  });

  describe('Metrics Capture', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should capture system metrics structure', async () => {
      const metrics = await agent.captureMetrics();

      expect(metrics).toBeDefined();
      expect(metrics).toHaveProperty('timestamp');
      expect(metrics.timestamp).toBeInstanceOf(Date);

      expect(metrics).toHaveProperty('cpu');
      expect(metrics.cpu).toHaveProperty('usage');
      expect(metrics.cpu).toHaveProperty('loadAverage');
      expect(metrics.cpu).toHaveProperty('cores');

      expect(metrics).toHaveProperty('memory');
      expect(metrics.memory).toHaveProperty('total');
      expect(metrics.memory).toHaveProperty('free');
      expect(metrics.memory).toHaveProperty('used');
      expect(metrics.memory).toHaveProperty('percentage');

      expect(metrics).toHaveProperty('system');
      expect(metrics.system).toHaveProperty('platform');
      expect(metrics.system).toHaveProperty('arch');
      expect(metrics.system).toHaveProperty('hostname');
    });

    it('should capture valid CPU metrics', async () => {
      const metrics = await agent.captureMetrics();

      expect(typeof metrics.cpu.usage).toBe('number');
      expect(metrics.cpu.usage).toBeGreaterThanOrEqual(0);
      expect(metrics.cpu.usage).toBeLessThanOrEqual(100);

      expect(Array.isArray(metrics.cpu.loadAverage)).toBe(true);
      expect(metrics.cpu.loadAverage).toHaveLength(3);

      expect(typeof metrics.cpu.cores).toBe('number');
      expect(metrics.cpu.cores).toBeGreaterThan(0);
    });

    it('should capture valid memory metrics', async () => {
      const metrics = await agent.captureMetrics();

      expect(typeof metrics.memory.total).toBe('number');
      expect(metrics.memory.total).toBeGreaterThan(0);

      expect(typeof metrics.memory.free).toBe('number');
      expect(metrics.memory.free).toBeGreaterThanOrEqual(0);

      expect(typeof metrics.memory.used).toBe('number');
      expect(metrics.memory.used).toBeGreaterThanOrEqual(0);

      expect(typeof metrics.memory.percentage).toBe('number');
      expect(metrics.memory.percentage).toBeGreaterThanOrEqual(0);
      expect(metrics.memory.percentage).toBeLessThanOrEqual(100);
    });

    it('should capture system information', async () => {
      const metrics = await agent.captureMetrics();

      expect(typeof metrics.system.platform).toBe('string');
      expect(metrics.system.platform.length).toBeGreaterThan(0);

      expect(typeof metrics.system.arch).toBe('string');
      expect(metrics.system.arch.length).toBeGreaterThan(0);

      expect(typeof metrics.system.hostname).toBe('string');
      expect(metrics.system.hostname.length).toBeGreaterThan(0);

      expect(typeof metrics.system.uptime).toBe('number');
      expect(metrics.system.uptime).toBeGreaterThan(0);
    });
  });

  describe('Health Status', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should return valid health status', async () => {
      const health = await agent.getSystemHealth();
      expect(['healthy', 'warning', 'critical']).toContain(health);
    });
  });

  describe('Monitoring Lifecycle', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should start and stop monitoring', async () => {
      await expect(agent.startMonitoring()).resolves.not.toThrow();
      await expect(agent.stopMonitoring()).resolves.not.toThrow();
    });

    it('should handle multiple start/stop calls', async () => {
      await agent.startMonitoring();
      await agent.startMonitoring(); // Should not throw
      await agent.stopMonitoring();
      await agent.stopMonitoring(); // Should not throw
    });

    it('should collect metrics history during monitoring', (done) => {
      let metricsReceived = 0;

      agent.on('metrics', () => {
        metricsReceived++;
        if (metricsReceived >= 2) {
          agent.stopMonitoring().then(() => {
            const history = agent.getMetricsHistory();
            expect(Array.isArray(history)).toBe(true);
            expect(history.length).toBeGreaterThan(0);
            done();
          });
        }
      });

      agent.startMonitoring();
    }, 15000);
  });

  describe('Health Report Generation', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should generate health report structure', async () => {
      const report = await agent.generateHealthReport();

      expect(report).toHaveProperty('timestamp');
      expect(report.timestamp).toBeInstanceOf(Date);

      expect(report).toHaveProperty('overall');
      expect(['healthy', 'warning', 'critical']).toContain(report.overall);

      expect(report).toHaveProperty('issues');
      expect(Array.isArray(report.issues)).toBe(true);

      expect(report).toHaveProperty('metrics');
      expect(report.metrics).toBeDefined();

      expect(report).toHaveProperty('recommendations');
      expect(Array.isArray(report.recommendations)).toBe(true);

      expect(report).toHaveProperty('resourceLeaks');
      expect(Array.isArray(report.resourceLeaks)).toBe(true);

      expect(report).toHaveProperty('performanceIssues');
      expect(Array.isArray(report.performanceIssues)).toBe(true);
    });

    it('should include current metrics in health report', async () => {
      const report = await agent.generateHealthReport();

      expect(report.metrics).toHaveProperty('cpu');
      expect(report.metrics).toHaveProperty('memory');
      expect(report.metrics).toHaveProperty('system');
    });
  });

  describe('Process Information', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should detect running processes', async () => {
      const metrics = await agent.captureMetrics();

      expect(Array.isArray(metrics.processes)).toBe(true);
      expect(metrics.processes.length).toBeGreaterThan(0);

      if (metrics.processes.length > 0) {
        const process = metrics.processes[0];
        expect(process).toHaveProperty('pid');
        expect(process).toHaveProperty('name');
        expect(process).toHaveProperty('cpu');
        expect(process).toHaveProperty('memory');
        expect(process).toHaveProperty('state');

        expect(typeof process.pid).toBe('number');
        expect(typeof process.name).toBe('string');
        expect(typeof process.cpu).toBe('number');
        expect(typeof process.memory).toBe('number');
        expect(typeof process.state).toBe('string');
      }
    });
  });

  describe('Error Handling', () => {
    it('should handle cleanup without initialization', async () => {
      const uninitializedAgent = createSystemAgent();
      await expect(uninitializedAgent.cleanup()).resolves.not.toThrow();
    });

    it('should handle metrics capture errors gracefully', async () => {
      await agent.initialize();
      await expect(agent.captureMetrics()).resolves.not.toThrow();
    });

    it('should handle monitoring errors gracefully', async () => {
      await agent.initialize();
      await agent.startMonitoring();

      // Let it run briefly
      await new Promise(resolve => setTimeout(resolve, 100));

      await expect(agent.stopMonitoring()).resolves.not.toThrow();
    });
  });

  describe('Data Structure Validation', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should return consistent data structure', async () => {
      const metrics1 = await agent.captureMetrics();
      const metrics2 = await agent.captureMetrics();

      // Both metrics should have the same structure
      expect(Object.keys(metrics1).sort()).toEqual(Object.keys(metrics2).sort());
      expect(Object.keys(metrics1.cpu).sort()).toEqual(Object.keys(metrics2.cpu).sort());
      expect(Object.keys(metrics1.memory).sort()).toEqual(Object.keys(metrics2.memory).sort());
      expect(Object.keys(metrics1.system).sort()).toEqual(Object.keys(metrics2.system).sort());
    });

    it('should maintain metrics history correctly', async () => {
      await agent.startMonitoring();

      // Wait for some metrics to be collected
      await new Promise(resolve => setTimeout(resolve, 2500));

      const history = agent.getMetricsHistory();
      expect(history.length).toBeGreaterThan(0);

      // Each entry should have timestamp
      history.forEach(metrics => {
        expect(metrics.timestamp).toBeInstanceOf(Date);
      });

      await agent.stopMonitoring();
    }, 10000);
  });

  describe('Configuration Handling', () => {
    it('should accept partial configuration', () => {
      const partialConfig = {
        monitoringInterval: 2000,
        cpuThreshold: 75
      };

      const configuredAgent = createSystemAgent(partialConfig);
      expect(configuredAgent).toBeInstanceOf(SystemAgent);
    });

    it('should handle empty configuration', () => {
      const emptyConfigAgent = createSystemAgent({});
      expect(emptyConfigAgent).toBeInstanceOf(SystemAgent);
    });

    it('should handle undefined configuration', () => {
      const undefinedConfigAgent = createSystemAgent(undefined);
      expect(undefinedConfigAgent).toBeInstanceOf(SystemAgent);
    });
  });
});
