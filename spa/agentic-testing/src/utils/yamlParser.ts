/**
 * YAML parsing utilities for test scenarios
 * Handles loading, parsing, validation, and variable substitution
 */

import * as yaml from 'js-yaml';
import fs from 'fs/promises';
import path from 'path';
import { TestScenario, TestStep, VerificationStep, Priority, TestInterface } from '../models/TestModels';

/**
 * YAML parsing error class
 */
export class YamlParseError extends Error {
  constructor(message: string, public fileName?: string, public lineNumber?: number) {
    super(message);
    this.name = 'YamlParseError';
  }
}

/**
 * Validation error class
 */
export class ValidationError extends Error {
  constructor(message: string, public field?: string, public value?: any) {
    super(message);
    this.name = 'ValidationError';
  }
}

/**
 * Variable substitution context
 */
export interface VariableContext {
  /** Environment variables */
  env: Record<string, string>;
  /** Global variables */
  global: Record<string, any>;
  /** Scenario-specific variables */
  scenario: Record<string, any>;
}

/**
 * YAML include directive
 */
interface IncludeDirective {
  include: string;
  variables?: Record<string, any>;
}

/**
 * Raw YAML scenario structure (before validation)
 */
interface RawScenario {
  id?: string;
  name?: string;
  description?: string;
  priority?: string;
  interface?: string;
  prerequisites?: string[];
  steps?: any[];
  verifications?: any[];
  expectedOutcome?: string;
  estimatedDuration?: number;
  tags?: string[];
  enabled?: boolean;
  environment?: Record<string, string>;
  cleanup?: any[];
  variables?: Record<string, any>;
  includes?: string[];
}

/**
 * YAML parser configuration
 */
export interface YamlParserConfig {
  /** Base directory for resolving includes */
  baseDir: string;
  /** Maximum recursion depth for includes */
  maxIncludeDepth: number;
  /** Whether to validate schemas strictly */
  strictValidation: boolean;
  /** Custom variable resolvers */
  variableResolvers: Record<string, (value: any) => any>;
  /** Default environment variables */
  defaultEnvironment: Record<string, string>;
}

/**
 * Default parser configuration
 */
const DEFAULT_CONFIG: YamlParserConfig = {
  baseDir: process.cwd(),
  maxIncludeDepth: 5,
  strictValidation: true,
  variableResolvers: {},
  defaultEnvironment: {}
};

/**
 * YAML parser for test scenarios
 */
export class YamlParser {
  private config: YamlParserConfig;
  private processedFiles: Set<string> = new Set();

  constructor(config: Partial<YamlParserConfig> = {}) {
    this.config = { ...DEFAULT_CONFIG, ...config };
  }

  /**
   * Load and parse a YAML file containing test scenarios
   */
  async loadScenarios(filePath: string, variables: VariableContext = this.createDefaultVariableContext()): Promise<TestScenario[]> {
    try {
      const absolutePath = path.resolve(this.config.baseDir, filePath);
      const content = await fs.readFile(absolutePath, 'utf-8');

      // Parse YAML content
      const parsed = yaml.load(content) as any;
      if (!parsed) {
        throw new YamlParseError('Empty or invalid YAML file', filePath);
      }

      // Handle includes
      const processedContent = await this.processIncludes(parsed, path.dirname(absolutePath), 0);

      // Substitute variables
      const substitutedContent = this.substituteVariables(processedContent, variables);

      // Convert to scenarios
      if (Array.isArray(substitutedContent)) {
        return substitutedContent.map((scenario, index) => this.validateAndConvertScenario(scenario, `${filePath}[${index}]`));
      } else if (substitutedContent.scenarios) {
        return substitutedContent.scenarios.map((scenario: any, index: number) =>
          this.validateAndConvertScenario(scenario, `${filePath}[scenarios][${index}]`)
        );
      } else {
        return [this.validateAndConvertScenario(substitutedContent, filePath)];
      }
    } catch (error) {
      if (error instanceof YamlParseError || error instanceof ValidationError) {
        throw error;
      }
      throw new YamlParseError(`Failed to load YAML file: ${error.message}`, filePath);
    }
  }

  /**
   * Load a single scenario from YAML string
   */
  parseScenario(yamlContent: string, variables: VariableContext = this.createDefaultVariableContext()): TestScenario {
    try {
      const parsed = yaml.load(yamlContent) as RawScenario;
      if (!parsed) {
        throw new YamlParseError('Empty or invalid YAML content');
      }

      const substituted = this.substituteVariables(parsed, variables);
      return this.validateAndConvertScenario(substituted, 'inline');
    } catch (error) {
      if (error instanceof YamlParseError || error instanceof ValidationError) {
        throw error;
      }
      throw new YamlParseError(`Failed to parse YAML: ${error.message}`);
    }
  }

  /**
   * Process include directives in YAML content
   */
  private async processIncludes(content: any, baseDir: string, depth: number): Promise<any> {
    if (depth > this.config.maxIncludeDepth) {
      throw new YamlParseError(`Maximum include depth of ${this.config.maxIncludeDepth} exceeded`);
    }

    if (typeof content !== 'object' || content === null) {
      return content;
    }

    if (Array.isArray(content)) {
      return Promise.all(content.map(item => this.processIncludes(item, baseDir, depth)));
    }

    // Handle include directive
    if (content.include && typeof content.include === 'string') {
      const includePath = path.resolve(baseDir, content.include);

      // Prevent circular includes
      if (this.processedFiles.has(includePath)) {
        throw new YamlParseError(`Circular include detected: ${includePath}`);
      }

      this.processedFiles.add(includePath);

      try {
        const includeContent = await fs.readFile(includePath, 'utf-8');
        const parsed = yaml.load(includeContent);

        // Merge variables if provided
        let result = parsed;
        if (content.variables && typeof parsed === 'object') {
          result = this.mergeVariables(parsed, content.variables);
        }

        return this.processIncludes(result, path.dirname(includePath), depth + 1);
      } finally {
        this.processedFiles.delete(includePath);
      }
    }

    // Process includes in object properties
    const result: any = {};
    for (const [key, value] of Object.entries(content)) {
      result[key] = await this.processIncludes(value, baseDir, depth);
    }

    return result;
  }

  /**
   * Substitute variables in content
   */
  private substituteVariables(content: any, variables: VariableContext): any {
    if (typeof content === 'string') {
      return this.substituteStringVariables(content, variables);
    }

    if (typeof content !== 'object' || content === null) {
      return content;
    }

    if (Array.isArray(content)) {
      return content.map(item => this.substituteVariables(item, variables));
    }

    const result: any = {};
    for (const [key, value] of Object.entries(content)) {
      result[key] = this.substituteVariables(value, variables);
    }

    return result;
  }

  /**
   * Substitute variables in a string
   */
  private substituteStringVariables(str: string, variables: VariableContext): string {
    return str.replace(/\$\{([^}]+)\}/g, (match, expression) => {
      try {
        // Handle nested property access (e.g., ${env.HOME})
        const parts = expression.split('.');
        let value: any = variables;

        for (const part of parts) {
          if (value && typeof value === 'object' && part in value) {
            value = value[part];
          } else {
            return match; // Keep original if not found
          }
        }

        // Apply custom resolvers if available
        if (parts.length >= 2 && this.config.variableResolvers[parts[0]]) {
          value = this.config.variableResolvers[parts[0]](value);
        }

        return String(value);
      } catch {
        return match; // Keep original on error
      }
    });
  }

  /**
   * Merge variables into content
   */
  private mergeVariables(content: any, variables: Record<string, any>): any {
    if (typeof content !== 'object' || content === null) {
      return content;
    }

    if (Array.isArray(content)) {
      return content;
    }

    return { ...content, variables: { ...content.variables, ...variables } };
  }

  /**
   * Validate and convert raw scenario to TestScenario
   */
  private validateAndConvertScenario(raw: RawScenario, context: string): TestScenario {
    const errors: string[] = [];

    // Required fields
    if (!raw.id) errors.push('id is required');
    if (!raw.name) errors.push('name is required');
    if (!raw.description) errors.push('description is required');

    // Validate priority
    const priority = this.validatePriority(raw.priority);
    if (!priority && this.config.strictValidation) {
      errors.push(`invalid priority: ${raw.priority}`);
    }

    // Validate interface
    const testInterface = this.validateInterface(raw.interface);
    if (!testInterface && this.config.strictValidation) {
      errors.push(`invalid interface: ${raw.interface}`);
    }

    // Validate steps
    const steps = this.validateSteps(raw.steps || []);
    const verifications = this.validateVerifications(raw.verifications || []);

    if (errors.length > 0) {
      throw new ValidationError(`Validation errors in ${context}: ${errors.join(', ')}`);
    }

    return {
      id: raw.id!,
      name: raw.name!,
      description: raw.description!,
      priority: priority || Priority.MEDIUM,
      interface: testInterface || TestInterface.CLI,
      prerequisites: raw.prerequisites || [],
      steps,
      verifications,
      expectedOutcome: raw.expectedOutcome || '',
      estimatedDuration: raw.estimatedDuration || 60,
      tags: raw.tags || [],
      enabled: raw.enabled !== false,
      environment: raw.environment,
      cleanup: raw.cleanup ? this.validateSteps(raw.cleanup) : undefined
    };
  }

  /**
   * Validate priority string
   */
  private validatePriority(priority?: string): Priority | null {
    if (!priority) return null;
    const upperPriority = priority.toUpperCase();
    return Object.values(Priority).includes(upperPriority as Priority) ? upperPriority as Priority : null;
  }

  /**
   * Validate interface string
   */
  private validateInterface(iface?: string): TestInterface | null {
    if (!iface) return null;
    const upperInterface = iface.toUpperCase();
    return Object.values(TestInterface).includes(upperInterface as TestInterface) ? upperInterface as TestInterface : null;
  }

  /**
   * Validate test steps
   */
  private validateSteps(rawSteps: any[]): TestStep[] {
    return rawSteps.map((step, index) => {
      if (typeof step !== 'object' || !step.action || !step.target) {
        throw new ValidationError(`Invalid step at index ${index}: action and target are required`);
      }

      return {
        action: step.action,
        target: step.target,
        value: step.value,
        waitFor: step.waitFor,
        timeout: step.timeout,
        description: step.description,
        expected: step.expected
      };
    });
  }

  /**
   * Validate verification steps
   */
  private validateVerifications(rawVerifications: any[]): VerificationStep[] {
    return rawVerifications.map((verification, index) => {
      if (typeof verification !== 'object' || !verification.type || !verification.target || !verification.expected || !verification.operator) {
        throw new ValidationError(`Invalid verification at index ${index}: type, target, expected, and operator are required`);
      }

      return {
        type: verification.type,
        target: verification.target,
        expected: verification.expected,
        operator: verification.operator,
        description: verification.description
      };
    });
  }

  /**
   * Create default variable context
   */
  private createDefaultVariableContext(): VariableContext {
    return {
      env: { ...process.env, ...this.config.defaultEnvironment } as Record<string, string>,
      global: {},
      scenario: {}
    };
  }

  /**
   * Validate YAML file structure without full parsing
   */
  async validateYamlFile(filePath: string): Promise<{ valid: boolean; errors: string[] }> {
    const errors: string[] = [];

    try {
      const content = await fs.readFile(filePath, 'utf-8');
      const parsed = yaml.load(content);

      if (!parsed) {
        errors.push('Empty or invalid YAML file');
        return { valid: false, errors };
      }

      // Basic structure validation
      if (typeof parsed !== 'object') {
        errors.push('YAML must contain an object or array');
      }

      return { valid: errors.length === 0, errors };
    } catch (error) {
      errors.push(`Failed to parse YAML: ${error.message}`);
      return { valid: false, errors };
    }
  }

  /**
   * Extract variables from YAML content
   */
  extractVariables(content: any): Record<string, any> {
    const variables: Record<string, any> = {};

    const extract = (obj: any, path: string = '') => {
      if (typeof obj !== 'object' || obj === null) return;

      if (Array.isArray(obj)) {
        obj.forEach((item, index) => extract(item, `${path}[${index}]`));
        return;
      }

      for (const [key, value] of Object.entries(obj)) {
        const currentPath = path ? `${path}.${key}` : key;

        if (key === 'variables' && typeof value === 'object') {
          Object.assign(variables, value);
        } else {
          extract(value, currentPath);
        }
      }
    };

    extract(content);
    return variables;
  }

  /**
   * Convert TestScenario back to YAML string
   */
  scenarioToYaml(scenario: TestScenario): string {
    const yamlObject = {
      id: scenario.id,
      name: scenario.name,
      description: scenario.description,
      priority: scenario.priority,
      interface: scenario.interface,
      prerequisites: scenario.prerequisites.length > 0 ? scenario.prerequisites : undefined,
      steps: scenario.steps,
      verifications: scenario.verifications.length > 0 ? scenario.verifications : undefined,
      expectedOutcome: scenario.expectedOutcome,
      estimatedDuration: scenario.estimatedDuration,
      tags: scenario.tags.length > 0 ? scenario.tags : undefined,
      enabled: scenario.enabled,
      environment: scenario.environment,
      cleanup: scenario.cleanup
    };

    // Remove undefined fields
    Object.keys(yamlObject).forEach(key => {
      if (yamlObject[key as keyof typeof yamlObject] === undefined) {
        delete yamlObject[key as keyof typeof yamlObject];
      }
    });

    return yaml.dump(yamlObject, {
      indent: 2,
      lineWidth: 120,
      noRefs: true,
      sortKeys: false
    });
  }
}

/**
 * Create a YAML parser instance
 */
export function createYamlParser(config?: Partial<YamlParserConfig>): YamlParser {
  return new YamlParser(config);
}

/**
 * Convenience function to load scenarios from a file
 */
export async function loadScenariosFromFile(filePath: string, variables?: VariableContext): Promise<TestScenario[]> {
  const parser = createYamlParser();
  return parser.loadScenarios(filePath, variables);
}

/**
 * Convenience function to parse a scenario from YAML string
 */
export function parseScenarioFromYaml(yamlContent: string, variables?: VariableContext): TestScenario {
  const parser = createYamlParser();
  return parser.parseScenario(yamlContent, variables);
}
