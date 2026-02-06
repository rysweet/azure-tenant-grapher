# Resource-Level Fidelity Validation Test Plan

Comprehensive failing tests written following TDD (Test-Driven Development) approach for resource-level validation feature.

## Test Coverage Summary

Following the testing pyramid principle (60% unit, 30% integration, 10% E2E):

| Test Category | File | Test Classes | Approximate Tests | Coverage |
|--------------|------|--------------|------------------|----------|
| **Unit Tests** | `test_resource_fidelity_calculator.py` | 6 classes | ~50 tests | Core logic |
| **Unit Tests** | `test_resource_fidelity_security.py` | 7 classes | ~40 tests | Security |
| **Integration** | `test_resource_fidelity_end_to_end.py` | 6 classes | ~30 tests | Workflows |
| **E2E/CLI** | `test_fidelity_resource_level.py` | 10 classes | ~35 tests | User interface |

**Total**: ~155 tests covering all aspects of resource-level validation

## Test Files

### 1. Unit Tests - Core Calculator Logic
**File**: `tests/unit/test_resource_fidelity_calculator.py`

**Test Classes**:
- `TestResourceStatus` - Enum classification tests
- `TestRedactionLevel` - Security level enum tests
- `TestPropertyComparison` - Property-level comparison dataclass
- `TestResourceClassification` - Resource classification dataclass
- `TestResourceFidelityMetrics` - Metrics dataclass and calculations
- `TestResourceFidelityCalculator` - Core calculator functionality
- `TestResourceFidelityCalculatorEdgeCases` - Edge cases and error handling
- `TestResourceFidelityCalculatorIntegrationWithComparator` - Integration with existing ResourceComparator

**Key Test Coverage**:
- Neo4j query construction for source/target resources
- Property comparison logic (exact match, drift detection)
- Metrics calculation (fidelity %, drift %, coverage)
- Filter validation and application
- Output formatting (console table, JSON)
- Null value handling
- Nested object comparison
- Empty subscription handling
- Query error handling

### 2. Unit Tests - Security Controls
**File**: `tests/unit/test_resource_fidelity_security.py`

**Test Classes**:
- `TestSensitivePropertyDetection` - Pattern detection for passwords, keys, secrets
- `TestRedactionLevelFull` - FULL redaction (default, most secure)
- `TestRedactionLevelMinimal` - MINIMAL redaction (balanced visibility)
- `TestRedactionLevelNone` - NONE redaction (debugging only)
- `TestSecurityWarnings` - Warning generation for reports
- `TestRedactionInPropertyComparisons` - Redaction integration
- `TestCertificateAndPrivateKeyRedaction` - Certificate/private key handling
- `TestStorageAccountKeyRedaction` - Azure Storage key handling

**Key Test Coverage**:
- Detection of sensitive properties (passwords, keys, secrets, tokens)
- FULL redaction completely hides sensitive values
- MINIMAL redaction preserves server info but redacts credentials
- NONE redaction shows all values (with warnings)
- Connection string redaction
- API key redaction
- Certificate and private key redaction
- Storage account key redaction
- Security warning generation

### 3. Integration Tests - End-to-End Workflows
**File**: `tests/integration/test_resource_fidelity_end_to_end.py`

**Test Classes**:
- `TestResourceFidelityWithNeo4j` - Real Neo4j query integration
- `TestCrossSubscriptionComparison` - Cross-subscription validation
- `TestMultipleResourceTypes` - Multiple Azure resource types
- `TestHistoricalTracking` - Historical metrics tracking
- `TestJSONExport` - JSON export functionality
- `TestFilteredValidation` - Resource type filtering

**Key Test Coverage**:
- Querying source/target resources from Neo4j
- Resource type filtering in queries
- Cross-subscription drift detection
- Missing resource detection (source vs target)
- Metrics calculation across subscriptions
- Multi-resource-type validation
- Historical metrics storage
- Historical metrics querying
- JSON export structure validation
- JSON metadata inclusion
- Filtered validation by resource type

### 4. E2E Tests - CLI Command Interface
**File**: `tests/commands/test_fidelity_resource_level.py`

**Test Classes**:
- `TestFidelityCommandBasicExecution` - Basic command execution
- `TestFidelityCommandResourceTypeFiltering` - --resource-type option
- `TestFidelityCommandJSONExport` - --output option
- `TestFidelityCommandHistoricalTracking` - --track option
- `TestFidelityCommandRedactionLevels` - --redaction-level option
- `TestFidelityCommandSubscriptionOverrides` - --source-subscription/--target-subscription options
- `TestFidelityCommandErrorHandling` - Error handling and user messages
- `TestFidelityCommandConsoleFormatting` - Console output formatting
- `TestFidelityCommandCombinedOptions` - Multiple options together

**Key Test Coverage**:
- Command requires --resource-level flag
- Console output formatting
- Resource type filtering
- JSON export creation and validation
- Historical tracking saves to database
- Redaction level options (FULL, MINIMAL, NONE)
- Subscription ID overrides
- Error handling (Neo4j connection, no resources, invalid paths)
- Console output formatting (header, details, summary, symbols)
- Combined options (filter + export, tracking + redaction, etc.)

## Expected Test Behavior

### All Tests Will FAIL Initially
This is expected and correct for TDD approach:

```bash
$ pytest tests/unit/test_resource_fidelity_calculator.py
# Expected: ImportError or ModuleNotFoundError
# Reason: ResourceFidelityCalculator doesn't exist yet
```

### Tests Define Expected Behavior
Each test clearly specifies:
1. **What** the feature should do
2. **How** it should behave
3. **What** output is expected

### Implementation Guidance
Tests provide clear specifications for implementation:
- Method signatures
- Input/output formats
- Error handling requirements
- Edge case handling

## Running Tests

### Run All Resource Fidelity Tests
```bash
pytest tests/ -k "resource_fidelity"
```

### Run Unit Tests Only
```bash
pytest tests/unit/test_resource_fidelity_calculator.py
pytest tests/unit/test_resource_fidelity_security.py
```

### Run Integration Tests Only
```bash
pytest tests/integration/test_resource_fidelity_end_to_end.py -m integration
```

### Run E2E Tests Only
```bash
pytest tests/commands/test_fidelity_resource_level.py
```

### Run Tests by Category
```bash
# Security tests
pytest tests/ -k "security or redaction"

# Neo4j integration tests
pytest tests/ -k "neo4j"

# CLI tests
pytest tests/commands/test_fidelity_resource_level.py
```

## Test Coverage Metrics

### Expected Coverage After Implementation

| Component | Target Coverage | Priority |
|-----------|----------------|----------|
| Core Calculator | 95%+ | HIGH |
| Security/Redaction | 100% | CRITICAL |
| Neo4j Integration | 85%+ | HIGH |
| CLI Commands | 90%+ | HIGH |
| Property Comparison | 95%+ | HIGH |
| Metrics Calculation | 95%+ | HIGH |

### Critical Paths Covered

1. **Source/Target Query** → Property Comparison → Classification → Metrics
2. **Sensitive Property Detection** → Redaction → Secure Export
3. **CLI Command** → Calculator → Output Formatting → JSON Export
4. **Historical Tracking** → Database Write → Query Historical Data

## Testing Strategy

### Unit Tests (60%)
- Fast execution (< 100ms per test)
- Heavy mocking of external dependencies
- Focus on individual methods and functions
- Test edge cases and error conditions

### Integration Tests (30%)
- Test component interactions
- Mock only external systems (Azure, file system)
- Real Neo4j queries (mocked driver)
- Test complete workflows

### E2E Tests (10%)
- Test user workflows end-to-end
- Use Click's CliRunner for CLI testing
- Test complete command execution
- Verify user-facing output

## Test Patterns Used

### Arrange-Act-Assert (AAA)
All tests follow AAA pattern:
```python
def test_example():
    # Arrange - Set up test data
    calculator = ResourceFidelityCalculator(...)

    # Act - Execute the code under test
    result = calculator.calculate_fidelity()

    # Assert - Verify expected behavior
    assert result.metrics.total_resources == 2
```

### Fixtures for Test Data
Pytest fixtures provide reusable test data:
```python
@pytest.fixture
def mock_calculator():
    """Create mock calculator with sample results."""
    return Mock(...)
```

### Parametrized Tests
Multiple test cases from single test:
```python
@pytest.mark.parametrize("prop_path,expected", [
    ("password", True),
    ("apiKey", True),
    ("sku.name", False),
])
def test_sensitive_detection(prop_path, expected):
    assert is_sensitive(prop_path) == expected
```

## Next Steps

1. **Run tests** - Verify all tests fail (TDD confirmation)
2. **Implement features** - Make tests pass one by one
3. **Refactor** - Clean up implementation while keeping tests green
4. **Add tests** - Add tests for any edge cases discovered during implementation

## Test Maintenance

### When to Update Tests
- When requirements change
- When edge cases are discovered
- When security patterns change
- When CLI interface changes

### Test Documentation
Each test includes:
- Clear docstring explaining what it tests
- Comments for complex assertions
- References to documentation when applicable

## Security Testing

### Sensitive Property Patterns Tested
- `password`, `adminPassword`, `osProfile.adminPassword`
- `key`, `apiKey`, `secretKey`, `storageAccountKeys`
- `secret`, `clientSecret`, `vaultSecrets`
- `token`, `accessToken`, `bearerToken`
- `connectionString`, `primaryConnectionString`
- `certificate`, `sslCertificate`, `tlsCertificate`
- `privateKey`, `sshPrivateKey`

### Redaction Levels Tested
- **FULL**: All sensitive values → `[REDACTED]`
- **MINIMAL**: Preserves structure, redacts credentials
- **NONE**: Shows all values (with warnings)

---

**Test Status**: All tests FAILING (expected - TDD approach)
**Last Updated**: 2026-02-05
**Feature**: Resource-Level Fidelity Validation
**Issue**: #894
