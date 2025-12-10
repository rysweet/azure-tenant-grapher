# Manual Testing Plan - Phase 1: Lighthouse Foundation

**Status**: Ready for manual testing in Azure environment
**Prerequisites**: Azure credentials, Neo4j running, all dependencies installed

## Test Environment Setup

```bash
# 1. Install dependencies
cd /Users/ryan/src/azure-tenant-grapher/worktrees/feat-issue-588-lighthouse-foundation
uv sync

# 2. Start Neo4j
docker-compose up -d neo4j

# 3. Set environment variables
export AZURE_LIGHTHOUSE_MANAGING_TENANT_ID="your-mssp-tenant-id"
export AZURE_LIGHTHOUSE_BICEP_DIR="./lighthouse_bicep"
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your-password"

# 4. Authenticate with Azure
az login --tenant $AZURE_LIGHTHOUSE_MANAGING_TENANT_ID
```

## Test Scenarios

### Scenario 1: Generate Delegation Template

**Command:**
```bash
atg lighthouse setup \
  --customer-tenant-id "22222222-2222-2222-2222-222222222222" \
  --customer-name "Test Customer Inc" \
  --subscription-id "33333333-3333-3333-3333-333333333333"
```

**Expected Results:**
- ✅ Bicep template generated in `./lighthouse_bicep/`
- ✅ README.md generated with deployment instructions
- ✅ Neo4j nodes created (MSSPTenant, CustomerTenant)
- ✅ LIGHTHOUSE_DELEGATES_TO relationship created with status='pending'
- ✅ Console output shows template path and next steps

### Scenario 2: List Delegations

**Command:**
```bash
atg lighthouse list
```

**Expected Results:**
- ✅ Table showing all delegations
- ✅ Columns: Customer Name, Tenant ID, Status, Subscription ID, Created At
- ✅ Color-coded status (green=active, yellow=pending, red=error)

**Command (JSON output):**
```bash
atg lighthouse list --output json
```

**Expected Results:**
- ✅ Valid JSON array
- ✅ Each delegation has all required fields

**Command (Filter by status):**
```bash
atg lighthouse list --status pending
atg lighthouse list --status active
```

**Expected Results:**
- ✅ Only shows delegations matching status filter

### Scenario 3: Deploy Template (Manual Step)

After `atg lighthouse setup` generates the Bicep template, deploy it manually:

```bash
cd lighthouse_bicep

# Deploy to customer tenant (customer must run this)
az login --tenant 22222222-2222-2222-2222-222222222222
az deployment sub create \
  --location eastus \
  --template-file delegation-test-customer-inc.bicep
```

**Expected Results:**
- ✅ Azure Lighthouse delegation created
- ✅ Managing tenant can now access customer subscription
- ✅ RBAC roles assigned (Sentinel Contributor, Security Reader)

### Scenario 4: Verify Delegation

After deploying the Bicep template, verify it's active:

**Command:**
```bash
atg lighthouse verify --customer-tenant-id "22222222-2222-2222-2222-222222222222"
```

**Expected Results:**
- ✅ Checks Azure API for delegation status
- ✅ Updates Neo4j status from 'pending' → 'active'
- ✅ Console output: "✓ Delegation verified and active"

### Scenario 5: Cross-Tenant Access Test

Verify managing tenant can access customer resources:

```bash
# Authenticate as managing tenant
az login --tenant $AZURE_LIGHTHOUSE_MANAGING_TENANT_ID

# List delegated subscriptions
az account list --query "[?tenantId=='22222222-2222-2222-2222-222222222222']"

# Should see the delegated customer subscription!
```

**Expected Results:**
- ✅ Customer subscription visible from managing tenant
- ✅ No tenant switching needed
- ✅ Lighthouse delegation working end-to-end

### Scenario 6: Revoke Delegation

**Command:**
```bash
atg lighthouse revoke --customer-tenant-id "22222222-2222-2222-2222-222222222222"
```

**Expected Results:**
- ✅ Confirmation prompt shown
- ✅ Azure API deletes registration assignment
- ✅ Neo4j status updated to 'revoked'
- ✅ Console output: "✓ Delegation revoked successfully"

**Verification:**
```bash
# Should no longer see customer subscription
az account list --query "[?tenantId=='22222222-2222-2222-2222-222222222222']"
# Returns empty array
```

## Error Testing

### Test 1: Invalid Tenant ID

```bash
atg lighthouse setup \
  --customer-tenant-id "invalid-tenant-id" \
  --customer-name "Test" \
  --subscription-id "33333333-3333-3333-3333-333333333333"
```

**Expected**: Clear error message: "Invalid tenant ID format"

### Test 2: Duplicate Delegation

```bash
# Run setup twice for same customer
atg lighthouse setup --customer-tenant-id "22222222..." --customer-name "Test" --subscription-id "33333333..."
atg lighthouse setup --customer-tenant-id "22222222..." --customer-name "Test" --subscription-id "33333333..."
```

**Expected**: Second command shows error: "Delegation already exists for this customer"

### Test 3: Verify Non-Existent Delegation

```bash
atg lighthouse verify --customer-tenant-id "99999999-9999-9999-9999-999999999999"
```

**Expected**: Error: "Delegation not found"

### Test 4: Revoke Non-Existent Delegation

```bash
atg lighthouse revoke --customer-tenant-id "99999999-9999-9999-9999-999999999999"
```

**Expected**: Error: "Delegation not found"

## Performance Testing

### Test: Bulk Operations (50 Customers)

Create 50 test delegations and measure performance:

```bash
# Generate 50 delegations
for i in {1..50}; do
  atg lighthouse setup \
    --customer-tenant-id "$(uuidgen)" \
    --customer-name "Customer $i" \
    --subscription-id "$(uuidgen)"
done
```

**Expected Results:**
- ✅ All 50 complete successfully
- ✅ Average time per delegation: <5 seconds
- ✅ Neo4j query performance acceptable
- ✅ No memory leaks

**List Performance:**
```bash
atg lighthouse list
```

**Expected**: Lists all 50 delegations in <2 seconds

## Neo4j Validation

After running all tests, verify Neo4j graph:

```cypher
// Count MSSP tenants
MATCH (m:MSSPTenant) RETURN count(m)
// Expected: 1

// Count customer tenants
MATCH (c:CustomerTenant) RETURN count(c)
// Expected: 50+ (from tests)

// Count active delegations
MATCH ()-[r:LIGHTHOUSE_DELEGATES_TO {status: 'active'}]->() RETURN count(r)
// Expected: Number of successfully deployed delegations

// Verify relationship structure
MATCH (m:MSSPTenant)-[r:LIGHTHOUSE_DELEGATES_TO]->(c:CustomerTenant)
RETURN m.name, c.name, r.status, r.created_at
LIMIT 10
```

## Automated Test Validation

All automated tests passed:
- ✅ 43/43 unit + integration tests passing
- ✅ Security tests (15 tests) all passing
- ✅ Linter (ruff) all checks passing
- ✅ Bandit security scan clean

## Sign-Off Checklist

- [ ] All CLI commands tested in real Azure environment
- [ ] Bicep templates deploy successfully
- [ ] Azure Lighthouse delegation visible in Azure Portal
- [ ] Cross-tenant access verified
- [ ] Neo4j graph accurately reflects delegations
- [ ] Error handling works as expected
- [ ] Performance acceptable for 50+ delegations
- [ ] Documentation accurate and complete

## Notes

**Tested in Development Environment:**
- ✅ Core modules import successfully
- ✅ 43/43 automated tests passing
- ✅ Security scan clean
- ✅ Linting issues fixed

**Requires Real Azure Environment:**
- ⏳ Azure Lighthouse API integration
- ⏳ Bicep template deployment
- ⏳ Cross-tenant access verification

This manual testing plan should be executed by someone with:
- Azure tenant admin access (both managing and customer tenants)
- Ability to create Service Principals
- Ability to deploy Bicep templates

**Estimated Testing Time:** 2-3 hours for complete manual validation
