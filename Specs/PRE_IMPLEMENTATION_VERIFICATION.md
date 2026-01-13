# Pre-Implementation Verification Checklist

**Purpose**: Verify assumptions BEFORE writing code

**Philosophy**: "Question everything before building"

---

## CRITICAL Verifications (MUST DO FIRST)

### 1. Azure Container Instances 64GB RAM Support

**Question**: Does ACI actually support 64GB RAM?

**Why This Matters**: Entire architecture assumes 64GB availability. If unavailable, need different approach (Container Apps).

**Verification Command**:
```bash
az container create \
  --resource-group test-rg \
  --name test-aci-64gb \
  --cpu 4 \
  --memory 64 \
  --image nginx:latest \
  --location eastus \
  --dry-run
```

**Expected Outcomes**:
- ✅ **SUCCESS**: Command completes without error → Proceed with ACI
- ❌ **FAILURE**: Error like "Memory limit exceeded" → Document error, reconsider approach

**Action if Failure**:
1. Screenshot error message
2. Check ACI documentation for actual limits
3. Evaluate Container Apps as alternative
4. Update architecture specs accordingly

**Status**: [ ] VERIFIED / [ ] FAILED / [ ] NOT YET RUN

---

### 2. Long HTTP Timeout Support

**Question**: Can Azure infrastructure support 60-minute HTTP requests?

**Why This Matters**: No Redis queue means relying on long HTTP timeout. If Azure Load Balancer kills long requests, need queue.

**Verification Method**:
```python
# Test script: test_long_http.py
import httpx
import asyncio
import time

async def test_long_request():
    """Test 60-minute HTTP request through Azure infrastructure."""
    start = time.time()

    try:
        async with httpx.AsyncClient(timeout=3600) as client:
            # Simulate 60-minute operation
            response = await client.get("https://test-endpoint/slow-operation")
            duration = time.time() - start
            print(f"Request completed after {duration}s")
            return True
    except httpx.TimeoutException:
        duration = time.time() - start
        print(f"Request timed out after {duration}s")
        return False

# Run test
result = asyncio.run(test_long_request())
print(f"60-minute HTTP supported: {result}")
```

**Expected Outcomes**:
- ✅ **SUCCESS**: Request completes after ~60 minutes → Proceed with long HTTP
- ❌ **FAILURE**: Request times out <60 minutes → Need Redis queue

**Action if Failure**:
1. Document actual timeout limit (e.g., 30 minutes)
2. Add Redis queue to architecture
3. Update implementation phases

**Status**: [ ] VERIFIED / [ ] FAILED / [ ] NOT YET RUN

---

### 3. WebSocket Support Through Azure Load Balancer

**Question**: Do WebSockets work through Azure Container Instances public endpoint?

**Why This Matters**: Progress updates rely on WebSocket. If blocked, need polling or SSE.

**Verification Method**:
```python
# Test script: test_websocket_azure.py
import asyncio
import websockets
import time

async def test_websocket_connection():
    """Test WebSocket through Azure infrastructure."""
    uri = "wss://test-endpoint/ws"

    try:
        async with websockets.connect(uri) as websocket:
            # Keep connection alive for 10 minutes
            start = time.time()
            while time.time() - start < 600:
                await websocket.send("ping")
                response = await websocket.recv()
                print(f"Received: {response}")
                await asyncio.sleep(30)

            print("WebSocket connection stable for 10 minutes")
            return True
    except Exception as e:
        print(f"WebSocket failed: {e}")
        return False

result = asyncio.run(test_websocket_connection())
print(f"WebSocket supported: {result}")
```

**Expected Outcomes**:
- ✅ **SUCCESS**: WebSocket stays connected >10 minutes → Proceed with WebSocket
- ❌ **FAILURE**: WebSocket disconnects or blocked → Consider Server-Sent Events (SSE)

**Action if Failure**:
1. Document error details
2. Try Server-Sent Events (SSE) as alternative
3. If SSE also fails, implement polling (simpler than queue)

**Status**: [ ] VERIFIED / [ ] FAILED / [ ] NOT YET RUN

---

### 4. Target Tenant Permissions

**Question**: Does managed identity have required permissions on target tenants?

**Why This Matters**: Service needs Reader role to discover resources. If missing, service fails silently.

**Verification Commands**:
```bash
# 1. Create test managed identity
az identity create \
  --name test-atg-identity \
  --resource-group test-rg

# 2. Get identity principal ID
IDENTITY_PRINCIPAL=$(az identity show \
  --name test-atg-identity \
  --resource-group test-rg \
  --query principalId \
  --output tsv)

# 3. Assign Reader role on target tenant
az role assignment create \
  --assignee $IDENTITY_PRINCIPAL \
  --role "Reader" \
  --scope "/subscriptions/$TARGET_SUBSCRIPTION_ID"

# 4. Verify role assignment
az role assignment list \
  --assignee $IDENTITY_PRINCIPAL \
  --query "[].{Role:roleDefinitionName, Scope:scope}" \
  --output table

# Expected output:
# Role    Scope
# Reader  /subscriptions/<target-sub-id>
```

**Expected Outcomes**:
- ✅ **SUCCESS**: Role assignment created and visible → Proceed
- ❌ **FAILURE**: Permission denied or role not visible → Fix permissions first

**Action if Failure**:
1. Check if service principal has permission to assign roles
2. Request admin to create role assignment
3. Document permission requirements clearly

**Status**: [ ] VERIFIED / [ ] FAILED / [ ] NOT YET RUN

---

## Recommended Verifications (SHOULD DO)

### 5. Neo4j 32GB RAM in Container

**Question**: Does Neo4j perform adequately with 32GB RAM for typical scans?

**Verification Method**:
```bash
# 1. Start Neo4j with 32GB heap
docker run \
  --name neo4j-test \
  -e NEO4J_AUTH=neo4j/testpassword \
  -e NEO4J_dbms_memory_heap_max__size=16G \
  -e NEO4J_dbms_memory_pagecache__size=8G \
  --memory 32g \
  neo4j:5.15-community

# 2. Load test data (simulate large tenant scan)
# Import ~10K nodes, ~50K relationships

# 3. Run typical queries
cypher-shell -u neo4j -p testpassword "
MATCH (r:Resource)-[:CONTAINS]->(child)
RETURN r.id, count(child) as children
ORDER BY children DESC
LIMIT 100
"

# 4. Monitor memory usage
docker stats neo4j-test
```

**Expected Outcomes**:
- ✅ **SUCCESS**: Queries complete <5 seconds, memory <28GB → Proceed with 32GB
- ⚠️ **WARNING**: Queries slow (>10s) or memory >30GB → Consider 48GB
- ❌ **FAILURE**: Out of memory errors → Need 64GB for Neo4j

**Status**: [ ] VERIFIED / [ ] NEEDS MORE RAM / [ ] NOT YET RUN

---

### 6. Concurrent Operation Limit

**Question**: Can service handle 3 concurrent scans without resource exhaustion?

**Verification Method**:
```python
# Test script: test_concurrent_scans.py
import asyncio
import httpx

async def simulate_scan(client, tenant_id, scan_num):
    """Simulate single scan operation."""
    print(f"Starting scan {scan_num} for tenant {tenant_id}")

    start = time.time()
    response = await client.post(
        "/api/v1/scan",
        json={"tenant_id": tenant_id},
        timeout=3600
    )
    duration = time.time() - start

    print(f"Scan {scan_num} completed in {duration}s")
    return response.json()

async def test_concurrent_scans():
    """Test 3 concurrent scans."""
    async with httpx.AsyncClient() as client:
        tasks = [
            simulate_scan(client, "tenant-1", 1),
            simulate_scan(client, "tenant-2", 2),
            simulate_scan(client, "tenant-3", 3),
        ]
        results = await asyncio.gather(*tasks)
        return results

results = asyncio.run(test_concurrent_scans())
print(f"All scans completed: {all(r['success'] for r in results)}")
```

**Expected Outcomes**:
- ✅ **SUCCESS**: All 3 scans complete successfully → Proceed with limit=3
- ⚠️ **WARNING**: 1-2 scans fail or slow → Lower limit to 2
- ❌ **FAILURE**: All scans fail → Resource exhaustion, need queue

**Status**: [ ] VERIFIED / [ ] NEEDS ADJUSTMENT / [ ] NOT YET RUN

---

### 7. Disk Space for Neo4j Data

**Question**: Is Azure File Share sufficient for Neo4j data storage?

**Verification Method**:
```bash
# 1. Check typical Neo4j database size after large scan
docker exec neo4j-test du -sh /data

# Typical sizes:
# Small tenant (100 resources): ~50MB
# Medium tenant (1000 resources): ~500MB
# Large tenant (10000 resources): ~5GB

# 2. Calculate required storage
# Dev: 10 tenants × 5GB = 50GB
# Integration: 20 tenants × 5GB = 100GB

# 3. Provision Azure File Share
az storage share create \
  --name neo4j-data-dev \
  --account-name atgstorage \
  --quota 200  # 200GB (4x buffer)
```

**Expected Outcomes**:
- ✅ **SUCCESS**: File share created successfully → Proceed
- ❌ **FAILURE**: Quota limits or performance issues → Evaluate alternatives

**Status**: [ ] VERIFIED / [ ] FAILED / [ ] NOT YET RUN

---

## Optional Verifications (NICE TO HAVE)

### 8. GitHub Actions Deployment Time

**Question**: How long does tag-based deployment take?

**Verification Method**:
```bash
# 1. Create test tag
git tag v0.0.1-dev
git push --tags

# 2. Monitor GitHub Actions workflow
gh run watch

# 3. Record durations:
# - Build Docker image: ?
# - Push to registry: ?
# - Deploy Bicep template: ?
# - Health check wait: ?
# - Smoke tests: ?
# Total: ?
```

**Expected Outcomes**:
- ✅ **SUCCESS**: Total deployment <15 minutes → Acceptable
- ⚠️ **WARNING**: Total deployment 15-30 minutes → Consider optimization
- ❌ **FAILURE**: Total deployment >30 minutes → Investigate bottlenecks

**Status**: [ ] VERIFIED / [ ] NEEDS OPTIMIZATION / [ ] NOT YET RUN

---

### 9. API Key Rotation Process

**Question**: Can we rotate API keys without downtime?

**Verification Method**:
```bash
# 1. Add second API key to Key Vault
az keyvault secret set \
  --vault-name atg-keyvault-dev \
  --name api-keys \
  --value "old-key,new-key"

# 2. Verify service accepts both keys
curl -H "Authorization: Bearer old-key" https://atg-service-dev/health
curl -H "Authorization: Bearer new-key" https://atg-service-dev/health

# 3. Remove old key
az keyvault secret set \
  --vault-name atg-keyvault-dev \
  --name api-keys \
  --value "new-key"

# 4. Verify old key rejected
curl -H "Authorization: Bearer old-key" https://atg-service-dev/health
# Expected: 401 Unauthorized
```

**Expected Outcomes**:
- ✅ **SUCCESS**: Rotation works without downtime → Proceed
- ❌ **FAILURE**: Downtime or errors → Document process improvements

**Status**: [ ] VERIFIED / [ ] FAILED / [ ] NOT YET RUN

---

## Verification Summary

### Priority Levels:

1. **CRITICAL** (MUST verify before implementation):
   - ACI 64GB RAM support
   - Long HTTP timeout support
   - WebSocket support
   - Target tenant permissions

2. **RECOMMENDED** (SHOULD verify before deployment):
   - Neo4j 32GB RAM performance
   - Concurrent operation limit
   - Disk space requirements

3. **OPTIONAL** (NICE TO verify before production):
   - Deployment time
   - API key rotation process

### Status Tracking:

```
CRITICAL Verifications:
[ ] 1. ACI 64GB RAM          - Status: _________
[ ] 2. Long HTTP timeout     - Status: _________
[ ] 3. WebSocket support     - Status: _________
[ ] 4. Target permissions    - Status: _________

RECOMMENDED Verifications:
[ ] 5. Neo4j 32GB RAM        - Status: _________
[ ] 6. Concurrent ops        - Status: _________
[ ] 7. Disk space            - Status: _________

OPTIONAL Verifications:
[ ] 8. Deployment time       - Status: _________
[ ] 9. API key rotation      - Status: _________
```

---

## Approval Gate

**BEFORE starting Phase 1 implementation**:

- [ ] All CRITICAL verifications completed
- [ ] All CRITICAL verifications passed OR mitigations documented
- [ ] Architecture updated based on verification results
- [ ] Team reviewed verification results
- [ ] Approval granted to proceed

**Sign-off**:
- Architect: _________________ Date: _________
- DevOps: _________________ Date: _________
- Security: _________________ Date: _________

---

## Verification Results Documentation

**Create file**: `Specs/VERIFICATION_RESULTS.md`

**Template**:
```markdown
# Verification Results

**Date**: 2025-12-09
**Environment**: Azure Container Instances (East US)

## 1. ACI 64GB RAM Support

**Command**:
```bash
az container create --memory 64 --dry-run
```

**Result**: [SUCCESS / FAILURE]

**Output**:
```
[Paste command output]
```

**Evidence**: [Screenshot if failure]

**Decision**: [Proceed with ACI / Consider Container Apps]

---

## 2. Long HTTP Timeout Support

[Repeat for each verification]
```

---

## Philosophy Alignment

**Principle**: "Question everything before building"

**Anti-Patterns Avoided**:
- ❌ Assuming ACI supports 64GB without verification
- ❌ Assuming long HTTP works without testing
- ❌ Assuming WebSocket works through Azure Load Balancer
- ❌ Assuming permissions are correct without checking

**Verification Benefits**:
- Catch architectural flaws early (before writing code)
- Avoid 2-3 weeks of wasted implementation
- Make evidence-based decisions (not assumptions)
- Document constraints clearly

**Time Investment**: 1-2 days verification vs 2-3 weeks rework
