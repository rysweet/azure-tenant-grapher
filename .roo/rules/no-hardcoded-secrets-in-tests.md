# Rule: No Hardcoded Secrets or Parameters in Tests

**Policy:**
Tests must never hardcode secrets, credentials, or sensitive parameters (such as passwords, API keys, tokens, or connection strings) in their setup or fixtures.
All such values must be provided via environment variables, configuration files excluded from version control, or secure test infrastructure.

**Rationale:**
Hardcoding secrets in test code can lead to accidental exposure, credential leaks, and security scanner alerts. Even test-only values can be misused or confused with production credentials.

**Guidelines:**
- Use environment variables for all secrets and sensitive parameters in tests.
- If a test requires a value, document the required environment variable in the test or its README.
- Never check in real or dummy secrets, passwords, or tokens to the repository.
- If a test cannot run without a secret, skip the test with a clear message.

**Example (Python):**
```python
password = os.environ.get("NEO4J_PASSWORD")
if not password:
    pytest.skip("NEO4J_PASSWORD must be set for this test.")
```

**Enforcement:**
Pull requests introducing hardcoded secrets or parameters in tests will be rejected.
