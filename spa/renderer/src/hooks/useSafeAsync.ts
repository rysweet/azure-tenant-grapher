import { useState, useCallback, useRef, useEffect } from 'react';
import { errorService } from '../services/errorService';

interface UseSafeAsyncState<T> {
  data: T | null;
  error: Error | null;
  loading: boolean;
}

interface UseSafeAsyncOptions {
  onError?: (error: Error) => void;
  retries?: number;
  retryDelay?: number;
  maxRetryDelay?: number; // Maximum delay between retries
  onCleanup?: () => void; // Cleanup function called on unmount or reset
  timeout?: number; // Operation timeout in milliseconds
}

/**
 * Hook for safely executing async operations with built-in error handling
 */
export function useSafeAsync<T = any>(
  asyncFunction: (...args: any[]) => Promise<T>,
  options: UseSafeAsyncOptions = {}
): [
  UseSafeAsyncState<T>,
  (...args: any[]) => Promise<void>,
  () => void
] {
  const [state, setState] = useState<UseSafeAsyncState<T>>({
    data: null,
    error: null,
    loading: false,
  });

  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);
  const timeoutIdRef = useRef<NodeJS.Timeout | null>(null);
  const cleanupCallbacksRef = useRef<Set<() => void>>(new Set());

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      
      // Cancel any pending operations on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
      
      // Clear any pending timeouts
      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }
      
      // Execute cleanup callbacks
      cleanupCallbacksRef.current.forEach(callback => {
        try {
          callback();
        } catch (cleanupError) {
          // Console error removed
        }
      });
      cleanupCallbacksRef.current.clear();
      
      // Call user-provided cleanup
      if (options.onCleanup) {
        try {
          options.onCleanup();
        } catch (cleanupError) {
          // Console error removed
        }
      }
    };
  }, [options]);

  const execute = useCallback(
    async (...args: any[]) => {
      // Cancel any previous operation
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }

      // Clear any pending timeout
      if (timeoutIdRef.current) {
        clearTimeout(timeoutIdRef.current);
        timeoutIdRef.current = null;
      }

      // Create new abort controller for this operation
      abortControllerRef.current = new AbortController();

      setState({ data: null, error: null, loading: true });

      let lastError: Error | null = null;
      const maxRetries = options.retries || 0;
      const retryDelay = options.retryDelay || 1000;
      const maxRetryDelay = options.maxRetryDelay || 30000;
      const timeout = options.timeout || 0;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          // Check if component is still mounted
          if (!isMountedRef.current) {
            return;
          }

          let result: T;
          
          // Execute with timeout if specified
          if (timeout > 0) {
            const timeoutPromise = new Promise<never>((_, reject) => {
              timeoutIdRef.current = setTimeout(() => {
                reject(new Error(`Operation timed out after ${timeout}ms`));
              }, timeout);
            });
            
            try {
              result = await Promise.race([
                asyncFunction(...args),
                timeoutPromise
              ]);
            } finally {
              // Clear timeout if operation completed
              if (timeoutIdRef.current) {
                clearTimeout(timeoutIdRef.current);
                timeoutIdRef.current = null;
              }
            }
          } else {
            // Execute without timeout
            result = await asyncFunction(...args);
          }

          // Check again if component is still mounted before updating state
          if (!isMountedRef.current) {
            return;
          }

          setState({ data: result, error: null, loading: false });
          return;
        } catch (error) {
          lastError = error instanceof Error ? error : new Error(String(error));

          // Don't retry if operation was aborted
          if (lastError.name === 'AbortError') {
            if (isMountedRef.current) {
              setState({ data: null, error: lastError, loading: false });
            }
            return;
          }

          // Log the error
          errorService.handleAsyncError(lastError, asyncFunction.name || 'anonymous');

          // Call custom error handler
          if (options.onError) {
            options.onError(lastError);
          }

          // If we have retries left, wait and try again
          if (attempt < maxRetries) {
            // Calculate delay with exponential backoff
            const delay = Math.min(
              retryDelay * Math.pow(2, attempt),
              maxRetryDelay
            );
            
            // Use AbortController-aware delay
            await new Promise<void>((resolve, reject) => {
              const timeoutId = setTimeout(resolve, delay);
              
              // Allow abort during retry delay
              const abortHandler = () => {
                clearTimeout(timeoutId);
                reject(new Error('Retry aborted'));
              };
              
              if (abortControllerRef.current) {
                abortControllerRef.current.signal.addEventListener('abort', abortHandler, { once: true });
              }
            }).catch(() => {
              // Retry was aborted
              throw new Error('Operation cancelled');
            });
          }
        }
      }

      // All retries failed
      if (isMountedRef.current && lastError) {
        setState({ data: null, error: lastError, loading: false });
      }
    },
    [asyncFunction, options]
  );

  const reset = useCallback(() => {
    // Cancel any pending operations
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    
    // Clear any pending timeouts
    if (timeoutIdRef.current) {
      clearTimeout(timeoutIdRef.current);
      timeoutIdRef.current = null;
    }
    
    // Execute cleanup callbacks
    cleanupCallbacksRef.current.forEach(callback => {
      try {
        callback();
      } catch (cleanupError) {
        // Console error removed
      }
    });
    
    setState({ data: null, error: null, loading: false });
  }, []);

  return [state, execute, reset];
}

/**
 * Hook for managing multiple async operations
 */
export function useSafeAsyncEffect(
  effect: () => Promise<void>,
  deps: React.DependencyList,
  options: UseSafeAsyncOptions = {}
): void {
  const isMountedRef = useRef(true);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Create new abort controller for this effect
    abortControllerRef.current = new AbortController();
    const currentController = abortControllerRef.current;

    const runEffect = async () => {
      try {
        if (!currentController.signal.aborted && isMountedRef.current) {
          // Run effect with timeout if specified
          if (options.timeout) {
            const timeoutPromise = new Promise<never>((_, reject) => {
              setTimeout(() => {
                reject(new Error(`Effect timed out after ${options.timeout}ms`));
              }, options.timeout);
            });
            
            await Promise.race([
              effect(),
              timeoutPromise
            ]);
          } else {
            await effect();
          }
        }
      } catch (error) {
        if (!currentController.signal.aborted && isMountedRef.current) {
          const err = error instanceof Error ? error : new Error(String(error));
          errorService.handleAsyncError(err, 'useEffect');
          
          if (options.onError) {
            options.onError(err);
          }
        }
      }
    };

    runEffect();

    return () => {
      // Abort the effect on cleanup
      currentController.abort();
      
      // Call user-provided cleanup
      if (options.onCleanup) {
        try {
          options.onCleanup();
        } catch (cleanupError) {
          // Console error removed
        }
      }
    };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);
}

export default useSafeAsync;