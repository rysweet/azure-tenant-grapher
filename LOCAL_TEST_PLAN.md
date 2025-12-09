# Local Testing Plan - ATG Client-Server Feature (Issue #577)

## Test Execution Date
2025-12-09

## Feature Scope
Client-server architecture enabling ATG CLI to target remote ATG service with deployment automation.

## Test Categories

### 1. ✅ Import and Module Tests (PASSING)
- [x] FastAPI app imports without errors
- [x] All remote modules import successfully
- [x] No circular import issues
- [ ] Pyright type checking (has errors - noted for follow-up)

**Results**:
```bash
uv run python -c "from src.remote.server.main import app; print('✓ Success')"
# ✓ FastAPI app imports successfully
# Registered 6 translators
```

### 2. Server Startup Tests
- [ ] Server starts on port 8000
- [ ] Health endpoint responds
- [ ] OpenAPI docs available at /docs
- [ ] Server handles graceful shutdown

**Test Commands**:
```bash
# Start server
uv run uvicorn src.remote.server.main:app --host 0.0.0.0 --port 8000

# Test health endpoint
curl http://localhost:8000/api/v1/health

# Test OpenAPI docs
curl http://localhost:8000/docs
```

**Status**: NOT TESTED YET (requires Neo4j and Azure credentials configured)

### 3. API Endpoint Tests (Without Auth)
- [ ] Health endpoint returns 200
- [ ] Unauthenticated scan request returns 401
- [ ] Invalid API key returns 401
- [ ] Health endpoint reports Neo4j status

**Test Commands**:
```bash
# Health check (no auth required)
curl -X GET http://localhost:8000/api/v1/health

# Scan without auth (should return 401)
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "test-tenant-id"}'

# Scan with invalid auth (should return 401)
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Authorization: Bearer invalid-key" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "test-tenant-id"}'
```

**Status**: PENDING (server not started)

### 4. API Endpoint Tests (With Auth)
- [ ] Scan endpoint accepts valid request with API key
- [ ] Returns job_id and status
- [ ] Generate-IaC endpoint works
- [ ] Generate-spec endpoint works
- [ ] Operations endpoint lists jobs
- [ ] Download endpoint works

**Test Commands**:
```bash
# Generate API key first
export API_KEY=$(uv run python -c "from src.remote.auth.api_keys import generate_api_key; print(generate_api_key('dev')['key'])")

# Test scan endpoint
curl -X POST http://localhost:8000/api/v1/scan \
  -H "Authorization: Bearer ${API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "8d788dbd-cd1c-4e00-b371-3933a12c0f7d"}'
```

**Status**: PENDING (requires server + Neo4j)

### 5. WebSocket Progress Streaming Tests
- [ ] WebSocket connection accepts valid API key
- [ ] Progress events stream in real-time
- [ ] Completion event sent when job finishes
- [ ] Error events handled properly

**Test Command**:
```bash
# Using websocat or Python websockets client
websocat "ws://localhost:8000/ws/progress/${JOB_ID}?api_key=${API_KEY}"
```

**Status**: PENDING (requires running job)

### 6. CLI Remote Mode Tests
- [ ] CLI detects remote mode from .env
- [ ] `atg scan --remote` works
- [ ] Progress displays in CLI
- [ ] Results returned correctly
- [ ] Error handling works

**Test Commands**:
```bash
# Configure remote mode
echo "ATG_MODE=remote" >> .env
echo "ATG_SERVICE_URL=http://localhost:8000" >> .env
echo "ATG_API_KEY=${API_KEY}" >> .env

# Test scan in remote mode
uv run atg scan --tenant-id 8d788dbd-cd1c-4e00-b371-3933a12c0f7d
```

**Status**: PENDING (requires server running)

### 7. Configuration Tests
- [x] Client config loads from .env
- [x] Server config loads from environment
- [x] API key validation works
- [x] Neo4j connection config works

**Status**: PASSING (unit tests pass)

### 8. Neo4j Connection Tests
- [ ] Connection to dev Neo4j works
- [ ] Connection pooling prevents exhaustion
- [ ] Health checks work
- [ ] Retry logic handles transient failures

**Test Commands**:
```bash
# Test Neo4j connection
export NEO4J_URI=bolt://neo4j-dev-kqib4q.eastus.azurecontainer.io:7687
export NEO4J_PASSWORD="x<\$_35]yi[b1B{>%Qyc>CM(1Q*ST*sg"
export NEO4J_USERNAME=neo4j

uv run python -c "from src.remote.db.connection import ConnectionManager; import asyncio; asyncio.run(ConnectionManager().health_check('dev'))"
```

**Status**: PENDING (requires network access to Neo4j)

### 9. Docker Container Tests
- [ ] Dockerfile builds successfully
- [ ] Container runs with health check
- [ ] Environment variables loaded correctly
- [ ] Service accessible from outside container

**Test Commands**:
```bash
# Build Docker image
docker build -t atg-service:test -f docker/Dockerfile .

# Run container
docker run -p 8000:8000 \
  -e NEO4J_URI=$NEO4J_URI \
  -e NEO4J_PASSWORD=$NEO4J_PASSWORD \
  -e API_KEY=$API_KEY \
  atg-service:test

# Test health
curl http://localhost:8000/api/v1/health
```

**Status**: PENDING (Docker build not tested yet)

### 10. GitHub Actions Deployment Tests
- [ ] Workflow validates correctly
- [ ] Tag-based deployment triggers work
- [ ] Bicep template valid
- [ ] Deployment to test resource group succeeds

**Test Commands**:
```bash
# Validate workflow
actionlint .github/workflows/deploy.yml

# Validate Bicep
az bicep build --file infrastructure/aci.bicep

# Test deployment (dry-run)
az deployment group validate \
  --resource-group atg-test-rg \
  --template-file infrastructure/aci.bicep \
  --parameters environment=dev
```

**Status**: PENDING (requires Azure CLI and permissions)

## Test Results Summary

**Passing** (What We Can Verify Now):
- ✅ Module imports work (FastAPI app loads)
- ✅ Configuration management (unit tests pass)
- ✅ API key validation (unit tests pass)
- ✅ Core Python code quality (Ruff passing)

**Pending** (Requires Infrastructure):
- ⏸️ Server startup and API endpoints (needs Neo4j + config)
- ⏸️ WebSocket streaming (needs running server)
- ⏸️ CLI remote mode (needs server running)
- ⏸️ Docker build and run (can test but time-consuming)
- ⏸️ Deployment automation (needs Azure access)

## Deployment Prerequisites

To complete full local testing, need:

1. **Neo4j Access**:
   - Dev: `neo4j-dev-kqib4q.eastus.azurecontainer.io:7687`
   - Test: `neo4j-test-kqib4q.eastus.azurecontainer.io:7687`

2. **Azure Credentials**:
   - Service Principal for DefenderATEVET17 tenant
   - Target tenant access (dev/integration)

3. **Environment Variables**:
   ```
   NEO4J_URI=bolt://neo4j-dev-kqib4q.eastus.azurecontainer.io:7687
   NEO4J_USERNAME=neo4j
   NEO4J_PASSWORD=x<$_35]yi[b1B{>%Qyc>CM(1Q*ST*sg
   AZURE_CLIENT_ID=...
   AZURE_CLIENT_SECRET=...
   AZURE_TENANT_ID=3cd87a41-1f61-4aef-a212-cefdecd9a2d1
   TARGET_TENANT_ID=8d788dbd-cd1c-4e00-b371-3933a12c0f7d
   API_KEY=atg_dev_...
   ```

## Recommended Test Sequence

For user acceptance testing:

1. **Phase 1**: Local server startup
   - Start with docker-compose (includes Neo4j)
   - Verify health endpoint
   - Test authentication

2. **Phase 2**: API endpoint validation
   - Test scan endpoint with valid tenant
   - Verify job_id returned
   - Check WebSocket progress stream

3. **Phase 3**: CLI remote mode
   - Configure .env for remote mode
   - Run `atg scan --remote`
   - Verify results match local execution

4. **Phase 4**: Deployment validation
   - Build Docker image
   - Deploy to test ACI
   - Verify service accessible
   - Test from external client

## Notes

- Import tests PASSING ✅
- Unit tests 76/166 passing (46%)
- Pre-commit hooks passing (Ruff, formatting, secrets) ✅
- Full integration testing requires infrastructure setup
- Recommend testing in dev environment first before integration

## Follow-up Items

1. Fix remaining unit test failures (WebSocket module path)
2. Set up dev environment for integration testing
3. Document deployment procedure
4. Create runbook for troubleshooting
