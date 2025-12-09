## ATG Client-Server Test Suite

Comprehensive TDD test suite fer the Azure Tenant Grapher client-server feature followin' the testin' pyramid approach.

### Test Organization

```
tests/remote/
├── unit/                    # 60% of tests - Fast, isolated
│   ├── test_api_authentication.py          (18 tests)
│   ├── test_configuration.py                (25 tests)
│   ├── test_neo4j_connection.py             (20 tests)
│   ├── test_websocket_protocol.py           (15 tests)
│   └── test_cli_dispatcher.py               (20 tests)
├── integration/             # 30% of tests - Component integration
│   ├── test_api_endpoints.py                (25 tests)
│   ├── test_cli_remote_mode.py              (12 tests)
│   ├── test_progress_streaming.py           (8 tests)
│   └── test_error_handling.py               (10 tests)
└── e2e/                     # 10% of tests - Complete workflows
    ├── test_remote_scan_workflow.py         (12 tests)
    └── test_deployment_workflow.py          (3 tests)
```

**Total Tests: ~168 tests**
- Unit: ~98 tests (58%)
- Integration: ~55 tests (33%)
- E2E: ~15 tests (9%)

### Running Tests

```bash
# Run all tests
pytest tests/remote/

# Run by layer
pytest tests/remote/unit/           # Fast unit tests
pytest tests/remote/integration/    # Integration tests
pytest tests/remote/e2e/            # E2E tests (slower)

# Run specific test file
pytest tests/remote/unit/test_api_authentication.py -v

# Run tests with coverage
pytest tests/remote/ --cov=src.remote --cov-report=term-missing

# Run tests matching pattern
pytest tests/remote/ -k "authentication"

# Run E2E tests (requires Docker for Neo4j)
pytest tests/remote/e2e/ --run-integration
```

### Test Philosophy

**Unit Tests (60%):**
- Test single components in isolation
- Mock all external dependencies
- Fast execution (< 100ms per test)
- Follow testing pyramid base

**Integration Tests (30%):**
- Test component interactions
- Use real or comprehensive mocks
- Moderate execution (< 5s per test)
- Verify API contracts

**E2E Tests (10%):**
- Test complete user workflows
- Use real services when possible
- Slower execution (< 30s per test)
- Validate end-user scenarios

### Architecture Coverage

Tests validate against these architecture documents:

1. **Specs/SIMPLIFIED_ARCHITECTURE.md** - Core architecture
2. **modules/api_contract/openapi.yaml** - API contracts
3. **NEO4J_CONNECTION_DESIGN.md** - Database design
4. **docs/security/ATG_CLIENT_SERVER_SECURITY_DESIGN.md** - Security
5. **docs/remote-mode/** - User documentation

### Key Test Areas

**Authentication & Authorization:**
- API key format validation
- Bearer token authentication
- Key expiration handling
- Constant-time comparison
- Rate limiting enforcement

**Configuration Management:**
- Environment variable parsing
- .env file loading
- Validation rules
- Secret redaction
- Multi-environment support

**Neo4j Connection:**
- Connection pooling
- Health checks
- Retry logic
- Transaction management
- Performance monitoring

**WebSocket Protocol:**
- Message serialization
- Progress streaming
- Error handling
- Connection lifecycle
- High-throughput handling

**CLI Dispatcher:**
- Local vs remote routing
- Mode detection
- Parameter validation
- Progress callbacks
- Error propagation

**API Endpoints:**
- Request validation
- Authentication middleware
- Error handling
- Rate limiting
- Long-running operations

**Progress Streaming:**
- WebSocket connections
- Real-time updates
- Error notifications
- Completion messages

**Complete Workflows:**
- End-to-end scan
- Cross-tenant deployment
- Concurrent operations
- Service reliability

### Test Fixtures

Common fixtures available in `conftest.py`:

```python
@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for unit tests."""
    pass

@pytest.fixture
def mock_azure_credential():
    """Mock Azure credential."""
    pass

@pytest.fixture
def test_api_key():
    """Valid test API key."""
    pass

@pytest.fixture
async def running_atg_service():
    """Running ATG service for E2E tests."""
    pass

@pytest.fixture
async def e2e_neo4j_container():
    """Neo4j container for E2E tests."""
    pass
```

### Current Status

**Implementation Status: NOT STARTED**

All tests are currently **failing by design** (TDD approach). They define:
- Expected interfaces
- Required behavior
- Error handling
- Performance requirements

**Next Steps:**
1. Implement authentication module (`src/remote/auth.py`)
2. Implement configuration module (`src/remote/client/config.py`, `src/remote/server/config.py`)
3. Implement Neo4j connection manager (`src/remote/db/connection_manager.py`)
4. Implement WebSocket protocol (`src/remote/websocket/`)
5. Implement CLI dispatcher (`src/remote/dispatcher.py`)
6. Implement API endpoints (`src/remote/server/main.py`)

### Test Data

Test data patterns used:

**Tenant IDs:**
- Valid: `12345678-1234-1234-1234-123456789012`
- Invalid: `invalid-tenant-id`, `short`, etc.

**API Keys:**
- Dev: `atg_dev_<64-hex-chars>`
- Integration: `atg_integration_<64-hex-chars>`
- Invalid: Various malformed patterns

**Neo4j URIs:**
- Local: `bolt://localhost:7687`
- Container: `bolt://neo4j-dev:7687`

### Performance Targets

**Unit Tests:**
- Individual test: < 100ms
- Full suite: < 10s

**Integration Tests:**
- Individual test: < 5s
- Full suite: < 2min

**E2E Tests:**
- Individual test: < 30s
- Full suite: < 5min

**Total Suite:** < 8min

### CI/CD Integration

Tests run in GitHub Actions workflow:

```yaml
- name: Run unit tests
  run: pytest tests/remote/unit/ --cov

- name: Run integration tests
  run: pytest tests/remote/integration/ --run-integration

- name: Run E2E tests (optional)
  run: pytest tests/remote/e2e/ --run-e2e
  if: github.event_name == 'pull_request'
```

### Maintenance

**Adding New Tests:**
1. Follow test file naming: `test_<module>.py`
2. Use descriptive test names: `test_<what>_<scenario>()`
3. Include docstrings explaining validation
4. Follow testing pyramid ratios
5. Update this README with test counts

**Modifying Tests:**
1. Ensure tests still fail initially (TDD)
2. Update related fixtures if needed
3. Maintain performance targets
4. Update documentation

### Troubleshooting

**Tests not found:**
```bash
# Ensure pytest can find tests
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
pytest tests/remote/ -v
```

**Import errors:**
```bash
# Install in development mode
pip install -e .
```

**Neo4j connection errors:**
```bash
# Start Neo4j container
docker run -p 7687:7687 -e NEO4J_AUTH=neo4j/test_password neo4j:5.15-community
```

**WebSocket errors:**
```bash
# Check WebSocket support
pip install websockets
```

### References

- **Testing Pyramid**: 60% unit, 30% integration, 10% E2E
- **TDD Approach**: Write failing tests first
- **ATG Patterns**: Follow existing test patterns in `tests/`
- **Philosophy**: Fast, isolated, repeatable tests

---

**Created**: 2025-12-09
**Status**: Initial test suite (all tests failing - ready for TDD implementation)
**Total Tests**: 168 tests across all layers
