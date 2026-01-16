/**
 * Validation utilities for user inputs
 */

/**
 * Validates if a string is a valid UUID format (for tenant IDs)
 */
export const isValidUUID = (id: string): boolean => {
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(id);
};

/**
 * Validates if a string is a valid Azure tenant ID (UUID or domain)
 */
export const isValidTenantId = (id: string): boolean => {
  // Check if it's a UUID
  if (isValidUUID(id)) {
    return true;
  }

  // Check if it's a valid domain format (e.g., contoso.onmicrosoft.com)
  const domainRegex = /^[a-zA-Z0-9][a-zA-Z0-9-]{0,61}[a-zA-Z0-9]?\.[a-zA-Z]{2,}$/;
  return domainRegex.test(id);
};

/**
 * Validates resource limit
 */
export const isValidResourceLimit = (limit: number): boolean => {
  return limit >= 0 && limit <= 10000;
};

/**
 * Validates thread count
 */
export const isValidThreadCount = (count: number): boolean => {
  return count >= 1 && count <= 100;
};

/**
 * Sanitizes file paths to prevent path traversal
 */
export const sanitizeFilePath = (path: string): string => {
  // Remove any path traversal attempts
  return path.replace(/\.\./g, '').replace(/^\//, '');
};

/**
 * Validates comma-separated list of subscription IDs or resource group names
 * Allows alphanumeric, hyphens, underscores, and commas only
 */
export const isValidFilterList = (filterList: string): boolean => {
  if (!filterList || filterList.trim() === '') {
    return true; // Empty is valid (means no filter)
  }

  // Allow alphanumeric, hyphens, underscores, commas, and spaces (trimmed)
  // Each item should be alphanumeric with hyphens/underscores
  const filterRegex = /^[a-zA-Z0-9_-]+(\s*,\s*[a-zA-Z0-9_-]+)*$/;
  return filterRegex.test(filterList.trim());
};

/**
 * Sanitizes error messages to prevent information disclosure
 * Removes sensitive details like file paths, internal IDs, stack traces
 */
export const sanitizeErrorMessage = (error: unknown): string => {
  if (!error) {
    return 'An error occurred';
  }

  let message: string;

  // Extract message from different error types
  if (error instanceof Error) {
    message = error.message;
  } else if (typeof error === 'string') {
    message = error;
  } else if (typeof error === 'object' && error !== null && 'message' in error) {
    message = String((error as { message: unknown }).message);
  } else {
    return 'An error occurred';
  }

  // Remove file paths (Unix and Windows style)
  message = message.replace(/\/[^\s]+\.(ts|tsx|js|jsx|py|java|cs|go)/gi, '[file path]');
  message = message.replace(/[A-Z]:\\[^\s]+\.(ts|tsx|js|jsx|py|java|cs|go)/gi, '[file path]');

  // Remove UUIDs and GUIDs
  message = message.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/gi, '[id]');

  // Remove IP addresses
  message = message.replace(/\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b/g, '[ip address]');

  // Remove port numbers in URLs
  message = message.replace(/:(\d{4,5})\//g, ':[port]/');

  // Remove stack trace indicators
  message = message.replace(/at\s+[^\n]+\([^\)]+\)/g, '');
  message = message.replace(/^\s*at\s+.*/gm, '');

  // Generic error message mapping for common patterns
  if (message.toLowerCase().includes('econnrefused')) {
    return 'Unable to connect to the server. Please check if the backend is running.';
  }
  if (message.toLowerCase().includes('timeout')) {
    return 'The operation timed out. Please try again.';
  }
  if (message.toLowerCase().includes('network')) {
    return 'A network error occurred. Please check your connection.';
  }
  if (message.toLowerCase().includes('permission denied') || message.toLowerCase().includes('unauthorized')) {
    return 'Permission denied. Please check your credentials.';
  }
  if (message.toLowerCase().includes('not found') && message.length < 50) {
    return 'The requested resource was not found.';
  }

  // Truncate very long messages
  if (message.length > 200) {
    message = message.substring(0, 200) + '...';
  }

  return message.trim() || 'An error occurred';
};

/**
 * Type guard to check if error is an Error object
 */
export const isError = (error: unknown): error is Error => {
  return error instanceof Error;
};

/**
 * Type guard to check if error has a response (axios error)
 */
export const hasErrorResponse = (error: unknown): error is { response: { data?: { error?: string } } } => {
  return (
    typeof error === 'object' &&
    error !== null &&
    'response' in error &&
    typeof (error as { response: unknown }).response === 'object' &&
    (error as { response: unknown }).response !== null
  );
};
