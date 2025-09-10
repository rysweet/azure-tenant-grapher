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

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      // Cancel any pending operations on unmount
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  const execute = useCallback(
    async (...args: any[]) => {
      // Cancel any previous operation
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }

      // Create new abort controller for this operation
      abortControllerRef.current = new AbortController();

      setState({ data: null, error: null, loading: true });

      let lastError: Error | null = null;
      const maxRetries = options.retries || 0;
      const retryDelay = options.retryDelay || 1000;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          // Check if component is still mounted
          if (!isMountedRef.current) {
            return;
          }

          // Execute the async function
          const result = await asyncFunction(...args);

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
            await new Promise(resolve => setTimeout(resolve, retryDelay * (attempt + 1)));
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
    }
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

  useEffect(() => {
    let cancelled = false;

    const runEffect = async () => {
      try {
        if (!cancelled && isMountedRef.current) {
          await effect();
        }
      } catch (error) {
        if (!cancelled && isMountedRef.current) {
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
      cancelled = true;
    };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
    };
  }, []);
}

export default useSafeAsync;