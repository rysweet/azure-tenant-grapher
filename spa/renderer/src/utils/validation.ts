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
