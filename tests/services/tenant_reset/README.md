## Tenant Reset Test Suite (Issue #627)

Comprehensive test coverage for the Tenant Reset feature following TDD methodology.

### Test Organization

#### 1. ATG SP Preservation (`test_atg_sp_preservation.py`)

**8 test classes covering CRITICAL security requirement:**

- `TestATGSPIdentification`: Multi-source SP identification
- `TestATGSPPreservationTenantScope`: Tenant-level preservation
- `TestATGSPPreservationSubscriptionScope`: Subscription-level preservation
- `TestATGSPPreservationResourceGroupScope`: Resource group-level preservation
- `TestATGSPPreservationResourceScope`: Single resource preservation
- `TestConfigurationIntegrity`: Configuration tampering detection
- `TestPreFlightValidation`: Pre-flight SP validation
- `TestPostDeletionVerification`: Post-deletion SP verification

**Critical Behaviors Tested:**
- ATG SP NEVER deleted under ANY circumstances
- Multi-source verification (env, CLI, Neo4j, config)
- Configuration tampering detection
- Pre-flight and post-deletion validation
- Emergency restore on accidental deletion

#### 2. Confirmation Flow (`test_confirmation_flow.py`)

**6 test classes covering 5-stage confirmation:**

- `TestConfirmationFlowStages`: Each of 5 stages individually
- `TestFullConfirmationFlow`: Complete flow integration
- `TestConfirmationBypass`: Force flag prevention
- `TestDryRunMode`: Dry-run without confirmation
- `TestKeyboardInterrupt`: Ctrl+C handling

**Critical Behaviors Tested:**
- 5-stage confirmation (scope → preview → type tenant ID → ATG SP ack → DELETE)
- Typed "DELETE" requirement (case-sensitive)
- NO --force or --yes flags allowed
- 3-second delay before final confirmation
- Dry-run mode skips confirmation safely

#### 3. Scope Calculation (`test_scope_calculation.py`)

**5 test classes covering all scopes:**

- `TestTenantScopeCalculation`: Entire tenant
- `TestSubscriptionScopeCalculation`: Single/multiple subscriptions
- `TestResourceGroupScopeCalculation`: Single/multiple resource groups
- `TestResourceScopeCalculation`: Single resource
- `TestScopeBoundaryValidation`: Cross-tenant/subscription validation

**Critical Behaviors Tested:**
- Tenant scope includes all subscriptions + identities
- Subscription scope filters correctly
- Resource group scope respects boundaries
- Single resource scope validates existence
- Empty scopes handled gracefully

#### 4. Security Controls (`test_security_controls.py`)

**10 test classes covering ALL 10 security controls:**

- `TestRateLimiting`: 1 reset/hour/tenant enforcement
- `TestDistributedLock`: Concurrent prevention via Redis
- `TestInputValidation`: Injection attack prevention
- `TestAuditLogTamperDetection`: Cryptographic chain validation
- `TestSecureErrorMessages`: Information disclosure prevention
- `TestNoForceFlag`: Force flag rejection

**Critical Behaviors Tested:**
- Rate limiting: First reset allowed, second blocked for 1 hour
- Distributed lock: Concurrent resets blocked on same tenant
- Input validation: Rejects malformed GUIDs, path traversal, injection
- Audit log: Tamper detection via cryptographic chain
- Error messages: Sanitize GUIDs, paths, IPs
- NO --force or --yes flags exist

#### 5. Deletion Logic (`test_deletion_logic.py`)

**6 test classes covering execution:**

- `TestDependencyOrdering`: Reverse dependency order
- `TestDeletionExecution`: Concurrent deletion with waves
- `TestAzureSDKIntegration`: Azure API calls
- `TestEntraIDDeletion`: Identity deletion
- `TestGraphCleanup`: Neo4j cleanup
- `TestErrorHandling`: Locked resources, permissions, network errors

**Critical Behaviors Tested:**
- Dependency-aware ordering (VMs before disks, NICs before VNets)
- Concurrent deletion respects concurrency limit
- Waves execute sequentially
- Partial failures tracked and reported
- Graph cleanup uses parameterized queries

### Running Tests

```bash
# Run all tenant reset tests
pytest tests/services/tenant_reset/ -v

# Run specific test file
pytest tests/services/tenant_reset/test_atg_sp_preservation.py -v

# Run security-critical tests only
pytest tests/services/tenant_reset/ -m security -v

# Run with coverage
pytest tests/services/tenant_reset/ --cov=src.services.tenant_reset_service --cov-report=term-missing
```

### Test Fixtures

All tests use shared fixtures from `conftest.py`:

- `mock_azure_credential`: Mock Azure credential
- `mock_resource_management_client`: Mock Azure SDK resource client
- `mock_graph_client`: Mock Microsoft Graph API client
- `mock_neo4j_driver`: Mock Neo4j driver
- `mock_redis_client`: Mock Redis client
- `mock_scope_data`: Mock scope calculation results
- `mock_azure_sdk_all`: Comprehensive SDK mocking

### Expected Test Status

**ALL TESTS ARE FAILING** (by design - TDD methodology)

These tests were written BEFORE implementation. They will pass once:

1. `TenantResetService` is implemented (`src/services/tenant_reset_service.py`)
2. `ResetConfirmation` is implemented (`src/services/reset_confirmation.py`)
3. `TamperProofAuditLog` is implemented (`src/services/audit_log.py`)
4. CLI commands are implemented (`src/commands/tenant_reset.py`)
5. Security controls are implemented (rate limiter, locks, validation)

### Test Coverage Goals

- **ATG SP Preservation**: 100% coverage (CRITICAL - no SP deletion)
- **Confirmation Flow**: 100% coverage (prevents accidents)
- **Scope Calculation**: 90% coverage (complex branching)
- **Security Controls**: 100% coverage (all 10 controls)
- **Deletion Logic**: 85% coverage (error paths)

**Overall Target: 95% line coverage**

### Test Metrics

- Total test files: 5
- Total test classes: ~25
- Total test methods: ~50-60
- Security-critical tests: ~25 (marked with `@pytest.mark.security`)
- Integration tests: ~10
- Unit tests: ~40-50

### Mock Dependencies

Tests mock the following external dependencies:

- **Azure SDK**:
  - `azure.identity.DefaultAzureCredential`
  - `azure.mgmt.resource.ResourceManagementClient`
  - `azure.mgmt.authorization.AuthorizationManagementClient`

- **Microsoft Graph**:
  - `msgraph.GraphServiceClient`

- **Neo4j**:
  - `neo4j.AsyncGraphDatabase.driver`

- **Redis**:
  - `redis.Redis`

### Test Markers

- `@pytest.mark.security`: Security-critical tests (rate limiting, locks, ATG SP preservation)
- `@pytest.mark.unit`: Unit tests (individual functions)
- `@pytest.mark.integration`: Integration tests (multiple components)
- `@pytest.mark.asyncio`: Async tests

### Notes

1. All imports will fail until implementation exists (expected for TDD)
2. Tests use `pytest-asyncio` for async test support
3. Tests use `pytest-mock` for mocking Azure SDK
4. SecurityError and RateLimitError exceptions defined in conftest.py
5. All tests follow AAA pattern (Arrange, Act, Assert)

### Related Documentation

- **Design**: `docs/security/ISSUE-627-SECURITY-DESIGN-REVIEW.md`
- **API Reference**: `docs/reference/TENANT_RESET_API.md`
- **User Guide**: `docs/guides/TENANT_RESET_GUIDE.md`
- **Safety Guide**: `docs/guides/TENANT_RESET_SAFETY.md`
