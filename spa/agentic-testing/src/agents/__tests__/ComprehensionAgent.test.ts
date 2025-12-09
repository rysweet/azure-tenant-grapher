/**
 * ComprehensionAgent Test Suite
 */

import { ComprehensionAgent, DocumentationLoader, createComprehensionAgent } from '../ComprehensionAgent';
import { Priority, TestInterface } from '../../models/TestModels';

// Mock OpenAI
jest.mock('openai', () => {
  return {
    __esModule: true,
    default: jest.fn().mockImplementation(() => ({
      chat: {
        completions: {
          create: jest.fn().mockResolvedValue({
            choices: [{
              message: {
                content: JSON.stringify({
                  name: 'Test Feature',
                  purpose: 'Test feature for testing',
                  inputs: [{ name: 'input1', type: 'string', required: true, description: 'Test input' }],
                  outputs: [{ name: 'output1', type: 'object', description: 'Test output' }],
                  success_criteria: ['Feature executes successfully', 'Output is valid'],
                  failure_modes: ['Invalid input', 'Network error'],
                  edge_cases: ['Empty input', 'Large input'],
                  dependencies: ['dependency1']
                })
              }
            }]
          })
        }
      }
    }))
  };
});

// Mock fs/promises
jest.mock('fs/promises', () => ({
  readFile: jest.fn().mockResolvedValue('# Test Documentation\n\n`atg build` command documentation'),
  readdir: jest.fn().mockResolvedValue(['test.md'])
}));

// Mock glob
jest.mock('glob', () => ({
  glob: jest.fn().mockResolvedValue(['docs/test.md'])
}));

describe('DocumentationLoader', () => {
  let docLoader: DocumentationLoader;

  beforeEach(() => {
    docLoader = new DocumentationLoader('docs', ['**/*.md'], ['**/node_modules/**']);
  });

  describe('extractFeatures', () => {
    it('should extract CLI features from documentation', () => {
      const content = `
# CLI Commands

Use \`atg build\` to build the graph database.
Use \`uv run atg generate-iac\` to generate infrastructure code.
      `;

      const features = docLoader.extractFeatures(content);

      expect(features).toHaveLength(2);
      expect(features[0]).toMatchObject({
        type: 'cli',
        name: 'build'
      });
      expect(features[1]).toMatchObject({
        type: 'cli',
        name: 'generate-iac'
      });
    });

    it('should extract UI features from headers', () => {
      const content = `
# Build Tab
This tab allows you to build the graph.

## Settings Dialog
Configure your settings here.

### Navigation Menu
Navigate through the application.
      `;

      const features = docLoader.extractFeatures(content);

      expect(features).toHaveLength(3);
      expect(features.every(f => f.type === 'ui')).toBe(true);
    });

    it('should extract API endpoints', () => {
      const content = `
API endpoints:
- GET /api/users
- POST /api/resources
- DELETE /api/cleanup
      `;

      const features = docLoader.extractFeatures(content);

      expect(features).toHaveLength(3);
      expect(features.every(f => f.type === 'api')).toBe(true);
    });
  });

  describe('loadMarkdownFiles', () => {
    it('should load markdown files successfully', async () => {
      const docs = await docLoader.loadMarkdownFiles();

      expect(docs).toBeDefined();
      expect(typeof docs).toBe('object');
    });
  });
});

describe('ComprehensionAgent', () => {
  let agent: ComprehensionAgent;

  beforeEach(() => {
    agent = createComprehensionAgent({
      llm: {
        provider: 'openai',
        apiKey: 'test-key',  // pragma: allowlist secret
        model: 'gpt-4',
        temperature: 0.1,
        maxTokens: 4000
      },
      docsDir: 'test-docs'
    });
  });

  afterEach(async () => {
    await agent.cleanup();
  });

  describe('initialization', () => {
    it('should initialize successfully', async () => {
      await expect(agent.initialize()).resolves.not.toThrow();
    });

    it('should have correct name and type', () => {
      expect(agent.name).toBe('ComprehensionAgent');
      expect(agent.type).toBe('comprehension');
    });
  });

  describe('analyzeFeature', () => {
    it('should analyze feature documentation and return FeatureSpec', async () => {
      await agent.initialize();

      const featureDoc = `
# Build Command
The atg build command creates a Neo4j graph from Azure resources.
Usage: atg build --tenant-id <id>
      `;

      const result = await agent.analyzeFeature(featureDoc);

      expect(result).toMatchObject({
        name: 'Test Feature',
        purpose: 'Test feature for testing',
        inputs: expect.arrayContaining([
          expect.objectContaining({
            name: 'input1',
            type: 'string',
            required: true
          })
        ]),
        successCriteria: expect.arrayContaining([
          'Feature executes successfully'
        ]),
        failureModes: expect.arrayContaining([
          'Invalid input'
        ])
      });
    });

    it('should handle LLM errors gracefully', async () => {
      // Mock OpenAI to throw an error
      const mockOpenAI = require('openai').default;
      mockOpenAI.mockImplementationOnce(() => ({
        chat: {
          completions: {
            create: jest.fn().mockRejectedValue(new Error('API Error'))
          }
        }
      }));

      const newAgent = createComprehensionAgent({
        llm: {
          provider: 'openai',
          apiKey: 'test-key',  // pragma: allowlist secret
          model: 'gpt-4',
          temperature: 0.1,
          maxTokens: 4000
        }
      });

      await newAgent.initialize();
      const result = await newAgent.analyzeFeature('test documentation');

      expect(result.name).toBe('Unknown Feature');
      expect(result.purpose).toBe('Feature purpose not determined');

      await newAgent.cleanup();
    });
  });

  describe('generateTestScenarios', () => {
    it('should generate test scenarios from feature spec', async () => {
      await agent.initialize();

      const featureSpec = {
        name: 'Build Command',
        purpose: 'Build Neo4j graph',
        inputs: [],
        outputs: [],
        successCriteria: ['Graph created', 'Resources discovered'],
        failureModes: ['Invalid tenant', 'Network error'],
        edgeCases: ['Empty tenant', 'Large tenant'],
        dependencies: []
      };

      const scenarios = await agent.generateTestScenarios(featureSpec);

      expect(scenarios).toHaveLength(4); // 1 success + 2 failures + 1 edge case

      // Check success scenario
      const successScenario = scenarios.find(s => s.name.includes('Success'));
      expect(successScenario).toBeDefined();
      expect(successScenario?.priority).toBe(Priority.HIGH);
      expect(successScenario?.tags).toContain('success-path');

      // Check failure scenarios
      const failureScenarios = scenarios.filter(s => s.name.includes('Failure'));
      expect(failureScenarios).toHaveLength(2);
      failureScenarios.forEach(scenario => {
        expect(scenario.priority).toBe(Priority.MEDIUM);
        expect(scenario.tags).toContain('failure-mode');
      });

      // Check edge case scenario
      const edgeScenario = scenarios.find(s => s.name.includes('Edge Case'));
      expect(edgeScenario).toBeDefined();
      expect(edgeScenario?.priority).toBe(Priority.LOW);
      expect(edgeScenario?.tags).toContain('edge-case');
    });
  });

  describe('interface determination', () => {
    it('should correctly determine CLI interface', async () => {
      await agent.initialize();

      const cliFeatureSpec = {
        name: 'atg build command',
        purpose: 'Build graph',
        inputs: [], outputs: [],
        successCriteria: [], failureModes: [], edgeCases: [],
        dependencies: []
      };

      const scenarios = await agent.generateTestScenarios(cliFeatureSpec);
      expect(scenarios[0].interface).toBe(TestInterface.CLI);
    });

    it('should correctly determine GUI interface', async () => {
      await agent.initialize();

      const guiFeatureSpec = {
        name: 'Settings Tab UI',
        purpose: 'Configure settings',
        inputs: [], outputs: [],
        successCriteria: [], failureModes: [], edgeCases: [],
        dependencies: []
      };

      const scenarios = await agent.generateTestScenarios(guiFeatureSpec);
      expect(scenarios[0].interface).toBe(TestInterface.GUI);
    });

    it('should correctly determine API interface', async () => {
      await agent.initialize();

      const apiFeatureSpec = {
        name: 'REST API endpoint',
        purpose: 'Handle requests',
        inputs: [], outputs: [],
        successCriteria: [], failureModes: [], edgeCases: [],
        dependencies: []
      };

      const scenarios = await agent.generateTestScenarios(apiFeatureSpec);
      expect(scenarios[0].interface).toBe(TestInterface.API);
    });
  });

  describe('discoverFeatures', () => {
    it('should discover features from documentation files', async () => {
      await agent.initialize();

      const features = await agent.discoverFeatures();

      expect(Array.isArray(features)).toBe(true);
      // Additional assertions would depend on mocked file content
    });
  });

  describe('execute method', () => {
    it('should skip execution with appropriate message', async () => {
      const result = await agent.execute({});

      expect(result).toMatchObject({
        status: 'skipped',
        reason: 'ComprehensionAgent does not execute scenarios'
      });
    });
  });
});

describe('createComprehensionAgent', () => {
  it('should create agent with default configuration', () => {
    const agent = createComprehensionAgent({});

    expect(agent).toBeInstanceOf(ComprehensionAgent);
    expect(agent.name).toBe('ComprehensionAgent');
    expect(agent.type).toBe('comprehension');
  });

  it('should create agent with custom configuration', () => {
    const config = {
      llm: {
        provider: 'azure' as const,
        apiKey: 'test-key',  // pragma: allowlist secret
        model: 'gpt-4',
        temperature: 0.2,
        maxTokens: 2000,
        endpoint: 'https://test.openai.azure.com',
        deployment: 'test-deployment'
      },
      docsDir: 'custom-docs',
      maxContextLength: 5000
    };

    const agent = createComprehensionAgent(config);

    expect(agent).toBeInstanceOf(ComprehensionAgent);
  });

  it('should use Azure configuration from environment variables', () => {
    // Mock environment variables
    const originalEnv = process.env;
    process.env = {
      ...originalEnv,
      AZURE_OPENAI_ENDPOINT: 'https://test.openai.azure.com',
      AZURE_OPENAI_KEY: 'test-azure-key',
      AZURE_OPENAI_DEPLOYMENT: 'test-deployment'
    };

    const agent = createComprehensionAgent({});
    expect(agent).toBeInstanceOf(ComprehensionAgent);

    // Restore environment
    process.env = originalEnv;
  });
});
