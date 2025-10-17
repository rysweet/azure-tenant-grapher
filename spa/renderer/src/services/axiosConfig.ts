import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { errorService } from './errorService';

// Configure axios defaults
axios.defaults.timeout = 30000; // 30 seconds timeout
axios.defaults.headers.common['Content-Type'] = 'application/json';

// Request interceptor
axios.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Add request timestamp for tracking
    (config as any).metadata = { startTime: new Date() };

    // Log request in development
    if (process.env.NODE_ENV === 'development') {
      // Console log removed
    }

    return config;
  },
  (error: AxiosError) => {
    errorService.handleNetworkError(error, error.config?.url);
    return Promise.reject(error);
  }
);

// Response interceptor
axios.interceptors.response.use(
  (response: AxiosResponse) => {
    // Calculate request duration
    const startTime = (response.config as any).metadata?.startTime;
    if (startTime) {
      const duration = new Date().getTime() - new Date(startTime).getTime();

      // Log slow requests
      if (duration > 5000) {
        errorService.logWarning(`Slow request detected: ${response.config.url} took ${duration}ms`, {
          url: response.config.url,
          method: response.config.method,
          duration
        });
      }
    }

    return response;
  },
  (error: AxiosError) => {
    // Don't log cancelled requests as errors
    if (axios.isCancel(error)) {
      // Console log removed
      return Promise.reject(error);
    }

    const errorDetails: any = {
      url: (error as any).config?.url,
      method: (error as any).config?.method,
      status: (error as any).response?.status,
      statusText: (error as any).response?.statusText,
      data: (error as any).response?.data,
    };

    // Categorize errors
    if ((error as any).code === 'ECONNABORTED' || (error as any).message?.includes('timeout')) {
      errorService.logError(
        `Request timeout: ${(error as any).config?.url}`,
        'network',
        { ...errorDetails, type: 'timeout' }
      );
    } else if (!(error as any).response) {
      // Network error (no response received)
      errorService.logError(
        `Network error: ${(error as any).message}`,
        'network',
        { ...errorDetails, type: 'network_failure' }
      );
    } else {
      // Server responded with error status
      const status = (error as any).response.status;
      const message = (error as any).response?.data?.message || (error as any).message;

      if (status >= 500) {
        errorService.logError(
          `Server error (${status}): ${message}`,
          'network',
          { ...errorDetails, type: 'server_error' }
        );
      } else if (status === 404) {
        errorService.logWarning(
          `Resource not found: ${(error as any).config?.url}`,
          errorDetails
        );
      } else if (status === 401 || status === 403) {
        errorService.logError(
          `Authentication/Authorization error (${status}): ${message}`,
          'network',
          { ...errorDetails, type: 'auth_error' }
        );
      } else if (status >= 400) {
        errorService.logError(
          `Client error (${status}): ${message}`,
          'network',
          { ...errorDetails, type: 'client_error' }
        );
      }
    }

    // Return user-friendly error message
    const userMessage = getUserFriendlyErrorMessage(error);
    (error as any).userMessage = userMessage;

    return Promise.reject(error);
  }
);

/**
 * Get user-friendly error message
 */
function getUserFriendlyErrorMessage(error: AxiosError): string {
  if (!error.response) {
    if ((error as any).code === 'ECONNABORTED' || (error as any).message?.includes('timeout')) {
      return 'Request timed out. Please try again.';
    }
    return 'Unable to connect to the server. Please check your connection.';
  }

  const status = error.response.status;
  const serverMessage = (error.response.data as any)?.message;

  if (serverMessage && typeof serverMessage === 'string') {
    return serverMessage;
  }

  switch (status) {
    case 400:
      return 'Invalid request. Please check your input.';
    case 401:
      return 'Authentication required. Please log in.';
    case 403:
      return 'You do not have permission to perform this action.';
    case 404:
      return 'The requested resource was not found.';
    case 429:
      return 'Too many requests. Please slow down.';
    case 500:
      return 'Server error. Please try again later.';
    case 502:
    case 503:
      return 'Service temporarily unavailable. Please try again later.';
    default:
      if (status >= 500) {
        return 'Server error. Please try again later.';
      }
      if (status >= 400) {
        return 'Request failed. Please try again.';
      }
      return 'An unexpected error occurred.';
  }
}

/**
 * Create a cancellable request
 */
export function createCancellableRequest() {
  const source = axios.CancelToken.source();
  return {
    token: source.token,
    cancel: (message?: string) => source.cancel(message || 'Request cancelled by user'),
  };
}

/**
 * Retry configuration for specific endpoints
 */
export const retryConfig = {
  retries: 3,
  retryDelay: (retryCount: number) => retryCount * 1000,
  retryCondition: (error: AxiosError) => {
    // Retry on network errors and 5xx errors
    return !error.response || (error.response.status >= 500 && error.response.status < 600);
  },
};

export default axios;
