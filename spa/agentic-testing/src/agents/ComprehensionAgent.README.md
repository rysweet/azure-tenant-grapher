# ComprehensionAgent

The ComprehensionAgent is an intelligent testing agent that uses Large Language Models (LLMs) to understand software features from documentation and automatically generate comprehensive test scenarios. It bridges the gap between documentation and testing by leveraging AI to interpret natural language descriptions and create structured test cases.

## Overview

The ComprehensionAgent analyzes markdown documentation files to:

1. **Discover Features**: Extract CLI commands, UI elements, and API endpoints from documentation
2. **Analyze Features**: Use LLM to understand feature specifications, inputs, outputs, and behavior
3. **Generate Test Scenarios**: Create comprehensive test scenarios including success paths, failure modes, and edge cases
4. **Support Multiple Interfaces**: Generate tests for CLI, GUI, API, and mixed interfaces

## Key Components

### DocumentationLoader

Handles scanning and parsing documentation files:

- **File Discovery**: Finds markdown files using configurable glob patterns
- **Feature Extraction**: Uses regex patterns to identify CLI commands, UI elements, and API endpoints
- **Context Extraction**: Captures surrounding documentation context for LLM analysis

### ComprehensionAgent

Main agent class implementing the IAgent interface:

- **LLM Integration**: Supports both OpenAI and Azure OpenAI
- **Feature Analysis**: Processes documentation through LLM to extract structured specifications
- **Scenario Generation**: Creates multiple test scenarios per feature
- **Interface Detection**: Automatically determines appropriate test interface (CLI/GUI/API)

## Configuration

### LLM Configuration

```typescript
interface LLMConfig {
  provider: 'openai' | 'azure';
  apiKey: string;
  model: string;
  temperature: number;
  maxTokens: number;
  // Azure-specific
  endpoint?: string;
  deployment?: string;
  apiVersion?: string;
}
```

### Agent Configuration

```typescript
interface ComprehensionAgentConfig {
  llm: LLMConfig;
  docsDir: string;
  includePatterns: string[];
  excludePatterns: string[];
  maxContextLength: number;
}
```

## Usage Examples

### Basic Usage

```typescript
import { createComprehensionAgent } from './ComprehensionAgent';

const agent = createComprehensionAgent({
  llm: {
    provider: 'openai',
    apiKey: process.env.OPENAI_API_KEY!,
    model: 'gpt-4',
    temperature: 0.1,
    maxTokens: 4000
  },
  docsDir: './docs'
});

await agent.initialize();

// Discover all features from documentation
const features = await agent.discoverFeatures();

// Generate test scenarios for all features
const scenarios = await agent.processDiscoveredFeatures();

await agent.cleanup();
```

### Azure OpenAI Configuration

```typescript
const agent = createComprehensionAgent({
  llm: {
    provider: 'azure',
    apiKey: process.env.AZURE_OPENAI_KEY!,
    model: 'gpt-4',
    endpoint: process.env.AZURE_OPENAI_ENDPOINT!,
    deployment: process.env.AZURE_OPENAI_DEPLOYMENT!,
    apiVersion: '2024-02-01',
    temperature: 0.1,
    maxTokens: 4000
  }
});
```

### Analyzing Specific Features

```typescript
const featureDoc = `
# Build Command

The \`atg build\` command discovers Azure resources and builds a Neo4j graph database.

## Usage
\`\`\`bash
uv run atg build --tenant-id <TENANT_ID>
\`\`\`

## Success Criteria
- Neo4j database is populated with discovered resources
- Resource relationships are correctly established
`;

const featureSpec = await agent.analyzeFeature(featureDoc);
const scenarios = await agent.generateTestScenarios(featureSpec);
```

## Feature Discovery

The agent automatically discovers features from documentation using pattern matching:

### CLI Commands

Recognizes patterns like:
- `atg build`
- `azure-tenant-grapher generate-iac`
- `uv run atg doctor`

### UI Elements

Identifies headers containing UI keywords:
- Tab, Button, Page, Dialog, Menu
- Panel, Widget, Form, Input
- SPA, GUI, Interface, Navigation

### API Endpoints

Detects HTTP method patterns:
- `GET /api/users`
- `POST /api/resources`
- `DELETE /api/cleanup`

## Test Scenario Generation

For each discovered feature, the agent generates multiple test scenarios:

### Success Path Scenarios
- **Priority**: HIGH
- **Tags**: success-path, smoke-test
- **Purpose**: Verify feature works with valid inputs

### Failure Mode Scenarios
- **Priority**: MEDIUM
- **Tags**: failure-mode, error-handling
- **Purpose**: Verify graceful error handling

### Edge Case Scenarios
- **Priority**: LOW
- **Tags**: edge-case
- **Purpose**: Test boundary conditions and unusual inputs

## Generated Test Structure

Each generated test scenario includes:

```typescript
interface TestScenario {
  id: string;                    // Unique identifier
  name: string;                  // Human-readable name
  description: string;           // Detailed description
  priority: Priority;            // HIGH/MEDIUM/LOW
  interface: TestInterface;      // CLI/GUI/API/MIXED
  prerequisites: string[];       // Setup requirements
  steps: TestStep[];            // Execution steps
  verifications: VerificationStep[];  // Result validation
  expectedOutcome: string;       // Expected final result
  estimatedDuration: number;     // Seconds
  tags: string[];               // Categorization tags
  enabled: boolean;             // Whether test is active
}
```

## LLM Prompting Strategy

The agent uses structured prompts to extract consistent information:

### Feature Analysis Prompt

```
Analyze this feature documentation and extract structured information.

Documentation:
[FEATURE_CONTEXT]

Extract and return ONLY valid JSON in this format:
{
  "name": "feature name",
  "purpose": "what the feature does",
  "inputs": [{"name": "input1", "type": "string", "required": true, "description": "..."}],
  "outputs": [{"name": "output1", "type": "object", "description": "..."}],
  "success_criteria": ["criterion 1", "criterion 2"],
  "failure_modes": ["possible failure 1", "possible failure 2"],
  "edge_cases": ["edge case 1", "edge case 2"],
  "dependencies": ["dependency1", "dependency2"]
}
```

## Error Handling

The agent implements comprehensive error handling:

### LLM Failures
- Falls back to basic feature specifications
- Continues processing other features
- Logs detailed error information

### Documentation Issues
- Handles missing or corrupted files
- Processes available files and continues
- Reports file loading problems

### API Limits
- Respects rate limiting
- Handles token limit exceeded errors
- Provides truncated context when necessary

## Integration with Other Agents

The ComprehensionAgent works seamlessly with other testing agents:

### With CLIAgent
- Generates CLI test scenarios
- Provides command specifications
- Defines expected outputs

### With ElectronUIAgent
- Creates UI interaction scenarios
- Specifies element targets
- Defines verification steps

### With IssueReporter
- Provides scenario context for bug reports
- Includes feature specifications in issues
- Links failures to documentation

### With PriorityAgent
- Contributes to priority scoring
- Provides feature impact analysis
- Helps categorize test failures

## Environment Variables

Required environment variables:

### OpenAI Configuration
```bash
OPENAI_API_KEY=your_openai_api_key
```

### Azure OpenAI Configuration
```bash
AZURE_OPENAI_KEY=your_azure_openai_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-01
```

## Best Practices

### Documentation Structure
- Use clear, descriptive headers
- Include usage examples
- Document success criteria and failure modes
- Specify input/output requirements

### Configuration
- Start with lower temperature (0.1-0.2) for consistent results
- Adjust maxTokens based on documentation complexity
- Use appropriate context length limits
- Configure relevant file patterns

### Testing
- Review generated scenarios for accuracy
- Adjust prompts if results are inconsistent
- Monitor LLM costs and usage
- Validate against actual feature behavior

## Limitations

### LLM Dependence
- Requires API access to OpenAI or Azure OpenAI
- Quality depends on prompt engineering
- May generate inaccurate scenarios from unclear documentation

### Documentation Quality
- Results depend on documentation completeness
- Cannot infer features not documented
- May miss implicit requirements

### Context Limits
- Limited by LLM token limits
- Large documents may be truncated
- Complex features may need multiple passes

## Future Enhancements

### Planned Improvements
- Support for additional LLM providers
- Interactive scenario refinement
- Integration with code analysis
- Automated documentation updates
- Multi-language documentation support

### Integration Opportunities
- CI/CD pipeline integration
- Automated test generation workflows
- Documentation quality assessment
- Feature coverage analysis

## Contributing

When contributing to the ComprehensionAgent:

1. Follow TypeScript best practices
2. Add comprehensive tests for new features
3. Update documentation and examples
4. Consider LLM cost implications
5. Test with both OpenAI and Azure OpenAI
6. Validate generated scenarios manually

## Support

For issues and questions:
- Check the examples in `examples/ComprehensionAgent.example.ts`
- Review test cases in `__tests__/ComprehensionAgent.test.ts`
- Examine generated scenarios for patterns
- Monitor LLM API logs for errors
- Verify environment variable configuration
