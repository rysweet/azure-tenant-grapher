/**
 * Error Service for centralized error handling and logging
 */

export interface ErrorLog {
  timestamp: Date;
  message: string;
  stack?: string;
  componentStack?: string;
  errorType: 'component' | 'async' | 'network' | 'unhandled';
  severity: 'error' | 'warning' | 'info';
  metadata?: Record<string, any>;
}

class ErrorService {
  private errorLogs: ErrorLog[] = [];
  private maxLogs = 100;
  private errorListeners: Set<(error: ErrorLog) => void> = new Set();

  /**
   * Log an error with full context
   */
  logError(
    error: Error | string,
    errorType: ErrorLog['errorType'] = 'unhandled',
    metadata?: Record<string, any>,
    componentStack?: string
  ): void {
    const errorLog: ErrorLog = {
      timestamp: new Date(),
      message: typeof error === 'string' ? error : error.message,
      stack: error instanceof Error ? error.stack : undefined,
      componentStack,
      errorType,
      severity: 'error',
      metadata
    };

    this.addLog(errorLog);

    // Console log for development
    // Console error removed

    // Send to backend if available
    this.sendToBackend(errorLog).catch(console.error);

    // Notify listeners
    this.notifyListeners(errorLog);
  }

  /**
   * Log a warning
   */
  logWarning(message: string, metadata?: Record<string, any>): void {
    const errorLog: ErrorLog = {
      timestamp: new Date(),
      message,
      errorType: 'unhandled',
      severity: 'warning',
      metadata
    };

    this.addLog(errorLog);
    // Console warn removed
  }

  /**
   * Log an info message
   */
  logInfo(message: string, metadata?: Record<string, any>): void {
    const errorLog: ErrorLog = {
      timestamp: new Date(),
      message,
      errorType: 'unhandled',
      severity: 'info',
      metadata
    };

    this.addLog(errorLog);
    // Console info removed
  }

  /**
   * Get all error logs
   */
  getErrorLogs(): ErrorLog[] {
    return [...this.errorLogs];
  }

  /**
   * Clear all error logs
   */
  clearLogs(): void {
    this.errorLogs = [];
  }

  /**
   * Subscribe to error events
   */
  subscribe(listener: (error: ErrorLog) => void): () => void {
    this.errorListeners.add(listener);
    return () => this.errorListeners.delete(listener);
  }

  /**
   * Handle network errors specifically
   */
  handleNetworkError(error: any, endpoint?: string): void {
    const message = error.response?.data?.message || error.message || 'Network request failed';
    const status = error.response?.status;

    this.logError(
      `Network Error: ${message}`,
      'network',
      {
        endpoint,
        status,
        statusText: error.response?.statusText,
        data: error.response?.data
      }
    );
  }

  /**
   * Handle async operation errors
   */
  handleAsyncError(error: Error, operation: string): void {
    this.logError(
      error,
      'async',
      { operation }
    );
  }

  private addLog(log: ErrorLog): void {
    this.errorLogs.unshift(log);

    // Keep only recent logs
    if (this.errorLogs.length > this.maxLogs) {
      this.errorLogs = this.errorLogs.slice(0, this.maxLogs);
    }
  }

  private notifyListeners(error: ErrorLog): void {
    this.errorListeners.forEach(listener => {
      try {
        listener(error);
      } catch (err) {
        // Console error removed
      }
    });
  }

  private async sendToBackend(error: ErrorLog): Promise<void> {
    try {
      // Only send errors to backend, not warnings or info
      if (error.severity !== 'error') return;

      const response = await fetch('http://localhost:3001/api/errors/log', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...error,
          userAgent: navigator.userAgent,
          url: window.location.href
        })
      });

      if (!response.ok) {
        // Console warn removed
      }
    } catch (err) {
      // Silently fail - we don't want to create an error loop
      // Console warn removed
    }
  }
}

// Export singleton instance
export const errorService = new ErrorService();

// Setup global error handlers
if (typeof window !== 'undefined') {
  // Handle unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    errorService.logError(
      new Error(event.reason?.message || event.reason || 'Unhandled Promise Rejection'),
      'unhandled',
      {
        promise: event.promise,
        reason: event.reason
      }
    );

    // Prevent default browser behavior
    event.preventDefault();
  });

  // Handle global errors
  window.addEventListener('error', (event) => {
    errorService.logError(
      event.error || new Error(event.message),
      'unhandled',
      {
        filename: event.filename,
        lineno: event.lineno,
        colno: event.colno
      }
    );

    // Prevent default browser behavior
    event.preventDefault();
  });
}

export default errorService;
