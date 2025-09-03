/**
 * SystemAgent standalone test - tests core functionality without external dependencies
 */

// Mock all external dependencies
jest.mock('../../utils/logger', () => ({
  createLogger: () => ({
    info: jest.fn(),
    error: jest.fn(),
    warn: jest.fn(),
    debug: jest.fn(),
    log: jest.fn()
  }),
  LogLevel: {
    INFO: 'info',
    ERROR: 'error',
    WARN: 'warn',
    DEBUG: 'debug'
  }
}));

jest.mock('../../utils/screenshot', () => ({
  ScreenshotManager: jest.fn()
}));

jest.mock('chokidar', () => ({
  default: {
    watch: jest.fn(() => ({
      on: jest.fn().mockReturnThis(),
      close: jest.fn()
    }))
  }
}));

import * as os from 'os';
import { SystemAgent, createSystemAgent } from '../SystemAgent';
import { AgentType } from '../index';

describe('SystemAgent - Standalone Tests', () => {
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
        enabled: false,
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

  describe('Basic Properties', () => {
    it('should have correct agent type', () => {
      expect(agent.type).toBe(AgentType.SYSTEM);
    });

    it('should have correct agent name', () => {
      expect(agent.name).toBe('SystemAgent');
    });

    it('should be instance of SystemAgent', () => {
      expect(agent).toBeInstanceOf(SystemAgent);
    });
  });

  describe('Factory Function', () => {
    it('should create SystemAgent with default config', () => {
      const defaultAgent = createSystemAgent();
      expect(defaultAgent).toBeInstanceOf(SystemAgent);
      expect(defaultAgent.type).toBe(AgentType.SYSTEM);
      expect(defaultAgent.name).toBe('SystemAgent');
    });

    it('should create SystemAgent with custom config', () => {
      const customAgent = createSystemAgent({
        monitoringInterval: 5000,
        cpuThreshold: 90
      });
      expect(customAgent).toBeInstanceOf(SystemAgent);
    });

    it('should handle empty config object', () => {
      const emptyConfigAgent = createSystemAgent({});
      expect(emptyConfigAgent).toBeInstanceOf(SystemAgent);
    });

    it('should handle undefined config', () => {
      const undefinedConfigAgent = createSystemAgent(undefined);
      expect(undefinedConfigAgent).toBeInstanceOf(SystemAgent);
    });
  });

  describe('Initialization', () => {
    it('should initialize without throwing', async () => {
      await expect(agent.initialize()).resolves.not.toThrow();
    });

    it('should handle multiple initializations', async () => {
      await agent.initialize();
      await expect(agent.initialize()).resolves.not.toThrow();
    });
  });

  describe('Metrics Structure Validation', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should capture metrics with correct structure', async () => {
      const metrics = await agent.captureMetrics();
      
      // Basic structure validation
      expect(metrics).toBeDefined();
      expect(typeof metrics).toBe('object');
      
      // Required properties
      expect(metrics).toHaveProperty('timestamp');
      expect(metrics).toHaveProperty('cpu');
      expect(metrics).toHaveProperty('memory');
      expect(metrics).toHaveProperty('disk');
      expect(metrics).toHaveProperty('network');
      expect(metrics).toHaveProperty('processes');
      expect(metrics).toHaveProperty('system');

      // Timestamp should be a Date
      expect(metrics.timestamp).toBeInstanceOf(Date);
    });

    it('should have valid CPU metrics structure', async () => {
      const metrics = await agent.captureMetrics();
      
      expect(metrics.cpu).toHaveProperty('usage');
      expect(metrics.cpu).toHaveProperty('loadAverage');
      expect(metrics.cpu).toHaveProperty('cores');
      
      expect(typeof metrics.cpu.usage).toBe('number');
      expect(Array.isArray(metrics.cpu.loadAverage)).toBe(true);
      expect(typeof metrics.cpu.cores).toBe('number');
    });

    it('should have valid memory metrics structure', async () => {
      const metrics = await agent.captureMetrics();
      
      expect(metrics.memory).toHaveProperty('total');
      expect(metrics.memory).toHaveProperty('free');
      expect(metrics.memory).toHaveProperty('used');
      expect(metrics.memory).toHaveProperty('percentage');
      expect(metrics.memory).toHaveProperty('available');
      
      expect(typeof metrics.memory.total).toBe('number');
      expect(typeof metrics.memory.free).toBe('number');
      expect(typeof metrics.memory.used).toBe('number');
      expect(typeof metrics.memory.percentage).toBe('number');
      expect(typeof metrics.memory.available).toBe('number');
    });

    it('should have valid system info structure', async () => {
      const metrics = await agent.captureMetrics();
      
      expect(metrics.system).toHaveProperty('uptime');
      expect(metrics.system).toHaveProperty('platform');
      expect(metrics.system).toHaveProperty('arch');
      expect(metrics.system).toHaveProperty('hostname');
      
      expect(typeof metrics.system.uptime).toBe('number');
      expect(typeof metrics.system.platform).toBe('string');
      expect(typeof metrics.system.arch).toBe('string');
      expect(typeof metrics.system.hostname).toBe('string');
    });

    it('should have valid process list structure', async () => {
      const metrics = await agent.captureMetrics();
      
      expect(Array.isArray(metrics.processes)).toBe(true);
      
      // If processes exist, validate structure
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

  describe('Health Status', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should return valid health status', async () => {
      const health = await agent.getSystemHealth();
      expect(health).toBeDefined();
      expect(['healthy', 'warning', 'critical']).toContain(health);
    });

    it('should generate health report', async () => {
      const report = await agent.generateHealthReport();
      
      expect(report).toBeDefined();
      expect(report).toHaveProperty('timestamp');
      expect(report).toHaveProperty('overall');
      expect(report).toHaveProperty('issues');
      expect(report).toHaveProperty('metrics');
      expect(report).toHaveProperty('recommendations');
      expect(report).toHaveProperty('resourceLeaks');
      expect(report).toHaveProperty('performanceIssues');
      
      expect(report.timestamp).toBeInstanceOf(Date);
      expect(['healthy', 'warning', 'critical']).toContain(report.overall);
      expect(Array.isArray(report.issues)).toBe(true);
      expect(Array.isArray(report.recommendations)).toBe(true);
      expect(Array.isArray(report.resourceLeaks)).toBe(true);
      expect(Array.isArray(report.performanceIssues)).toBe(true);
    });
  });

  describe('Monitoring Lifecycle', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should start monitoring', async () => {
      await expect(agent.startMonitoring()).resolves.not.toThrow();
    });

    it('should stop monitoring', async () => {
      await agent.startMonitoring();
      await expect(agent.stopMonitoring()).resolves.not.toThrow();
    });

    it('should handle stop without start', async () => {
      await expect(agent.stopMonitoring()).resolves.not.toThrow();
    });

    it('should handle multiple starts', async () => {
      await agent.startMonitoring();
      await agent.startMonitoring(); // Should not throw
      await agent.stopMonitoring();
    });
  });

  describe('Data Collection', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should maintain metrics history', async () => {
      const initialHistory = agent.getMetricsHistory();
      expect(Array.isArray(initialHistory)).toBe(true);
    });

    it('should track file system changes', async () => {
      const changes = agent.getFileSystemChanges();
      expect(Array.isArray(changes)).toBe(true);
    });

    it('should handle performance baseline', async () => {
      const baseline = agent.getPerformanceBaseline();
      // May be undefined if not captured
      if (baseline) {
        expect(baseline).toHaveProperty('timestamp');
        expect(baseline).toHaveProperty('duration');
        expect(baseline).toHaveProperty('metrics');
      }
    });
  });

  describe('Cleanup and Error Handling', () => {
    it('should cleanup without initialization', async () => {
      const uninitializedAgent = createSystemAgent();
      await expect(uninitializedAgent.cleanup()).resolves.not.toThrow();
    });

    it('should handle errors in metrics capture gracefully', async () => {
      await agent.initialize();
      await expect(agent.captureMetrics()).resolves.not.toThrow();
    });

    it('should handle cleanup after operations', async () => {
      await agent.initialize();
      await agent.startMonitoring();
      await new Promise(resolve => setTimeout(resolve, 100));
      await agent.stopMonitoring();
      await expect(agent.cleanup()).resolves.not.toThrow();
    });
  });

  describe('Configuration Validation', () => {
    it('should handle various threshold configurations', () => {
      const configs = [
        { cpuThreshold: 50 },
        { memoryThreshold: 70 },
        { diskThreshold: 80 },
        { processCountThreshold: 100 },
        {
          cpuThreshold: 90,
          memoryThreshold: 85,
          diskThreshold: 95,
          processCountThreshold: 1000
        }
      ];

      configs.forEach(config => {
        const configuredAgent = createSystemAgent(config);
        expect(configuredAgent).toBeInstanceOf(SystemAgent);
      });
    });

    it('should handle monitoring interval configurations', () => {
      const intervals = [1000, 5000, 10000, 30000];
      
      intervals.forEach(interval => {
        const configuredAgent = createSystemAgent({
          monitoringInterval: interval
        });
        expect(configuredAgent).toBeInstanceOf(SystemAgent);
      });
    });
  });

  describe('Real System Integration', () => {
    beforeEach(async () => {
      await agent.initialize();
    });

    it('should capture real system metrics', async () => {
      const metrics = await agent.captureMetrics();
      
      // Validate against actual system
      expect(metrics.cpu.cores).toBe(os.cpus().length);
      expect(metrics.memory.total).toBe(os.totalmem());
      expect(metrics.system.platform).toBe(os.platform());
      expect(metrics.system.arch).toBe(os.arch());
      expect(metrics.system.hostname).toBe(os.hostname());
    });

    it('should have reasonable metric values', async () => {
      const metrics = await agent.captureMetrics();
      
      // CPU usage should be between 0 and 100
      expect(metrics.cpu.usage).toBeGreaterThanOrEqual(0);
      expect(metrics.cpu.usage).toBeLessThanOrEqual(100);
      
      // Memory percentage should be between 0 and 100
      expect(metrics.memory.percentage).toBeGreaterThanOrEqual(0);
      expect(metrics.memory.percentage).toBeLessThanOrEqual(100);
      
      // Used memory should be less than total
      expect(metrics.memory.used).toBeLessThanOrEqual(metrics.memory.total);
      
      // System uptime should be positive
      expect(metrics.system.uptime).toBeGreaterThan(0);
    });

    it('should detect at least current process', async () => {
      const metrics = await agent.captureMetrics();
      
      expect(metrics.processes.length).toBeGreaterThan(0);
      
      // Should find a process with current process ID
      const currentProcess = metrics.processes.find(p => p.pid === process.pid);
      if (currentProcess) {
        expect(currentProcess.name).toBeDefined();
        expect(currentProcess.cpu).toBeGreaterThanOrEqual(0);
        expect(currentProcess.memory).toBeGreaterThanOrEqual(0);
      }
    });
  });
});