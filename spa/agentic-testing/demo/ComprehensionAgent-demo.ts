#!/usr/bin/env ts-node

/**
 * ComprehensionAgent Demonstration Script
 * 
 * This script demonstrates the capabilities of the ComprehensionAgent by:
 * 1. Creating sample documentation
 * 2. Discovering features from the documentation
 * 3. Analyzing features with LLM
 * 4. Generating comprehensive test scenarios
 * 
 * Run with: npx ts-node demo/ComprehensionAgent-demo.ts
 */

import { writeFileSync, mkdirSync } from 'fs';
import { join } from 'path';
import { createComprehensionAgent, ComprehensionAgent } from '../src/agents/ComprehensionAgent';
import { logger } from '../src/utils/logger';

// Sample documentation content for demonstration
const SAMPLE_DOCS = {
  'cli-commands.md': `
# CLI Commands

## Build Command

The \`atg build\` command discovers Azure resources and builds a Neo4j graph database representation.

### Usage

\`\`\`bash
uv run atg build --tenant-id <TENANT_ID> [options]
\`\`\`

### Options

- \`--tenant-id\` (required): Azure tenant ID to discover resources from
- \`--resource-limit <number>\`: Limit the number of resources to discover (useful for testing)
- \`--debug\`: Enable verbose debug output
- \`--force-refresh\`: Force refresh of cached data

### Success Criteria

- Neo4j database is populated with discovered Azure resources
- Resource relationships are correctly established
- Progress dashboard shows 100% completion
- No authentication or permission errors occur

### Failure Modes

- Invalid or missing tenant ID provided
- Azure authentication credentials are incorrect or expired
- Neo4j container is not running or accessible
- Network connectivity issues prevent resource discovery
- Insufficient permissions to access Azure resources

### Edge Cases

- Large tenants with thousands of resources (performance considerations)
- Tenants with no resources or empty subscriptions
- Partial discovery due to limited permissions
- Interrupted discovery process (should resume gracefully)

## Generate IaC Command

The \`atg generate-iac\` command creates Infrastructure-as-Code from the Neo4j graph.

### Usage

\`\`\`bash
uv run atg generate-iac --tenant-id <TENANT_ID> --format <FORMAT>
\`\`\`

### Formats Supported

- terraform: Generates Terraform HCL files
- arm: Generates ARM templates
- bicep: Generates Bicep templates

### Success Criteria

- IaC files are generated in the correct format
- All resources from the graph are included
- Dependencies are properly ordered
- Output files are syntactically valid

### Failure Modes

- Graph database is empty or corrupted
- Unsupported resource types encountered
- Circular dependencies detected
- File system permission errors

## Doctor Command

The \`atg doctor\` command checks system dependencies and configuration.

### Usage

\`\`\`bash
uv run atg doctor
\`\`\`

### Checks Performed

- Docker installation and service status
- Neo4j container availability
- Azure CLI authentication status
- Python environment and dependencies
- Network connectivity to Azure APIs

### Success Criteria

- All dependency checks pass
- System is ready for ATG operations
- Clear status report provided

### Failure Modes

- Missing or outdated dependencies
- Docker service not running
- Authentication not configured
- Network connectivity issues
`,

  'spa-ui.md': `
# SPA User Interface

## Build Tab

The Build tab provides a graphical interface for discovering Azure resources and building the Neo4j graph.

### Features

- Tenant ID input field with validation
- Resource limit slider for testing purposes
- Real-time progress indicators
- Log output display with filtering
- Start/Stop/Cancel operation buttons

### Success Criteria

- Tenant ID validation works correctly
- Progress indicators update in real-time
- Log messages are displayed clearly
- Operations can be controlled via buttons
- Results are displayed after completion

### Failure Modes

- Invalid tenant ID shows appropriate error
- Network errors are displayed to user
- Long operations can be cancelled gracefully
- UI remains responsive during operations

## Settings Dialog

The Settings dialog allows configuration of application preferences.

### Configuration Options

- Azure authentication settings
- Neo4j connection parameters
- Logging preferences
- UI theme selection
- Default operation timeouts

### Success Criteria

- All settings are persisted correctly
- Changes take effect immediately
- Input validation prevents invalid configurations
- Default values are clearly indicated

### Failure Modes

- Invalid configurations are rejected with clear messages
- Corrupted settings files are handled gracefully
- Network connectivity issues during validation

## Navigation Menu

The main navigation menu provides access to all application features.

### Menu Items

- Build: Resource discovery and graph building
- Generate Spec: Documentation generation
- Generate IaC: Infrastructure code generation
- Create Tenant: New tenant setup
- Visualize: Graph visualization
- Agent Mode: Autonomous testing
- Config: Application settings

### Success Criteria

- All menu items are accessible
- Current page is clearly indicated
- Navigation is smooth and responsive
- Keyboard shortcuts work correctly

### Edge Cases

- Very long menu item names
- Disabled menu items during operations
- Deep navigation hierarchies
`,

  'api-endpoints.md': `
# API Endpoints

## Graph Data API

### GET /api/graph/nodes

Retrieves nodes from the Neo4j graph database.

#### Parameters

- \`type\` (optional): Filter by node type
- \`limit\` (optional): Maximum number of nodes to return
- \`offset\` (optional): Pagination offset

#### Success Response

\`\`\`json
{
  "nodes": [
    {
      "id": "node-id",
      "type": "Resource",
      "properties": {...}
    }
  ],
  "total": 1234,
  "hasMore": true
}
\`\`\`

#### Failure Modes

- Database connection unavailable
- Invalid query parameters
- Authentication required
- Rate limiting exceeded

### POST /api/graph/query

Executes custom Cypher queries against the graph.

#### Request Body

\`\`\`json
{
  "query": "MATCH (n) RETURN n LIMIT 10",
  "parameters": {}
}
\`\`\`

#### Success Criteria

- Query executes successfully
- Results returned in standard format
- Query performance is acceptable
- Security validation passes

#### Failure Modes

- Invalid Cypher syntax
- Query timeout exceeded
- Resource limits exceeded
- Unauthorized query attempted

### DELETE /api/graph/cleanup

Clears all data from the graph database.

#### Success Criteria

- All nodes and relationships removed
- Database is in clean state
- Operation completes quickly
- Confirmation is logged

#### Failure Modes

- Database connection issues
- Insufficient permissions
- Concurrent operations conflict
- Partial cleanup due to errors
`
};

/**
 * Create sample documentation files for demonstration
 */
function createSampleDocs(): void {
  const docsDir = join(__dirname, 'temp-docs');
  
  // Create docs directory
  mkdirSync(docsDir, { recursive: true });
  
  // Write sample documentation files
  Object.entries(SAMPLE_DOCS).forEach(([filename, content]) => {
    const filePath = join(docsDir, filename);
    writeFileSync(filePath, content.trim(), 'utf-8');
    logger.info(`Created sample doc: ${filename}`);
  });
  
  logger.info(`Sample documentation created in: ${docsDir}`);
}

/**
 * Demonstrate basic feature discovery
 */
async function demonstrateFeatureDiscovery(agent: ComprehensionAgent): Promise<void> {
  logger.info('\n=== Feature Discovery Demonstration ===');
  
  const features = await agent.discoverFeatures();
  
  logger.info(`\nDiscovered ${features.length} features:`);
  
  // Group features by type
  const featuresByType = features.reduce((acc, feature) => {
    if (!acc[feature.type]) acc[feature.type] = [];
    acc[feature.type].push(feature);
    return acc;
  }, {} as Record<string, typeof features>);
  
  Object.entries(featuresByType).forEach(([type, typeFeatures]) => {
    logger.info(`\n${type.toUpperCase()} Features (${typeFeatures.length}):`);
    typeFeatures.forEach((feature, index) => {
      logger.info(`  ${index + 1}. ${feature.name}`);
      logger.info(`     Source: ${feature.source}`);
      logger.info(`     Context: ${feature.context.substring(0, 100)}...`);
    });
  });
}

/**
 * Demonstrate feature analysis with LLM
 */
async function demonstrateFeatureAnalysis(agent: ComprehensionAgent): Promise<void> {
  logger.info('\n=== Feature Analysis Demonstration ===');
  
  // Sample feature documentation for analysis
  const sampleFeature = `
# Build Command Analysis

The \`atg build\` command is the core functionality of Azure Tenant Grapher. It performs comprehensive discovery of Azure resources within a specified tenant and constructs a detailed Neo4j graph database representation.

## Detailed Functionality

### Input Requirements
- **tenant-id**: Valid Azure tenant ID (GUID format)
- **resource-limit** (optional): Integer limiting resource discovery for testing
- **debug** (optional): Boolean flag for verbose logging

### Processing Steps
1. Authenticate with Azure using configured credentials
2. Enumerate all subscriptions within the tenant
3. Discover resources across all resource groups
4. Establish relationships between resources
5. Populate Neo4j database with nodes and edges
6. Validate data integrity and completeness

### Expected Outputs
- Populated Neo4j graph database
- Progress reports during execution
- Summary statistics of discovered resources
- Log files with detailed operation traces

### Success Indicators
- All accessible resources are discovered and cataloged
- Resource relationships are accurately mapped
- Neo4j database queries return expected results
- No authentication or authorization errors
- Operation completes within reasonable timeframe

### Known Failure Scenarios
- Authentication failures due to expired or invalid credentials
- Network connectivity issues preventing Azure API access
- Neo4j database unavailability or connection failures
- Insufficient permissions to access certain resource types
- Tenant contains resources in unsupported regions
- Resource discovery timeout due to large tenant size

### Edge Cases and Boundary Conditions
- Empty tenant with no subscriptions or resources
- Tenant with thousands of resources requiring pagination
- Resources with circular or complex dependency relationships  
- Partial tenant access due to limited user permissions
- Concurrent operations on the same tenant
- Recovery from interrupted discovery processes
`;

  try {
    logger.info('Analyzing sample feature with LLM...');
    const featureSpec = await agent.analyzeFeature(sampleFeature);
    
    logger.info('\nFeature Analysis Results:');
    logger.info(`Name: ${featureSpec.name}`);
    logger.info(`Purpose: ${featureSpec.purpose}`);
    
    logger.info(`\nInputs (${featureSpec.inputs.length}):`);
    featureSpec.inputs.forEach((input, index) => {
      logger.info(`  ${index + 1}. ${input.name} (${input.type}) - ${input.required ? 'Required' : 'Optional'}`);
      logger.info(`     ${input.description}`);
    });
    
    logger.info(`\nOutputs (${featureSpec.outputs.length}):`);
    featureSpec.outputs.forEach((output, index) => {
      logger.info(`  ${index + 1}. ${output.name} (${output.type}): ${output.description}`);
    });
    
    logger.info(`\nSuccess Criteria (${featureSpec.successCriteria.length}):`);
    featureSpec.successCriteria.forEach((criterion, index) => {
      logger.info(`  ${index + 1}. ${criterion}`);
    });
    
    logger.info(`\nFailure Modes (${featureSpec.failureModes.length}):`);
    featureSpec.failureModes.forEach((failure, index) => {
      logger.info(`  ${index + 1}. ${failure}`);
    });
    
    logger.info(`\nEdge Cases (${featureSpec.edgeCases.length}):`);
    featureSpec.edgeCases.forEach((edgeCase, index) => {
      logger.info(`  ${index + 1}. ${edgeCase}`);
    });
    
    return featureSpec;
  } catch (error) {
    logger.error(`Feature analysis failed: ${error}`);
    logger.warn('This is expected if no LLM API key is configured');
    return null;
  }
}

/**
 * Demonstrate test scenario generation
 */
async function demonstrateScenarioGeneration(agent: ComprehensionAgent): Promise<void> {
  logger.info('\n=== Test Scenario Generation Demonstration ===');
  
  // Create a mock feature spec for demonstration
  const mockFeatureSpec = {
    name: 'Build Command',
    purpose: 'Discover Azure resources and build Neo4j graph database',
    inputs: [
      { name: 'tenant-id', type: 'string', required: true, description: 'Azure tenant ID' },
      { name: 'resource-limit', type: 'number', required: false, description: 'Maximum resources to discover' }
    ],
    outputs: [
      { name: 'graph-database', type: 'Neo4j', description: 'Populated graph database' },
      { name: 'summary-report', type: 'object', description: 'Discovery summary statistics' }
    ],
    successCriteria: [
      'All accessible resources are discovered',
      'Resource relationships are correctly established',
      'Neo4j database is populated successfully',
      'Progress indicators show completion'
    ],
    failureModes: [
      'Invalid tenant ID provided',
      'Azure authentication fails',
      'Neo4j container not running',
      'Network connectivity issues',
      'Insufficient permissions'
    ],
    edgeCases: [
      'Empty tenant with no resources',
      'Large tenant with thousands of resources',
      'Interrupted discovery process'
    ],
    dependencies: ['Docker', 'Neo4j', 'Azure CLI']
  };
  
  try {
    const scenarios = await agent.generateTestScenarios(mockFeatureSpec);
    
    logger.info(`\nGenerated ${scenarios.length} test scenarios:`);
    
    scenarios.forEach((scenario, index) => {
      logger.info(`\n${index + 1}. ${scenario.name}`);
      logger.info(`   Priority: ${scenario.priority}`);
      logger.info(`   Interface: ${scenario.interface}`);
      logger.info(`   Description: ${scenario.description}`);
      logger.info(`   Steps: ${scenario.steps.length}`);
      logger.info(`   Verifications: ${scenario.verifications.length}`);
      logger.info(`   Tags: ${scenario.tags.join(', ')}`);
      logger.info(`   Expected: ${scenario.expectedOutcome.substring(0, 100)}...`);
      
      if (scenario.steps.length > 0) {
        logger.info('   Sample Steps:');
        scenario.steps.slice(0, 2).forEach((step, stepIndex) => {
          logger.info(`     ${stepIndex + 1}. ${step.action} "${step.target}"${step.value ? ` with "${step.value}"` : ''}`);
        });
      }
    });
    
  } catch (error) {
    logger.error(`Scenario generation failed: ${error}`);
  }
}

/**
 * Demonstrate complete workflow
 */
async function demonstrateCompleteWorkflow(): Promise<void> {
  logger.info('\n=== Complete Workflow Demonstration ===');
  
  const docsDir = join(__dirname, 'temp-docs');
  
  // Create agent with mock configuration
  const agent = createComprehensionAgent({
    llm: {
      provider: 'openai',
      apiKey: process.env.OPENAI_API_KEY || 'mock-key',
      model: 'gpt-4',
      temperature: 0.1,
      maxTokens: 4000
    },
    docsDir,
    includePatterns: ['**/*.md'],
    excludePatterns: ['**/node_modules/**', '**/temp/**']
  });
  
  try {
    // Initialize agent
    await agent.initialize();
    logger.info('ComprehensionAgent initialized successfully');
    
    // Run demonstrations
    await demonstrateFeatureDiscovery(agent);
    await demonstrateFeatureAnalysis(agent);
    await demonstrateScenarioGeneration(agent);
    
    // If LLM is available, run full workflow
    if (process.env.OPENAI_API_KEY || process.env.AZURE_OPENAI_KEY) {
      logger.info('\n=== Full Workflow with LLM ===');
      const allScenarios = await agent.processDiscoveredFeatures();
      logger.info(`\nComplete workflow generated ${allScenarios.length} test scenarios from documentation`);
      
      // Summary by priority
      const priorityCount = allScenarios.reduce((acc, scenario) => {
        acc[scenario.priority] = (acc[scenario.priority] || 0) + 1;
        return acc;
      }, {} as Record<string, number>);
      
      logger.info('\nScenarios by Priority:');
      Object.entries(priorityCount).forEach(([priority, count]) => {
        logger.info(`  ${priority}: ${count} scenarios`);
      });
    } else {
      logger.warn('\nSkipping full LLM workflow - no API key configured');
      logger.info('Set OPENAI_API_KEY or Azure OpenAI environment variables to test with real LLM');
    }
    
    // Cleanup
    await agent.cleanup();
    logger.info('\nComprehensionAgent demonstration completed successfully');
    
  } catch (error) {
    logger.error(`Demonstration failed: ${error}`);
  }
}

/**
 * Main demonstration function
 */
async function main(): Promise<void> {
  logger.info('ComprehensionAgent Demonstration Starting...');
  logger.info('============================================');
  
  try {
    // Create sample documentation
    createSampleDocs();
    
    // Run complete demonstration
    await demonstrateCompleteWorkflow();
    
    logger.info('\n============================================');
    logger.info('ComprehensionAgent Demonstration Complete!');
    
    // Cleanup temp files
    const { rmSync } = await import('fs');
    const tempDocsDir = join(__dirname, 'temp-docs');
    rmSync(tempDocsDir, { recursive: true, force: true });
    logger.info('Temporary files cleaned up');
    
  } catch (error) {
    logger.error(`Demonstration error: ${error}`);
    process.exit(1);
  }
}

// Run demonstration if this file is executed directly
if (require.main === module) {
  main().catch((error) => {
    logger.error(`Fatal error: ${error}`);
    process.exit(1);
  });
}

export default main;