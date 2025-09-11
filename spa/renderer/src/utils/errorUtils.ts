import { errorService } from '../services/errorService';

/**
 * Wraps an async function with error handling
 */
export async function withErrorHandling<T>(
  operation: () => Promise<T>,
  operationName: string,
  options?: {
    fallbackValue?: T;
    retries?: number;
    retryDelay?: number;
    onError?: (error: Error) => void;
    rethrow?: boolean;
  }
): Promise<T | undefined> {
  const { 
    fallbackValue, 
    retries = 0, 
    retryDelay = 1000, 
    onError,
    rethrow = false 
  } = options || {};

  let lastError: Error | null = null;
  let attempt = 0;

  while (attempt <= retries) {
    try {
      return await operation();
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      
      errorService.handleAsyncError(lastError, operationName);

      if (onError) {
        onError(lastError);
      }

      if (attempt < retries) {
        attempt++;
        await delay(retryDelay * attempt); // Exponential backoff
      } else {
        break;
      }
    }
  }

  if (rethrow && lastError) {
    throw lastError;
  }

  return fallbackValue;
}

/**
 * Wraps a network request with error handling
 */
export async function withNetworkErrorHandling<T>(
  request: () => Promise<T>,
  endpoint: string,
  options?: {
    fallbackValue?: T;
    retries?: number;
    retryDelay?: number;
    onError?: (error: any) => void;
    rethrow?: boolean;
  }
): Promise<T | undefined> {
  const { 
    fallbackValue, 
    retries = 2, 
    retryDelay = 1000, 
    onError,
    rethrow = false 
  } = options || {};

  let lastError: any = null;
  let attempt = 0;

  while (attempt <= retries) {
    try {
      return await request();
    } catch (error) {
      lastError = error;
      
      errorService.handleNetworkError(error, endpoint);

      if (onError) {
        onError(error);
      }

      // Don't retry on client errors (4xx)
      if (error?.response?.status >= 400 && error?.response?.status < 500) {
        break;
      }

      if (attempt < retries) {
        attempt++;
        await delay(retryDelay * attempt); // Exponential backoff
      } else {
        break;
      }
    }
  }

  if (rethrow && lastError) {
    throw lastError;
  }

  return fallbackValue;
}

/**
 * Creates a debounced version of an async function with error handling
 */
export function createSafeAsyncHandler<T extends (...args: any[]) => Promise<any>>(
  handler: T,
  operationName: string,
  debounceMs: number = 0
): (...args: Parameters<T>) => Promise<ReturnType<T> | undefined> {
  let timeoutId: NodeJS.Timeout | null = null;

  return async (...args: Parameters<T>): Promise<ReturnType<T> | undefined> => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    return new Promise((resolve) => {
      const execute = async () => {
        try {
          const result = await handler(...args);
          resolve(result);
        } catch (error) {
          const err = error instanceof Error ? error : new Error(String(error));
          errorService.handleAsyncError(err, operationName);
          resolve(undefined);
        }
      };

      if (debounceMs > 0) {
        timeoutId = setTimeout(execute, debounceMs);
      } else {
        execute();
      }
    });
  };
}

/**
 * Wraps event handlers with error handling
 */
export function createSafeEventHandler<T extends (...args: any[]) => void>(
  handler: T,
  componentName: string
): T {
  return ((...args: Parameters<T>) => {
    try {
      handler(...args);
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      errorService.logError(err, 'component', { componentName });
    }
  }) as T;
}

/**
 * Helper to delay execution
 */
function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Safe JSON parse with error handling
 */
export function safeJsonParse<T>(json: string, fallback: T): T {
  try {
    return JSON.parse(json);
  } catch (error) {
    errorService.logWarning(`Failed to parse JSON: ${error}`, { json: json.substring(0, 100) });
    return fallback;
  }
}

/**
 * Safe local storage operations
 */
export const safeStorage = {
  getItem<T>(key: string, fallback: T): T {
    try {
      const item = localStorage.getItem(key);
      if (item === null) return fallback;
      return safeJsonParse(item, fallback);
    } catch (error) {
      errorService.logWarning(`Failed to get localStorage item: ${key}`, { error });
      return fallback;
    }
  },

  setItem(key: string, value: any): boolean {
    try {
      localStorage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      errorService.logWarning(`Failed to set localStorage item: ${key}`, { error });
      return false;
    }
  },

  removeItem(key: string): boolean {
    try {
      localStorage.removeItem(key);
      return true;
    } catch (error) {
      errorService.logWarning(`Failed to remove localStorage item: ${key}`, { error });
      return false;
    }
  }
};

export default {
  withErrorHandling,
  withNetworkErrorHandling,
  createSafeAsyncHandler,
  createSafeEventHandler,
  safeJsonParse,
  safeStorage
};