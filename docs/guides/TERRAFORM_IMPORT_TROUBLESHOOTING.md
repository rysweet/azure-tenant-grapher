# Terraform Import Block Troubleshooting

Quick guide to diagnose and fix missing or broken Terraform import blocks.

---

## Check Import Coverage

Verify how many resources have import blocks:

```bash
python3 << 'EOF'
import json

with open('main.tf.json') as f:
    config = json.load(f)

import_count = len(config.get('import', []))
resource_count = sum(len(r) for r in config.get('resource', {}).values())

print(f"Import blocks: {import_count}/{resource_count} ({100*import_count/resource_count:.1f}%)")

if import_count < resource_count:
    print(f"\n⚠️  {resource_count - import_count} resources missing import blocks")
    print("See troubleshooting steps below")
else:
    print("\n✅ All resources have import blocks")
EOF
```

**Expected:** 100% coverage if using `--auto-import-existing` flag.

---

## Problem: Low Import Coverage (< 100%)

### Symptom
```
Import blocks: 67/177 (37.9%)
⚠️  110 resources missing import blocks
```

### Cause 1: Missing SCAN_SOURCE_NODE Relationships

**Check:**
```cypher
// Run in Neo4j browser
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN count(r) as with_original_id

UNION

MATCH (r:Resource)
WHERE NOT (r)-[:SCAN_SOURCE_NODE]->()
RETURN count(r) as without_original_id
```

**Expected:**
- `with_original_id`: Should equal total resource count
- `without_original_id`: Should be 0

**If relationships missing:** Your scan was performed before Bug #117 fix. See [SCAN_SOURCE_NODE Migration Guide](scan-source-node-migration.md).

**Fix:**
```bash
# Option 1: Re-scan tenant (recommended)
uv run atg scan --tenant-id YOUR_TENANT_ID

# Option 2: Migrate existing layer (if re-scan not possible)
# See migration guide: docs/guides/scan-source-node-migration.md
```

### Cause 2: Query Missing original_id Field

**Check your code:**
```python
# WRONG - Query doesn't retrieve original_id
query = """
MATCH (r:Resource)
RETURN r.id as id, r.name as name  // ❌ Missing original_id
"""

# RIGHT - Query includes original_id via SCAN_SOURCE_NODE
query = """
MATCH (r:Resource)
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN r.id as id, r.name as name, o.id as original_id  // ✅ Includes original_id
"""
```

**Fix:** Update query to include `o.id as original_id` and ensure emitter passes `original_id_map` to `ResourceIDBuilder`.

### Cause 3: Not Using --auto-import-existing Flag

**Check command:**
```bash
# WRONG - No import blocks generated
uv run atg generate-iac --format terraform

# RIGHT - Import blocks enabled
uv run atg generate-iac --format terraform --auto-import-existing
```

---

## Problem: Import IDs Contain Variables

### Symptom
```
Import ID: /subscriptions/00.../resourceGroups/${azurerm_resource_group.rg_123.name}/...
                                              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                              ❌ Terraform variable reference
```

### Cause
Using config-based ID reconstruction instead of original_id from Neo4j.

**Check:**
```bash
# Inspect import IDs for variables
python3 << 'EOF'
import json

with open('main.tf.json') as f:
    config = json.load(f)

import_blocks = config.get('import', [])
bad_imports = [ib for ib in import_blocks if '$' in ib.get('id', '')]

if bad_imports:
    print(f"❌ {len(bad_imports)} import IDs contain Terraform variables")
    for ib in bad_imports[:3]:
        print(f"\n{ib['to']}")
        print(f"  ID: {ib['id']}")
else:
    print("✅ All import IDs are clean Azure resource IDs")
EOF
```

**Fix:**
1. Ensure SCAN_SOURCE_NODE relationships exist (see Cause 1 above)
2. Verify query includes `original_id` field (see Cause 2 above)
3. Ensure `original_id_map` is passed to `ResourceIDBuilder` constructor

---

## Problem: Import IDs Have Wrong Subscription

### Symptom
```
Import ID: /subscriptions/SOURCE_SUB_ID/resourceGroups/my-rg/...
                         ^^^^^^^^^^^^^^
                         ❌ Source subscription, not target
```

### Cause
Cross-tenant deployment without target subscription specified.

**Check:**
```bash
# Inspect subscription IDs in import blocks
python3 << 'EOF'
import json

with open('main.tf.json') as f:
    config = json.load(f)

import_blocks = config.get('import', [])
subscription_ids = set()

for ib in import_blocks:
    import_id = ib.get('id', '')
    if '/subscriptions/' in import_id:
        sub_id = import_id.split('/subscriptions/')[1].split('/')[0]
        subscription_ids.add(sub_id)

print(f"Subscription IDs found in import blocks:")
for sub_id in subscription_ids:
    print(f"  {sub_id}")

if len(subscription_ids) > 1:
    print("\n⚠️  Multiple subscription IDs - check if this is expected")
EOF
```

**Fix:**
```bash
# Include --target-subscription flag
uv run atg generate-iac \
  --target-tenant-id TARGET_TENANT_ID \
  --target-subscription TARGET_SUB_ID \
  --auto-import-existing
```

---

## Problem: Import Fails "Resource Not Found"

### Symptom
```
Error: Cannot import non-existent remote object
│
│ While attempting to import with address "azurerm_subnet.subnet_123",
│ Terraform could not find the resource in the Azure subscription.
```

### Cause
Resource doesn't exist in target tenant (only in source).

**Expected behavior:** Import blocks should only be generated for resources existing in BOTH tenants.

**Check:**
```bash
# Did you use --scan-target flag?
uv run atg generate-iac \
  --target-tenant-id TARGET_TENANT_ID \
  --scan-target \  # ← Required to scan target
  --auto-import-existing
```

**Fix:**

Without `--scan-target`:
- Generates import blocks for ALL source resources
- May fail if resource doesn't exist in target

With `--scan-target`:
- Scans target tenant first
- Only generates import blocks for resources existing in both
- Resources only in source: CREATE blocks (no import)
- Resources in both: IMPORT blocks + resource definitions

---

## Problem: Import Succeeds But Terraform Plan Shows Drift

### Symptom
```
Terraform will perform the following actions:

  # azurerm_subnet.subnet_123 will be updated in-place
  ~ resource "azurerm_subnet" "subnet_123" {
      ~ address_prefixes = ["10.0.1.0/24"] -> ["10.0.2.0/24"]
    }
```

### Cause
Configuration drift between source and target.

**This is expected behavior:**
1. Import brings resource under Terraform management
2. Terraform detects configuration differs from source
3. Next apply will reconcile target to match source

**Decision points:**
- **Accept drift:** Update source config to match target
- **Fix drift:** Run `terraform apply` to reconcile target to source
- **Investigate:** Check if drift is intentional (different environments)

**Check drift details:**
```bash
cd /path/to/terraform/output
terraform plan -detailed-exitcode

# Exit codes:
#   0 = No changes needed
#   1 = Error
#   2 = Changes needed (drift detected)
```

---

## Problem: "Duplicate Import Block" Error

### Symptom
```
Error: Duplicate import configuration for "azurerm_subnet.subnet_123"
│
│ An import block for this resource was already declared at main.tf.json:456
```

### Cause
Multiple import blocks generated for same resource.

**Check:**
```bash
# Find duplicate import blocks
python3 << 'EOF'
import json
from collections import Counter

with open('main.tf.json') as f:
    config = json.load(f)

import_blocks = config.get('import', [])
targets = [ib.get('to') for ib in import_blocks]
duplicates = [t for t, count in Counter(targets).items() if count > 1]

if duplicates:
    print(f"❌ {len(duplicates)} resources have duplicate import blocks:")
    for target in duplicates[:5]:
        print(f"  {target}")
else:
    print("✅ No duplicate import blocks")
EOF
```

**Fix:** This indicates a bug in import block generation. Report to development team with:
1. Command used to generate IaC
2. Resource types affected
3. Output of duplicate detection script above

---

## Problem: Child Resources Missing Import Blocks

### Symptom
```
Import blocks: 67/177 (37.9%)

Parent resources: ✅ All have imports
Child resources: ❌ No imports
```

### Cause
This was **Bug #10**. Fixed in recent release.

**Check version:**
```bash
uv run atg --version
```

**If using old version:**
- Update to latest: `git pull && uv sync`
- Re-generate IaC: `uv run atg generate-iac --auto-import-existing`

**If using latest version but still seeing issue:**
- Check SCAN_SOURCE_NODE relationships (see "Low Import Coverage" above)
- Verify original_id_map is being used (check debug logs)

---

## Diagnostic Commands

### Full Import Block Analysis
```bash
python3 << 'EOF'
import json
from collections import defaultdict

with open('main.tf.json') as f:
    config = json.load(f)

import_blocks = config.get('import', [])
resources = config.get('resource', {})

# Group by resource type
imports_by_type = defaultdict(int)
resources_by_type = defaultdict(int)

for ib in import_blocks:
    target = ib.get('to', '')
    resource_type = target.split('.')[0] if '.' in target else 'unknown'
    imports_by_type[resource_type] += 1

for resource_type, instances in resources.items():
    resources_by_type[resource_type] = len(instances)

# Print coverage by type
print("Import Coverage by Resource Type:")
print(f"{'Type':<40} {'Imports':<10} {'Resources':<10} {'Coverage':<10}")
print("-" * 70)

all_types = sorted(set(list(imports_by_type.keys()) + list(resources_by_type.keys())))
for resource_type in all_types:
    import_count = imports_by_type.get(resource_type, 0)
    resource_count = resources_by_type.get(resource_type, 0)
    coverage = f"{100*import_count/resource_count:.1f}%" if resource_count > 0 else "N/A"
    status = "✅" if import_count == resource_count else "⚠️ "
    print(f"{status} {resource_type:<38} {import_count:<10} {resource_count:<10} {coverage:<10}")

# Summary
total_imports = len(import_blocks)
total_resources = sum(resources_by_type.values())
overall_coverage = 100 * total_imports / total_resources if total_resources > 0 else 0

print("-" * 70)
print(f"{'TOTAL':<40} {total_imports:<10} {total_resources:<10} {overall_coverage:.1f}%")
EOF
```

### Validate Import IDs
```bash
python3 << 'EOF'
import json
import re

with open('main.tf.json') as f:
    config = json.load(f)

import_blocks = config.get('import', [])

issues = {
    'contains_variables': [],
    'missing_subscription': [],
    'malformed': []
}

azure_id_pattern = re.compile(r'^/subscriptions/[0-9a-f-]+/.*', re.IGNORECASE)

for ib in import_blocks:
    import_id = ib.get('id', '')
    target = ib.get('to', 'unknown')

    # Check for Terraform variables
    if '$' in import_id or '${' in import_id:
        issues['contains_variables'].append(target)

    # Check for subscription
    elif '/subscriptions/' not in import_id.lower():
        issues['missing_subscription'].append(target)

    # Check general format
    elif not azure_id_pattern.match(import_id):
        issues['malformed'].append(target)

# Report
print("Import ID Validation Results:")
print(f"Total import blocks: {len(import_blocks)}\n")

for issue_type, targets in issues.items():
    if targets:
        print(f"❌ {issue_type.replace('_', ' ').title()}: {len(targets)}")
        for target in targets[:3]:
            print(f"   {target}")
        if len(targets) > 3:
            print(f"   ... and {len(targets) - 3} more")
    else:
        print(f"✅ {issue_type.replace('_', ' ').title()}: 0")

print(f"\n{'✅ All import IDs valid' if not any(issues.values()) else '⚠️  Issues detected - see above'}")
EOF
```

---

## Quick Reference

| Problem | Check | Fix |
|---------|-------|-----|
| Low import coverage | SCAN_SOURCE_NODE relationships | Re-scan tenant or migrate layer |
| Variables in IDs | Query includes original_id | Update query and emitter |
| Wrong subscription | --target-subscription flag | Add flag with target sub ID |
| Resource not found | --scan-target flag | Add flag to scan target |
| Drift detected | Expected after import | Run terraform apply or update config |
| Duplicate imports | Bug in generation | Report to dev team |
| Child resources missing | Old version | Update and regenerate |

---

## Getting Help

**Check logs:**
```bash
# Enable debug logging
uv run atg generate-iac --auto-import-existing --debug 2>&1 | tee debug.log

# Search for import-related messages
grep -i "import" debug.log
grep -i "original_id" debug.log
```

**Verify Neo4j data:**
```cypher
// Check a specific resource
MATCH (r:Resource {id: 'ABSTRACTED_ID'})
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN r.id as abstracted_id, o.id as original_id, r.name as name
```

**Report issues:**
Include in bug report:
1. Import coverage output (see "Full Import Block Analysis" above)
2. Import ID validation results (see "Validate Import IDs" above)
3. Neo4j SCAN_SOURCE_NODE count
4. Command used to generate IaC
5. Debug logs (if available)

---

## Related Documentation

- **[Bug #10 Documentation](../BUG_10_DOCUMENTATION.md)** - Child resource import fix
- **[Import-First Strategy](../patterns/IMPORT_FIRST_STRATEGY.md)** - Why imports matter
- **[SCAN_SOURCE_NODE Migration](scan-source-node-migration.md)** - Fix missing relationships
- **[Dual Graph Schema](../DUAL_GRAPH_SCHEMA.md)** - Architecture details
