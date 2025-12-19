# API Contract Validation Guide

This guide shows ye how to validate and test the ATG Remote API contract before implementin' the server.

## Prerequisites

```bash
# Install OpenAPI tools
npm install -g @apidevtools/swagger-cli @stoplight/prism-cli

# Or use Python alternatives
pip install openapi-spec-validator connexion[swagger-ui]
```

## Validation Steps

### Step 1: Validate OpenAPI Specification

Ensures the OpenAPI spec is syntactically correct and follows OpenAPI 3.0 standard.

```bash
# Using swagger-cli (Node.js)
cd modules/api_contract
swagger-cli validate openapi.yaml

# Using Python
openapi-spec-validator openapi.yaml

# Expected output:
# openapi.yaml is valid
```

**Common Issues:**
- Missing required fields
- Invalid schema references
- Type mismatches
- Invalid enum values

### Step 2: Lint OpenAPI Specification

Check for best practices and style issues.

```bash
# Install spectral (OpenAPI linter)
npm install -g @stoplight/spectral-cli

# Run linter
spectral lint openapi.yaml

# Expected: Minimal warnings, no errors
```

### Step 3: Start Mock Server

Run a mock server that implements the API based on the spec.

```bash
# Using Prism mock server
prism mock openapi.yaml

# Server starts at http://localhost:4010
```

**Mock server provides:**
- Auto-generated responses based on schemas
- Request validation against schemas
- Interactive testing without implementing server

### Step 4: Test Mock Server

Test API endpoints against the mock server.

```bash
# Test health endpoint (no auth)
curl http://localhost:4010/v1/health

# Expected:
# {
#   "status": "healthy",
#   "version": "string",
#   "neo4j_status": "connected"
# }

# Test job submission (with mock API key)
curl -X POST http://localhost:4010/v1/jobs/scan \
  -H "X-API-Key: test-key" \
  -H "Content-Type: application/json" \
  -d @examples/scan_job_request.json

# Expected:
# {
#   "job_id": "550e8400-e29b-41d4-a716-446655440000",
#   "status": "pending",
#   "status_url": "/v1/jobs/550e8400-...",
#   "progress_url": "/v1/jobs/550e8400-.../progress"
# }

# Test authentication validation
curl http://localhost:4010/v1/auth/validate \
  -H "X-API-Key: test-key"

# Test without API key (should fail)
curl http://localhost:4010/v1/jobs/scan \
  -H "Content-Type: application/json" \
  -d @examples/scan_job_request.json

# Expected: 401 Unauthorized
```

### Step 5: Validate Request/Response Examples

Ensure example files match the schemas defined in openapi.yaml.

```bash
# Validate example against schema
swagger-cli validate --json examples/scan_job_request.json openapi.yaml

# Or manually check with jq
cat examples/scan_job_request.json | jq '.'
```

### Step 6: Generate Documentation

Generate human-readable API docs from the OpenAPI spec.

```bash
# Using Redoc (generates static HTML)
npm install -g redoc-cli
redoc-cli bundle openapi.yaml -o api-docs.html

# Open in browser
open api-docs.html

# Or use Swagger UI (interactive)
docker run -p 8080:8080 \
  -e SWAGGER_JSON=/openapi.yaml \
  -v $(pwd):/usr/share/nginx/html \
  swaggerapi/swagger-ui
```

### Step 7: Test with Real Client

Write a simple client to test API contract usability.

```python
# test_client.py
import requests
import time

API_BASE = "http://localhost:4010/v1"
API_KEY = "test-key" <!-- pragma: allowlist secret -->

def test_scan_workflow():
    """Test complete scan workflow"""
    headers = {
        "X-API-Key": API_KEY,
        "Content-Type": "application/json"
    }

    # Submit job
    response = requests.post(
        f"{API_BASE}/jobs/scan",
        headers=headers,
        json={
            "tenant_id": "12345678-1234-1234-1234-123456789abc",
            "generate_spec": True
        }
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    print(f"Job submitted: {job_id}")

    # Poll status
    for _ in range(5):
        response = requests.get(
            f"{API_BASE}/jobs/{job_id}",
            headers=headers
        )
        assert response.status_code == 200
        status = response.json()["status"]
        print(f"Status: {status}")
        time.sleep(1)

    print("✅ Workflow test passed")

if __name__ == "__main__":
    test_scan_workflow()
```

Run the test:
```bash
python test_client.py
```

## Automated Validation

### Pre-Commit Hook

Add OpenAPI validation to git pre-commit hooks:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/python-jsonschema/check-jsonschema
    rev: 0.27.0
    hooks:
      - id: check-openapi
        files: modules/api_contract/openapi.yaml
```

### CI Pipeline

Add validation to GitHub Actions:

```yaml
# .github/workflows/validate-api-contract.yml
name: Validate API Contract

on:
  pull_request:
    paths:
      - 'modules/api_contract/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Install validators
        run: npm install -g @apidevtools/swagger-cli @stoplight/spectral-cli

      - name: Validate OpenAPI spec
        run: swagger-cli validate modules/api_contract/openapi.yaml

      - name: Lint OpenAPI spec
        run: spectral lint modules/api_contract/openapi.yaml

      - name: Start mock server
        run: |
          npx @stoplight/prism-cli mock modules/api_contract/openapi.yaml &
          sleep 5

      - name: Test mock endpoints
        run: |
          curl http://localhost:4010/v1/health
          curl -X POST http://localhost:4010/v1/jobs/scan \
            -H "X-API-Key: test-key" \
            -H "Content-Type: application/json" \
            -d @modules/api_contract/examples/scan_job_request.json
```

## Testing Checklist

Before marking the contract as complete:

- [ ] OpenAPI spec validates without errors
- [ ] No critical linting issues
- [ ] Mock server starts successfully
- [ ] All example requests work against mock
- [ ] Error responses match schema
- [ ] Authentication handled correctly
- [ ] All 7 operations have valid schemas
- [ ] SSE progress format documented
- [ ] File download endpoint defined
- [ ] Documentation generates cleanly

## Common Validation Errors

### Error: Missing Required Property

```
Error: Missing required property 'tenant_id' in ScanJobRequest
```

**Fix:** Add required property to schema or make it optional.

### Error: Invalid $ref

```
Error: Can't resolve $ref '#/components/schemas/NonExistent'
```

**Fix:** Ensure all schema references exist in `components/schemas`.

### Error: Type Mismatch

```
Error: Expected type 'integer', got 'string'
```

**Fix:** Correct type in schema or example.

### Error: Invalid Enum Value

```
Error: Value 'invalid' not in enum [pending, running, completed, failed]
```

**Fix:** Use only defined enum values.

## Contract Testing Strategy

### 1. Schema Validation (Automated)

Validate all requests/responses against schemas.

```bash
# Validate examples
for file in examples/*.json; do
  echo "Validating $file"
  swagger-cli validate --json $file openapi.yaml
done
```

### 2. Mock Server Testing (Manual)

Test real workflows against mock server.

```bash
# Start mock
prism mock openapi.yaml

# Run test suite
python test_api_contract.py
```

### 3. Consumer-Driven Contracts (Future)

When implementing server, use contract testing:

```python
# Using pact or similar
from pact import Consumer, Provider

pact = Consumer('atg-client').has_pact_with(Provider('atg-api'))

# Define contract expectations
(pact
  .given('A tenant exists')
  .upon_receiving('A scan request')
  .with_request('POST', '/v1/jobs/scan')
  .will_respond_with(202, body={'job_id': '...'}))
```

## Performance Testing

### Load Test Mock Server

```bash
# Install k6 or apache bench
brew install k6

# Load test
k6 run - <<EOF
import http from 'k6/http';

export default function() {
  http.get('http://localhost:4010/v1/health');
  http.post('http://localhost:4010/v1/jobs/scan',
    JSON.stringify({tenant_id: "test"}),
    {headers: {'X-API-Key': 'test', 'Content-Type': 'application/json'}}
  );
}
EOF
```

## Contract Evolution

### Versioning Strategy

- **Minor changes** (backward compatible): Add optional fields, new endpoints
- **Major changes** (breaking): Bump version to v2, maintain v1 for transition

### Breaking Changes Checklist

Before making breaking changes:
- [ ] Document breaking change in CHANGELOG
- [ ] Bump version to v2
- [ ] Maintain v1 endpoint for 6 months
- [ ] Update all clients before deprecating v1

## Resources

- OpenAPI 3.0 Spec: https://swagger.io/specification/
- Prism Mock Server: https://stoplight.io/open-source/prism
- Spectral Linter: https://stoplight.io/open-source/spectral
- Contract Testing: https://pact.io/

## Next Steps

1. ✅ Validate spec: `swagger-cli validate openapi.yaml`
2. ✅ Start mock server: `prism mock openapi.yaml`
3. ✅ Test workflows manually
4. ⬜ Implement server (FastAPI)
5. ⬜ Run contract tests against real server
6. ⬜ Deploy to production
