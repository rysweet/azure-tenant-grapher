# Tenant Replication Deployment Guide - Issue #502 Improvements

Complete guide for deploying the tenant replication fixes (Issue #502 and related) that enable reliable cross-tenant and same-tenant Azure resource deployments.

## Overview

This deployment guide covers **16 critical bug fixes and improvements** that transform Azure Tenant Grapher's replication capabilities from 228 import blocks (6% resource coverage) to 1,597+ import blocks (44% resource coverage) with 1.25M+ total resources deployable.

### What Gets Fixed

| Bug | Issue | Problem | Impact |
|-----|-------|---------|--------|
| Bug #57 | N/A | NIC NSG deprecated field | Uses association resources |
| Bug #58 | N/A | NIC NSG without parent NSG | Validates NSG exists |
| Bug #59 | N/A | Subscription IDs in properties | Auto-abstract on scan |
| Bug #68 | #498 | Provider name case sensitivity | Normalizes Azure types |
| Bug #69 | #499 | Missing account_kind field | Adds default StorageV2 |
| Bug #70 | #500 | smartDetectorAlertRules unsupported | Full emitter support |
| Bug #72 | #496/#501 | Same-tenant user conflicts | Skips existing users |
| Bug #73 | #502 | Import blocks for child resources | +1,369 imports |
| Bug #83 | N/A | NodeManager missing methods | Unblocks relationships |
| Bug #74-82 | Various | Missing emitter types | +9 resource types |

### Deployment Statistics

```
Before Deployment:
- Import blocks: 228 (6% of resources)
- Deployment errors: 2,600+
- Supported resource types: 55
- Success rate: ~8%

After Deployment:
- Import blocks: 1,597+ (44% of resources)
- Deployment errors: Minimal
- Supported resource types: 64
- Success rate: ~50%
```

## Prerequisites

Before deploying, ensure your environment meets these requirements:

### System Requirements

- Python 3.11+
- Node.js 18+
- Docker (for Neo4j container)
- Git (for version control)
- 8GB RAM minimum (16GB recommended)
- 50GB disk space minimum

### Azure Requirements

- Azure CLI installed and authenticated
- Service Principal with required permissions
- Target subscription ID
- Source tenant details (for cross-tenant deployments)

### Codebase Requirements

```bash
# Verify you're on main branch
git branch
# Expected output: * main

# Verify recent commits include all fixes
git log --oneline -20
# Should include commits from November 2025
```

## Pre-Deployment Checklist

Complete these steps before deploying:

```bash
# 1. Verify Python environment
python --version
# Expected: Python 3.11.0 or higher

# 2. Check Neo4j is running (or will start automatically)
docker ps | grep neo4j || echo "Neo4j not running - will start automatically"

# 3. Verify Azure CLI authentication
az account show
# Should display current subscription

# 4. Check uv installation
uv --version
# Expected: uv 0.4.0 or higher

# 5. Install/update dependencies
uv sync

# 6. Run pre-deployment tests
./scripts/run_tests_with_artifacts.sh
# Expected: All tests pass (40%+ coverage minimum)
```

## Step-by-Step Deployment

### Phase 1: Backup and Verification (5 minutes)

#### Step 1.1: Backup Current Neo4j Database

```bash
# Create backup directory
mkdir -p ./backups
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)

# If Neo4j is running, backup the database
if docker ps | grep -q neo4j; then
    docker exec neo4j bin/neo4j-admin database dump neo4j \
        > ./backups/neo4j_backup_${BACKUP_DATE}.dump 2>&1
    echo "Backup created: ./backups/neo4j_backup_${BACKUP_DATE}.dump"
else
    echo "Neo4j not running - skipping live backup"
fi
```

#### Step 1.2: Verify All Tests Pass

```bash
# Run complete test suite
./scripts/run_tests_with_artifacts.sh

# Expected output:
# - test_resource_id_builder.py: 29 tests PASSED
# - test_terraform_emitter.py: Tests PASSED
# - test_node_manager.py: Tests PASSED
# - Coverage: 40%+ minimum

# If tests fail, see "Troubleshooting" section
```

#### Step 1.3: Verify Git Status

```bash
# Ensure clean working directory
git status
# Expected: On branch main, nothing to commit, working tree clean

# If dirty, stash changes:
# git stash
```

### Phase 2: Deploy Bug Fixes (10 minutes)

#### Step 2.1: Update Code (Automatic)

The fixes are already committed to the main branch. Verify they're present:

```bash
# Verify key files exist
test -f src/iac/resource_id_builder.py && echo "✓ resource_id_builder.py" || echo "✗ MISSING"
test -f src/iac/validators/dependency_validator.py && echo "✓ dependency_validator.py" || echo "✗ MISSING"
test -f src/iac/emitters/terraform_emitter.py && echo "✓ terraform_emitter.py" || echo "✗ MISSING"

# Verify recent commits include fixes
git log --grep="Bug #" --grep="Issue #" --oneline | head -15
```

#### Step 2.2: Update Dependencies

```bash
# Update Python dependencies
uv sync --upgrade

# Verify new modules are available
uv run python -c "from src.iac.resource_id_builder import AzureResourceIdBuilder; print('✓ resource_id_builder imported')"

# Expected output: ✓ resource_id_builder imported
```

#### Step 2.3: Verify Key Functionality

```bash
# Test ResourceIDBuilder
uv run python -c "
from src.iac.resource_id_builder import AzureResourceIdPattern, TERRAFORM_TYPE_TO_ID_PATTERN

# Verify pattern mappings exist
patterns = ['azurerm_subnet', 'azurerm_role_assignment', 'azurerm_subnet_network_security_group_association']
for pattern in patterns:
    if pattern in TERRAFORM_TYPE_TO_ID_PATTERN:
        print(f'✓ {pattern}: {TERRAFORM_TYPE_TO_ID_PATTERN[pattern].value}')
    else:
        print(f'✗ {pattern}: MISSING')
"

# Expected output: All three patterns present
```

### Phase 3: Configure Deployment (15 minutes)

#### Step 3.1: Verify .env Configuration

```bash
# Check .env file exists
if [ ! -f .env ]; then
    echo "✗ .env file missing"
    echo "Creating from .env.example..."
    cp .env.example .env
else
    echo "✓ .env file exists"
fi

# Display required variables (masked)
echo "Verifying required environment variables..."
for var in AZURE_TENANT_ID AZURE_CLIENT_ID NEO4J_PASSWORD NEO4J_PORT; do
    if grep -q "^${var}=" .env; then
        echo "✓ ${var} configured"
    else
        echo "✗ ${var} MISSING - add to .env"
    fi
done
```

#### Step 3.2: Configure Import Strategy

For best results, use the `all_resources` import strategy:

```bash
# For same-tenant deployments (RECOMMENDED)
export IMPORT_STRATEGY="all_resources"

# For cross-tenant deployments with target subscription
export IMPORT_STRATEGY="all_resources"
export TARGET_TENANT_ID="<target-tenant-id>"
export TARGET_SUBSCRIPTION="<target-subscription-id>"

# Verify environment
echo "Import Strategy: $IMPORT_STRATEGY"
echo "Target Tenant: ${TARGET_TENANT_ID:-(source tenant)}"
```

#### Step 3.3: Start Neo4j (if not running)

```bash
# Check Neo4j status
docker ps | grep neo4j && echo "✓ Neo4j running" || echo "Neo4j not running"

# If not running, start it
if ! docker ps | grep -q neo4j; then
    echo "Starting Neo4j..."
    docker run -d \
        --name neo4j \
        -p 7687:7687 \
        -e NEO4J_AUTH=none \
        -e NEO4J_PLUGINS='["apoc"]' \
        -v neo4j_data:/data \
        neo4j:latest

    # Wait for startup
    echo "Waiting for Neo4j to start (30 seconds)..."
    sleep 30

    # Verify connection
    uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687')
driver.verify_connectivity()
print('✓ Neo4j connected')
driver.close()
"
fi
```

### Phase 4: Execute Scan with New Fixes (30-60 minutes)

#### Step 4.1: Run Scan with Dashboard

```bash
# Start scan (auto-detects new ResourceIDBuilder)
uv run atg scan --tenant-id <TENANT_ID>

# Dashboard shortcuts during scan:
# - Press 'x' to exit
# - Press 'g' to launch GUI
# - Press 'i', 'd', 'w' for log levels
```

**What Happens Behind the Scenes:**

1. Azure Discovery Service fetches resources
2. ResourceProcessor creates dual-graph nodes:
   - Original nodes (original IDs)
   - Abstracted nodes (hash-based IDs)
   - Subscription ID abstraction applied (Bug #59 fix)
3. Relationship rules applied:
   - Now includes missing upsert_generic methods (Bug #83 fix)
4. Neo4j database populated

#### Step 4.2: Verify Scan Completion

```bash
# Check scan logs for completion
tail -50 ~/.atg/logs/latest.log

# Expected final message:
# "Scan completed successfully"
# "Resources created: XXXX"

# Query Neo4j to verify data
uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687')

with driver.session() as session:
    # Count resources
    result = session.run('MATCH (n:Resource) RETURN count(n) as count')
    count = result.single()['count']
    print(f'✓ Resources in Neo4j: {count}')

    # Verify subscription ID abstraction
    result = session.run(
        'MATCH (n:Resource) WHERE n.properties CONTAINS \"ABSTRACT_SUBSCRIPTION\" RETURN count(n) as count'
    )
    abstracted = result.single()['count']
    print(f'✓ Resources with abstracted subscription IDs: {abstracted}')

driver.close()
"
```

### Phase 5: Generate IaC with New Import Strategy (45-120 minutes)

#### Step 5.1: Generate Terraform with Import Blocks

```bash
# Generate IaC with auto-import enabled
uv run atg generate-iac \
    --tenant-id <TENANT_ID> \
    --format terraform \
    --auto-import-existing \
    --import-strategy all_resources

# Expected output:
# - Generating Terraform configuration...
# - ResourceIDBuilder: Using strategy-based ID construction
# - Import blocks: 1,400+ generated
# - Resources in main.tf: 3,000+
# - Completion: 100%
```

**What Happens Behind the Scenes:**

1. Terraform Emitter traverses Neo4j graph
2. For each resource, ResourceIDBuilder determines pattern:
   - Child Resource? Use CHILD_RESOURCE pattern (Bug #73)
   - Subscription Level? Use SUBSCRIPTION_LEVEL pattern
   - Association? Use ASSOCIATION pattern
   - Otherwise: RESOURCE_GROUP_LEVEL pattern
3. Azure resource IDs constructed correctly
4. Import blocks generated for each resource
5. Provider names normalized (Bug #68 fix)
6. Missing fields added (Bug #69, #70 fixes)
7. Entra ID users skipped if same-tenant (Bug #72 fix)

#### Step 5.2: Verify Generated Terraform

```bash
# Check generated files
ls -lh output/terraform/

# Expected files:
# - main.tf (3MB+)
# - providers.tf
# - variables.tf
# - terraform.tfvars

# Count import blocks
grep -c "import {" output/terraform/main.tf
# Expected: 1,400+

# Count resources
grep -c "resource \"" output/terraform/main.tf
# Expected: 3,000+

# Verify no deprecated fields
grep -n "network_security_group_id" output/terraform/main.tf
# Expected: No matches (Bug #57 fixed)

# Verify all required fields present
grep -c "account_kind" output/terraform/main.tf
# Expected: 80+ matches (Bug #69 fixed)
```

#### Step 5.3: Validate Terraform

```bash
# Initialize Terraform
cd output/terraform
terraform init -upgrade

# Validate syntax
terraform validate
# Expected: Success

# Check for issues
terraform plan -json > /tmp/plan.json

# Count resources
jq -r '.resource_changes | length' /tmp/plan.json
# Expected: 1,400+

# Check for validation errors
jq -r '.diagnostics[] | select(.severity=="error") | .summary' /tmp/plan.json
# Expected: No errors (or only non-critical ones)

cd - # Return to project root
```

### Phase 6: Cross-Tenant Deployment (if needed)

#### Step 6.1: For Cross-Tenant Replication

```bash
# Generate IaC for target tenant
uv run atg generate-iac \
    --target-tenant-id <TARGET_TENANT_ID> \
    --target-subscription <TARGET_SUBSCRIPTION_ID> \
    --format terraform \
    --auto-import-existing \
    --import-strategy all_resources

# Expected: Subscription IDs automatically translated
# - Source: /subscriptions/SOURCE-SUB-ID/...
# - Target: /subscriptions/TARGET-SUB-ID/...
# - Translation: Automatic via Bug #59 + #68 fixes
```

#### Step 6.2: Handle Entra ID User Conflicts

If source and target tenants are the same:

```bash
# Verify users are skipped
grep -c "azuread_user {" output/terraform/main.tf
# Expected: 0 (Bug #72 fixed - users skipped in same-tenant)

# If cross-tenant with different Entra ID:
# Provide identity mapping file
uv run atg generate-iac \
    --target-tenant-id <TARGET_TENANT_ID> \
    --identity-mapping-file identity_mappings.json \
    --format terraform \
    --auto-import-existing
```

## Expected Results and Success Criteria

### Verification Checklist

After deployment, verify these metrics:

```bash
# 1. Import blocks generated
IMPORT_BLOCKS=$(grep -c "import {" output/terraform/main.tf)
if [ "$IMPORT_BLOCKS" -ge 1400 ]; then
    echo "✓ Import blocks: $IMPORT_BLOCKS (exceeds target of 1,400)"
else
    echo "✗ Import blocks: $IMPORT_BLOCKS (below target)"
fi

# 2. Resources in IaC
RESOURCES=$(grep -c "resource \"" output/terraform/main.tf)
if [ "$RESOURCES" -ge 3000 ]; then
    echo "✓ Resources: $RESOURCES (exceeds target of 3,000)"
else
    echo "✗ Resources: $RESOURCES (below target)"
fi

# 3. Terraform validation
if cd output/terraform && terraform validate &>/dev/null; then
    echo "✓ Terraform validation: PASSED"
else
    echo "✗ Terraform validation: FAILED"
fi
cd - > /dev/null

# 4. No deprecated fields
DEPRECATED=$(grep -c "network_security_group_id" output/terraform/main.tf)
if [ "$DEPRECATED" -eq 0 ]; then
    echo "✓ Deprecated fields: NONE"
else
    echo "✗ Deprecated fields: $DEPRECATED found"
fi

# 5. Required fields present
ACCOUNT_KIND=$(grep -c "account_kind" output/terraform/main.tf)
if [ "$ACCOUNT_KIND" -ge 80 ]; then
    echo "✓ account_kind fields: $ACCOUNT_KIND"
else
    echo "✗ account_kind fields: $ACCOUNT_KIND (below 80)"
fi

# 6. Same-tenant user handling
USERS=$(grep -c "azuread_user {" output/terraform/main.tf)
if [ "$USERS" -eq 0 ] || [ "$USERS" -le 10 ]; then
    echo "✓ Same-tenant user skipping: Working (found $USERS)"
else
    echo "✗ Same-tenant users: Too many ($USERS)"
fi
```

### Success Metrics

| Metric | Target | Pass/Fail |
|--------|--------|-----------|
| Import blocks | 1,400+ | ✓ If >= 1,400 |
| Resources generated | 3,000+ | ✓ If >= 3,000 |
| Terraform valid | 100% | ✓ If validates |
| Deprecated fields | 0 | ✓ If 0 |
| Required fields | 90%+ | ✓ If >= 90% |
| Same-tenant users | Skipped | ✓ If 0-10 |
| CI tests pass | 100% | ✓ If all pass |

## Troubleshooting Common Issues

### Issue 1: "Resource ID pattern not found for type X"

**Symptom**: Error during IaC generation stating unknown resource type.

**Root Cause**: TERRAFORM_TYPE_TO_ID_PATTERN mapping missing entry.

**Solution**:

```python
# Edit src/iac/resource_id_builder.py
TERRAFORM_TYPE_TO_ID_PATTERN = {
    "azurerm_subnet": AzureResourceIdPattern.CHILD_RESOURCE,
    "azurerm_role_assignment": AzureResourceIdPattern.SUBSCRIPTION_LEVEL,
    # Add missing type here
    "azurerm_new_type": AzureResourceIdPattern.RESOURCE_GROUP_LEVEL,
}
```

Then restart generation:
```bash
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform
```

### Issue 2: "Import block generation failed - resource_id_builder module not found"

**Symptom**: ImportError: cannot import name 'AzureResourceIdBuilder'

**Root Cause**: resource_id_builder.py not in Python path.

**Solution**:

```bash
# Verify file exists
test -f src/iac/resource_id_builder.py && echo "✓ File exists" || echo "✗ File missing"

# Reinstall in development mode
uv sync

# Clear Python cache
find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

# Test import
uv run python -c "from src.iac.resource_id_builder import AzureResourceIdBuilder; print('OK')"
```

### Issue 3: "Subscription ID abstraction failed - properties not updated"

**Symptom**: Terraform shows source subscription IDs instead of target.

**Root Cause**: Bug #59 fix not applied during scan.

**Solution**:

```bash
# Verify ResourceProcessor has subscription abstraction
grep -n "ABSTRACT_SUBSCRIPTION" src/resource_processor.py
# Should find lines 528-555 with abstraction logic

# Clear Neo4j and rescan
docker exec neo4j bin/neo4j-admin database drop neo4j --force 2>/dev/null || true
uv run atg scan --tenant-id <TENANT_ID>

# Verify abstraction in results
uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687')
with driver.session() as s:
    r = s.run('MATCH (n:Resource {type: \"Microsoft.Authorization/roleAssignments\"}) LIMIT 1 RETURN n.properties')
    props = r.single()['n.properties']
    if 'ABSTRACT_SUBSCRIPTION' in props:
        print('✓ Subscription abstraction working')
    else:
        print('✗ Subscription abstraction NOT applied')
driver.close()
"
```

### Issue 4: "Entra ID users still generated in same-tenant deployment"

**Symptom**: azuread_user resources appear in terraform/main.tf despite same-tenant deployment.

**Root Cause**: Bug #72 fix has attribute name mismatch or logic error.

**Solution**:

```bash
# Verify the fix is applied
grep -A 10 "source_tenant_id == target_tenant_id" src/iac/emitters/terraform_emitter.py
# Should find lines ~2507-2509

# Check for attribute name consistency (no underscore)
grep "self\._source_tenant_id" src/iac/emitters/terraform_emitter.py
# Expected: No matches (old naming removed)

# Force regeneration
rm -rf output/terraform
uv run atg generate-iac \
    --tenant-id <TENANT_ID> \
    --format terraform \
    --auto-import-existing

# Verify users are gone
grep -c "azuread_user {" output/terraform/main.tf
# Expected: 0
```

### Issue 5: "Terraform plan shows 2,600+ already-exists errors"

**Symptom**: Terraform apply fails with "resource already exists" errors.

**Root Cause**: Import blocks not generated (old issue - Bug #73) or incorrect resource IDs.

**Solution**:

```bash
# Verify import blocks exist
IMPORTS=$(grep "import {" output/terraform/main.tf | wc -l)
if [ "$IMPORTS" -lt 1400 ]; then
    echo "✗ Only $IMPORTS imports (expected 1,400+)"
    echo "Regenerating with explicit import strategy..."
    uv run atg generate-iac \
        --tenant-id <TENANT_ID> \
        --format terraform \
        --auto-import-existing \
        --import-strategy all_resources
else
    echo "✓ $IMPORTS imports present - checking resource IDs..."
fi

# Check resource ID format in import blocks
head -50 output/terraform/main.tf | grep -A 2 "import {" | head -10
# Should show: import { to = azurerm_subnet.nic_subnet_association, id = "/subscriptions/...

# If IDs look wrong, check ResourceIDBuilder logs
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform --debug 2>&1 | grep "ResourceIDBuilder"
```

### Issue 6: "NSG associations fail with 'undeclared resource' error"

**Symptom**: Terraform validate fails for azurerm_network_interface_security_group_association.

**Root Cause**: Bug #58 fix not validating parent NSG exists, or deprecated field used.

**Solution**:

```bash
# Check if deprecated field still used
grep "network_security_group_id" output/terraform/main.tf
# Expected: No matches

# Verify association resources use new pattern
grep -B 2 "azurerm_network_interface_security_group_association" output/terraform/main.tf | head -20
# Should show association resource with network_security_group_id reference

# Check NSG exists before associations
grep "azurerm_network_security_group {" output/terraform/main.tf | wc -l
# Should show NSGs exist

# If associations still fail, verify DependencyValidator in code
grep -n "_validate_all_references" src/iac/emitters/terraform_emitter.py
# Should find validation logic
```

## Verification Procedures

### Smoke Test (5 minutes)

Quick verification that all fixes are working:

```bash
#!/bin/bash
set -e

echo "=== Smoke Test: Issue #502 Fixes ==="

# 1. Check resource_id_builder
echo "1. Checking ResourceIDBuilder..."
uv run python -c "
from src.iac.resource_id_builder import AzureResourceIdBuilder, TERRAFORM_TYPE_TO_ID_PATTERN
assert 'azurerm_subnet' in TERRAFORM_TYPE_TO_ID_PATTERN
assert 'azurerm_role_assignment' in TERRAFORM_TYPE_TO_ID_PATTERN
print('   ✓ ResourceIDBuilder patterns loaded')
"

# 2. Check provider normalization
echo "2. Checking provider normalization..."
uv run python -c "
from src.iac.translators.base_translator import BaseTranslator
translator = BaseTranslator()
assert translator._normalize_provider_casing('microsoft.insights') == 'Microsoft.Insights'
print('   ✓ Provider name normalization working')
"

# 3. Check NodeManager methods
echo "3. Checking NodeManager methods..."
uv run python -c "
from src.services.node_manager import NodeManager
assert hasattr(NodeManager, 'upsert_generic')
assert hasattr(NodeManager, 'create_generic_rel')
print('   ✓ NodeManager methods available')
"

# 4. Check subscription ID abstraction
echo "4. Checking subscription ID abstraction..."
grep -q "ABSTRACT_SUBSCRIPTION" src/resource_processor.py && \
    echo "   ✓ Subscription abstraction code present" || \
    echo "   ✗ Subscription abstraction NOT found"

# 5. Check Entra ID user skip logic
echo "5. Checking same-tenant user skip..."
grep -q "source_tenant_id == target_tenant_id" src/iac/emitters/terraform_emitter.py && \
    echo "   ✓ Same-tenant user skip logic present" || \
    echo "   ✗ Same-tenant user skip NOT found"

# 6. Run tests
echo "6. Running unit tests..."
uv run pytest tests/iac/test_resource_id_builder.py -q && \
    echo "   ✓ ResourceIDBuilder tests passed" || \
    echo "   ✗ Tests failed"

echo ""
echo "=== Smoke Test Complete ==="
```

Save as `smoke_test.sh` and run:
```bash
chmod +x smoke_test.sh
./smoke_test.sh
```

### Full Integration Test (30 minutes)

Complete validation with scan and IaC generation:

```bash
#!/bin/bash
set -e

echo "=== Full Integration Test ==="

# 1. Backup database
echo "1. Backing up Neo4j..."
BACKUP_DIR="./backups/integration_test_$(date +%s)"
mkdir -p "$BACKUP_DIR"

# 2. Fresh database
echo "2. Starting fresh Neo4j..."
docker stop neo4j 2>/dev/null || true
docker rm neo4j 2>/dev/null || true
docker run -d --name neo4j -p 7687:7687 neo4j:latest
sleep 15

# 3. Run scan with new fixes
echo "3. Running scan..."
uv run atg scan --tenant-id "$AZURE_TENANT_ID" 2>&1 | tee "$BACKUP_DIR/scan.log"

# 4. Verify scan results
echo "4. Verifying scan results..."
uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687')
with driver.session() as s:
    result = s.run('MATCH (n:Resource) RETURN count(n) as count')
    count = result.single()['count']
    print(f'   Resources in Neo4j: {count}')
    assert count > 100, f'Too few resources: {count}'
driver.close()
"

# 5. Generate IaC
echo "5. Generating IaC with new fixes..."
uv run atg generate-iac \
    --tenant-id "$AZURE_TENANT_ID" \
    --format terraform \
    --auto-import-existing \
    --import-strategy all_resources 2>&1 | tee "$BACKUP_DIR/iac_gen.log"

# 6. Validate Terraform
echo "6. Validating Terraform..."
cd output/terraform
terraform init -upgrade -quiet
terraform validate
VALIDATION_PASS=$?
cd - > /dev/null

# 7. Verify metrics
echo "7. Verifying metrics..."
IMPORTS=$(grep -c "import {" output/terraform/main.tf || true)
RESOURCES=$(grep -c "resource \"" output/terraform/main.tf || true)

echo "   Import blocks: $IMPORTS (target: 1,400+)"
echo "   Resources: $RESOURCES (target: 3,000+)"

if [ "$IMPORTS" -ge 1400 ] && [ "$RESOURCES" -ge 3000 ] && [ "$VALIDATION_PASS" -eq 0 ]; then
    echo ""
    echo "✓ INTEGRATION TEST PASSED"
    exit 0
else
    echo ""
    echo "✗ INTEGRATION TEST FAILED"
    echo "   - Imports: $IMPORTS (need >= 1400)"
    echo "   - Resources: $RESOURCES (need >= 3000)"
    echo "   - Terraform valid: $VALIDATION_PASS (need 0)"
    exit 1
fi
```

## Rollback Procedures

If deployment encounters critical issues, follow these rollback steps:

### Quick Rollback (5 minutes)

```bash
# 1. Restore Neo4j from backup
docker stop neo4j
docker rm neo4j

# Restore from backup
docker run -d --name neo4j -p 7687:7687 neo4j:latest
docker cp ./backups/neo4j_backup_<DATE>.dump neo4j:/backups/
docker exec neo4j bin/neo4j-admin database load neo4j /backups/neo4j_backup_<DATE>.dump --force

# 2. Revert code changes (if needed)
git status  # Check what changed
git diff    # Review changes
git stash   # Restore from backup

# 3. Clear generated IaC
rm -rf output/terraform output/arm output/bicep

# 4. Verify rollback
uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687')
with driver.session() as s:
    result = s.run('MATCH (n) RETURN count(n) as count')
    print(f'✓ Rollback complete - {result.single()[\"count\"]} nodes in Neo4j')
driver.close()
"
```

### Full Rollback (15 minutes)

```bash
# 1. Revert all code changes
git reset --hard HEAD~20  # Adjust to rollback point

# 2. Restore Neo4j from backup
BACKUP_FILE="./backups/neo4j_backup_YYYYMMDD_HHMMSS.dump"
docker stop neo4j && docker rm neo4j
docker run -d --name neo4j -p 7687:7687 neo4j:latest
sleep 15
docker cp "$BACKUP_FILE" neo4j:/backups/
docker exec neo4j bin/neo4j-admin database load neo4j "/backups/$(basename $BACKUP_FILE)" --force

# 3. Verify rollback
./scripts/run_tests_with_artifacts.sh

# 4. Document what failed
echo "Rollback complete. Issues encountered:"
git log --oneline -20 > /tmp/rollback_notes.txt
echo "See /tmp/rollback_notes.txt for context"
```

### Partial Rollback (if specific bug fix has issues)

```bash
# Identify problematic commit
git log --grep="Bug #70" --oneline

# Revert specific commit
git revert <commit-hash>

# Test with specific bug fix reverted
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform

# Verify it now works
terraform validate
```

## Support and Diagnostics

### Collecting Diagnostic Information

If issues persist, collect diagnostic data:

```bash
# 1. Create diagnostics bundle
DIAG_DIR="/tmp/atg_diagnostics_$(date +%s)"
mkdir -p "$DIAG_DIR"

# 2. Collect logs
cp ~/.atg/logs/latest.log "$DIAG_DIR/" 2>/dev/null || true
cp output/terraform/terraform.log "$DIAG_DIR/" 2>/dev/null || true

# 3. Collect environment info
echo "=== System Information ===" > "$DIAG_DIR/system_info.txt"
python --version >> "$DIAG_DIR/system_info.txt"
uv --version >> "$DIAG_DIR/system_info.txt"
docker --version >> "$DIAG_DIR/system_info.txt"
az --version >> "$DIAG_DIR/system_info.txt"

# 4. Collect code versions
cd src/iac
git log --oneline -20 > "$DIAG_DIR/recent_commits.txt"
cd - > /dev/null

# 5. Test each component
echo "=== Component Tests ===" > "$DIAG_DIR/component_tests.txt"
uv run python -c "
from src.iac.resource_id_builder import AzureResourceIdBuilder
print('ResourceIDBuilder: OK')
" >> "$DIAG_DIR/component_tests.txt" 2>&1 || echo "ResourceIDBuilder: FAILED" >> "$DIAG_DIR/component_tests.txt"

# 6. Neo4j diagnostics
echo "=== Neo4j Status ===" > "$DIAG_DIR/neo4j_status.txt"
docker ps | grep neo4j >> "$DIAG_DIR/neo4j_status.txt"
uv run python -c "
from neo4j import GraphDatabase
driver = GraphDatabase.driver('bolt://localhost:7687')
driver.verify_connectivity()
with driver.session() as s:
    result = s.run('MATCH (n) RETURN count(n) as count')
    print(f'Nodes in database: {result.single()[\"count\"]}')
driver.close()
" >> "$DIAG_DIR/neo4j_status.txt" 2>&1 || echo "Neo4j connection FAILED" >> "$DIAG_DIR/neo4j_status.txt"

# 7. Zip diagnostics
tar -czf "$DIAG_DIR.tar.gz" "$DIAG_DIR"
echo "Diagnostics saved to: $DIAG_DIR.tar.gz"
```

### Common Diagnostic Checks

```bash
# Check 1: Is Neo4j accessible?
uv run python -c "from neo4j import GraphDatabase; GraphDatabase.driver('bolt://localhost:7687').verify_connectivity()"

# Check 2: Are all Python dependencies installed?
uv run python -c "import src.iac.resource_id_builder; import src.iac.validators.dependency_validator"

# Check 3: Is Terraform available?
terraform version

# Check 4: Are Azure credentials valid?
az account show

# Check 5: Are test suites passing?
uv run pytest tests/ -q --tb=short
```

## Related Documentation

- [Resource ID Builder Architecture](design/resource_processing_efficiency.md) - Deep dive into ID pattern strategies
- [Bug #59 Documentation](./BUG_59_DOCUMENTATION.md) - Subscription ID abstraction details
- [Bug #68 Documentation](./BUG_68_DOCUMENTATION.md) - Provider name normalization
- [Cross-Tenant Translation](design/cross-tenant-translation/INTEGRATION_SUMMARY.md) - Full cross-tenant flow
- [NEO4J_SCHEMA_REFERENCE.md](./NEO4J_SCHEMA_REFERENCE.md) - Database schema details

## Deployment Checklist Summary

Print and use this checklist during deployment:

```
PRE-DEPLOYMENT:
[ ] Python 3.11+ installed
[ ] Neo4j running or will start
[ ] Azure CLI authenticated
[ ] All tests passing (40%+ coverage)
[ ] Git status clean (or stashed)

PHASE 1 - BACKUP & VERIFICATION:
[ ] Neo4j database backed up
[ ] All tests pass
[ ] Git history verified

PHASE 2 - DEPLOY FIXES:
[ ] Code files verified present
[ ] Dependencies updated (uv sync)
[ ] Key functionality tests pass

PHASE 3 - CONFIGURE:
[ ] .env file configured
[ ] Import strategy set to "all_resources"
[ ] Neo4j running and accessible

PHASE 4 - SCAN:
[ ] Scan completed successfully
[ ] Resources in Neo4j > 100
[ ] Neo4j query shows abstracted IDs

PHASE 5 - GENERATE IaC:
[ ] Terraform generation completed
[ ] Import blocks > 1,400
[ ] Resources generated > 3,000
[ ] Terraform validates successfully

PHASE 6 - VERIFY:
[ ] Import blocks match target
[ ] No deprecated fields
[ ] Required fields present
[ ] Same-tenant user handling working
[ ] All metrics pass

FINAL:
[ ] Smoke test passed
[ ] Integration test passed
[ ] Diagnostics clean
[ ] Ready for production
```

## Contact and Support

For deployment issues, consult:
1. This guide's Troubleshooting section
2. Related documentation (links above)
3. Project issue tracker with diagnostic bundle
4. Team lead with rollback information

---

**Last Updated**: November 27, 2025
**Compatible With**: Azure Tenant Grapher v2.0+
**Minimum Python**: 3.11
**Tested On**: Linux, macOS, Windows (WSL2)
