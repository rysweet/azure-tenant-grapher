/**
 * SystemAgent - Comprehensive system resource monitoring and management agent
 * 
 * This agent provides complete system monitoring capabilities including:
 * - CPU usage, memory consumption, disk I/O monitoring
 * - Process tracking and resource usage analysis
 * - Resource leak detection and performance issue identification
 * - Network activity monitoring
 * - System health checks before/after tests
 * - Zombie process cleanup
 * - Temporary file management
 * - Docker container monitoring
 * - File system change tracking
 */

import * as os from 'os';
import * as fs from 'fs/promises';
import * as path from 'path';
import { spawn, exec, ChildProcess } from 'child_process';
import { EventEmitter } from 'events';
import { promisify } from 'util';
import * as si from 'systeminformation';
import pidusage from 'pidusage';
import { IAgent, AgentType } from './index';
import { TestLogger, createLogger, LogLevel } from '../utils/logger';

const execAsync = promisify(exec);

/**
 * System monitoring configuration
 */
export interface SystemAgentConfig {
  /** Monitoring interval in milliseconds */
  monitoringInterval?: number;
  /** CPU usage threshold for alerts (percentage) */
  cpuThreshold?: number;
  /** Memory usage threshold for alerts (percentage) */
  memoryThreshold?: number;
  /** Disk usage threshold for alerts (percentage) */
  diskThreshold?: number;
  /** Maximum process count threshold */
  processCountThreshold?: number;
  /** Network monitoring configuration */
  networkMonitoring?: {
    enabled: boolean;
    interfaces: string[];
    bandwidth: boolean;
  };
  /** Docker monitoring configuration */
  dockerMonitoring?: {
    enabled: boolean;
    containerFilters: string[];
  };
  /** File system monitoring */
  fileSystemMonitoring?: {
    enabled: boolean;
    watchPaths: string[];
    excludePatterns: RegExp[];
  };
  /** Cleanup configuration */
  cleanup?: {
    killZombieProcesses: boolean;
    cleanTempFiles: boolean;
    tempDirPatterns: string[];
    processNamePatterns: string[];
  };
  /** Performance baseline configuration */
  performanceBaseline?: {
    captureBaseline: boolean;
    baselineDuration: number;
    comparisonThreshold: number;
  };
}

/**
 * System metrics data structure
 */
export interface SystemMetrics {
  timestamp: Date;
  cpu: {
    usage: number;
    loadAverage: number[];
    cores: number;
    temperature?: number;
  };
  memory: {
    total: number;
    free: number;
    used: number;
    percentage: number;
    available: number;
  };
  disk: {
    usage: DiskUsage[];
    io?: DiskIO;
  };
  network: {
    interfaces: NetworkInterface[];
    connections?: number;
  };
  processes: ProcessInfo[];
  docker?: DockerInfo[];
  system: {
    uptime: number;
    platform: string;
    arch: string;
    hostname: string;
  };
}

/**
 * Disk usage information
 */
export interface DiskUsage {
  filesystem: string;
  size: number;
  used: number;
  available: number;
  percentage: number;
  mountpoint: string;
}

/**
 * Disk I/O information
 */
export interface DiskIO {
  reads: number;
  writes: number;
  readBytes: number;
  writeBytes: number;
}

/**
 * Network interface information
 */
export interface NetworkInterface {
  name: string;
  rx: number;
  tx: number;
  rxBytes: number;
  txBytes: number;
  speed?: number;
}

/**
 * Process information
 */
export interface ProcessInfo {
  pid: number;
  name: string;
  command: string;
  cpu: number;
  memory: number;
  state: string;
  ppid?: number;
  uid?: number;
  gid?: number;
  priority?: number;
  nice?: number;
  threads?: number;
  startTime?: Date;
  zombie?: boolean;
}

/**
 * Docker container information
 */
export interface DockerInfo {
  id: string;
  name: string;
  image: string;
  state: string;
  status: string;
  ports: string[];
  cpu: number;
  memory: number;
  networkIO?: {
    rx: number;
    tx: number;
  };
  blockIO?: {
    read: number;
    write: number;
  };
}

/**
 * System health report
 */
export interface SystemHealthReport {
  timestamp: Date;
  overall: 'healthy' | 'warning' | 'critical';
  issues: SystemIssue[];
  metrics: SystemMetrics;
  recommendations: string[];
  resourceLeaks: ResourceLeak[];
  performanceIssues: PerformanceIssue[];
}

/**
 * System issue information
 */
export interface SystemIssue {
  type: 'cpu' | 'memory' | 'disk' | 'process' | 'network' | 'docker';
  severity: 'low' | 'medium' | 'high' | 'critical';
  message: string;
  details: any;
  timestamp: Date;
}

/**
 * Resource leak information
 */
export interface ResourceLeak {
  type: 'memory' | 'file-descriptor' | 'process' | 'network';
  source: string;
  severity: 'low' | 'medium' | 'high';
  trend: number[];
  recommendation: string;
}

/**
 * Performance issue information
 */
export interface PerformanceIssue {
  type: 'cpu-spike' | 'memory-leak' | 'disk-thrashing' | 'network-congestion';
  component: string;
  impact: 'low' | 'medium' | 'high';
  duration: number;
  details: any;
}

/**
 * File system change information
 */
export interface FileSystemChange {
  path: string;
  type: 'created' | 'modified' | 'deleted';
  timestamp: Date;
  size?: number;
}

/**
 * Performance baseline data
 */
export interface PerformanceBaseline {
  timestamp: Date;
  duration: number;
  metrics: {
    avgCPU: number;
    avgMemory: number;
    avgDiskIO: number;
    avgNetworkIO: number;
    processCount: number;
  };
}

/**
 * Default configuration for SystemAgent
 */
const defaultSystemAgentConfig: SystemAgentConfig = {
  monitoringInterval: 5000, // 5 seconds
  cpuThreshold: 80,
  memoryThreshold: 85,
  diskThreshold: 90,
  processCountThreshold: 500,
  networkMonitoring: {
    enabled: true,
    interfaces: [],
    bandwidth: true,
  },
  dockerMonitoring: {
    enabled: true,
    containerFilters: [],
  },
  fileSystemMonitoring: {
    enabled: true,
    watchPaths: ['/tmp', './temp', './logs'],
    excludePatterns: [/node_modules/, /\.git/, /\.DS_Store/],
  },
  cleanup: {
    killZombieProcesses: true,
    cleanTempFiles: true,
    tempDirPatterns: ['/tmp/test-*', './temp/*', './logs/*.tmp'],
    processNamePatterns: ['zombie-*', 'test-*'],
  },
  performanceBaseline: {
    captureBaseline: true,
    baselineDuration: 30000, // 30 seconds
    comparisonThreshold: 20, // 20% deviation
  },
};

/**
 * SystemAgent implementation
 */
export class SystemAgent extends EventEmitter implements IAgent {
  public readonly name = 'SystemAgent';
  public readonly type = AgentType.SYSTEM;
  
  private config: SystemAgentConfig;
  private logger: TestLogger;
  private monitoringInterval?: NodeJS.Timeout;
  private isMonitoring = false;
  private metricsHistory: SystemMetrics[] = [];
  private fsWatchers: Map<string, any> = new Map();
  private fileSystemChanges: FileSystemChange[] = [];
  private performanceBaseline?: PerformanceBaseline;
  private initialMetrics?: SystemMetrics;
  private dockerAvailable = false;
  private readonly maxHistorySize = 1000;

  constructor(config: Partial<SystemAgentConfig> = {}) {
    super();
    this.config = { ...defaultSystemAgentConfig, ...config };
    this.logger = createLogger({ level: LogLevel.INFO });
  }

  /**
   * Initialize the SystemAgent
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing SystemAgent...');

    try {
      // Check if Docker is available
      await this.checkDockerAvailability();
      
      // Capture initial system state
      this.initialMetrics = await this.captureMetrics();
      this.logger.info('Initial system metrics captured');

      // Set up file system monitoring
      if (this.config.fileSystemMonitoring?.enabled) {
        await this.setupFileSystemMonitoring();
      }

      // Capture performance baseline if configured
      if (this.config.performanceBaseline?.captureBaseline) {
        await this.capturePerformanceBaseline();
      }

      this.logger.info('SystemAgent initialized successfully');
    } catch (error) {
      this.logger.error('Failed to initialize SystemAgent', { error });
      throw error;
    }
  }

  /**
   * Execute system monitoring for a scenario
   */
  async execute(scenario: any): Promise<SystemHealthReport> {
    this.logger.info('Starting system monitoring for scenario', { scenario: scenario?.name });

    try {
      // Start continuous monitoring
      await this.startMonitoring();

      // Wait for scenario completion or timeout
      const scenarioDuration = scenario?.timeout || 60000;
      await new Promise(resolve => setTimeout(resolve, scenarioDuration));

      // Generate health report
      const healthReport = await this.generateHealthReport();
      
      this.logger.info('System monitoring completed', { 
        overall: healthReport.overall,
        issues: healthReport.issues.length,
        leaks: healthReport.resourceLeaks.length
      });

      return healthReport;
    } catch (error) {
      this.logger.error('System monitoring execution failed', { error });
      throw error;
    }
  }

  /**
   * Cleanup resources and stop monitoring
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up SystemAgent...');

    try {
      // Stop monitoring
      await this.stopMonitoring();

      // Clean up file system watchers
      this.fsWatchers.forEach(watcher => {
        if (watcher.close) {
          watcher.close();
        }
      });
      this.fsWatchers.clear();

      // Perform system cleanup if configured
      if (this.config.cleanup?.killZombieProcesses) {
        await this.killZombieProcesses();
      }

      if (this.config.cleanup?.cleanTempFiles) {
        await this.cleanTempFiles();
      }

      this.logger.info('SystemAgent cleanup completed');
    } catch (error) {
      this.logger.error('SystemAgent cleanup failed', { error });
      throw error;
    }
  }

  /**
   * Start continuous system monitoring
   */
  async startMonitoring(): Promise<void> {
    if (this.isMonitoring) {
      this.logger.warn('Monitoring is already active');
      return;
    }

    this.isMonitoring = true;
    this.monitoringInterval = setInterval(async () => {
      try {
        const metrics = await this.captureMetrics();
        this.metricsHistory.push(metrics);
        
        // Keep history size manageable
        if (this.metricsHistory.length > this.maxHistorySize) {
          this.metricsHistory = this.metricsHistory.slice(-this.maxHistorySize);
        }

        // Emit metrics event
        this.emit('metrics', metrics);

        // Check for issues
        const issues = await this.analyzeMetrics(metrics);
        if (issues.length > 0) {
          this.emit('issues', issues);
        }

      } catch (error) {
        this.logger.error('Error during monitoring cycle', { error });
      }
    }, this.config.monitoringInterval);

    this.logger.info('System monitoring started');
  }

  /**
   * Stop continuous monitoring
   */
  async stopMonitoring(): Promise<void> {
    if (!this.isMonitoring) {
      return;
    }

    if (this.monitoringInterval) {
      clearInterval(this.monitoringInterval);
      this.monitoringInterval = undefined;
    }

    this.isMonitoring = false;
    this.logger.info('System monitoring stopped');
  }

  /**
   * Capture comprehensive system metrics
   */
  async captureMetrics(): Promise<SystemMetrics> {
    const timestamp = new Date();

    try {
      const [
        cpuData,
        memData,
        diskData,
        networkData,
        processData,
        systemData
      ] = await Promise.all([
        this.getCPUMetrics(),
        this.getMemoryMetrics(),
        this.getDiskMetrics(),
        this.getNetworkMetrics(),
        this.getProcessMetrics(),
        this.getSystemInfo()
      ]);

      const dockerData = this.dockerAvailable ? await this.getDockerMetrics() : undefined;

      const metrics: SystemMetrics = {
        timestamp,
        cpu: cpuData,
        memory: memData,
        disk: diskData,
        network: networkData,
        processes: processData,
        docker: dockerData,
        system: systemData
      };

      return metrics;
    } catch (error) {
      this.logger.error('Failed to capture system metrics', { error });
      throw error;
    }
  }

  /**
   * Get CPU metrics
   */
  private async getCPUMetrics(): Promise<SystemMetrics['cpu']> {
    try {
      const currentLoad = await si.currentLoad();
      const cpuTemperature = await si.cpuTemperature().catch(() => ({ main: undefined }));
      
      return {
        usage: currentLoad.currentLoad,
        loadAverage: os.loadavg(),
        cores: os.cpus().length,
        temperature: cpuTemperature.main
      };
    } catch (error) {
      this.logger.error('Failed to get CPU metrics', { error });
      return {
        usage: 0,
        loadAverage: [0, 0, 0],
        cores: os.cpus().length
      };
    }
  }

  /**
   * Get memory metrics
   */
  private async getMemoryMetrics(): Promise<SystemMetrics['memory']> {
    try {
      const mem = await si.mem();
      
      return {
        total: mem.total,
        free: mem.free,
        used: mem.used,
        percentage: (mem.used / mem.total) * 100,
        available: mem.available
      };
    } catch (error) {
      this.logger.error('Failed to get memory metrics', { error });
      const totalMem = os.totalmem();
      const freeMem = os.freemem();
      const usedMem = totalMem - freeMem;
      
      return {
        total: totalMem,
        free: freeMem,
        used: usedMem,
        percentage: (usedMem / totalMem) * 100,
        available: freeMem
      };
    }
  }

  /**
   * Get disk metrics
   */
  private async getDiskMetrics(): Promise<SystemMetrics['disk']> {
    try {
      const [fsSize, diskIO] = await Promise.all([
        si.fsSize(),
        si.disksIO().catch(() => undefined)
      ]);

      const usage: DiskUsage[] = fsSize.map(fs => ({
        filesystem: fs.fs,
        size: fs.size,
        used: fs.used,
        available: fs.available,
        percentage: fs.use,
        mountpoint: fs.mount
      }));

      const io: DiskIO | undefined = diskIO ? {
        reads: diskIO.rIO,
        writes: diskIO.wIO,
        readBytes: (diskIO.rIO_sec || 0) * 512, // Approximate
        writeBytes: (diskIO.wIO_sec || 0) * 512  // Approximate
      } : undefined;

      return { usage, io };
    } catch (error) {
      this.logger.error('Failed to get disk metrics', { error });
      return { usage: [] };
    }
  }

  /**
   * Get network metrics
   */
  private async getNetworkMetrics(): Promise<SystemMetrics['network']> {
    try {
      const [networkStats, networkConnections] = await Promise.all([
        si.networkStats(),
        si.networkConnections().catch(() => [])
      ]);

      const interfaces: NetworkInterface[] = networkStats.map(stat => ({
        name: stat.iface,
        rx: stat.rx_sec,
        tx: stat.tx_sec,
        rxBytes: stat.rx_bytes,
        txBytes: stat.tx_bytes,
        speed: undefined
      }));

      return {
        interfaces,
        connections: networkConnections.length
      };
    } catch (error) {
      this.logger.error('Failed to get network metrics', { error });
      return { interfaces: [] };
    }
  }

  /**
   * Get process metrics
   */
  private async getProcessMetrics(): Promise<ProcessInfo[]> {
    try {
      const processes = await si.processes();
      const processInfos: ProcessInfo[] = [];

      for (const proc of processes.list) {
        try {
          const stats = await pidusage(proc.pid).catch(() => null);
          
          processInfos.push({
            pid: proc.pid,
            name: proc.name,
            command: proc.command,
            cpu: stats ? stats.cpu : proc.cpu,
            memory: stats ? stats.memory : proc.memRss || 0,
            state: proc.state,
            ppid: proc.parentPid,
            uid: undefined,
            gid: undefined,
            priority: proc.priority,
            nice: proc.nice,
            threads: undefined,
            startTime: proc.started ? new Date(proc.started) : undefined,
            zombie: proc.state === 'zombie' || proc.state === 'Z'
          });
        } catch (procError) {
          // Skip processes we can't access
          continue;
        }
      }

      return processInfos;
    } catch (error) {
      this.logger.error('Failed to get process metrics', { error });
      return [];
    }
  }

  /**
   * Get system information
   */
  private async getSystemInfo(): Promise<SystemMetrics['system']> {
    try {
      const systemInfo = await si.system();
      
      return {
        uptime: os.uptime(),
        platform: os.platform(),
        arch: os.arch(),
        hostname: os.hostname()
      };
    } catch (error) {
      this.logger.error('Failed to get system info', { error });
      return {
        uptime: os.uptime(),
        platform: os.platform(),
        arch: os.arch(),
        hostname: os.hostname()
      };
    }
  }

  /**
   * Get Docker container metrics
   */
  private async getDockerMetrics(): Promise<DockerInfo[]> {
    if (!this.dockerAvailable) {
      return [];
    }

    try {
      const { stdout } = await execAsync(
        'docker ps --format "table {{.ID}}\\t{{.Names}}\\t{{.Image}}\\t{{.State}}\\t{{.Status}}\\t{{.Ports}}"'
      );

      const lines = stdout.trim().split('\n').slice(1); // Skip header
      const containers: DockerInfo[] = [];

      for (const line of lines) {
        const [id, name, image, state, status, ports] = line.split('\t');
        
        try {
          // Get container stats
          const { stdout: statsOutput } = await execAsync(
            `docker stats ${id} --no-stream --format "{{.CPUPerc}},{{.MemPerc}},{{.NetIO}},{{.BlockIO}}"`
          );

          const [cpuPerc, memPerc, netIO, blockIO] = statsOutput.trim().split(',');
          
          containers.push({
            id: id.substring(0, 12),
            name,
            image,
            state,
            status,
            ports: ports ? ports.split(',') : [],
            cpu: parseFloat(cpuPerc.replace('%', '')) || 0,
            memory: parseFloat(memPerc.replace('%', '')) || 0,
            networkIO: this.parseDockerNetworkIO(netIO),
            blockIO: this.parseDockerIO(blockIO)
          });
        } catch (statsError) {
          // Add container without stats
          containers.push({
            id: id.substring(0, 12),
            name,
            image,
            state,
            status,
            ports: ports ? ports.split(',') : [],
            cpu: 0,
            memory: 0
          });
        }
      }

      return containers;
    } catch (error) {
      this.logger.error('Failed to get Docker metrics', { error });
      return [];
    }
  }

  /**
   * Parse Docker network I/O stats
   */
  private parseDockerNetworkIO(ioString: string): { rx: number; tx: number } {
    if (!ioString || ioString === '--') {
      return { rx: 0, tx: 0 };
    }

    try {
      const [input, output] = ioString.split(' / ');
      const inputBytes = this.parseBytes(input);
      const outputBytes = this.parseBytes(output);
      
      return { rx: inputBytes, tx: outputBytes };
    } catch (error) {
      return { rx: 0, tx: 0 };
    }
  }

  /**
   * Parse Docker I/O stats
   */
  private parseDockerIO(ioString: string): { read: number; write: number } {
    if (!ioString || ioString === '--') {
      return { read: 0, write: 0 };
    }

    try {
      const [input, output] = ioString.split(' / ');
      const inputBytes = this.parseBytes(input);
      const outputBytes = this.parseBytes(output);
      
      return { read: inputBytes, write: outputBytes };
    } catch (error) {
      return { read: 0, write: 0 };
    }
  }

  /**
   * Parse byte string to number
   */
  private parseBytes(byteString: string): number {
    if (!byteString) return 0;
    
    const match = byteString.match(/^([\d.]+)\s*([KMGT]?B?)$/i);
    if (!match) return 0;
    
    const value = parseFloat(match[1]);
    const unit = match[2].toUpperCase();
    
    const multipliers: Record<string, number> = {
      'B': 1,
      'KB': 1024,
      'MB': 1024 * 1024,
      'GB': 1024 * 1024 * 1024,
      'TB': 1024 * 1024 * 1024 * 1024
    };
    
    return value * (multipliers[unit] || 1);
  }

  /**
   * Check Docker availability
   */
  private async checkDockerAvailability(): Promise<void> {
    try {
      await execAsync('docker --version');
      this.dockerAvailable = true;
      this.logger.info('Docker is available for monitoring');
    } catch (error) {
      this.dockerAvailable = false;
      this.logger.info('Docker is not available');
    }
  }

  /**
   * Set up file system monitoring
   */
  private async setupFileSystemMonitoring(): Promise<void> {
    if (!this.config.fileSystemMonitoring?.enabled) {
      return;
    }

    const { watchPaths, excludePatterns } = this.config.fileSystemMonitoring;

    for (const watchPath of watchPaths) {
      try {
        const absolutePath = path.resolve(watchPath);
        
        // Check if path exists
        await fs.access(absolutePath).catch(() => {
          // Create directory if it doesn't exist
          return fs.mkdir(absolutePath, { recursive: true });
        });

        // Set up watcher
        const chokidar = require('chokidar');
        const watcher = chokidar.watch(absolutePath, {
          ignored: (filePath: string) => 
            excludePatterns?.some(pattern => pattern.test(filePath)) || false,
          persistent: true,
          ignoreInitial: true
        });

        watcher
          .on('add', (filePath: string, stats: any) => {
            this.fileSystemChanges.push({
              path: filePath,
              type: 'created',
              timestamp: new Date(),
              size: stats?.size
            });
            this.emit('fileSystemChange', { path: filePath, type: 'created' });
          })
          .on('change', (filePath: string, stats: any) => {
            this.fileSystemChanges.push({
              path: filePath,
              type: 'modified',
              timestamp: new Date(),
              size: stats?.size
            });
            this.emit('fileSystemChange', { path: filePath, type: 'modified' });
          })
          .on('unlink', (filePath: string) => {
            this.fileSystemChanges.push({
              path: filePath,
              type: 'deleted',
              timestamp: new Date()
            });
            this.emit('fileSystemChange', { path: filePath, type: 'deleted' });
          });

        this.fsWatchers.set(absolutePath, watcher);
        this.logger.info(`File system monitoring set up for: ${absolutePath}`);
      } catch (error) {
        this.logger.error(`Failed to set up monitoring for ${watchPath}`, { error });
      }
    }
  }

  /**
   * Capture performance baseline
   */
  private async capturePerformanceBaseline(): Promise<void> {
    const startTime = Date.now();
    const duration = this.config.performanceBaseline?.baselineDuration || 30000;
    const samples: SystemMetrics[] = [];

    this.logger.info(`Capturing performance baseline for ${duration}ms...`);

    const interval = setInterval(async () => {
      try {
        const metrics = await this.captureMetrics();
        samples.push(metrics);
      } catch (error) {
        this.logger.error('Error capturing baseline sample', { error });
      }
    }, 1000);

    setTimeout(() => {
      clearInterval(interval);
      
      if (samples.length > 0) {
        const avgCPU = samples.reduce((sum, s) => sum + s.cpu.usage, 0) / samples.length;
        const avgMemory = samples.reduce((sum, s) => sum + s.memory.percentage, 0) / samples.length;
        const avgDiskIO = samples.reduce((sum, s) => sum + (s.disk.io?.reads || 0), 0) / samples.length;
        const avgNetworkIO = samples.reduce((sum, s) => 
          sum + s.network.interfaces.reduce((netSum, iface) => netSum + iface.rx + iface.tx, 0), 0
        ) / samples.length;
        const avgProcessCount = samples.reduce((sum, s) => sum + s.processes.length, 0) / samples.length;

        this.performanceBaseline = {
          timestamp: new Date(),
          duration,
          metrics: {
            avgCPU,
            avgMemory,
            avgDiskIO,
            avgNetworkIO,
            processCount: avgProcessCount
          }
        };

        this.logger.info('Performance baseline captured', { baseline: this.performanceBaseline.metrics });
      }
    }, duration);
  }

  /**
   * Analyze metrics for issues
   */
  private async analyzeMetrics(metrics: SystemMetrics): Promise<SystemIssue[]> {
    const issues: SystemIssue[] = [];

    // CPU usage check
    if (metrics.cpu.usage > (this.config.cpuThreshold || 80)) {
      issues.push({
        type: 'cpu',
        severity: metrics.cpu.usage > 95 ? 'critical' : 'high',
        message: `High CPU usage: ${metrics.cpu.usage.toFixed(1)}%`,
        details: { usage: metrics.cpu.usage, loadAverage: metrics.cpu.loadAverage },
        timestamp: metrics.timestamp
      });
    }

    // Memory usage check
    if (metrics.memory.percentage > (this.config.memoryThreshold || 85)) {
      issues.push({
        type: 'memory',
        severity: metrics.memory.percentage > 95 ? 'critical' : 'high',
        message: `High memory usage: ${metrics.memory.percentage.toFixed(1)}%`,
        details: { 
          percentage: metrics.memory.percentage,
          used: metrics.memory.used,
          total: metrics.memory.total
        },
        timestamp: metrics.timestamp
      });
    }

    // Disk usage check
    for (const disk of metrics.disk.usage) {
      if (disk.percentage > (this.config.diskThreshold || 90)) {
        issues.push({
          type: 'disk',
          severity: disk.percentage > 98 ? 'critical' : 'high',
          message: `High disk usage on ${disk.filesystem}: ${disk.percentage.toFixed(1)}%`,
          details: disk,
          timestamp: metrics.timestamp
        });
      }
    }

    // Process count check
    if (metrics.processes.length > (this.config.processCountThreshold || 500)) {
      issues.push({
        type: 'process',
        severity: 'medium',
        message: `High process count: ${metrics.processes.length}`,
        details: { count: metrics.processes.length },
        timestamp: metrics.timestamp
      });
    }

    // Zombie process check
    const zombieProcesses = metrics.processes.filter(p => p.zombie);
    if (zombieProcesses.length > 0) {
      issues.push({
        type: 'process',
        severity: 'medium',
        message: `Found ${zombieProcesses.length} zombie processes`,
        details: { zombies: zombieProcesses.map(p => ({ pid: p.pid, name: p.name })) },
        timestamp: metrics.timestamp
      });
    }

    return issues;
  }

  /**
   * Generate comprehensive health report
   */
  async generateHealthReport(): Promise<SystemHealthReport> {
    const currentMetrics = await this.captureMetrics();
    const issues = await this.analyzeMetrics(currentMetrics);
    const resourceLeaks = await this.detectResourceLeaks();
    const performanceIssues = await this.detectPerformanceIssues();

    // Determine overall health
    let overall: 'healthy' | 'warning' | 'critical' = 'healthy';
    
    if (issues.some(i => i.severity === 'critical') || resourceLeaks.some(l => l.severity === 'high')) {
      overall = 'critical';
    } else if (issues.length > 0 || resourceLeaks.length > 0 || performanceIssues.length > 0) {
      overall = 'warning';
    }

    // Generate recommendations
    const recommendations = this.generateRecommendations(issues, resourceLeaks, performanceIssues);

    return {
      timestamp: new Date(),
      overall,
      issues,
      metrics: currentMetrics,
      recommendations,
      resourceLeaks,
      performanceIssues
    };
  }

  /**
   * Detect resource leaks
   */
  private async detectResourceLeaks(): Promise<ResourceLeak[]> {
    const leaks: ResourceLeak[] = [];

    if (this.metricsHistory.length < 10) {
      return leaks; // Need more data
    }

    const recentMetrics = this.metricsHistory.slice(-10);
    
    // Memory leak detection
    const memoryTrend = recentMetrics.map(m => m.memory.percentage);
    if (this.isIncreasingTrend(memoryTrend, 5)) {
      leaks.push({
        type: 'memory',
        source: 'system',
        severity: 'medium',
        trend: memoryTrend,
        recommendation: 'Investigate processes with increasing memory usage'
      });
    }

    // Process leak detection
    const processCounts = recentMetrics.map(m => m.processes.length);
    if (this.isIncreasingTrend(processCounts, 10)) {
      leaks.push({
        type: 'process',
        source: 'system',
        severity: 'medium',
        trend: processCounts,
        recommendation: 'Check for processes that are not being properly terminated'
      });
    }

    return leaks;
  }

  /**
   * Detect performance issues
   */
  private async detectPerformanceIssues(): Promise<PerformanceIssue[]> {
    const issues: PerformanceIssue[] = [];

    if (this.metricsHistory.length < 5) {
      return issues;
    }

    const recentMetrics = this.metricsHistory.slice(-5);

    // CPU spike detection
    const avgCPU = recentMetrics.reduce((sum, m) => sum + m.cpu.usage, 0) / recentMetrics.length;
    if (avgCPU > 90) {
      issues.push({
        type: 'cpu-spike',
        component: 'system',
        impact: 'high',
        duration: recentMetrics.length * (this.config.monitoringInterval || 5000),
        details: { averageUsage: avgCPU, samples: recentMetrics.map(m => m.cpu.usage) }
      });
    }

    // Disk thrashing detection
    const diskIOSamples = recentMetrics
      .map(m => m.disk.io?.reads || 0)
      .filter(io => io > 0);
    
    if (diskIOSamples.length > 0) {
      const avgDiskIO = diskIOSamples.reduce((sum, io) => sum + io, 0) / diskIOSamples.length;
      if (avgDiskIO > 1000) { // Threshold for high disk activity
        issues.push({
          type: 'disk-thrashing',
          component: 'storage',
          impact: 'medium',
          duration: recentMetrics.length * (this.config.monitoringInterval || 5000),
          details: { averageReads: avgDiskIO, samples: diskIOSamples }
        });
      }
    }

    return issues;
  }

  /**
   * Check if array shows increasing trend
   */
  private isIncreasingTrend(values: number[], threshold: number): boolean {
    if (values.length < 3) return false;
    
    let increases = 0;
    for (let i = 1; i < values.length; i++) {
      if (values[i] > values[i - 1]) {
        increases++;
      }
    }
    
    return (increases / (values.length - 1)) * 100 > threshold;
  }

  /**
   * Generate recommendations based on issues
   */
  private generateRecommendations(
    issues: SystemIssue[],
    leaks: ResourceLeak[],
    performanceIssues: PerformanceIssue[]
  ): string[] {
    const recommendations: string[] = [];

    // CPU recommendations
    if (issues.some(i => i.type === 'cpu')) {
      recommendations.push('Consider optimizing CPU-intensive operations or reducing concurrent processes');
    }

    // Memory recommendations
    if (issues.some(i => i.type === 'memory') || leaks.some(l => l.type === 'memory')) {
      recommendations.push('Monitor application memory usage and implement garbage collection optimizations');
    }

    // Disk recommendations
    if (issues.some(i => i.type === 'disk')) {
      recommendations.push('Clean up temporary files and consider increasing available disk space');
    }

    // Process recommendations
    if (issues.some(i => i.type === 'process' && i.message.includes('zombie'))) {
      recommendations.push('Implement proper process cleanup to prevent zombie processes');
    }

    // Performance recommendations
    if (performanceIssues.some(p => p.type === 'cpu-spike')) {
      recommendations.push('Investigate and optimize high CPU usage patterns during test execution');
    }

    if (performanceIssues.some(p => p.type === 'disk-thrashing')) {
      recommendations.push('Reduce disk I/O operations or implement caching mechanisms');
    }

    return recommendations;
  }

  /**
   * Kill zombie processes
   */
  private async killZombieProcesses(): Promise<void> {
    try {
      const currentMetrics = await this.captureMetrics();
      const zombies = currentMetrics.processes.filter(p => p.zombie);

      for (const zombie of zombies) {
        try {
          process.kill(zombie.pid, 'SIGKILL');
          this.logger.info(`Killed zombie process: ${zombie.name} (PID: ${zombie.pid})`);
        } catch (error) {
          this.logger.warn(`Failed to kill zombie process ${zombie.pid}`, { error });
        }
      }

      // Also kill processes matching name patterns
      const { processNamePatterns } = this.config.cleanup || {};
      if (processNamePatterns) {
        const processesToKill = currentMetrics.processes.filter(p => 
          processNamePatterns.some(pattern => p.name.match(pattern))
        );

        for (const proc of processesToKill) {
          try {
            process.kill(proc.pid, 'SIGTERM');
            this.logger.info(`Terminated process: ${proc.name} (PID: ${proc.pid})`);
          } catch (error) {
            this.logger.warn(`Failed to terminate process ${proc.pid}`, { error });
          }
        }
      }

    } catch (error) {
      this.logger.error('Failed to kill zombie processes', { error });
    }
  }

  /**
   * Clean temporary files
   */
  private async cleanTempFiles(): Promise<void> {
    try {
      const { tempDirPatterns } = this.config.cleanup || {};
      if (!tempDirPatterns) {
        return;
      }

      for (const pattern of tempDirPatterns) {
        try {
          // Use glob to find matching files/directories
          const glob = require('glob');
          const matches = glob.sync(pattern);

          for (const match of matches) {
            try {
              const stat = await fs.stat(match);
              if (stat.isDirectory()) {
                await fs.rmdir(match, { recursive: true });
                this.logger.info(`Removed temporary directory: ${match}`);
              } else {
                await fs.unlink(match);
                this.logger.info(`Removed temporary file: ${match}`);
              }
            } catch (error) {
              this.logger.warn(`Failed to remove ${match}`, { error });
            }
          }
        } catch (error) {
          this.logger.warn(`Failed to process pattern ${pattern}`, { error });
        }
      }
    } catch (error) {
      this.logger.error('Failed to clean temporary files', { error });
    }
  }

  /**
   * Get current system health status
   */
  async getSystemHealth(): Promise<'healthy' | 'warning' | 'critical'> {
    const metrics = await this.captureMetrics();
    const issues = await this.analyzeMetrics(metrics);
    
    if (issues.some(i => i.severity === 'critical')) {
      return 'critical';
    } else if (issues.length > 0) {
      return 'warning';
    } else {
      return 'healthy';
    }
  }

  /**
   * Get metrics history
   */
  getMetricsHistory(): SystemMetrics[] {
    return [...this.metricsHistory];
  }

  /**
   * Get file system changes
   */
  getFileSystemChanges(): FileSystemChange[] {
    return [...this.fileSystemChanges];
  }

  /**
   * Get performance baseline
   */
  getPerformanceBaseline(): PerformanceBaseline | undefined {
    return this.performanceBaseline;
  }
}

/**
 * Factory function to create a SystemAgent
 */
export function createSystemAgent(config?: Partial<SystemAgentConfig>): SystemAgent {
  return new SystemAgent(config);
}

export { defaultSystemAgentConfig };