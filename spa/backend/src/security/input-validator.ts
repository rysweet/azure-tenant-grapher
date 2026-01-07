/**
 * Input validation module for command injection prevention
 * Implements whitelisting, sanitization, and path validation
 */

import * as path from 'path';
import { createHash } from 'crypto';

// Whitelist of allowed commands
const ALLOWED_COMMANDS = new Set([
  'scan',
  'generate-spec',
  'generate-iac',
  'undeploy',
  'create-tenant',
  'threat-model',
  'config',
  'cli',
  'agent-mode'
]);

// Whitelist of allowed CLI arguments
const ALLOWED_ARGS = new Set([
  '--tenant-id',
  '--subscription-id',
  '--filter-by-subscriptions',
  '--filter-by-rgs',
  '--tenant-name',
  '--resource-group',
  '--filters',
  '--format',
  '--output',
  '--dry-run',
  '--verbose',
  '--debug',
  '--help',
  '--max-llm-threads',
  '--max-build-threads',
  '--resource-limit',
  '--rebuild-edges',
  '--visualize',
  '--visualize-only',
  '--container-only',
  '--skip-container',
  '--question',
  '-h',
  '-v'
]);

// Maximum lengths for various inputs
const MAX_LENGTHS = {
  command: 50,
  arg: 500,  // Increased for agent-mode questions
  path: 260,
  tenantName: 50,
  resourceGroup: 90
};

// Dangerous characters and patterns
const DANGEROUS_PATTERNS = [
  /[;&|`$(){}[\]<>]/g,  // Shell metacharacters
  /\.\./g,               // Path traversal
  ///^-/,                  // Options that could be interpreted as flags
  /\0/g,                 // Null bytes
  /[\r\n]/g              // Line breaks
];

export interface ValidationResult {
  isValid: boolean;
  sanitized?: string | string[];
  error?: string;
}

export class InputValidator {
  /**
   * Validate a command against the whitelist
   */
  static validateCommand(command: string): ValidationResult {
    if (!command || typeof command !== 'string') {
      return { isValid: false, error: 'Command must be a non-empty string' };
    }

    if (command.length > MAX_LENGTHS.command) {
      return { isValid: false, error: `Command exceeds maximum length of ${MAX_LENGTHS.command}` };
    }

    const sanitized = command.trim().toLowerCase();

    if (!ALLOWED_COMMANDS.has(sanitized)) {
      return { isValid: false, error: `Command '${sanitized}' is not allowed` };
    }

    return { isValid: true, sanitized };
  }

  /**
   * Validate and sanitize command arguments
   */
  static validateArguments(args: string[]): ValidationResult {
    if (!Array.isArray(args)) {
      return { isValid: false, error: 'Arguments must be an array' };
    }

    const sanitizedArgs: string[] = [];

    for (let i = 0; i < args.length; i++) {
      const arg = args[i];

      if (typeof arg !== 'string') {
        return { isValid: false, error: `Argument at index ${i} must be a string` };
      }

      if (arg.length > MAX_LENGTHS.arg) {
        return { isValid: false, error: `Argument at index ${i} exceeds maximum length` };
      }

      // Check for dangerous patterns
      for (const pattern of DANGEROUS_PATTERNS) {
        if (pattern.test(arg)) {
          return { isValid: false, error: `Argument contains dangerous characters: ${arg}` };
        }
      }

      // If it's a flag, validate against whitelist
      if (arg.startsWith('--') || arg.startsWith('-')) {
        const flag = arg.split('=')[0]; // Handle --flag=value format
        if (!ALLOWED_ARGS.has(flag)) {
          return { isValid: false, error: `Flag '${flag}' is not allowed` };
        }
      }

      sanitizedArgs.push(arg);
    }

    return { isValid: true, sanitized: sanitizedArgs };
  }

  /**
   * Validate tenant name
   */
  static validateTenantName(tenantName: string): ValidationResult {
    if (!tenantName || typeof tenantName !== 'string') {
      return { isValid: false, error: 'Tenant name must be a non-empty string' };
    }

    if (tenantName.length > MAX_LENGTHS.tenantName) {
      return { isValid: false, error: `Tenant name exceeds maximum length of ${MAX_LENGTHS.tenantName}` };
    }

    // Allow only alphanumeric, dash, and underscore
    const pattern = /^[a-zA-Z0-9_-]+$/;
    if (!pattern.test(tenantName)) {
      return { isValid: false, error: 'Tenant name contains invalid characters' };
    }

    return { isValid: true, sanitized: tenantName };
  }

  /**
   * Validate resource group name
   */
  static validateResourceGroup(resourceGroup: string): ValidationResult {
    if (!resourceGroup || typeof resourceGroup !== 'string') {
      return { isValid: false, error: 'Resource group must be a non-empty string' };
    }

    if (resourceGroup.length > MAX_LENGTHS.resourceGroup) {
      return { isValid: false, error: `Resource group exceeds maximum length of ${MAX_LENGTHS.resourceGroup}` };
    }

    // Azure resource group naming rules
    const pattern = /^[a-zA-Z0-9._()-]+$/;
    if (!pattern.test(resourceGroup)) {
      return { isValid: false, error: 'Resource group contains invalid characters' };
    }

    return { isValid: true, sanitized: resourceGroup };
  }

  /**
   * Validate file path to prevent path traversal
   */
  static validatePath(filePath: string, baseDir: string): ValidationResult {
    if (!filePath || typeof filePath !== 'string') {
      return { isValid: false, error: 'Path must be a non-empty string' };
    }

    if (filePath.length > MAX_LENGTHS.path) {
      return { isValid: false, error: `Path exceeds maximum length of ${MAX_LENGTHS.path}` };
    }

    // Resolve the absolute path
    const resolvedPath = path.resolve(baseDir, filePath);
    const resolvedBase = path.resolve(baseDir);

    // Ensure the resolved path is within the base directory
    if (!resolvedPath.startsWith(resolvedBase)) {
      return { isValid: false, error: 'Path traversal detected' };
    }

    // Check for dangerous patterns
    if (filePath.includes('..') || filePath.includes('\0')) {
      return { isValid: false, error: 'Path contains dangerous characters' };
    }

    return { isValid: true, sanitized: resolvedPath };
  }

  /**
   * Validate resource filters
   */
  static validateFilters(filters: string[]): ValidationResult {
    if (!Array.isArray(filters)) {
      return { isValid: false, error: 'Filters must be an array' };
    }

    const sanitizedFilters: string[] = [];
    const allowedFilterPattern = /^[a-zA-Z0-9_-]+$/;

    for (const filter of filters) {
      if (typeof filter !== 'string') {
        return { isValid: false, error: 'Each filter must be a string' };
      }

      if (filter.length > MAX_LENGTHS.resourceGroup) {
        return { isValid: false, error: `Filter '${filter}' exceeds maximum length` };
      }

      if (!allowedFilterPattern.test(filter)) {
        return { isValid: false, error: `Filter '${filter}' contains invalid characters` };
      }

      sanitizedFilters.push(filter);
    }

    return { isValid: true, sanitized: sanitizedFilters.join(',') };
  }

  /**
   * Create a safe command object for execution
   */
  static createSafeCommand(command: string, args: string[], options?: {
    tenantName?: string;
    resourceGroup?: string;
    filters?: string[];
  }): { command: string; args: string[]; hash: string } | null {
    // Validate command
    const cmdResult = this.validateCommand(command);
    if (!cmdResult.isValid) {
      console.error('Command validation failed:', cmdResult.error);
      return null;
    }

    // Build safe arguments
    const safeArgs: string[] = [];

    // Add validated options
    if (options?.tenantName) {
      const tenantResult = this.validateTenantName(options.tenantName);
      if (!tenantResult.isValid) {
        console.error('Tenant name validation failed:', tenantResult.error);
        return null;
      }
      safeArgs.push('--tenant-name', tenantResult.sanitized as string);
    }

    if (options?.resourceGroup) {
      const rgResult = this.validateResourceGroup(options.resourceGroup);
      if (!rgResult.isValid) {
        console.error('Resource group validation failed:', rgResult.error);
        return null;
      }
      safeArgs.push('--resource-group', rgResult.sanitized as string);
    }

    if (options?.filters && options.filters.length > 0) {
      const filterResult = this.validateFilters(options.filters);
      if (!filterResult.isValid) {
        console.error('Filter validation failed:', filterResult.error);
        return null;
      }
      safeArgs.push('--filters', filterResult.sanitized as string);
    }

    // Validate additional arguments
    if (args && args.length > 0) {
      const argsResult = this.validateArguments(args);
      if (!argsResult.isValid) {
        console.error('Arguments validation failed:', argsResult.error);
        return null;
      }
      safeArgs.push(...args);
    }

    // Create a hash of the command for logging/auditing
    const commandString = `${cmdResult.sanitized as string} ${safeArgs.join(' ')}`;
    const hash = createHash('sha256').update(commandString).digest('hex').substring(0, 8);

    return {
      command: cmdResult.sanitized as string,
      args: safeArgs,
      hash
    };
  }

  /**
   * Sanitize output before sending to client
   */
  static sanitizeOutput(output: string): string {
    if (typeof output !== 'string') {
      return '';
    }

    // Remove ALL ANSI escape codes (colors, cursor movement, etc.)
    // This regex matches: ESC [ ... (any letter or @)
    // eslint-disable-next-line no-control-regex
    const ansiRegex = /\x1b\[[0-9;?]*[a-zA-Z@]/g;
    let sanitized = output.replace(ansiRegex, '');

    // Remove potential sensitive patterns (customize based on your needs)
    const sensitivePatterns = [
      /password\s*=\s*['"]?[^'"\s]+/gi,
      /api[_-]?key\s*=\s*['"]?[^'"\s]+/gi,
      /secret\s*=\s*['"]?[^'"\s]+/gi,
      /token\s*=\s*['"]?[^'"\s]+/gi
    ];

    for (const pattern of sensitivePatterns) {
      sanitized = sanitized.replace(pattern, '[REDACTED]');
    }

    return sanitized;
  }
}

// Additional validation functions needed by server-secure.ts
export function validateProcessId(processId: string): boolean {
  // UUID v4 format validation
  const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
  return uuidRegex.test(processId);
}

export function validateNodeId(nodeId: string): boolean {
  // Basic validation for node IDs (alphanumeric, dash, underscore)
  if (!nodeId || typeof nodeId !== 'string') return false;
  if (nodeId.length > 100) return false;
  const pattern = /^[a-zA-Z0-9_-]+$/;
  return pattern.test(nodeId);
}

export function validateSearchQuery(query: string): ValidationResult {
  if (!query || typeof query !== 'string') {
    return { isValid: false, error: 'Query must be a non-empty string' };
  }

  if (query.length > 200) {
    return { isValid: false, error: 'Query exceeds maximum length of 200' };
  }

  // Remove potentially dangerous characters but allow spaces for search
  const sanitized = query.replace(/[;<>{}[\]()]/g, '').trim();

  return { isValid: true, sanitized };
}

export function validateFilePath(filePath: string, baseDir: string): ValidationResult {
  return InputValidator.validatePath(filePath, baseDir);
}

// Export static methods for backward compatibility
export const validateCommand = InputValidator.validateCommand.bind(InputValidator);
export const validateArguments = InputValidator.validateArguments.bind(InputValidator);
export const sanitizeOutput = InputValidator.sanitizeOutput.bind(InputValidator);
