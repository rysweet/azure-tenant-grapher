# AzureTenantGrapher.Container

## Neo4j Test Container Policy

### Container Naming and Password Policy

- **Container Name:**
  The Neo4j test container name should be set via the `NEO4J_CONTAINER_NAME` environment variable.
  If not set, a unique name should be generated for each test run (e.g., `azure-tenant-grapher-neo4j-<random>`).
  This avoids race conditions and port conflicts in parallel or CI test runs.

- **Password:**
  The Neo4j password for tests must be provided via the `NEO4J_PASSWORD` environment variable.
  If not set, a random password should be generated for each test run.
  **Never hardcode secrets or passwords in test code or fixtures.**

### Parallel/CI/Idempotency

- All test containers and volumes must be uniquely named per test run to avoid conflicts in parallel/CI scenarios.
- Tests and cleanup logic must be idempotent: repeated setup/teardown should not fail or leave artifacts.
- Cleanup of all test artifacts (containers, volumes) must be ensured even on test failure.

### Test Password Policy

- All secrets, credentials, and sensitive parameters must be provided via environment variables or secure test infrastructure.
- If a test cannot run without a secret, it should be skipped with a clear message.
- **Never check in real or dummy secrets, passwords, or tokens to the repository.**

### Example (C#)

```csharp
// Set environment variables before running tests
Environment.SetEnvironmentVariable("NEO4J_CONTAINER_NAME", "azure-tenant-grapher-neo4j-<random>");
Environment.SetEnvironmentVariable("NEO4J_PASSWORD", "<random-password>");
```

### See Also

- Python implementation in [`src/container_manager.py`](../../../src/container_manager.py)
- Test fixture in [`tests/conftest.py`](../../../tests/conftest.py)
