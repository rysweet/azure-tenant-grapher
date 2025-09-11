/**
 * ComprehensionAgent Usage Examples
 *
 * This file demonstrates how to use the ComprehensionAgent to discover features from
 * documentation and generate comprehensive test scenarios.
 */

import {
  ComprehensionAgent,
  createComprehensionAgent,
  ComprehensionAgentConfig,
  LLMProvider
} from '../ComprehensionAgent';
import { logger } from '../../utils/logger';

/**
 * Example 1: Basic ComprehensionAgent usage with OpenAI
 */
export async function basicOpenAIExample(): Promise<void> {
  logger.info('Starting basic OpenAI ComprehensionAgent example');

  // Create agent with OpenAI configuration
  const agent = createComprehensionAgent({
    llm: {
      provider: 'openai' as LLMProvider,
      apiKey: process.env.OPENAI_API_KEY!,
      model: 'gpt-4',
      temperature: 0.1,
      maxTokens: 4000
    },
    docsDir: './docs',
    includePatterns: ['**/*.md'],
    excludePatterns: ['**/node_modules/**', '**/dist/**']
  });

  try {
    // Initialize the agent
    await agent.initialize();

    // Discover features from documentation
    const features = await agent.discoverFeatures();
    logger.info(`Discovered ${features.length} features`);

    // Process a single feature
    if (features.length > 0) {
      const firstFeature = features[0];
      logger.info(`Analyzing feature: ${firstFeature.name}`);

      const featureSpec = await agent.analyzeFeature(firstFeature.context);
      const scenarios = await agent.generateTestScenarios(featureSpec);

      logger.info(`Generated ${scenarios.length} test scenarios for ${featureSpec.name}`);
      scenarios.forEach((scenario, index) => {
        logger.info(`  ${index + 1}. ${scenario.name} (${scenario.priority})`);
      });
    }

    // Cleanup
    await agent.cleanup();
  } catch (error) {
    logger.error(`Example failed: ${error}`);
  }
}

/**
 * Example 2: Azure OpenAI configuration
 */
export async function azureOpenAIExample(): Promise<void> {
  logger.info('Starting Azure OpenAI ComprehensionAgent example');

  const config: ComprehensionAgentConfig = {
    llm: {
      provider: 'azure' as LLMProvider,
      apiKey: process.env.AZURE_OPENAI_KEY!,
      model: 'gpt-4',
      temperature: 0.1,
      maxTokens: 4000,
      endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
      deployment: process.env.AZURE_OPENAI_DEPLOYMENT!,
      apiVersion: '2024-02-01'
    },
    docsDir: './docs',
    includePatterns: ['**/*.md'],
    excludePatterns: ['**/node_modules/**'],
    maxContextLength: 8000
  };

  const agent = new ComprehensionAgent(config);

  try {
    await agent.initialize();

    // Process all discovered features and generate scenarios
    const allScenarios = await agent.processDiscoveredFeatures();

    logger.info(`Generated ${allScenarios.length} total test scenarios`);

    // Group scenarios by interface type
    const scenariosByInterface = allScenarios.reduce((acc, scenario) => {
      const key = scenario.interface;
      if (!acc[key]) acc[key] = [];
      acc[key].push(scenario);
      return acc;
    }, {} as Record<string, any[]>);

    Object.entries(scenariosByInterface).forEach(([interfaceType, scenarios]) => {
      logger.info(`${interfaceType}: ${scenarios.length} scenarios`);
    });

    await agent.cleanup();
  } catch (error) {
    logger.error(`Azure example failed: ${error}`);
  }
}

/**
 * Example 3: Analyzing a specific feature documentation
 */
export async function analyzeSpecificFeatureExample(): Promise<void> {
  logger.info('Starting specific feature analysis example');

  const agent = createComprehensionAgent({});

  const featureDocumentation = `
# Build Command

The \`atg build\` command discovers Azure resources and builds a Neo4j graph database.

## Usage

\`\`\`bash
uv run atg build --tenant-id <TENANT_ID>
\`\`\`

## Options

- \`--tenant-id\`: Azure tenant ID (required)
- \`--resource-limit\`: Limit number of resources for testing
- \`--debug\`: Enable debug output

## Success Criteria

- Neo4j database is populated with discovered resources
- Resource relationships are correctly established
- Progress dashboard shows completion status

## Failure Modes

- Invalid tenant ID provided
- Azure authentication fails
- Neo4j container not running
- Network connectivity issues

## Edge Cases

- Large tenants with thousands of resources
- Tenants with no resources
- Partial discovery due to permissions
  `;

  try {
    await agent.initialize();

    // Analyze the specific feature
    const featureSpec = await agent.analyzeFeature(featureDocumentation);

    logger.info(`Feature Analysis Results:`);
    logger.info(`Name: ${featureSpec.name}`);
    logger.info(`Purpose: ${featureSpec.purpose}`);
    logger.info(`Success Criteria: ${featureSpec.successCriteria.length} items`);
    logger.info(`Failure Modes: ${featureSpec.failureModes.length} items`);
    logger.info(`Edge Cases: ${featureSpec.edgeCases.length} items`);

    // Generate test scenarios
    const scenarios = await agent.generateTestScenarios(featureSpec);

    logger.info(`\nGenerated Test Scenarios:`);
    scenarios.forEach((scenario, index) => {
      logger.info(`${index + 1}. ${scenario.name}`);
      logger.info(`   Priority: ${scenario.priority}`);
      logger.info(`   Interface: ${scenario.interface}`);
      logger.info(`   Steps: ${scenario.steps.length}`);
      logger.info(`   Expected: ${scenario.expectedOutcome}`);
      logger.info('');
    });

    await agent.cleanup();
  } catch (error) {
    logger.error(`Specific feature example failed: ${error}`);
  }
}

/**
 * Example 4: Custom documentation patterns
 */
export async function customPatternsExample(): Promise<void> {
  logger.info('Starting custom patterns example');

  const agent = createComprehensionAgent({
    docsDir: './custom-docs',
    includePatterns: ['**/*.md', '**/*.txt', '**/README*'],
    excludePatterns: ['**/node_modules/**', '**/temp/**', '**/*.log'],
    maxContextLength: 6000
  });

  try {
    await agent.initialize();

    // Discover features with custom patterns
    const features = await agent.discoverFeatures();

    logger.info(`Discovered features by type:`);
    const featuresByType = features.reduce((acc, feature) => {
      if (!acc[feature.type]) acc[feature.type] = 0;
      acc[feature.type]++;
      return acc;
    }, {} as Record<string, number>);

    Object.entries(featuresByType).forEach(([type, count]) => {
      logger.info(`  ${type}: ${count} features`);
    });

    // Show some examples
    logger.info('\nExample CLI features:');
    features.filter(f => f.type === 'cli').slice(0, 3).forEach(feature => {
      logger.info(`  - ${feature.name} (from ${feature.source})`);
    });

    logger.info('\nExample UI features:');
    features.filter(f => f.type === 'ui').slice(0, 3).forEach(feature => {
      logger.info(`  - ${feature.name} (from ${feature.source})`);
    });

    await agent.cleanup();
  } catch (error) {
    logger.error(`Custom patterns example failed: ${error}`);
  }
}

/**
 * Run all examples
 */
export async function runAllExamples(): Promise<void> {
  logger.info('Running all ComprehensionAgent examples');

  try {
    // Check if required environment variables are set
    if (process.env.OPENAI_API_KEY) {
      await basicOpenAIExample();
    } else {
      logger.warn('OPENAI_API_KEY not set, skipping OpenAI example');
    }

    if (process.env.AZURE_OPENAI_KEY && process.env.AZURE_OPENAI_ENDPOINT) {
      await azureOpenAIExample();
    } else {
      logger.warn('Azure OpenAI environment variables not set, skipping Azure example');
    }

    // These examples don't require API keys (will fail gracefully)
    await analyzeSpecificFeatureExample();
    await customPatternsExample();

    logger.info('All examples completed');
  } catch (error) {
    logger.error(`Examples execution failed: ${error}`);
  }
}

// Export default for easy import
export default {
  basicOpenAIExample,
  azureOpenAIExample,
  analyzeSpecificFeatureExample,
  customPatternsExample,
  runAllExamples
};
