/**
 * Retry logic utilities with exponential backoff and circuit breaker patterns
 * Provides robust retry mechanisms for test operations
 */

/**
 * Retry strategy enumeration
 */
export enum RetryStrategy {
  /** Fixed delay between retries */
  FIXED = 'fixed',
  /** Exponential backoff with jitter */
  EXPONENTIAL = 'exponential',
  /** Linear increase in delay */
  LINEAR = 'linear',
  /** Custom delay function */
  CUSTOM = 'custom'
}

/**
 * Circuit breaker state enumeration
 */
export enum CircuitBreakerState {
  CLOSED = 'closed',
  OPEN = 'open',
  HALF_OPEN = 'half_open'
}

/**
 * Retry configuration options
 */
export interface RetryOptions {
  /** Maximum number of retry attempts */
  maxAttempts: number;
  /** Initial delay in milliseconds */
  initialDelay: number;
  /** Maximum delay in milliseconds */
  maxDelay?: number;
  /** Retry strategy to use */
  strategy: RetryStrategy;
  /** Multiplier for exponential backoff */
  backoffMultiplier?: number;
  /** Jitter factor (0-1) for adding randomness to delays */
  jitter?: number;
  /** Custom delay function for CUSTOM strategy */
  delayFunction?: (attempt: number) => number;
  /** Function to determine if error should trigger retry */
  shouldRetry?: (error: Error, attempt: number) => boolean;
  /** Timeout for each individual attempt in milliseconds */
  attemptTimeout?: number;
  /** Callback for retry attempts */
  onRetry?: (error: Error, attempt: number, delay: number) => void;
  /** Callback for final failure */
  onFailure?: (error: Error, totalAttempts: number) => void;
}

/**
 * Circuit breaker configuration
 */
export interface CircuitBreakerOptions {
  /** Failure threshold to open circuit */
  failureThreshold: number;
  /** Reset timeout in milliseconds */
  resetTimeout: number;
  /** Success threshold to close circuit from half-open */
  successThreshold?: number;
  /** Monitoring window in milliseconds */
  monitoringWindow?: number;
  /** Function to determine if error counts as failure */
  isFailure?: (error: Error) => boolean;
  /** Callback when circuit opens */
  onCircuitOpen?: () => void;
  /** Callback when circuit closes */
  onCircuitClose?: () => void;
}

/**
 * Retry result interface
 */
export interface RetryResult<T> {
  /** Final result if successful */
  result?: T;
  /** Final error if all retries failed */
  error?: Error;
  /** Total number of attempts made */
  attempts: number;
  /** Total time taken in milliseconds */
  totalTime: number;
  /** Whether operation succeeded */
  success: boolean;
  /** Details of each attempt */
  attemptDetails: AttemptDetail[];
}

/**
 * Individual attempt details
 */
export interface AttemptDetail {
  /** Attempt number (1-indexed) */
  attempt: number;
  /** Start timestamp */
  startTime: Date;
  /** End timestamp */
  endTime: Date;
  /** Duration in milliseconds */
  duration: number;
  /** Error if attempt failed */
  error?: Error;
  /** Whether attempt succeeded */
  success: boolean;
  /** Delay before this attempt */
  delay: number;
}

/**
 * Default retry configuration
 */
const DEFAULT_RETRY_OPTIONS: RetryOptions = {
  maxAttempts: 3,
  initialDelay: 1000,
  maxDelay: 30000,
  strategy: RetryStrategy.EXPONENTIAL,
  backoffMultiplier: 2,
  jitter: 0.1,
  shouldRetry: (error: Error) => true, // Retry all errors by default
  attemptTimeout: 30000
};

/**
 * Retry utility class
 */
export class RetryManager {
  private options: RetryOptions;

  constructor(options: Partial<RetryOptions> = {}) {
    this.options = { ...DEFAULT_RETRY_OPTIONS, ...options };
  }

  /**
   * Execute a function with retry logic
   */
  async execute<T>(fn: () => Promise<T>): Promise<T> {
    const result = await this.executeWithDetails(fn);

    if (result.success && result.result !== undefined) {
      return result.result;
    }

    throw result.error || new Error('Operation failed after all retry attempts');
  }

  /**
   * Execute a function with detailed retry information
   */
  async executeWithDetails<T>(fn: () => Promise<T>): Promise<RetryResult<T>> {
    const attemptDetails: AttemptDetail[] = [];
    const startTime = Date.now();
    let lastError: Error | undefined;

    for (let attempt = 1; attempt <= this.options.maxAttempts; attempt++) {
      const attemptStart = new Date();
      const delay = attempt === 1 ? 0 : this.calculateDelay(attempt - 1);

      // Apply delay before attempt (except for first attempt)
      if (delay > 0) {
        await this.sleep(delay);
      }

      try {
        // Execute with timeout if specified
        const result = this.options.attemptTimeout
          ? await this.withTimeout(fn(), this.options.attemptTimeout)
          : await fn();

        const attemptEnd = new Date();
        attemptDetails.push({
          attempt,
          startTime: attemptStart,
          endTime: attemptEnd,
          duration: attemptEnd.getTime() - attemptStart.getTime(),
          success: true,
          delay
        });

        return {
          result,
          attempts: attempt,
          totalTime: Date.now() - startTime,
          success: true,
          attemptDetails
        };

      } catch (error) {
        const attemptEnd = new Date();
        lastError = error instanceof Error ? error : new Error(String(error));

        attemptDetails.push({
          attempt,
          startTime: attemptStart,
          endTime: attemptEnd,
          duration: attemptEnd.getTime() - attemptStart.getTime(),
          error: lastError,
          success: false,
          delay
        });

        // Check if we should retry this error
        const shouldRetry = this.options.shouldRetry?.(lastError, attempt) ?? true;

        if (attempt < this.options.maxAttempts && shouldRetry) {
          this.options.onRetry?.(lastError, attempt, this.calculateDelay(attempt));
        }
      }
    }

    // All attempts failed
    this.options.onFailure?.(lastError!, this.options.maxAttempts);

    return {
      error: lastError,
      attempts: this.options.maxAttempts,
      totalTime: Date.now() - startTime,
      success: false,
      attemptDetails
    };
  }

  /**
   * Calculate delay for the given attempt
   */
  private calculateDelay(attempt: number): number {
    let delay: number;

    switch (this.options.strategy) {
      case RetryStrategy.FIXED:
        delay = this.options.initialDelay;
        break;

      case RetryStrategy.EXPONENTIAL:
        delay = this.options.initialDelay * Math.pow(this.options.backoffMultiplier || 2, attempt - 1);
        break;

      case RetryStrategy.LINEAR:
        delay = this.options.initialDelay * attempt;
        break;

      case RetryStrategy.CUSTOM:
        delay = this.options.delayFunction?.(attempt) || this.options.initialDelay;
        break;

      default:
        delay = this.options.initialDelay;
    }

    // Apply maximum delay limit
    if (this.options.maxDelay) {
      delay = Math.min(delay, this.options.maxDelay);
    }

    // Apply jitter to avoid thundering herd
    if (this.options.jitter && this.options.jitter > 0) {
      const jitterAmount = delay * this.options.jitter;
      delay += (Math.random() - 0.5) * jitterAmount;
    }

    return Math.max(0, Math.round(delay));
  }

  /**
   * Sleep for specified milliseconds
   */
  private sleep(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  /**
   * Wrap a promise with timeout
   */
  private withTimeout<T>(promise: Promise<T>, timeoutMs: number): Promise<T> {
    return Promise.race([
      promise,
      new Promise<never>((_, reject) => {
        setTimeout(() => reject(new Error(`Operation timed out after ${timeoutMs}ms`)), timeoutMs);
      })
    ]);
  }
}

/**
 * Circuit breaker implementation
 */
export class CircuitBreaker<T> {
  private state: CircuitBreakerState = CircuitBreakerState.CLOSED;
  private failures: number = 0;
  private successes: number = 0;
  private lastFailureTime: number = 0;
  private options: CircuitBreakerOptions;
  private metrics: {
    totalCalls: number;
    totalFailures: number;
    totalSuccesses: number;
    stateChanges: number;
  } = {
    totalCalls: 0,
    totalFailures: 0,
    totalSuccesses: 0,
    stateChanges: 0
  };

  constructor(options: CircuitBreakerOptions) {
    this.options = {
      successThreshold: 1,
      monitoringWindow: 60000,
      isFailure: () => true,
      ...options
    };
  }

  /**
   * Execute function through circuit breaker
   */
  async execute(fn: () => Promise<T>): Promise<T> {
    this.metrics.totalCalls++;

    if (this.state === CircuitBreakerState.OPEN) {
      if (Date.now() - this.lastFailureTime > this.options.resetTimeout) {
        this.setState(CircuitBreakerState.HALF_OPEN);
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure(error instanceof Error ? error : new Error(String(error)));
      throw error;
    }
  }

  /**
   * Get current circuit breaker state
   */
  getState(): CircuitBreakerState {
    return this.state;
  }

  /**
   * Get circuit breaker metrics
   */
  getMetrics() {
    return { ...this.metrics };
  }

  /**
   * Reset circuit breaker to closed state
   */
  reset(): void {
    this.setState(CircuitBreakerState.CLOSED);
    this.failures = 0;
    this.successes = 0;
    this.lastFailureTime = 0;
  }

  /**
   * Handle successful operation
   */
  private onSuccess(): void {
    this.metrics.totalSuccesses++;
    this.successes++;

    if (this.state === CircuitBreakerState.HALF_OPEN) {
      if (this.successes >= (this.options.successThreshold || 1)) {
        this.setState(CircuitBreakerState.CLOSED);
        this.failures = 0;
        this.successes = 0;
      }
    } else if (this.state === CircuitBreakerState.CLOSED) {
      this.failures = 0; // Reset failure count on success
    }
  }

  /**
   * Handle failed operation
   */
  private onFailure(error: Error): void {
    const isFailure = this.options.isFailure?.(error) ?? true;

    if (!isFailure) {
      return; // Don't count this as a failure
    }

    this.metrics.totalFailures++;
    this.failures++;
    this.lastFailureTime = Date.now();

    if (this.state === CircuitBreakerState.CLOSED) {
      if (this.failures >= this.options.failureThreshold) {
        this.setState(CircuitBreakerState.OPEN);
      }
    } else if (this.state === CircuitBreakerState.HALF_OPEN) {
      this.setState(CircuitBreakerState.OPEN);
    }
  }

  /**
   * Change circuit breaker state
   */
  private setState(newState: CircuitBreakerState): void {
    if (this.state !== newState) {
      const oldState = this.state;
      this.state = newState;
      this.metrics.stateChanges++;

      if (newState === CircuitBreakerState.OPEN) {
        this.options.onCircuitOpen?.();
      } else if (newState === CircuitBreakerState.CLOSED && oldState === CircuitBreakerState.OPEN) {
        this.options.onCircuitClose?.();
      }
    }
  }
}

/**
 * Composite retry with circuit breaker
 */
export class RetryWithCircuitBreaker<T> {
  private retryManager: RetryManager;
  private circuitBreaker: CircuitBreaker<T>;

  constructor(retryOptions: Partial<RetryOptions>, circuitBreakerOptions: CircuitBreakerOptions) {
    this.retryManager = new RetryManager(retryOptions);
    this.circuitBreaker = new CircuitBreaker(circuitBreakerOptions);
  }

  /**
   * Execute function with both retry logic and circuit breaker
   */
  async execute(fn: () => Promise<T>): Promise<T> {
    return this.circuitBreaker.execute(async () => {
      return this.retryManager.execute(fn);
    });
  }

  /**
   * Get circuit breaker state
   */
  getCircuitState(): CircuitBreakerState {
    return this.circuitBreaker.getState();
  }

  /**
   * Get metrics from both components
   */
  getMetrics() {
    return {
      circuitBreaker: this.circuitBreaker.getMetrics()
    };
  }

  /**
   * Reset both retry and circuit breaker state
   */
  reset(): void {
    this.circuitBreaker.reset();
  }
}

/**
 * Convenience functions for common retry patterns
 */

/**
 * Simple retry with exponential backoff
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  options: Partial<RetryOptions> = {}
): Promise<T> {
  const retry = new RetryManager({
    strategy: RetryStrategy.EXPONENTIAL,
    ...options
  });
  return retry.execute(fn);
}

/**
 * Fixed interval retry
 */
export async function retryWithFixedDelay<T>(
  fn: () => Promise<T>,
  attempts: number = 3,
  delay: number = 1000
): Promise<T> {
  const retry = new RetryManager({
    maxAttempts: attempts,
    initialDelay: delay,
    strategy: RetryStrategy.FIXED
  });
  return retry.execute(fn);
}

/**
 * Retry only specific error types
 */
export async function retryOnSpecificErrors<T>(
  fn: () => Promise<T>,
  errorTypes: (new (...args: any[]) => Error)[],
  options: Partial<RetryOptions> = {}
): Promise<T> {
  const retry = new RetryManager({
    ...options,
    shouldRetry: (error) => errorTypes.some(ErrorType => error instanceof ErrorType)
  });
  return retry.execute(fn);
}

/**
 * Create a circuit breaker for a specific service
 */
export function createCircuitBreaker<T>(
  failureThreshold: number = 5,
  resetTimeout: number = 60000
): CircuitBreaker<T> {
  return new CircuitBreaker({
    failureThreshold,
    resetTimeout,
    onCircuitOpen: () => console.warn('Circuit breaker opened'),
    onCircuitClose: () => console.info('Circuit breaker closed')
  });
}

/**
 * Create retry manager with test-specific defaults
 */
export function createTestRetry(options: Partial<RetryOptions> = {}): RetryManager {
  return new RetryManager({
    maxAttempts: 3,
    initialDelay: 1000,
    strategy: RetryStrategy.EXPONENTIAL,
    backoffMultiplier: 1.5,
    jitter: 0.1,
    shouldRetry: (error) => {
      // Don't retry assertion errors or syntax errors
      return !error.message.includes('AssertionError') &&
             !error.message.includes('SyntaxError');
    },
    ...options
  });
}
