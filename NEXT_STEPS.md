# Next Steps to Complete Deployment - Issue #570

## Current Status
- ✅ Code fix complete (PR #571 merged)
- ✅ APOC installed and working
- ❌ Neo4j data lost (need to restore or re-scan)

## Quick Path to Deployment

### Step 1: Restore Data (Choose One)

**Option A - From Backup** (15 min, IF backup exists):
```bash
# Find backup
find . -name "*neo4j*.dump" -o -name "*backup*" | grep neo4j

# If found, restore:
docker stop neo4j
docker exec neo4j bin/neo4j-admin database load neo4j --from-path=/path/to/backup.dump
docker start neo4j
```

**Option B - Re-scan Azure** (2-4 hours):
```bash
az login --tenant c7674d41-af6c-46f5-89a5-d41495d2151e
uv run azure-tenant-grapher scan --tenant-id c7674d41-af6c-46f5-89a5-d41495d2151e
```

### Step 2: Test the Fix (30 min)

```bash
# Create test layer
uv run azure-tenant-grapher layer create test-src --tenant-id <TENANT> --yes

# Add some resources to it (via Neo4j)
# Copy it to verify SCAN_SOURCE_NODE preserved
uv run azure-tenant-grapher layer copy test-src test-dst --yes

# Verify SCAN_SOURCE_NODE copied (Python/Cypher query)
# Should show non-zero count
```

### Step 3: Generate IaC (15 min)

```bash
uv run azure-tenant-grapher generate-iac \
  --format terraform \
  --scan-target \
  --output ./deployment-test

# Check classification in generation_report.txt
# Should show:
# - EXACT_MATCH: 60%+
# - DRIFTED: 20%+
# - NEW: <20% (NOT 90%!)
```

### Step 4: Deploy (30 min)

```bash
cd ./deployment-test
terraform init
terraform plan   # Verify imports present
terraform apply  # Should succeed
```

## Troubleshooting

**If data restore fails**:
- Check available backups in `.deployments/backups/`
- Consider re-scanning (takes time but guaranteed to work)

**If layer copy fails**:
- Verify APOC loaded: Query `RETURN apoc.version()`
- Check logs: `docker logs neo4j | grep -i error`

**If IaC generation fails**:
- Check Neo4j has data: Query `MATCH (r:Resource) RETURN count(r)`
- Verify SCAN_SOURCE_NODE exists: Query `MATCH ()-[r:SCAN_SOURCE_NODE]->() RETURN count(r)`

## Quick Verification Commands

```bash
# Verify APOC
docker exec neo4j cypher-shell -u neo4j -p azure-grapher-2024 "RETURN apoc.version();"

# Verify data
docker exec neo4j cypher-shell -u neo4j -p azure-grapher-2024 "MATCH (r:Resource) RETURN count(r);"

# Verify SCAN_SOURCE_NODE
docker exec neo4j cypher-shell -u neo4j -p azure-grapher-2024 "MATCH ()-[r:SCAN_SOURCE_NODE]->() RETURN count(r);"
```

## Complete Documentation

See `FINAL_DEPLOYMENT_REPORT_ISSUE570.md` for comprehensive details.
