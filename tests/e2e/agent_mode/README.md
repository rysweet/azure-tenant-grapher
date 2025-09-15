# Agent Mode E2E Tests

Comprehensive end-to-end tests for Agent Mode and MCP Integration in Azure Tenant Grapher.

## Test Structure

```
tests/e2e/agent_mode/
├── __init__.py                 # Package initialization
├── conftest.py                 # Fixtures and mocks for testing
├── test_agent_mode_e2e.py      # Main agent mode E2E tests
├── test_mcp_tools.py           # MCP tool-specific tests
└── README.md                   # This file
```

## Gadugi Test Scenarios

```
spa/agentic-testing/scenarios/
└── agent-mode-workflows.yaml   # YAML-based test scenarios for UI testing
```

## Test Categories

### 1. Agent Mode E2E Tests (`test_agent_mode_e2e.py`)

- **Agent Mode Initialization**: Tests startup and MCP connection
- **Natural Language Processing**: Validates query understanding and processing
- **Tool Chaining**: Tests complex multi-tool workflows
- **WebSocket Communication**: Real-time update testing
- **Error Handling**: MCP unavailable fallback scenarios
- **Concurrent Queries**: Tests parallel query execution
- **UI Interactions**: Tests various UI interaction patterns
- **Streaming Responses**: Tests real-time streaming capabilities
- **Resilience**: Tests recovery from failures

### 2. MCP Tools Tests (`test_mcp_tools.py`)

- **Query Graph Tool**: Tests Neo4j graph queries
- **Discover Resources Tool**: Tests Azure resource discovery
- **Analyze Security Tool**: Tests security posture analysis
- **Generate Terraform Tool**: Tests IaC generation
- **Tool Composition**: Tests combining multiple tools
- **Error Handling**: Tests tool-specific error scenarios
- **Validation**: Tests parameter and response validation

### 3. UI Workflow Tests (`agent-mode-workflows.yaml`)

- **Agent Mode Initialization**: UI-based startup verification
- **Natural Language Queries**: UI query submission and response
- **Multi-Tool Workflows**: Complex UI-driven workflows
- **WebSocket Streaming**: Real-time UI updates
- **Error Recovery**: UI behavior during failures
- **Concurrent Operations**: Multiple tab/query handling
- **User Feedback**: Feedback collection flows
- **Performance Monitoring**: Metrics display validation
- **Session Recovery**: Reconnection handling

## Running the Tests

### Prerequisites

1. Install test dependencies:
```bash
pip install -r requirements-dev.txt
```

2. Start required services:
```bash
# Start Neo4j
docker-compose up -d neo4j

# Start MCP server (in separate terminal)
python -m src.mcp_server

# Start the SPA (in separate terminal)
cd spa && npm start
```

### Running Python Tests

```bash
# Run all E2E tests
pytest tests/e2e/agent_mode/ -v

# Run specific test file
pytest tests/e2e/agent_mode/test_agent_mode_e2e.py -v

# Run specific test
pytest tests/e2e/agent_mode/test_agent_mode_e2e.py::TestAgentModeE2E::test_natural_language_query_processing -v

# Run with coverage
pytest tests/e2e/agent_mode/ --cov=src.services.mcp_integration --cov-report=html

# Run with markers
pytest tests/e2e/agent_mode/ -m "not slow"
```

### Running Gadugi UI Tests

```bash
# Navigate to agentic-testing directory
cd spa/agentic-testing

# Install dependencies
npm install

# Run agent mode scenarios
npm run test:scenario -- scenarios/agent-mode-workflows.yaml

# Run specific scenario
npm run test:scenario -- scenarios/agent-mode-workflows.yaml --scenario=nlp-query-basic

# Run test suite
npm run test:suite -- --suite="Basic Agent Mode"

# Run with video recording
npm run test:scenario -- scenarios/agent-mode-workflows.yaml --video

# Run in headless mode
npm run test:scenario -- scenarios/agent-mode-workflows.yaml --headless
```

## Mock Data

The tests use comprehensive mock data defined in `conftest.py`:

- **Azure Resources**: Subscriptions, resource groups, VMs, storage accounts
- **Graph Data**: Users, groups, relationships
- **MCP Responses**: Tool results, error conditions
- **WebSocket Messages**: Real-time updates, streaming responses

## Test Fixtures

Key fixtures provided by `conftest.py`:

- `mock_azure_credentials`: Mocked Azure authentication
- `mock_graph_client`: Mocked Microsoft Graph client
- `mock_azure_clients`: Mocked Azure SDK clients
- `mock_mcp_server`: Mock MCP WebSocket server
- `mock_neo4j_session`: Mocked Neo4j database session
- `agent_mode_config`: Test configuration
- `mock_websocket_client`: WebSocket client for testing
- `mock_llm_client`: Mocked LLM for intent parsing
- `performance_monitor`: Performance metrics tracking

## Environment Variables

Set these for testing:

```bash
export NEO4J_PASSWORD=test_password
export MCP_ENDPOINT=ws://localhost:8080
export AZURE_TENANT_ID=test-tenant-1
export AZURE_SUBSCRIPTION_ID=test-sub-1
```

## CI/CD Integration

### GitHub Actions

```yaml
- name: Run Agent Mode E2E Tests
  run: |
    pytest tests/e2e/agent_mode/ \
      --junit-xml=test-results/agent-mode-e2e.xml \
      --cov=src.services.mcp_integration \
      --cov-report=xml
```

### Docker Compose for Testing

```yaml
# docker-compose.test.yml
services:
  neo4j:
    image: neo4j:5.x
    environment:
      NEO4J_AUTH: neo4j/test_password
    ports:
      - "7687:7687"
      - "7474:7474"

  mcp-server:
    build:
      context: .
      dockerfile: Dockerfile.mcp
    ports:
      - "8080:8080"
    environment:
      NEO4J_URI: bolt://neo4j:7687
      NEO4J_PASSWORD: test_password
```

## Debugging Tips

1. **Enable debug logging**:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

2. **Use pytest debugging**:
```bash
pytest tests/e2e/agent_mode/ -vv --pdb
```

3. **Capture WebSocket traffic**:
```python
# In conftest.py, add logging to mock_mcp_server
async def handle_connection(websocket, path):
    print(f"WS Message: {message}")  # Add logging
```

4. **Check UI test screenshots**:
```bash
# Screenshots saved in:
spa/agentic-testing/screenshots/
```

## Performance Benchmarks

Expected performance metrics:

- Agent mode initialization: < 2 seconds
- Simple query processing: < 3 seconds
- Multi-tool workflow: < 10 seconds
- WebSocket connection: < 500ms
- Tool execution: < 2 seconds per tool
- Concurrent queries: < 1.5x single query time

## Troubleshooting

### Common Issues

1. **MCP Connection Failed**
   - Ensure MCP server is running
   - Check WebSocket endpoint configuration
   - Verify network connectivity

2. **Neo4j Authentication Error**
   - Set NEO4J_PASSWORD environment variable
   - Ensure Neo4j container is running
   - Check database connection string

3. **UI Tests Failing**
   - Ensure SPA is running on correct port
   - Check for JavaScript errors in console
   - Verify element selectors are up-to-date

4. **Timeout Errors**
   - Increase timeout values for slow systems
   - Check for blocking operations
   - Ensure mock servers are responding

## Contributing

When adding new tests:

1. Follow existing test patterns
2. Add appropriate fixtures to `conftest.py`
3. Update mock data as needed
4. Document new test scenarios
5. Ensure tests are independent and repeatable
6. Add performance assertions where relevant

## Test Coverage Goals

- Agent Mode Service: > 90%
- MCP Integration: > 85%
- WebSocket Handlers: > 80%
- UI Workflows: > 75%

## Future Enhancements

- [ ] Add load testing scenarios
- [ ] Implement chaos testing for resilience
- [ ] Add accessibility testing for UI
- [ ] Create performance regression tests
- [ ] Add security testing scenarios
- [ ] Implement contract testing for MCP protocol