import { errorService } from './errorService';

/**
 * Error Recovery Service for implementing recovery strategies
 */

export interface RecoveryStrategy {
  id: string;
  name: string;
  condition: (error: Error) => boolean;
  recover: () => Promise<void> | void;
  maxAttempts?: number;
  backoffMs?: number;
}

export interface RecoveryResult {
  success: boolean;
  strategyUsed?: string;
  attempts: number;
  error?: Error;
}

class ErrorRecoveryService {
  private strategies: Map<string, RecoveryStrategy> = new Map();
  private recoveryAttempts: Map<string, number> = new Map();
  private lastRecoveryTime: Map<string, number> = new Map();
  private isRecovering = false;

  constructor() {
    this.registerDefaultStrategies();
  }

  /**
   * Register default recovery strategies
   */
  private registerDefaultStrategies(): void {
    // Network error recovery
    this.registerStrategy({
      id: 'network-retry',
      name: 'Network Retry',
      condition: (error) => {
        return (
          error.message.includes('fetch') ||
          error.message.includes('network') ||
          error.message.includes('Failed to fetch') ||
          error.name === 'NetworkError'
        );
      },
      recover: async () => {
        // Wait for network to stabilize
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // Check if we're back online
        if (!navigator.onLine) {
          throw new Error('Still offline');
        }
      },
      maxAttempts: 3,
      backoffMs: 2000,
    });

    // Memory pressure recovery
    this.registerStrategy({
      id: 'memory-pressure',
      name: 'Memory Pressure Recovery',
      condition: (error) => {
        return (
          error.message.includes('out of memory') ||
          error.message.includes('Maximum call stack') ||
          error.name === 'RangeError'
        );
      },
      recover: () => {
        // Clear caches and non-essential data
        this.performMemoryCleanup();
      },
      maxAttempts: 1,
    });

    // Token expiry recovery
    this.registerStrategy({
      id: 'token-refresh',
      name: 'Token Refresh',
      condition: (error) => {
        return (
          error.message.includes('401') ||
          error.message.includes('unauthorized') ||
          error.message.includes('token expired')
        );
      },
      recover: async () => {
        // Attempt to refresh authentication token
        await this.refreshAuthToken();
      },
      maxAttempts: 2,
      backoffMs: 1000,
    });

    // Rate limiting recovery
    this.registerStrategy({
      id: 'rate-limit',
      name: 'Rate Limit Backoff',
      condition: (error) => {
        return (
          error.message.includes('429') ||
          error.message.includes('rate limit') ||
          error.message.includes('too many requests')
        );
      },
      recover: async () => {
        // Wait with exponential backoff
        const attempts = this.recoveryAttempts.get('rate-limit') || 0;
        const delay = Math.min(1000 * Math.pow(2, attempts), 30000);
        await new Promise(resolve => setTimeout(resolve, delay));
      },
      maxAttempts: 5,
      backoffMs: 1000,
    });
  }

  /**
   * Register a custom recovery strategy
   */
  registerStrategy(strategy: RecoveryStrategy): void {
    this.strategies.set(strategy.id, strategy);
  }

  /**
   * Unregister a recovery strategy
   */
  unregisterStrategy(id: string): void {
    this.strategies.delete(id);
    this.recoveryAttempts.delete(id);
    this.lastRecoveryTime.delete(id);
  }

  /**
   * Attempt to recover from an error
   */
  async attemptRecovery(error: Error): Promise<RecoveryResult> {
    if (this.isRecovering) {
      return {
        success: false,
        attempts: 0,
        error: new Error('Recovery already in progress'),
      };
    }

    this.isRecovering = true;

    try {
      // Find applicable recovery strategies
      const applicableStrategies = Array.from(this.strategies.values()).filter(
        strategy => strategy.condition(error)
      );

      if (applicableStrategies.length === 0) {
        return {
          success: false,
          attempts: 0,
          error: new Error('No recovery strategy available'),
        };
      }

      // Try each applicable strategy
      for (const strategy of applicableStrategies) {
        const result = await this.executeStrategy(strategy, error);
        if (result.success) {
          return result;
        }
      }

      // All strategies failed
      return {
        success: false,
        attempts: applicableStrategies.reduce(
          (sum, s) => sum + (this.recoveryAttempts.get(s.id) || 0),
          0
        ),
        error: new Error('All recovery strategies failed'),
      };
    } finally {
      this.isRecovering = false;
    }
  }

  /**
   * Execute a specific recovery strategy
   */
  private async executeStrategy(
    strategy: RecoveryStrategy,
    originalError: Error
  ): Promise<RecoveryResult> {
    const attempts = this.recoveryAttempts.get(strategy.id) || 0;
    const maxAttempts = strategy.maxAttempts || 1;

    if (attempts >= maxAttempts) {
      return {
        success: false,
        strategyUsed: strategy.id,
        attempts,
        error: new Error(`Max attempts reached for ${strategy.name}`),
      };
    }

    // Check if we need to wait before retrying
    const lastTime = this.lastRecoveryTime.get(strategy.id) || 0;
    const backoffMs = strategy.backoffMs || 0;
    const timeSinceLastAttempt = Date.now() - lastTime;

    if (timeSinceLastAttempt < backoffMs) {
      await new Promise(resolve => 
        setTimeout(resolve, backoffMs - timeSinceLastAttempt)
      );
    }

    try {
      // Update attempt tracking
      this.recoveryAttempts.set(strategy.id, attempts + 1);
      this.lastRecoveryTime.set(strategy.id, Date.now());

      // Execute recovery
      await strategy.recover();

      // Log successful recovery
      errorService.logError(
        originalError,
        'recovery',
        {
          strategy: strategy.name,
          attempts: attempts + 1,
          recovered: true,
        }
      );

      // Reset attempts on success
      this.recoveryAttempts.set(strategy.id, 0);

      return {
        success: true,
        strategyUsed: strategy.id,
        attempts: attempts + 1,
      };
    } catch (recoveryError) {
      // Log failed recovery attempt
      errorService.logError(
        originalError,
        'recovery',
        {
          strategy: strategy.name,
          attempts: attempts + 1,
          recovered: false,
          recoveryError: recoveryError instanceof Error ? recoveryError.message : String(recoveryError),
        }
      );

      return {
        success: false,
        strategyUsed: strategy.id,
        attempts: attempts + 1,
        error: recoveryError instanceof Error ? recoveryError : new Error(String(recoveryError)),
      };
    }
  }

  /**
   * Perform memory cleanup
   */
  private performMemoryCleanup(): void {
    // Clear any caches
    if ('caches' in window) {
      caches.keys().then(names => {
        names.forEach(name => {
          caches.delete(name).catch(console.error);
        });
      }).catch(console.error);
    }

    // Clear session storage for non-essential data
    try {
      const keysToKeep = ['auth_token', 'user_id', 'tenant_id'];
      const allKeys = Object.keys(sessionStorage);
      
      allKeys.forEach(key => {
        if (!keysToKeep.includes(key)) {
          sessionStorage.removeItem(key);
        }
      });
    } catch (e) {
      console.error('Failed to clear session storage:', e);
    }

    // Force garbage collection if available (non-standard)
    if (typeof (globalThis as any).gc === 'function') {
      (globalThis as any).gc();
    }
  }

  /**
   * Refresh authentication token
   */
  private async refreshAuthToken(): Promise<void> {
    // This would typically call your auth service
    // Placeholder implementation
    const refreshToken = localStorage.getItem('refresh_token');
    
    if (!refreshToken) {
      throw new Error('No refresh token available');
    }

    // Simulate token refresh
    await new Promise(resolve => setTimeout(resolve, 1000));
    
    // In real implementation, this would call your auth endpoint
    // and update the stored tokens
  }

  /**
   * Get recovery statistics
   */
  getStats(): {
    totalStrategies: number;
    attemptsByStrategy: Record<string, number>;
    isRecovering: boolean;
  } {
    const attemptsByStrategy: Record<string, number> = {};
    
    for (const [id, attempts] of this.recoveryAttempts.entries()) {
      const strategy = this.strategies.get(id);
      if (strategy) {
        attemptsByStrategy[strategy.name] = attempts;
      }
    }

    return {
      totalStrategies: this.strategies.size,
      attemptsByStrategy,
      isRecovering: this.isRecovering,
    };
  }

  /**
   * Reset all recovery attempts
   */
  resetAttempts(): void {
    this.recoveryAttempts.clear();
    this.lastRecoveryTime.clear();
  }
}

export const errorRecoveryService = new ErrorRecoveryService();