/**
 * ComprehensionAgent - Uses LLM to understand features from documentation and generate test scenarios
 *
 * This agent analyzes documentation files to extract feature information and generate comprehensive
 * test scenarios using large language models (OpenAI GPT or Azure OpenAI).
 */

import { readdir, readFile } from 'fs/promises';
import { join, relative } from 'path';
import { glob } from 'glob';
import OpenAI from 'openai';
import { logger } from '../utils/logger';
import { IAgent } from './index';
import { TestScenario, TestStep, VerificationStep, Priority, TestInterface } from '../models/TestModels';

/**
 * LLM provider types
 */
export type LLMProvider = 'openai' | 'azure';

/**
 * LLM configuration interface
 */
export interface LLMConfig {
  /** LLM provider (openai or azure) */
  provider: LLMProvider;
  /** API key for authentication */
  apiKey: string;
  /** Model name/deployment to use */
  model: string;
  /** Temperature for response randomness (0.0 - 1.0) */
  temperature: number;
  /** Maximum tokens in response */
  maxTokens: number;
  /** API version for Azure OpenAI */
  apiVersion?: string;
  /** Azure OpenAI endpoint URL */
  endpoint?: string;
  /** Azure OpenAI deployment name */
  deployment?: string;
}

/**
 * Feature specification extracted from documentation
 */
export interface FeatureSpec {
  /** Feature name */
  name: string;
  /** Purpose and description of the feature */
  purpose: string;
  /** Input parameters and types */
  inputs: FeatureInput[];
  /** Output parameters and types */
  outputs: FeatureOutput[];
  /** Success criteria for the feature */
  successCriteria: string[];
  /** Known failure modes */
  failureModes: string[];
  /** Edge cases to consider */
  edgeCases: string[];
  /** Dependencies on other features */
  dependencies: string[];
}

/**
 * Feature input specification
 */
export interface FeatureInput {
  /** Input parameter name */
  name: string;
  /** Input data type */
  type: string;
  /** Whether input is required */
  required: boolean;
  /** Input description */
  description: string;
}

/**
 * Feature output specification
 */
export interface FeatureOutput {
  /** Output parameter name */
  name: string;
  /** Output data type */
  type: string;
  /** Output description */
  description: string;
}

/**
 * Discovered feature from documentation
 */
export interface DiscoveredFeature {
  /** Feature type (cli, ui, api) */
  type: string;
  /** Feature name */
  name: string;
  /** Context from documentation */
  context: string;
  /** Source file path */
  source: string;
}

/**
 * ComprehensionAgent configuration
 */
export interface ComprehensionAgentConfig {
  /** LLM configuration */
  llm: LLMConfig;
  /** Documentation directory to scan */
  docsDir: string;
  /** File patterns to include */
  includePatterns: string[];
  /** File patterns to exclude */
  excludePatterns: string[];
  /** Maximum context length for LLM */
  maxContextLength: number;
}

/**
 * Documentation loader for parsing markdown files and extracting features
 */
export class DocumentationLoader {
  private docsDir: string;
  private includePatterns: string[];
  private excludePatterns: string[];

  constructor(
    docsDir: string = 'docs',
    includePatterns: string[] = ['**/*.md'],
    excludePatterns: string[] = ['**/node_modules/**']
  ) {
    this.docsDir = docsDir;
    this.includePatterns = includePatterns;
    this.excludePatterns = excludePatterns;
  }

  /**
   * Load all markdown documentation files
   * @returns Dictionary of file paths to content
   */
  async loadMarkdownFiles(): Promise<Record<string, string>> {
    const docs: Record<string, string> = {};

    try {
      // Find all markdown files matching patterns
      const files = await this.findDocumentationFiles();

      logger.info(`Found ${files.length} documentation files to process`);

      // Load content for each file
      for (const file of files) {
        try {
          const content = await readFile(file, 'utf-8');
          const relativePath = relative(process.cwd(), file);
          docs[relativePath] = content;
          logger.debug(`Loaded documentation: ${relativePath}`);
        } catch (error) {
          logger.error(`Failed to load ${file}: ${error}`);
        }
      }

      return docs;
    } catch (error) {
      logger.error(`Error loading documentation files: ${error}`);
      return {};
    }
  }

  /**
   * Find documentation files matching include/exclude patterns
   * @returns Array of file paths
   */
  private async findDocumentationFiles(): Promise<string[]> {
    const allFiles: string[] = [];

    // Search for files matching include patterns
    for (const pattern of this.includePatterns) {
      try {
        const files = await glob(join(this.docsDir, pattern), {
          ignore: this.excludePatterns.map(p => join(this.docsDir, p))
        });
        allFiles.push(...files);
      } catch (error) {
        logger.error(`Error searching for files with pattern ${pattern}: ${error}`);
      }
    }

    // Remove duplicates and return
    const uniqueFiles = Array.from(new Set(allFiles));
    return uniqueFiles;
  }

  /**
   * Extract feature descriptions from documentation content
   * @param content - Documentation content
   * @returns List of discovered features
   */
  extractFeatures(content: string): DiscoveredFeature[] {
    const features: DiscoveredFeature[] = [];

    // Extract CLI commands using regex patterns
    const cliPatterns = [
      /`atg\s+([a-z-]+)`/gi,
      /`azure-tenant-grapher\s+([a-z-]+)`/gi,
      /`uv run atg\s+([a-z-]+)`/gi
    ];

    for (const pattern of cliPatterns) {
      let match;
      while ((match = pattern.exec(content)) !== null) {
        const command = match[1];
        const contextStart = Math.max(0, match.index - 200);
        const contextEnd = Math.min(content.length, match.index + match[0].length + 200);
        const context = content.substring(contextStart, contextEnd);

        features.push({
          type: 'cli',
          name: command,
          context,
          source: ''
        });
      }
    }

    // Extract UI features from headers
    const headerPattern = /^#{1,3}\s+(.+)$/gm;
    let match;
    while ((match = headerPattern.exec(content)) !== null) {
      const header = match[1];
      const headerLower = header.toLowerCase();

      // Check if header indicates UI feature
      if (this.isUIFeature(headerLower)) {
        const contextStart = Math.max(0, match.index - 200);
        const contextEnd = Math.min(content.length, match.index + 500);
        const context = content.substring(contextStart, contextEnd);

        features.push({
          type: 'ui',
          name: header,
          context,
          source: ''
        });
      }
    }

    // Extract API endpoints
    const apiPattern = /(?:GET|POST|PUT|DELETE|PATCH)\s+([/\w-]+)/gi;
    while ((match = apiPattern.exec(content)) !== null) {
      const endpoint = match[1];
      const contextStart = Math.max(0, match.index - 100);
      const contextEnd = Math.min(content.length, match.index + match[0].length + 100);
      const context = content.substring(contextStart, contextEnd);

      features.push({
        type: 'api',
        name: endpoint,
        context,
        source: ''
      });
    }

    return features;
  }

  /**
   * Check if a header text indicates a UI feature
   * @param headerText - Header text in lowercase
   * @returns True if UI feature
   */
  private isUIFeature(headerText: string): boolean {
    const uiKeywords = [
      'tab', 'button', 'page', 'dialog', 'menu', 'panel', 'widget',
      'form', 'input', 'dropdown', 'checkbox', 'radio', 'slider',
      'spa', 'gui', 'interface', 'navigation', 'sidebar', 'toolbar'
    ];

    return uiKeywords.some(keyword => headerText.includes(keyword));
  }
}

/**
 * ComprehensionAgent - Main agent class for feature comprehension and test generation
 */
export class ComprehensionAgent implements IAgent {
  name = 'ComprehensionAgent';
  type = 'comprehension';

  private config: ComprehensionAgentConfig;
  private docLoader: DocumentationLoader;
  private llmClient: OpenAI | null = null;

  constructor(config: ComprehensionAgentConfig) {
    this.config = config;
    this.docLoader = new DocumentationLoader(
      config.docsDir,
      config.includePatterns,
      config.excludePatterns
    );
  }

  /**
   * Initialize the agent and LLM client
   */
  async initialize(): Promise<void> {
    logger.info('Initializing ComprehensionAgent');

    try {
      await this.initializeLLMClient();
      logger.info('ComprehensionAgent initialized successfully');
    } catch (error) {
      logger.error(`Failed to initialize ComprehensionAgent: ${error}`);
      throw error;
    }
  }

  /**
   * Execute test scenario (not used for ComprehensionAgent)
   * @param scenario - Test scenario to execute
   * @returns Execution result
   */
  async execute(scenario: any): Promise<any> {
    logger.warn('ComprehensionAgent.execute() called - this agent generates scenarios, not executes them');
    return { status: 'skipped', reason: 'ComprehensionAgent does not execute scenarios' };
  }

  /**
   * Cleanup resources
   */
  async cleanup(): Promise<void> {
    logger.info('Cleaning up ComprehensionAgent');
    this.llmClient = null;
  }

  /**
   * Initialize the LLM client based on configuration
   */
  private async initializeLLMClient(): Promise<void> {
    const { llm } = this.config;

    if (llm.provider === 'azure') {
      if (!llm.endpoint || !llm.deployment) {
        throw new Error('Azure OpenAI requires endpoint and deployment configuration');
      }

      this.llmClient = new OpenAI({
        apiKey: llm.apiKey,
        baseURL: `${llm.endpoint}/openai/deployments/${llm.deployment}`,
        defaultQuery: { 'api-version': llm.apiVersion || '2024-02-01' },
        defaultHeaders: {
          'api-key': llm.apiKey
        }
      });

      logger.info(`Initialized Azure OpenAI client with deployment: ${llm.deployment}`);
    } else {
      this.llmClient = new OpenAI({
        apiKey: llm.apiKey
      });

      logger.info('Initialized OpenAI client');
    }
  }

  /**
   * Get or create LLM client
   * @returns OpenAI client instance
   */
  private async getLLMClient(): Promise<OpenAI> {
    if (!this.llmClient) {
      await this.initializeLLMClient();
    }
    return this.llmClient!;
  }

  /**
   * Analyze a feature from documentation using LLM
   * @param featureDoc - Feature documentation text
   * @returns FeatureSpec with extracted information
   */
  async analyzeFeature(featureDoc: string): Promise<FeatureSpec> {
    logger.debug('Analyzing feature with LLM');

    try {
      const client = await this.getLLMClient();
      const { llm } = this.config;

      // Truncate context if too long
      const context = featureDoc.length > this.config.maxContextLength
        ? featureDoc.substring(0, this.config.maxContextLength) + '...'
        : featureDoc;

      const prompt = this.buildFeatureAnalysisPrompt(context);

      const response = await client.chat.completions.create({
        model: llm.model,
        messages: [
          {
            role: 'system',
            content: 'You are a test scenario generator and feature analyst. Extract structured information from documentation and return valid JSON only.'
          },
          {
            role: 'user',
            content: prompt
          }
        ],
        temperature: llm.temperature,
        max_tokens: llm.maxTokens
      });

      const content = response.choices[0].message.content;
      if (!content) {
        throw new Error('No content in LLM response');
      }

      // Extract and parse JSON from response
      const jsonMatch = content.match(/\{[\s\S]*\}/);
      if (!jsonMatch) {
        throw new Error('No JSON found in LLM response');
      }

      const featureData = JSON.parse(jsonMatch[0]);
      return this.parseFeatureSpec(featureData);

    } catch (error) {
      logger.error(`LLM analysis failed: ${error}`);

      // Return a basic spec as fallback
      return {
        name: 'Unknown Feature',
        purpose: 'Feature purpose not determined',
        inputs: [],
        outputs: [],
        successCriteria: ['Feature executes without error'],
        failureModes: ['Feature fails to execute'],
        edgeCases: [],
        dependencies: []
      };
    }
  }

  /**
   * Build the feature analysis prompt for LLM
   * @param context - Feature documentation context
   * @returns Formatted prompt
   */
  private buildFeatureAnalysisPrompt(context: string): string {
    return `Analyze this feature documentation and extract structured information.

Documentation:
${context}

Extract and return ONLY valid JSON in this exact format:
{
  "name": "feature name",
  "purpose": "what the feature does",
  "inputs": [
    {"name": "input1", "type": "string", "required": true, "description": "..."}
  ],
  "outputs": [
    {"name": "output1", "type": "object", "description": "..."}
  ],
  "success_criteria": [
    "criterion 1",
    "criterion 2"
  ],
  "failure_modes": [
    "possible failure 1",
    "possible failure 2"
  ],
  "edge_cases": [
    "edge case 1",
    "edge case 2"
  ],
  "dependencies": ["dependency1", "dependency2"]
}`;
  }

  /**
   * Parse feature specification from LLM response data
   * @param data - Raw LLM response data
   * @returns Parsed FeatureSpec
   */
  private parseFeatureSpec(data: any): FeatureSpec {
    return {
      name: data.name || 'Unknown Feature',
      purpose: data.purpose || 'Purpose not specified',
      inputs: (data.inputs || []).map((input: any) => ({
        name: input.name || 'unknown',
        type: input.type || 'any',
        required: input.required !== false,
        description: input.description || ''
      })),
      outputs: (data.outputs || []).map((output: any) => ({
        name: output.name || 'result',
        type: output.type || 'any',
        description: output.description || ''
      })),
      successCriteria: data.success_criteria || data.successCriteria || ['Feature executes successfully'],
      failureModes: data.failure_modes || data.failureModes || ['Feature fails to execute'],
      edgeCases: data.edge_cases || data.edgeCases || [],
      dependencies: data.dependencies || []
    };
  }

  /**
   * Generate test scenarios from feature specification
   * @param featureSpec - Feature specification
   * @returns List of test scenarios
   */
  async generateTestScenarios(featureSpec: FeatureSpec): Promise<TestScenario[]> {
    logger.info(`Generating test scenarios for feature: ${featureSpec.name}`);

    const scenarios: TestScenario[] = [];
    let scenarioId = 1;

    // Generate success path scenario
    const successScenario = await this.generateSuccessScenario(featureSpec, scenarioId++);
    scenarios.push(successScenario);

    // Generate failure mode scenarios (limited to 3)
    for (const failureMode of featureSpec.failureModes.slice(0, 3)) {
      const failureScenario = await this.generateFailureScenario(featureSpec, failureMode, scenarioId++);
      scenarios.push(failureScenario);
    }

    // Generate edge case scenarios (limited to 2)
    for (const edgeCase of featureSpec.edgeCases.slice(0, 2)) {
      const edgeCaseScenario = await this.generateEdgeCaseScenario(featureSpec, edgeCase, scenarioId++);
      scenarios.push(edgeCaseScenario);
    }

    logger.info(`Generated ${scenarios.length} test scenarios for ${featureSpec.name}`);
    return scenarios;
  }

  /**
   * Generate a success path test scenario
   * @param spec - Feature specification
   * @param scenarioId - Scenario ID number
   * @returns Success test scenario
   */
  private async generateSuccessScenario(spec: FeatureSpec, scenarioId: number): Promise<TestScenario> {
    const id = `${spec.name.replace(/\s+/g, '_').toLowerCase()}_${scenarioId}`;

    return {
      id,
      name: `${spec.name} - Success Path`,
      description: `Verify ${spec.name} works correctly with valid inputs`,
      priority: Priority.HIGH,
      interface: this.determineInterface(spec.name),
      prerequisites: spec.dependencies,
      steps: this.generateSuccessSteps(spec),
      verifications: this.generateVerificationSteps(spec),
      expectedOutcome: spec.successCriteria.slice(0, 2).join('; ') || 'Feature executes successfully',
      estimatedDuration: 60,
      tags: ['success-path', 'smoke-test'],
      enabled: true,
      environment: {},
      cleanup: []
    };
  }

  /**
   * Generate a failure mode test scenario
   * @param spec - Feature specification
   * @param failureMode - Specific failure mode to test
   * @param scenarioId - Scenario ID number
   * @returns Failure test scenario
   */
  private async generateFailureScenario(spec: FeatureSpec, failureMode: string, scenarioId: number): Promise<TestScenario> {
    const id = `${spec.name.replace(/\s+/g, '_').toLowerCase()}_${scenarioId}`;

    return {
      id,
      name: `${spec.name} - Failure: ${failureMode.slice(0, 50)}`,
      description: `Verify ${spec.name} handles failure: ${failureMode}`,
      priority: Priority.MEDIUM,
      interface: this.determineInterface(spec.name),
      prerequisites: spec.dependencies,
      steps: this.generateFailureSteps(spec, failureMode),
      verifications: [{
        type: 'text',
        target: 'error_message',
        expected: failureMode,
        operator: 'contains',
        description: `Verify error message contains: ${failureMode}`
      }],
      expectedOutcome: `Feature handles error gracefully: ${failureMode}`,
      estimatedDuration: 45,
      tags: ['failure-mode', 'error-handling'],
      enabled: true,
      environment: {},
      cleanup: []
    };
  }

  /**
   * Generate an edge case test scenario
   * @param spec - Feature specification
   * @param edgeCase - Specific edge case to test
   * @param scenarioId - Scenario ID number
   * @returns Edge case test scenario
   */
  private async generateEdgeCaseScenario(spec: FeatureSpec, edgeCase: string, scenarioId: number): Promise<TestScenario> {
    const id = `${spec.name.replace(/\s+/g, '_').toLowerCase()}_${scenarioId}`;

    return {
      id,
      name: `${spec.name} - Edge Case: ${edgeCase.slice(0, 50)}`,
      description: `Verify ${spec.name} handles edge case: ${edgeCase}`,
      priority: Priority.LOW,
      interface: this.determineInterface(spec.name),
      prerequisites: spec.dependencies,
      steps: this.generateEdgeCaseSteps(spec, edgeCase),
      verifications: this.generateVerificationSteps(spec),
      expectedOutcome: `Feature handles edge case correctly: ${edgeCase}`,
      estimatedDuration: 30,
      tags: ['edge-case'],
      enabled: true,
      environment: {},
      cleanup: []
    };
  }

  /**
   * Determine test interface based on feature name
   * @param featureName - Name of the feature
   * @returns Test interface type
   */
  private determineInterface(featureName: string): TestInterface {
    const featureLower = featureName.toLowerCase();

    if (this.isCLIFeature(featureLower)) {
      return TestInterface.CLI;
    } else if (this.isGUIFeature(featureLower)) {
      return TestInterface.GUI;
    } else if (this.isAPIFeature(featureLower)) {
      return TestInterface.API;
    } else {
      return TestInterface.MIXED;
    }
  }

  /**
   * Check if feature is CLI-related
   * @param featureName - Feature name in lowercase
   * @returns True if CLI feature
   */
  private isCLIFeature(featureName: string): boolean {
    const cliKeywords = ['command', 'cli', 'atg', 'generate', 'build', 'doctor', 'agent-mode'];
    return cliKeywords.some(keyword => featureName.includes(keyword));
  }

  /**
   * Check if feature is GUI-related
   * @param featureName - Feature name in lowercase
   * @returns True if GUI feature
   */
  private isGUIFeature(featureName: string): boolean {
    const guiKeywords = ['tab', 'button', 'page', 'ui', 'spa', 'electron', 'dialog', 'menu'];
    return guiKeywords.some(keyword => featureName.includes(keyword));
  }

  /**
   * Check if feature is API-related
   * @param featureName - Feature name in lowercase
   * @returns True if API feature
   */
  private isAPIFeature(featureName: string): boolean {
    const apiKeywords = ['api', 'endpoint', 'rest', 'http', 'webhook'];
    return apiKeywords.some(keyword => featureName.includes(keyword));
  }

  /**
   * Generate success path test steps
   * @param spec - Feature specification
   * @returns Array of test steps
   */
  private generateSuccessSteps(spec: FeatureSpec): TestStep[] {
    const steps: TestStep[] = [];

    // Add setup step if dependencies exist
    if (spec.dependencies.length > 0) {
      steps.push({
        action: 'execute',
        target: `setup ${spec.dependencies[0]}`,
        description: `Set up ${spec.dependencies[0]}`,
        timeout: 30000
      });
    }

    // Add main execution step
    steps.push({
      action: 'execute',
      target: spec.name.toLowerCase().replace(/\s+/g, '-'),
      description: `Execute ${spec.name}`,
      timeout: 60000
    });

    // Add verification step
    steps.push({
      action: 'verify',
      target: 'output',
      expected: spec.successCriteria[0] || 'Success',
      description: 'Verify successful execution',
      timeout: 10000
    });

    return steps;
  }

  /**
   * Generate failure mode test steps
   * @param spec - Feature specification
   * @param failureMode - Failure mode to test
   * @returns Array of test steps
   */
  private generateFailureSteps(spec: FeatureSpec, failureMode: string): TestStep[] {
    return [
      {
        action: 'execute',
        target: spec.name.toLowerCase().replace(/\s+/g, '-'),
        value: 'invalid_input',
        description: `Execute ${spec.name} with invalid input`,
        timeout: 60000
      },
      {
        action: 'verify',
        target: 'error',
        expected: failureMode,
        description: `Verify error handling for: ${failureMode}`,
        timeout: 10000
      }
    ];
  }

  /**
   * Generate edge case test steps
   * @param spec - Feature specification
   * @param edgeCase - Edge case to test
   * @returns Array of test steps
   */
  private generateEdgeCaseSteps(spec: FeatureSpec, edgeCase: string): TestStep[] {
    return [
      {
        action: 'execute',
        target: spec.name.toLowerCase().replace(/\s+/g, '-'),
        value: edgeCase,
        description: `Execute ${spec.name} with edge case: ${edgeCase}`,
        timeout: 60000
      },
      {
        action: 'verify',
        target: 'output',
        expected: 'handled',
        description: `Verify edge case handled: ${edgeCase}`,
        timeout: 10000
      }
    ];
  }

  /**
   * Generate verification steps
   * @param spec - Feature specification
   * @returns Array of verification steps
   */
  private generateVerificationSteps(spec: FeatureSpec): VerificationStep[] {
    return spec.successCriteria.slice(0, 3).map((criterion, index) => ({
      type: 'text',
      target: 'output',
      expected: criterion,
      operator: 'contains',
      description: `Verify: ${criterion}`
    }));
  }

  /**
   * Discover features from documentation
   * @returns List of discovered features
   */
  async discoverFeatures(): Promise<DiscoveredFeature[]> {
    logger.info('Discovering features from documentation');

    try {
      const docs = await this.docLoader.loadMarkdownFiles();
      const allFeatures: DiscoveredFeature[] = [];

      for (const [docPath, content] of Object.entries(docs)) {
        const features = this.docLoader.extractFeatures(content);
        for (const feature of features) {
          feature.source = docPath;
        }
        allFeatures.push(...features);
      }

      logger.info(`Discovered ${allFeatures.length} features from documentation`);
      return allFeatures;
    } catch (error) {
      logger.error(`Error discovering features: ${error}`);
      return [];
    }
  }

  /**
   * Process all discovered features and generate comprehensive test scenarios
   * @returns Comprehensive list of test scenarios
   */
  async processDiscoveredFeatures(): Promise<TestScenario[]> {
    logger.info('Processing discovered features and generating test scenarios');

    try {
      const discoveredFeatures = await this.discoverFeatures();
      const allScenarios: TestScenario[] = [];

      for (const feature of discoveredFeatures) {
        try {
          logger.debug(`Analyzing feature: ${feature.name}`);
          const featureSpec = await this.analyzeFeature(feature.context);
          const scenarios = await this.generateTestScenarios(featureSpec);
          allScenarios.push(...scenarios);
        } catch (error) {
          logger.error(`Failed to process feature ${feature.name}: ${error}`);
        }
      }

      logger.info(`Generated ${allScenarios.length} total test scenarios from ${discoveredFeatures.length} features`);
      return allScenarios;
    } catch (error) {
      logger.error(`Error processing features: ${error}`);
      return [];
    }
  }
}

/**
 * Create a ComprehensionAgent instance with default configuration
 * @param config - Partial configuration to override defaults
 * @returns Configured ComprehensionAgent instance
 */
export function createComprehensionAgent(config: Partial<ComprehensionAgentConfig>): ComprehensionAgent {
  const defaultConfig: ComprehensionAgentConfig = {
    llm: {
      provider: 'openai',
      apiKey: process.env.OPENAI_API_KEY || '',
      model: 'gpt-4',
      temperature: 0.1,
      maxTokens: 4000,
      apiVersion: '2024-02-01'
    },
    docsDir: 'docs',
    includePatterns: ['**/*.md'],
    excludePatterns: ['**/node_modules/**'],
    maxContextLength: 8000
  };

  // Override with Azure configuration if available
  if (process.env.AZURE_OPENAI_ENDPOINT) {
    defaultConfig.llm = {
      ...defaultConfig.llm,
      provider: 'azure',
      apiKey: process.env.AZURE_OPENAI_KEY || process.env.AZURE_OPENAI_API_KEY || '',
      endpoint: process.env.AZURE_OPENAI_ENDPOINT,
      deployment: process.env.AZURE_OPENAI_DEPLOYMENT || 'gpt-4',
      apiVersion: process.env.AZURE_OPENAI_API_VERSION || '2024-02-01'
    };
  }

  const finalConfig = { ...defaultConfig, ...config };

  if (config.llm) {
    finalConfig.llm = { ...defaultConfig.llm, ...config.llm };
  }

  return new ComprehensionAgent(finalConfig);
}

/**
 * Default configuration for ComprehensionAgent
 */
export const defaultComprehensionAgentConfig: ComprehensionAgentConfig = {
  llm: {
    provider: 'openai',
    apiKey: process.env.OPENAI_API_KEY || '',
    model: 'gpt-4',
    temperature: 0.1,
    maxTokens: 4000
  },
  docsDir: 'docs',
  includePatterns: ['**/*.md'],
  excludePatterns: ['**/node_modules/**'],
  maxContextLength: 8000
};
