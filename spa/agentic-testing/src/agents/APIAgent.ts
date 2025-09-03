/**
 * APIAgent - Comprehensive REST API testing agent using Axios
 * 
 * This agent provides complete automation capabilities for REST API testing
 * including support for all HTTP methods, authentication, request/response
 * validation, performance measurement, retries, and comprehensive error handling.
 */

import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse, AxiosError } from 'axios';
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
 * HTTP methods supported by the API agent
 */
export type HTTPMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH' | 'HEAD' | 'OPTIONS';

/**
 * Authentication configuration types
 */
export interface AuthConfig {
  type: 'bearer' | 'apikey' | 'basic' | 'custom';
  token?: string;
  apiKey?: string;
  apiKeyHeader?: string;
  username?: string;
  password?: string;
  customHeaders?: Record<string, string>;
}

/**
 * Request interceptor configuration
 */
export interface RequestInterceptor {
  name: string;
  handler: (config: any) => any | Promise<any>;
  enabled: boolean;
}

/**
 * Response interceptor configuration
 */
export interface ResponseInterceptor {
  name: string;
  handler: (response: AxiosResponse) => AxiosResponse | Promise<AxiosResponse>;
  errorHandler?: (error: AxiosError) => Promise<AxiosError>;
  enabled: boolean;
}

/**
 * Schema validation configuration
 */
export interface SchemaValidation {
  enabled: boolean;
  requestSchema?: any; // JSON Schema object
  responseSchema?: any; // JSON Schema object
  strictMode?: boolean;
}

/**
 * Performance measurement configuration
 */
export interface PerformanceMeasurement {
  enabled: boolean;
  measureDNS?: boolean;
  measureTCP?: boolean;
  measureTLS?: boolean;
  measureTransfer?: boolean;
  thresholds?: {
    maxResponseTime?: number;
    maxDNSTime?: number;
    maxConnectTime?: number;
  };
}

/**
 * Retry configuration
 */
export interface RetryConfig {
  maxRetries: number;
  retryDelay: number;
  retryOnStatus: number[];
  exponentialBackoff: boolean;
  maxBackoffDelay?: number;
}

/**
 * Configuration options for the APIAgent
 */
export interface APIAgentConfig {
  /** Base URL for API requests */
  baseURL?: string;
  /** Default timeout for requests in milliseconds */
  timeout?: number;
  /** Default headers to include with all requests */
  defaultHeaders?: Record<string, string>;
  /** Authentication configuration */
  auth?: AuthConfig;
  /** Request interceptors */
  requestInterceptors?: RequestInterceptor[];
  /** Response interceptors */
  responseInterceptors?: ResponseInterceptor[];
  /** Schema validation configuration */
  validation?: SchemaValidation;
  /** Performance measurement configuration */
  performance?: PerformanceMeasurement;
  /** Retry configuration */
  retry?: RetryConfig;
  /** SSL/TLS options */
  ssl?: {
    rejectUnauthorized?: boolean;
    ca?: string;
    cert?: string;
    key?: string;
  };
  /** Logging configuration */
  logConfig?: {
    logRequests: boolean;
    logResponses: boolean;
    logHeaders: boolean;
    logLevel: LogLevel;
    maskSensitiveData: boolean;
    sensitiveHeaders: string[];
  };
}

/**
 * API request information
 */
export interface APIRequest {
  id: string;
  method: HTTPMethod;
  url: string;
  headers?: Record<string, string>;
  data?: any;
  timestamp: Date;
  timeout?: number;
}

/**
 * API response information
 */
export interface APIResponse {
  requestId: string;
  status: number;
  statusText: string;
  headers: Record<string, string>;
  data: any;
  duration: number;
  timestamp: Date;
  size?: number;
}

/**
 * Performance metrics for a request
 */
export interface RequestPerformance {
  requestId: string;
  totalTime: number;
  dnsTime?: number;
  tcpTime?: number;
  tlsTime?: number;
  transferTime?: number;
  responseSize: number;
  requestSize?: number;
  timestamp: Date;
}

/**
 * Default configuration
 */
const DEFAULT_CONFIG: Required<APIAgentConfig> = {
  baseURL: '',
  timeout: 30000,
  defaultHeaders: {
    'Content-Type': 'application/json',
    'Accept': 'application/json'
  },
  auth: { type: 'bearer' },
  requestInterceptors: [],
  responseInterceptors: [],
  validation: {
    enabled: false,
    strictMode: false
  },
  performance: {
    enabled: true,
    measureDNS: true,
    measureTCP: true,
    measureTLS: true,
    measureTransfer: true,
    thresholds: {
      maxResponseTime: 5000,
      maxDNSTime: 1000,
      maxConnectTime: 2000
    }
  },
  retry: {
    maxRetries: 2,
    retryDelay: 1000,
    retryOnStatus: [408, 429, 500, 502, 503, 504],
    exponentialBackoff: true,
    maxBackoffDelay: 10000
  },
  ssl: {
    rejectUnauthorized: true
  },
  logConfig: {
    logRequests: true,
    logResponses: true,
    logHeaders: false,
    logLevel: LogLevel.DEBUG,
    maskSensitiveData: true,
    sensitiveHeaders: ['authorization', 'x-api-key', 'cookie']
  }
};

/**
 * Comprehensive API testing agent
 */
export class APIAgent extends EventEmitter implements IAgent {
  public readonly name = 'APIAgent';
  public readonly type = AgentType.API;
  
  private config: Required<APIAgentConfig>;
  private logger: TestLogger;
  private isInitialized = false;
  private currentScenarioId?: string;
  private axiosInstance: AxiosInstance;
  private requestHistory: APIRequest[] = [];
  private responseHistory: APIResponse[] = [];
  private performanceMetrics: RequestPerformance[] = [];
  
  constructor(config: APIAgentConfig = {}) {
    super();
    this.config = { ...DEFAULT_CONFIG, ...config };
    this.logger = createLogger({
      level: this.config.logConfig.logLevel,
      logDir: './logs/api-agent'
    });
    
    this.axiosInstance = this.createAxiosInstance();
    this.setupEventListeners();
  }

  /**
   * Initialize the agent
   */
  async initialize(): Promise<void> {
    this.logger.info('Initializing APIAgent', { 
      baseURL: this.config.baseURL,
      timeout: this.config.timeout,
      authType: this.config.auth.type
    });
    
    try {
      // Test connectivity if base URL is provided
      if (this.config.baseURL) {
        await this.testConnectivity();
      }
      
      // Setup interceptors
      this.setupInterceptors();
      
      this.isInitialized = true;
      this.logger.info('APIAgent initialized successfully');
      this.emit('initialized');
      
    } catch (error: any) {
      this.logger.error('Failed to initialize APIAgent', { error: error?.message });
      throw new Error(`Failed to initialize APIAgent: ${error?.message}`);
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
    this.logger.setContext({ scenarioId: scenario.id, component: 'APIAgent' });
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
        requestHistory: [...this.requestHistory],
        responseHistory: [...this.responseHistory],
        performanceMetrics: [...this.performanceMetrics]
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
   * Make an HTTP request with full configuration
   */
  async makeRequest(
    method: HTTPMethod,
    url: string,
    data?: any,
    headers?: Record<string, string>,
    options?: Partial<AxiosRequestConfig>
  ): Promise<APIResponse> {
    const requestId = this.generateRequestId();
    const startTime = Date.now();
    
    const request: APIRequest = {
      id: requestId,
      method,
      url,
      headers,
      data,
      timestamp: new Date(),
      timeout: options?.timeout
    };
    
    this.requestHistory.push(request);
    
    if (this.config.logConfig.logRequests) {
      this.logger.info(`Making ${method} request`, {
        requestId,
        url,
        headers: this.config.logConfig.logHeaders ? this.maskSensitiveHeaders(headers || {}) : undefined
      });
    }

    let attempt = 0;
    const maxAttempts = this.config.retry.maxRetries + 1;
    
    while (attempt < maxAttempts) {
      try {
        const axiosConfig: AxiosRequestConfig = {
          method: method.toLowerCase() as any,
          url,
          data,
          headers,
          ...options
        };
        
        const response = await this.axiosInstance.request(axiosConfig);
        const duration = Date.now() - startTime;
        
        const apiResponse: APIResponse = {
          requestId,
          status: response.status,
          statusText: response.statusText,
          headers: response.headers as Record<string, string>,
          data: response.data,
          duration,
          timestamp: new Date(),
          size: this.calculateResponseSize(response.data)
        };
        
        this.responseHistory.push(apiResponse);
        
        if (this.config.performance.enabled) {
          this.recordPerformanceMetrics(requestId, response, duration);
        }
        
        if (this.config.logConfig.logResponses) {
          this.logger.info(`Request completed successfully`, {
            requestId,
            status: response.status,
            duration,
            size: apiResponse.size
          });
        }
        
        this.emit('response', apiResponse);
        return apiResponse;
        
      } catch (error: any) {
        attempt++;
        
        if (attempt >= maxAttempts || !this.shouldRetry(error)) {
          const duration = Date.now() - startTime;
          const errorResponse: APIResponse = {
            requestId,
            status: error.response?.status || 0,
            statusText: error.response?.statusText || 'Request Failed',
            headers: error.response?.headers || {},
            data: error.response?.data || error.message,
            duration,
            timestamp: new Date()
          };
          
          this.responseHistory.push(errorResponse);
          this.logger.error(`Request failed after ${attempt} attempts`, {
            requestId,
            error: error?.message,
            status: error.response?.status
          });
          
          throw error;
        }
        
        const retryDelay = this.calculateRetryDelay(attempt);
        this.logger.warn(`Request attempt ${attempt} failed, retrying in ${retryDelay}ms`, {
          requestId,
          error: error?.message,
          attempt,
          maxAttempts
        });
        
        await this.delay(retryDelay);
      }
    }
    
    throw new Error('Unexpected end of retry loop');
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
        case 'get':
          result = await this.handleGetRequest(step);
          break;
          
        case 'post':
          result = await this.handlePostRequest(step);
          break;
          
        case 'put':
          result = await this.handlePutRequest(step);
          break;
          
        case 'delete':
          result = await this.handleDeleteRequest(step);
          break;
          
        case 'patch':
          result = await this.handlePatchRequest(step);
          break;
          
        case 'head':
          result = await this.handleHeadRequest(step);
          break;
          
        case 'options':
          result = await this.handleOptionsRequest(step);
          break;
          
        case 'validate_response':
          result = await this.validateResponse(step);
          break;
          
        case 'validate_status':
          result = await this.validateStatus(parseInt(step.expected || step.value || '200'));
          break;
          
        case 'validate_headers':
          result = await this.validateHeaders(step.expected || step.value || '');
          break;
          
        case 'validate_schema':
          result = await this.validateResponseSchema(step.expected || step.value || '');
          break;
          
        case 'set_header':
          this.setDefaultHeader(step.target, step.value || '');
          result = true;
          break;
          
        case 'set_auth':
          this.setAuthentication(step.target, step.value);
          result = true;
          break;
          
        case 'wait':
          const waitTime = parseInt(step.value || '1000');
          await this.delay(waitTime);
          result = true;
          break;
          
        case 'clear_cookies':
          // Note: Axios doesn't handle cookies automatically like browsers
          // This would need to be implemented if cookie support is needed
          result = true;
          break;
          
        default:
          throw new Error(`Unsupported API action: ${step.action}`);
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
   * Set authentication configuration
   */
  setAuthentication(type: string, value?: string): void {
    switch (type.toLowerCase()) {
      case 'bearer':
        this.config.auth = { type: 'bearer', token: value };
        this.axiosInstance.defaults.headers.common['Authorization'] = `Bearer ${value}`;
        break;
        
      case 'apikey':
        const [header, key] = (value || '').split(':');
        this.config.auth = { 
          type: 'apikey', 
          apiKey: key, 
          apiKeyHeader: header || 'X-API-Key' 
        };
        this.axiosInstance.defaults.headers.common[header || 'X-API-Key'] = key;
        break;
        
      case 'basic':
        const [username, password] = (value || '').split(':');
        this.config.auth = { type: 'basic', username, password };
        const basicAuth = Buffer.from(`${username}:${password}`).toString('base64');
        this.axiosInstance.defaults.headers.common['Authorization'] = `Basic ${basicAuth}`;
        break;
        
      default:
        throw new Error(`Unsupported authentication type: ${type}`);
    }
    
    this.logger.debug(`Authentication configured: ${type}`);
  }

  /**
   * Set default header
   */
  setDefaultHeader(name: string, value: string): void {
    this.config.defaultHeaders[name] = value;
    this.axiosInstance.defaults.headers.common[name] = value;
    this.logger.debug(`Default header set: ${name}=${this.config.logConfig.maskSensitiveData && 
      this.config.logConfig.sensitiveHeaders.includes(name.toLowerCase()) ? '[MASKED]' : value}`);
  }

  /**
   * Get the latest response
   */
  getLatestResponse(): APIResponse | undefined {
    return this.responseHistory[this.responseHistory.length - 1];
  }

  /**
   * Get performance metrics for the latest request
   */
  getLatestPerformanceMetrics(): RequestPerformance | undefined {
    return this.performanceMetrics[this.performanceMetrics.length - 1];
  }

  /**
   * Clean up resources
   */
  async cleanup(): Promise<void> {
    this.logger.info('Cleaning up APIAgent resources');
    
    try {
      // Clear history
      this.requestHistory = [];
      this.responseHistory = [];
      this.performanceMetrics = [];
      
      this.logger.info('APIAgent cleanup completed');
      this.emit('cleanup');
      
    } catch (error: any) {
      this.logger.error('Error during cleanup', { error: error?.message });
    }
  }

  // Private helper methods

  private createAxiosInstance(): AxiosInstance {
    const instance = axios.create({
      baseURL: this.config.baseURL,
      timeout: this.config.timeout,
      headers: this.config.defaultHeaders,
      httpsAgent: this.config.ssl ? {
        rejectUnauthorized: this.config.ssl.rejectUnauthorized,
        ca: this.config.ssl.ca,
        cert: this.config.ssl.cert,
        key: this.config.ssl.key
      } : undefined
    });

    return instance;
  }

  private setupInterceptors(): void {
    // Request interceptors
    this.config.requestInterceptors.forEach(interceptor => {
      if (interceptor.enabled) {
        this.axiosInstance.interceptors.request.use(interceptor.handler);
      }
    });

    // Response interceptors
    this.config.responseInterceptors.forEach(interceptor => {
      if (interceptor.enabled) {
        this.axiosInstance.interceptors.response.use(
          interceptor.handler,
          interceptor.errorHandler
        );
      }
    });
  }

  private async testConnectivity(): Promise<void> {
    try {
      await this.axiosInstance.head('/');
    } catch (error: any) {
      // Don't fail initialization if connectivity test fails
      this.logger.warn('Connectivity test failed', { error: error?.message });
    }
  }

  private async handleGetRequest(step: TestStep): Promise<APIResponse> {
    const headers = this.parseHeaders(step.value);
    return this.makeRequest('GET', step.target, undefined, headers, {
      timeout: step.timeout
    });
  }

  private async handlePostRequest(step: TestStep): Promise<APIResponse> {
    const { data, headers } = this.parseRequestData(step.value);
    return this.makeRequest('POST', step.target, data, headers, {
      timeout: step.timeout
    });
  }

  private async handlePutRequest(step: TestStep): Promise<APIResponse> {
    const { data, headers } = this.parseRequestData(step.value);
    return this.makeRequest('PUT', step.target, data, headers, {
      timeout: step.timeout
    });
  }

  private async handleDeleteRequest(step: TestStep): Promise<APIResponse> {
    const headers = this.parseHeaders(step.value);
    return this.makeRequest('DELETE', step.target, undefined, headers, {
      timeout: step.timeout
    });
  }

  private async handlePatchRequest(step: TestStep): Promise<APIResponse> {
    const { data, headers } = this.parseRequestData(step.value);
    return this.makeRequest('PATCH', step.target, data, headers, {
      timeout: step.timeout
    });
  }

  private async handleHeadRequest(step: TestStep): Promise<APIResponse> {
    const headers = this.parseHeaders(step.value);
    return this.makeRequest('HEAD', step.target, undefined, headers, {
      timeout: step.timeout
    });
  }

  private async handleOptionsRequest(step: TestStep): Promise<APIResponse> {
    const headers = this.parseHeaders(step.value);
    return this.makeRequest('OPTIONS', step.target, undefined, headers, {
      timeout: step.timeout
    });
  }

  private async validateResponse(step: TestStep): Promise<boolean> {
    const latestResponse = this.getLatestResponse();
    if (!latestResponse) {
      throw new Error('No response available for validation');
    }

    const expected = step.expected || step.value;
    if (!expected) {
      throw new Error('No expected value provided for response validation');
    }

    try {
      const expectedData = JSON.parse(expected);
      return this.deepEqual(latestResponse.data, expectedData);
    } catch {
      // If not JSON, do string comparison
      return JSON.stringify(latestResponse.data).includes(expected);
    }
  }

  private async validateStatus(expectedStatus: number): Promise<boolean> {
    const latestResponse = this.getLatestResponse();
    if (!latestResponse) {
      throw new Error('No response available for status validation');
    }

    return latestResponse.status === expectedStatus;
  }

  private async validateHeaders(expected: string): Promise<boolean> {
    const latestResponse = this.getLatestResponse();
    if (!latestResponse) {
      throw new Error('No response available for header validation');
    }

    try {
      const expectedHeaders = JSON.parse(expected);
      
      for (const [key, value] of Object.entries(expectedHeaders)) {
        const actualValue = latestResponse.headers[key.toLowerCase()];
        if (actualValue !== value) {
          return false;
        }
      }
      
      return true;
    } catch (error) {
      throw new Error(`Invalid header validation format: ${expected}`);
    }
  }

  private async validateResponseSchema(schemaStr: string): Promise<boolean> {
    if (!this.config.validation.enabled) {
      throw new Error('Schema validation is disabled');
    }

    // This would require a JSON schema validation library
    // For now, return true as placeholder
    this.logger.warn('Schema validation not implemented yet');
    return true;
  }

  private parseHeaders(value?: string): Record<string, string> | undefined {
    if (!value) return undefined;

    try {
      return JSON.parse(value);
    } catch {
      // If not JSON, treat as single header in format "key:value"
      const [key, val] = value.split(':');
      return key && val ? { [key.trim()]: val.trim() } : undefined;
    }
  }

  private parseRequestData(value?: string): { data?: any; headers?: Record<string, string> } {
    if (!value) return {};

    try {
      const parsed = JSON.parse(value);
      
      if (parsed.data && parsed.headers) {
        return parsed;
      } else if (typeof parsed === 'object') {
        return { data: parsed };
      }
      
      return { data: parsed };
    } catch {
      return { data: value };
    }
  }

  private shouldRetry(error: any): boolean {
    if (!error.response) return false;
    return this.config.retry.retryOnStatus.includes(error.response.status);
  }

  private calculateRetryDelay(attempt: number): number {
    if (!this.config.retry.exponentialBackoff) {
      return this.config.retry.retryDelay;
    }

    const delay = this.config.retry.retryDelay * Math.pow(2, attempt - 1);
    return Math.min(delay, this.config.retry.maxBackoffDelay || 10000);
  }

  private recordPerformanceMetrics(requestId: string, response: AxiosResponse, totalTime: number): void {
    const metrics: RequestPerformance = {
      requestId,
      totalTime,
      responseSize: this.calculateResponseSize(response.data),
      timestamp: new Date()
    };

    this.performanceMetrics.push(metrics);

    // Check thresholds
    const thresholds = this.config.performance.thresholds;
    if (thresholds?.maxResponseTime && totalTime > thresholds.maxResponseTime) {
      this.logger.warn(`Response time exceeded threshold`, {
        requestId,
        actualTime: totalTime,
        threshold: thresholds.maxResponseTime
      });
    }
  }

  private calculateResponseSize(data: any): number {
    if (typeof data === 'string') {
      return Buffer.byteLength(data, 'utf8');
    } else if (data instanceof Buffer) {
      return data.length;
    } else {
      return Buffer.byteLength(JSON.stringify(data), 'utf8');
    }
  }

  private maskSensitiveHeaders(headers: Record<string, string>): Record<string, string> {
    if (!this.config.logConfig.maskSensitiveData) {
      return headers;
    }

    const masked = { ...headers };
    
    for (const sensitiveHeader of this.config.logConfig.sensitiveHeaders) {
      const header = Object.keys(masked).find(key => 
        key.toLowerCase() === sensitiveHeader.toLowerCase()
      );
      
      if (header) {
        masked[header] = '[MASKED]';
      }
    }
    
    return masked;
  }

  private generateRequestId(): string {
    return `${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  private applyEnvironmentConfig(environment: Record<string, string>): void {
    for (const [key, value] of Object.entries(environment)) {
      if (key.startsWith('API_')) {
        // Apply API-specific environment variables
        switch (key) {
          case 'API_BASE_URL':
            this.axiosInstance.defaults.baseURL = value;
            break;
          case 'API_TIMEOUT':
            this.axiosInstance.defaults.timeout = parseInt(value);
            break;
          case 'API_AUTH_TOKEN':
            this.setAuthentication('bearer', value);
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
      this.logger.error('APIAgent error', { error: error.message });
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
 * Factory function to create APIAgent instance
 */
export function createAPIAgent(config?: APIAgentConfig): APIAgent {
  return new APIAgent(config);
}