/**
 * SystemAgent test suite
 */

import { SystemAgent, createSystemAgent, SystemAgentConfig } from '../SystemAgent';
import { AgentType } from '../index';

describe('SystemAgent', () => {
  let agent: SystemAgent;

  beforeEach(() => {
    agent = createSystemAgent();
  });

  afterEach(async () => {
    await agent.cleanup();
  });

  describe('Initialization', () => {
    it('should have correct type and name', () => {
      expect(agent.type).toBe(AgentType.SYSTEM);
      expect(agent.name).toBe('SystemAgent');
    });

    it('should initialize successfully', async () => {
      await expect(agent.initialize()).resolves.not.toThrow();
    });

    it('should accept custom configuration', () => {
      const customConfig: Partial<SystemAgentConfig> = {
        monitoringInterval: 10000,
        cpuThreshold: 90,
        memoryThreshold: 95
      };

      const customAgent = createSystemAgent(customConfig);
      expect(customAgent).toBeInstanceOf(SystemAgent);
    });
  });

  describe('Metrics Capture', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should capture system metrics', async () => {
      const metrics = await agent.captureMetrics();
      
      expect(metrics).toHaveProperty('timestamp');
      expect(metrics).toHaveProperty('cpu');
      expect(metrics).toHaveProperty('memory');
      expect(metrics).toHaveProperty('disk');
      expect(metrics).toHaveProperty('network');
      expect(metrics).toHaveProperty('processes');
      expect(metrics).toHaveProperty('system');

      // Validate CPU metrics
      expect(metrics.cpu).toHaveProperty('usage');
      expect(metrics.cpu).toHaveProperty('loadAverage');
      expect(metrics.cpu).toHaveProperty('cores');
      expect(typeof metrics.cpu.usage).toBe('number');
      expect(Array.isArray(metrics.cpu.loadAverage)).toBe(true);

      // Validate memory metrics
      expect(metrics.memory).toHaveProperty('total');
      expect(metrics.memory).toHaveProperty('free');
      expect(metrics.memory).toHaveProperty('used');
      expect(metrics.memory).toHaveProperty('percentage');

      // Validate system info
      expect(metrics.system).toHaveProperty('platform');
      expect(metrics.system).toHaveProperty('arch');
      expect(metrics.system).toHaveProperty('hostname');
    });

    it('should get system health status', async () => {
      const health = await agent.getSystemHealth();
      expect(['healthy', 'warning', 'critical']).toContain(health);
    });
  });

  describe('Monitoring', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should start and stop monitoring', async () => {
      await expect(agent.startMonitoring()).resolves.not.toThrow();
      await expect(agent.stopMonitoring()).resolves.not.toThrow();
    });

    it('should emit metrics events during monitoring', (done) => {
      let eventReceived = false;
      
      agent.on('metrics', (metrics) => {
        if (!eventReceived) {
          eventReceived = true;
          expect(metrics).toHaveProperty('timestamp');
          expect(metrics).toHaveProperty('cpu');
          agent.stopMonitoring().then(() => done());
        }
      });

      agent.startMonitoring();
    }, 10000);
  });

  describe('Health Report Generation', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should generate comprehensive health report', async () => {
      const report = await agent.generateHealthReport();
      
      expect(report).toHaveProperty('timestamp');
      expect(report).toHaveProperty('overall');
      expect(report).toHaveProperty('issues');
      expect(report).toHaveProperty('metrics');
      expect(report).toHaveProperty('recommendations');
      expect(report).toHaveProperty('resourceLeaks');
      expect(report).toHaveProperty('performanceIssues');

      expect(['healthy', 'warning', 'critical']).toContain(report.overall);
      expect(Array.isArray(report.issues)).toBe(true);
      expect(Array.isArray(report.recommendations)).toBe(true);
      expect(Array.isArray(report.resourceLeaks)).toBe(true);
      expect(Array.isArray(report.performanceIssues)).toBe(true);
    });
  });

  describe('Process Management', () => {
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
      }
    });

    it('should handle process metrics errors gracefully', async () => {
      // This test ensures the agent doesn't crash when process info is unavailable
      await expect(agent.captureMetrics()).resolves.not.toThrow();
    });
  });

  describe('File System Monitoring', () => {
    beforeEach(async () => {
      const config: Partial<SystemAgentConfig> = {
        fileSystemMonitoring: {
          enabled: true,
          watchPaths: ['./temp-test'],
          excludePatterns: [/node_modules/]
        }
      };
      agent = createSystemAgent(config);
      await agent.initialize();
    });

    it('should track file system changes', async () => {
      const changes = agent.getFileSystemChanges();
      expect(Array.isArray(changes)).toBe(true);
    });
  });

  describe('Resource Cleanup', () => {
    it('should cleanup resources without errors', async () => {
      await agent.initialize();
      await agent.startMonitoring();
      await expect(agent.cleanup()).resolves.not.toThrow();
    });

    it('should handle cleanup when not initialized', async () => {
      await expect(agent.cleanup()).resolves.not.toThrow();
    });
  });

  describe('Docker Monitoring', () => {
    beforeEach(async () => {
      const config: Partial<SystemAgentConfig> = {
        dockerMonitoring: {
          enabled: true,
          containerFilters: []
        }
      };
      agent = createSystemAgent(config);
      await agent.initialize();
    });

    it('should handle Docker monitoring gracefully when Docker is unavailable', async () => {
      const metrics = await agent.captureMetrics();
      
      // Should not crash even if Docker is not available
      expect(metrics.docker).toBeDefined();
      if (metrics.docker) {
        expect(Array.isArray(metrics.docker)).toBe(true);
      }
    });
  });

  describe('Performance Analysis', () => {
    beforeEach(async () => {
      const config: Partial<SystemAgentConfig> = {
        performanceBaseline: {
          captureBaseline: false, // Disable for faster tests
          baselineDuration: 1000,
          comparisonThreshold: 20
        }
      };
      agent = createSystemAgent(config);
      await agent.initialize();
    });

    it('should analyze metrics for issues', async () => {
      // Get some metrics first
      await agent.captureMetrics();
      
      const report = await agent.generateHealthReport();
      expect(report.issues).toBeDefined();
      expect(Array.isArray(report.issues)).toBe(true);
    });

    it('should provide performance history', async () => {
      await agent.startMonitoring();
      
      // Wait for some metrics to be collected
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      const history = agent.getMetricsHistory();
      expect(Array.isArray(history)).toBe(true);
      
      await agent.stopMonitoring();
    });
  });

  describe('Error Handling', () => {
    it('should handle initialization errors gracefully', async () => {
      // Test with invalid configuration
      const agent = createSystemAgent({
        fileSystemMonitoring: {
          enabled: true,
          watchPaths: ['/nonexistent/path/that/should/not/exist'],
          excludePatterns: []
        }
      });

      // Should not throw but may log warnings
      await expect(agent.initialize()).resolves.not.toThrow();
      await agent.cleanup();
    });

    it('should handle metrics capture errors gracefully', async () => {
      await agent.initialize();
      
      // Even if some metrics fail to capture, it should not crash
      await expect(agent.captureMetrics()).resolves.not.toThrow();
    });

    it('should handle execution without scenario', async () => {
      await agent.initialize();
      
      // Should handle undefined scenario gracefully
      await expect(agent.execute(undefined)).rejects.toThrow();
    });
  });
});