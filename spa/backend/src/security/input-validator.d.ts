/**
 * Input validation module for command injection prevention
 * Implements whitelisting, sanitization, and path validation
 */
export interface ValidationResult {
    isValid: boolean;
    sanitized?: string;
    error?: string;
}
export declare class InputValidator {
    /**
     * Validate a command against the whitelist
     */
    static validateCommand(command: string): ValidationResult;
    /**
     * Validate and sanitize command arguments
     */
    static validateArguments(args: string[]): ValidationResult;
    /**
     * Validate tenant name
     */
    static validateTenantName(tenantName: string): ValidationResult;
    /**
     * Validate resource group name
     */
    static validateResourceGroup(resourceGroup: string): ValidationResult;
    /**
     * Validate file path to prevent path traversal
     */
    static validatePath(filePath: string, baseDir: string): ValidationResult;
    /**
     * Validate resource filters
     */
    static validateFilters(filters: string[]): ValidationResult;
    /**
     * Create a safe command object for execution
     */
    static createSafeCommand(command: string, args: string[], options?: {
        tenantName?: string;
        resourceGroup?: string;
        filters?: string[];
    }): {
        command: string;
        args: string[];
        hash: string;
    } | null;
    /**
     * Sanitize output before sending to client
     */
    static sanitizeOutput(output: string): string;
}
//# sourceMappingURL=input-validator.d.ts.map