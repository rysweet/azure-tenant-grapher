"use strict";
/**
 * Input validation module for command injection prevention
 * Implements whitelisting, sanitization, and path validation
 */
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.InputValidator = void 0;
const path = __importStar(require("path"));
const crypto_1 = require("crypto");
// Whitelist of allowed commands
const ALLOWED_COMMANDS = new Set([
    'scan',
    'generate-spec',
    'generate-iac',
    'undeploy',
    'create-tenant',
    'threat-model',
    'config',
    'cli'
]);
// Whitelist of allowed CLI arguments
const ALLOWED_ARGS = new Set([
    '--tenant-name',
    '--resource-group',
    '--filters',
    '--format',
    '--output',
    '--dry-run',
    '--verbose',
    '--debug',
    '--help',
    '-h',
    '-v'
]);
// Maximum lengths for various inputs
const MAX_LENGTHS = {
    command: 50,
    arg: 100,
    path: 260,
    tenantName: 50,
    resourceGroup: 90
};
// Dangerous characters and patterns
const DANGEROUS_PATTERNS = [
    /[;&|`$(){}[\]<>]/g, // Shell metacharacters
    /\.\./g, // Path traversal
    /^-/, // Options that could be interpreted as flags
    /\0/g, // Null bytes
    /[\r\n]/g // Line breaks
];
class InputValidator {
    /**
     * Validate a command against the whitelist
     */
    static validateCommand(command) {
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
    static validateArguments(args) {
        if (!Array.isArray(args)) {
            return { isValid: false, error: 'Arguments must be an array' };
        }
        const sanitizedArgs = [];
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
        return { isValid: true, sanitized: sanitizedArgs.join(' ') };
    }
    /**
     * Validate tenant name
     */
    static validateTenantName(tenantName) {
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
    static validateResourceGroup(resourceGroup) {
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
    static validatePath(filePath, baseDir) {
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
    static validateFilters(filters) {
        if (!Array.isArray(filters)) {
            return { isValid: false, error: 'Filters must be an array' };
        }
        const sanitizedFilters = [];
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
    static createSafeCommand(command, args, options) {
        // Validate command
        const cmdResult = this.validateCommand(command);
        if (!cmdResult.isValid) {
            console.error('Command validation failed:', cmdResult.error);
            return null;
        }
        // Build safe arguments
        const safeArgs = [];
        // Add validated options
        if (options?.tenantName) {
            const tenantResult = this.validateTenantName(options.tenantName);
            if (!tenantResult.isValid) {
                console.error('Tenant name validation failed:', tenantResult.error);
                return null;
            }
            safeArgs.push('--tenant-name', tenantResult.sanitized);
        }
        if (options?.resourceGroup) {
            const rgResult = this.validateResourceGroup(options.resourceGroup);
            if (!rgResult.isValid) {
                console.error('Resource group validation failed:', rgResult.error);
                return null;
            }
            safeArgs.push('--resource-group', rgResult.sanitized);
        }
        if (options?.filters && options.filters.length > 0) {
            const filterResult = this.validateFilters(options.filters);
            if (!filterResult.isValid) {
                console.error('Filter validation failed:', filterResult.error);
                return null;
            }
            safeArgs.push('--filters', filterResult.sanitized);
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
        const commandString = `${cmdResult.sanitized} ${safeArgs.join(' ')}`;
        const hash = (0, crypto_1.createHash)('sha256').update(commandString).digest('hex').substring(0, 8);
        return {
            command: cmdResult.sanitized,
            args: safeArgs,
            hash
        };
    }
    /**
     * Sanitize output before sending to client
     */
    static sanitizeOutput(output) {
        if (typeof output !== 'string') {
            return '';
        }
        // Remove ANSI escape codes
        const ansiRegex = /\x1b\[[0-9;]*m/g;
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
exports.InputValidator = InputValidator;
//# sourceMappingURL=input-validator.js.map