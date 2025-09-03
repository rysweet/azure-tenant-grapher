/**
 * WebSocketAgent - Comprehensive WebSocket testing agent using Socket.IO Client
 * 
 * This agent provides complete automation capabilities for WebSocket testing
 * including connection lifecycle management, message sending/receiving,
 * event handling, performance measurement, reconnection logic, and
 * comprehensive error handling.
 */

import { io, Socket } from 'socket.io-client';
import { EventEmitter } from 'events';
import { IAgent, AgentType } from './index';
import { 
  TestStep, 
  TestStatus, 
  StepResult, 
  TestScenario 
} from '../models/TestModels';
import { TestLogger, createLogger, LogLevel } from '../utils/logger';

/**
 * WebSocket connection states
 */
export enum ConnectionState {
  DISCONNECTED = 'disconnected',
  CONNECTING = 'connecting',
  CONNECTED = 'connected',
  RECONNECTING = 'reconnecting',
  ERROR = 'error'
}

/**
 * WebSocket message types
 */
export interface WebSocketMessage {
  id: string;
  event: string;
  data: any;
  timestamp: Date;
  direction: 'sent' | 'received';
  ack?: boolean;
  namespace?: string;
}

/**
 * Connection performance metrics
 */
export interface ConnectionMetrics {
  connectionId: string;
  connectTime: number;
  totalMessages: number;
  messagesSent: number;
  messagesReceived: number;
  reconnectCount: number;
  lastLatency?: number;
  averageLatency?: number;
  uptime: number;
  timestamp: Date;
}

/**
 * Latency measurement
 */
export interface LatencyMeasurement {
  messageId: string;
  event: string;
  latency: number;
  timestamp: Date;
}

/**
 * Event listener configuration
 */
export interface EventListener {
  event: string;
  handler: (data: any) => void | Promise<void>;
  once?: boolean;
  enabled: boolean;
}

/**
 * Reconnection configuration
 */
export interface ReconnectionConfig {
  enabled: boolean;
  maxAttempts: number;
  delay: number;
  exponentialBackoff: boolean;
  maxBackoffDelay: number;
  randomizationFactor: number;
}

/**
 * Authentication configuration for WebSocket
 */
export interface WebSocketAuth {
  type: 'token' | 'query' | 'header' | 'custom';
  token?: string;
  queryParam?: string;
  headerName?: string;
  customAuth?: Record<string, any>;
}

/**
 * Configuration options for the WebSocketAgent
 */
export interface WebSocketAgentConfig {
  /** Server URL (ws:// or wss://) */
  serverURL?: string;
  /** Namespace to connect to */
  namespace?: string;
  /** Connection timeout in milliseconds */
  connectionTimeout?: number;
  /** Socket.IO options */
  socketOptions?: {
    transports?: ('websocket' | 'polling')[];
    upgrade?: boolean;
    rememberUpgrade?: boolean;
    timeout?: number;
    forceNew?: boolean;
    multiplex?: boolean;
  };
  /** Authentication configuration */
  auth?: WebSocketAuth;
  /** Reconnection configuration */
  reconnection?: ReconnectionConfig;
  /** Event listeners */
  eventListeners?: EventListener[];
  /** Performance measurement configuration */
  performance?: {
    enabled: boolean;
    measureLatency: boolean;
    pingInterval?: number;
    maxLatencyHistory: number;
  };
  /** Message validation */
  messageValidation?: {
    enabled: boolean;
    schemas?: Record<string, any>; // Event -> JSON Schema
    strictMode?: boolean;
  };
  /** Logging configuration */
  logConfig?: {
    logConnections: boolean;
    logMessages: boolean;
    logEvents: boolean;
    logLevel: LogLevel;
    maskSensitiveData: boolean;
    sensitiveEvents: string[];
  };
}

/**
 * Connection information
 */
export interface ConnectionInfo {
  id: string;
  url: string;
  namespace?: string;
  state: ConnectionState;
  connectTime?: Date;
  disconnectTime?: Date;
  error?: string;
  reconnectCount: number;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<WebSocketAgentConfig> = {
  serverURL: '',
  namespace: '/',
  connectionTimeout: 10000,
  socketOptions: {
    transports: ['websocket', 'polling'],
    upgrade: true,
    rememberUpgrade: true,
    timeout: 20000,
    forceNew: false,
    multiplex: true
  },
  auth: { type: 'token' },
  reconnection: {
    enabled: true,
    maxAttempts: 5,
    delay: 1000,
    exponentialBackoff: true,
    maxBackoffDelay: 10000,
    randomizationFactor: 0.5
  },
  eventListeners: [],
  performance: {
    enabled: true,
    measureLatency: true,
    pingInterval: 5000,
    maxLatencyHistory: 100
  },
  messageValidation: {
    enabled: false,
    schemas: {},
    strictMode: false
  },
  logConfig: {
    logConnections: true,
    logMessages: true,
    logEvents: true,
    logLevel: LogLevel.DEBUG,
    maskSensitiveData: true,
    sensitiveEvents: ['auth', 'login', 'authentication']
  }
};

/**
 * Comprehensive WebSocket testing agent
 */
export class WebSocketAgent extends EventEmitter implements IAgent {
  public readonly name = 'WebSocketAgent';
  public readonly type = AgentType.WEBSOCKET;
  
  private config: Required<WebSocketAgentConfig>;
  private logger: TestLogger;
  private isInitialized = false;
  private currentScenarioId?: string;
  private socket?: Socket;
  private connectionInfo?: ConnectionInfo;
  private messageHistory: WebSocketMessage[] = [];
  private latencyHistory: LatencyMeasurement[] = [];
  private connectionMetrics?: ConnectionMetrics;
  private pendingMessages: Map<string, { timestamp: Date; event: string }> = new Map();
  private eventHandlers: Map<string, Function> = new Map();
  private pingInterval?: NodeJS.Timeout;
  private connectionPromise?: Promise<void>;
  
  constructor(config: WebSocketAgentConfig = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = createLogger({
      level: this.config.logConfig.logLevel,
      logDir: './logs/websocket-agent'
    });
    
    this.setupEventListeners();
  }

  /**
   * Initialize the agent
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing WebSocketAgent', { 
      serverURL: this.config.serverURL,
      namespace: this.config.namespace,
      authType: this.config.auth.type
    });
    
    try {
      // Validate server URL
      if (this.config.serverURL) {
        this.validateServerURL(this.config.serverURL);
      }
      
      // Setup default event listeners
      this.setupDefaultEventListeners();
      
      this.isInitialized = true;
      this.logger.info('WebSocketAgent initialized successfully');
      this.emit('initialized');
      
    } catch (error: any) {
      this.logger.error('Failed to initialize WebSocketAgent', { error: error?.message });
      throw new Error(`Failed to initialize WebSocketAgent: ${error?.message}`);
    }
  }

  /**
   * Execute a test scenario
   */
  async execute(scenario: TestScenario): Promise<any> {
    if (!this.isInitialized) {
      throw new Error('Agent not initialized. Call initialize() first.');
    }

    this.currentScenarioId = scenario.id;
    this.logger.setContext({ scenarioId: scenario.id, component: 'WebSocketAgent' });
    this.logger.scenarioStart(scenario.id, scenario.name);

    const startTime = Date.now();
    let status = TestStatus.PASSED;
    let error: string | undefined;
    
    try {
      // Set environment variables if specified in scenario
      if (scenario.environment) {
        this.applyEnvironmentConfig(scenario.environment);
      }
      
      // Execute scenario steps
      const stepResults: StepResult[] = [];
      
      for (let i = 0; i < scenario.steps.length; i++) {
        const step = scenario.steps[i];
        const stepResult = await this.executeStep(step, i);
        stepResults.push(stepResult);
        
        if (stepResult.status === TestStatus.FAILED || stepResult.status === TestStatus.ERROR) {
          status = stepResult.status;
          error = stepResult.error;
          break;
        }
      }
      
      return {
        scenarioId: scenario.id,
        status,
        duration: Date.now() - startTime,
        startTime: new Date(startTime),
        endTime: new Date(),
        error,
        stepResults,
        logs: this.getScenarioLogs(),
        messageHistory: [...this.messageHistory],
        connectionInfo: this.connectionInfo,
        latencyMetrics: [...this.latencyHistory],
        connectionMetrics: this.connectionMetrics
      };
      
    } catch (executeError: any) {
      this.logger.error('Scenario execution failed', { error: executeError?.message });
      status = TestStatus.ERROR;
      error = executeError?.message;
      throw executeError;
      
    } finally {
      this.logger.scenarioEnd(scenario.id, status, Date.now() - startTime);
      this.currentScenarioId = undefined;
    }
  }

  /**
   * Connect to WebSocket server
   */
  async connect(url?: string, options?: any): Promise<void> {
    const serverURL = url || this.config.serverURL;
    if (!serverURL) {
      throw new Error('Server URL is required for connection');
    }

    if (this.socket && this.socket.connected) {
      this.logger.warn('Already connected to WebSocket server');
      return;
    }

    this.logger.info('Connecting to WebSocket server', { url: serverURL });

    // Create connection info
    this.connectionInfo = {
      id: this.generateConnectionId(),
      url: serverURL,
      namespace: this.config.namespace,
      state: ConnectionState.CONNECTING,
      reconnectCount: 0
    };

    // Prepare socket options
    const socketOptions = {
      ...this.config.socketOptions,
      ...options,
      timeout: this.config.connectionTimeout
    };

    // Add authentication
    if (this.config.auth.type !== 'token' || this.config.auth.token) {
      this.addAuthentication(socketOptions);
    }

    // Create socket connection
    this.socket = io(serverURL, socketOptions);
    this.setupSocketEventHandlers();

    // Setup performance monitoring
    if (this.config.performance.enabled) {
      this.setupPerformanceMonitoring();
    }

    // Wait for connection
    this.connectionPromise = new Promise((resolve, reject) => {
      const timeout = setTimeout(() => {
        this.connectionInfo!.state = ConnectionState.ERROR;
        this.connectionInfo!.error = 'Connection timeout';
        reject(new Error(`Connection timeout after ${this.config.connectionTimeout}ms`));
      }, this.config.connectionTimeout);

      this.socket!.on('connect', () => {
        clearTimeout(timeout);
        this.connectionInfo!.state = ConnectionState.CONNECTED;
        this.connectionInfo!.connectTime = new Date();
        this.logger.info('WebSocket connected successfully', { 
          connectionId: this.connectionInfo!.id 
        });
        resolve();
      });

      this.socket!.on('connect_error', (error: Error) => {
        clearTimeout(timeout);
        this.connectionInfo!.state = ConnectionState.ERROR;
        this.connectionInfo!.error = error.message;
        this.logger.error('WebSocket connection failed', { error: error.message });
        reject(error);
      });
    });

    return this.connectionPromise;
  }

  /**
   * Disconnect from WebSocket server
   */
  async disconnect(): Promise<void> {
    if (!this.socket) {
      return;
    }

    this.logger.info('Disconnecting from WebSocket server');

    // Clear ping interval
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = undefined;
    }

    // Update connection info
    if (this.connectionInfo) {
      this.connectionInfo.state = ConnectionState.DISCONNECTED;
      this.connectionInfo.disconnectTime = new Date();
    }

    // Disconnect socket
    this.socket.disconnect();
    this.socket = undefined;
    this.connectionPromise = undefined;

    this.logger.info('WebSocket disconnected');
  }

  /**
   * Send a message through WebSocket
   */
  async sendMessage(event: string, data?: any, ack?: boolean): Promise<WebSocketMessage> {
    if (!this.socket || !this.socket.connected) {
      throw new Error('WebSocket is not connected');
    }

    const messageId = this.generateMessageId();
    const message: WebSocketMessage = {
      id: messageId,
      event,
      data,
      timestamp: new Date(),
      direction: 'sent',
      ack,
      namespace: this.config.namespace
    };

    this.messageHistory.push(message);

    if (this.config.logConfig.logMessages) {
      this.logger.debug('Sending WebSocket message', {
        messageId,
        event,
        data: this.shouldMaskData(event) ? '[MASKED]' : data
      });
    }

    // Track for latency measurement
    if (this.config.performance.measureLatency) {
      this.pendingMessages.set(messageId, {
        timestamp: new Date(),
        event
      });
    }

    // Send message
    if (ack) {
      return new Promise((resolve, reject) => {
        this.socket!.emit(event, data, (response: any) => {
          this.handleAcknowledgment(messageId, response);
          resolve(message);
        });
      });
    } else {
      this.socket.emit(event, data);
      return message;
    }
  }

  /**
   * Wait for a specific message/event
   */
  async waitForMessage(event: string, timeout: number = 10000, filter?: (data: any) => boolean): Promise<WebSocketMessage> {
    return new Promise((resolve, reject) => {
      const timeoutHandle = setTimeout(() => {
        this.socket!.off(event, messageHandler);
        reject(new Error(`Timeout waiting for event: ${event}`));
      }, timeout);

      const messageHandler = (data: any) => {
        if (filter && !filter(data)) {
          return; // Continue waiting
        }

        clearTimeout(timeoutHandle);
        this.socket!.off(event, messageHandler);

        const message: WebSocketMessage = {
          id: this.generateMessageId(),
          event,
          data,
          timestamp: new Date(),
          direction: 'received',
          namespace: this.config.namespace
        };

        this.messageHistory.push(message);
        resolve(message);
      };

      this.socket!.on(event, messageHandler);
    });
  }

  /**
   * Execute a test step
   */
  async executeStep(step: TestStep, stepIndex: number): Promise<StepResult> {
    const startTime = Date.now();
    this.logger.stepExecution(stepIndex, step.action, step.target);
    
    try {
      let result: any;
      
      switch (step.action.toLowerCase()) {
        case 'connect':
          await this.connect(step.target || undefined);
          result = true;
          break;
          
        case 'disconnect':
          await this.disconnect();
          result = true;
          break;
          
        case 'send':
        case 'emit':
          result = await this.handleSendMessage(step);
          break;
          
        case 'wait_for_message':
        case 'wait_for_event':
          result = await this.handleWaitForMessage(step);
          break;
          
        case 'validate_message':
          result = await this.validateMessage(step);
          break;
          
        case 'validate_connection':
          result = this.validateConnection();
          break;
          
        case 'add_listener':
          this.addEventListener(step.target, step.value);
          result = true;
          break;
          
        case 'remove_listener':
          this.removeEventListener(step.target);
          result = true;
          break;
          
        case 'ping':
          result = await this.pingServer();
          break;
          
        case 'wait':
          const waitTime = parseInt(step.value || '1000');
          await this.delay(waitTime);
          result = true;
          break;
          
        case 'set_auth':
          this.setAuthentication(step.target, step.value);
          result = true;
          break;
          
        default:
          throw new Error(`Unsupported WebSocket action: ${step.action}`);
      }
      
      const duration = Date.now() - startTime;
      this.logger.stepComplete(stepIndex, TestStatus.PASSED, duration);
      
      return {
        stepIndex,
        status: TestStatus.PASSED,
        duration,
        actualResult: typeof result === 'string' ? result : JSON.stringify(result)
      };
      
    } catch (error: any) {
      const duration = Date.now() - startTime;
      this.logger.stepComplete(stepIndex, TestStatus.FAILED, duration);
      
      return {
        stepIndex,
        status: TestStatus.FAILED,
        duration,
        error: error?.message
      };
    }
  }

  /**
   * Get connection state
   */
  getConnectionState(): ConnectionState {
    return this.connectionInfo?.state || ConnectionState.DISCONNECTED;
  }

  /**
   * Get latest message
   */
  getLatestMessage(): WebSocketMessage | undefined {
    return this.messageHistory[this.messageHistory.length - 1];
  }

  /**
   * Get messages by event type
   */
  getMessagesByEvent(event: string): WebSocketMessage[] {
    return this.messageHistory.filter(msg => msg.event === event);
  }

  /**
   * Get connection metrics
   */
  getConnectionMetrics(): ConnectionMetrics | undefined {
    return this.connectionMetrics;
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up WebSocketAgent resources');
    
    try {
      // Disconnect if connected
      await this.disconnect();
      
      // Clear history
      this.messageHistory = [];
      this.latencyHistory = [];
      this.pendingMessages.clear();
      this.eventHandlers.clear();
      
      this.logger.info('WebSocketAgent cleanup completed');
      this.emit('cleanup');
      
    } catch (error: any) {
      this.logger.error('Error during cleanup', { error: error?.message });
    }
  }

  // Private helper methods

  private validateServerURL(url: string): void {
    try {
      const parsed = new URL(url);
      if (!['ws:', 'wss:', 'http:', 'https:'].includes(parsed.protocol)) {
        throw new Error(`Invalid WebSocket protocol: ${parsed.protocol}`);
      }
    } catch (error) {
      throw new Error(`Invalid server URL: ${url}`);
    }
  }

  private addAuthentication(socketOptions: any): void {
    switch (this.config.auth.type) {
      case 'token':
        if (this.config.auth.token) {
          socketOptions.auth = { token: this.config.auth.token };
        }
        break;
        
      case 'query':
        if (this.config.auth.token && this.config.auth.queryParam) {
          socketOptions.query = {
            ...socketOptions.query,
            [this.config.auth.queryParam]: this.config.auth.token
          };
        }
        break;
        
      case 'header':
        if (this.config.auth.token && this.config.auth.headerName) {
          socketOptions.extraHeaders = {
            ...socketOptions.extraHeaders,
            [this.config.auth.headerName]: this.config.auth.token
          };
        }
        break;
        
      case 'custom':
        if (this.config.auth.customAuth) {
          Object.assign(socketOptions, this.config.auth.customAuth);
        }
        break;
    }
  }

  private setupSocketEventHandlers(): void {
    if (!this.socket) return;

    // Connection events
    this.socket.on('connect', () => {
      this.emit('connected');
      if (this.connectionInfo) {
        this.connectionInfo.state = ConnectionState.CONNECTED;
      }
    });

    this.socket.on('disconnect', (reason: string) => {
      this.emit('disconnected', reason);
      if (this.connectionInfo) {
        this.connectionInfo.state = ConnectionState.DISCONNECTED;
        this.connectionInfo.disconnectTime = new Date();
      }
    });

    this.socket.on('reconnect', (attemptNumber: number) => {
      this.emit('reconnected', attemptNumber);
      if (this.connectionInfo) {
        this.connectionInfo.reconnectCount = attemptNumber;
        this.connectionInfo.state = ConnectionState.CONNECTED;
      }
    });

    this.socket.on('reconnect_attempt', (attemptNumber: number) => {
      this.emit('reconnecting', attemptNumber);
      if (this.connectionInfo) {
        this.connectionInfo.state = ConnectionState.RECONNECTING;
      }
    });

    // Error events
    this.socket.on('connect_error', (error: Error) => {
      this.emit('error', error);
      if (this.connectionInfo) {
        this.connectionInfo.state = ConnectionState.ERROR;
        this.connectionInfo.error = error.message;
      }
    });

    // Setup custom event listeners
    this.setupCustomEventListeners();
  }

  private setupCustomEventListeners(): void {
    this.config.eventListeners.forEach(listener => {
      if (listener.enabled && this.socket) {
        const wrappedHandler = (data: any) => {
          // Record received message
          const message: WebSocketMessage = {
            id: this.generateMessageId(),
            event: listener.event,
            data,
            timestamp: new Date(),
            direction: 'received',
            namespace: this.config.namespace
          };

          this.messageHistory.push(message);

          if (this.config.logConfig.logMessages) {
            this.logger.debug('Received WebSocket message', {
              event: listener.event,
              data: this.shouldMaskData(listener.event) ? '[MASKED]' : data
            });
          }

          // Call the handler
          try {
            const result = listener.handler(data);
            if (result instanceof Promise) {
              result.catch(error => {
                this.logger.error('Event handler error', { 
                  event: listener.event, 
                  error: error.message 
                });
              });
            }
          } catch (error: any) {
            this.logger.error('Event handler error', { 
              event: listener.event, 
              error: error.message 
            });
          }
        };

        if (listener.once) {
          this.socket.once(listener.event, wrappedHandler);
        } else {
          this.socket.on(listener.event, wrappedHandler);
        }

        this.eventHandlers.set(listener.event, wrappedHandler);
      }
    });
  }

  private setupDefaultEventListeners(): void {
    // Add default listeners that are always useful
    this.config.eventListeners.push({
      event: 'error',
      handler: (error: any) => {
        this.logger.error('WebSocket error event', { error });
      },
      enabled: true
    });

    this.config.eventListeners.push({
      event: 'pong',
      handler: (latency: number) => {
        this.recordLatency('ping', latency);
      },
      enabled: this.config.performance.measureLatency
    });
  }

  private setupPerformanceMonitoring(): void {
    if (!this.config.performance.enabled || !this.socket) return;

    // Initialize connection metrics
    this.connectionMetrics = {
      connectionId: this.connectionInfo!.id,
      connectTime: Date.now(),
      totalMessages: 0,
      messagesSent: 0,
      messagesReceived: 0,
      reconnectCount: 0,
      uptime: 0,
      timestamp: new Date()
    };

    // Setup ping interval for latency measurement
    if (this.config.performance.measureLatency && this.config.performance.pingInterval) {
      this.pingInterval = setInterval(() => {
        this.pingServer().catch(error => {
          this.logger.warn('Ping failed', { error: error.message });
        });
      }, this.config.performance.pingInterval);
    }
  }

  private async handleSendMessage(step: TestStep): Promise<WebSocketMessage> {
    const event = step.target;
    let data: any;
    let ack = false;

    if (step.value) {
      try {
        const parsed = JSON.parse(step.value);
        data = parsed.data || parsed;
        ack = parsed.ack || false;
      } catch {
        data = step.value;
      }
    }

    return this.sendMessage(event, data, ack);
  }

  private async handleWaitForMessage(step: TestStep): Promise<WebSocketMessage> {
    const event = step.target;
    const timeout = step.timeout || 10000;
    
    let filter: ((data: any) => boolean) | undefined;
    
    if (step.value) {
      try {
        const filterConfig = JSON.parse(step.value);
        if (filterConfig.filter) {
          // This would need to be a more sophisticated filter implementation
          filter = (data: any) => {
            return JSON.stringify(data).includes(filterConfig.filter);
          };
        }
      } catch {
        // Use value as simple string filter
        filter = (data: any) => JSON.stringify(data).includes(step.value!);
      }
    }

    return this.waitForMessage(event, timeout, filter);
  }

  private async validateMessage(step: TestStep): Promise<boolean> {
    const latestMessage = this.getLatestMessage();
    if (!latestMessage) {
      throw new Error('No message available for validation');
    }

    const expected = step.expected || step.value;
    if (!expected) {
      throw new Error('No expected value provided for message validation');
    }

    try {
      const expectedData = JSON.parse(expected);
      return this.deepEqual(latestMessage.data, expectedData);
    } catch {
      // If not JSON, do string comparison
      return JSON.stringify(latestMessage.data).includes(expected);
    }
  }

  private validateConnection(): boolean {
    return this.socket?.connected === true && 
           this.connectionInfo?.state === ConnectionState.CONNECTED;
  }

  private addEventListener(event: string, handlerStr?: string): void {
    const handler = (data: any) => {
      this.logger.debug(`Event received: ${event}`, { data });
    };

    if (this.socket) {
      this.socket.on(event, handler);
      this.eventHandlers.set(event, handler);
    }
  }

  private removeEventListener(event: string): void {
    const handler = this.eventHandlers.get(event);
    if (handler && this.socket) {
      this.socket.off(event, handler as (...args: any[]) => void);
      this.eventHandlers.delete(event);
    }
  }

  private async pingServer(): Promise<number> {
    if (!this.socket || !this.socket.connected) {
      throw new Error('WebSocket is not connected');
    }

    return new Promise((resolve, reject) => {
      const startTime = Date.now();
      
      const timeout = setTimeout(() => {
        reject(new Error('Ping timeout'));
      }, 5000);

      this.socket!.emit('ping', startTime, (response: any) => {
        clearTimeout(timeout);
        const latency = Date.now() - startTime;
        this.recordLatency('ping', latency);
        resolve(latency);
      });
    });
  }

  private setAuthentication(type: string, value?: string): void {
    switch (type.toLowerCase()) {
      case 'token':
        this.config.auth = { type: 'token', token: value };
        break;
        
      case 'query':
        const [param, token] = (value || '').split(':');
        this.config.auth = { 
          type: 'query', 
          queryParam: param || 'token', 
          token: token || value 
        };
        break;
        
      case 'header':
        const [header, headerToken] = (value || '').split(':');
        this.config.auth = { 
          type: 'header', 
          headerName: header || 'Authorization', 
          token: headerToken || value 
        };
        break;
        
      default:
        throw new Error(`Unsupported WebSocket authentication type: ${type}`);
    }
    
    this.logger.debug(`WebSocket authentication configured: ${type}`);
  }

  private recordLatency(event: string, latency: number): void {
    const measurement: LatencyMeasurement = {
      messageId: this.generateMessageId(),
      event,
      latency,
      timestamp: new Date()
    };

    this.latencyHistory.push(measurement);

    // Keep only the latest measurements
    if (this.latencyHistory.length > this.config.performance.maxLatencyHistory) {
      this.latencyHistory.shift();
    }

    // Update connection metrics
    if (this.connectionMetrics) {
      this.connectionMetrics.lastLatency = latency;
      this.connectionMetrics.averageLatency = this.calculateAverageLatency();
    }

    this.logger.debug('Latency recorded', { event, latency });
  }

  private calculateAverageLatency(): number {
    if (this.latencyHistory.length === 0) return 0;
    
    const sum = this.latencyHistory.reduce((acc, measurement) => acc + measurement.latency, 0);
    return sum / this.latencyHistory.length;
  }

  private handleAcknowledgment(messageId: string, response: any): void {
    const pendingMessage = this.pendingMessages.get(messageId);
    if (pendingMessage && this.config.performance.measureLatency) {
      const latency = Date.now() - pendingMessage.timestamp.getTime();
      this.recordLatency(pendingMessage.event, latency);
      this.pendingMessages.delete(messageId);
    }
  }

  private shouldMaskData(event: string): boolean {
    return this.config.logConfig.maskSensitiveData && 
           this.config.logConfig.sensitiveEvents.some(sensitiveEvent => 
             event.toLowerCase().includes(sensitiveEvent.toLowerCase())
           );
  }

  private generateConnectionId(): string {
    return `conn_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private generateMessageId(): string {
    return `msg_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private applyEnvironmentConfig(environment: Record<string, string>): void {
    for (const [key, value] of Object.entries(environment)) {
      if (key.startsWith('WS_')) {
        // Apply WebSocket-specific environment variables
        switch (key) {
          case 'WS_SERVER_URL':
            this.config.serverURL = value;
            break;
          case 'WS_AUTH_TOKEN':
            this.setAuthentication('token', value);
            break;
          case 'WS_NAMESPACE':
            this.config.namespace = value;
            break;
        }
      }
    }
  }

  private getScenarioLogs(): string[] {
    // Return recent logs related to the current scenario
    return [];
  }

  private setupEventListeners(): void {
    this.on('error', (error) => {
      this.logger.error('WebSocketAgent error', { error: error.message });
    });
  }

  private deepEqual(obj1: any, obj2: any): boolean {
    if (obj1 === obj2) return true;
    
    if (obj1 == null || obj2 == null) return false;
    
    if (typeof obj1 !== typeof obj2) return false;
    
    if (typeof obj1 !== 'object') return obj1 === obj2;
    
    const keys1 = Object.keys(obj1);
    const keys2 = Object.keys(obj2);
    
    if (keys1.length !== keys2.length) return false;
    
    for (const key of keys1) {
      if (!keys2.includes(key)) return false;
      if (!this.deepEqual(obj1[key], obj2[key])) return false;
    }
    
    return true;
  }

  private async delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}

/**
 * Factory function to create WebSocketAgent instance
 */
export function createWebSocketAgent(config?: WebSocketAgentConfig): WebSocketAgent {
  return new WebSocketAgent(config);
}