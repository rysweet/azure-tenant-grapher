# Terraform Import Blocks - Quick Reference

Fast reference for generating and verifying Terraform import blocks.

---

## Generate Import Blocks

```bash
# Standard: Single tenant with existing resources
uv run atg generate-iac \
  --format terraform \
  --auto-import-existing

# Cross-tenant: Deploy to different tenant
uv run atg generate-iac \
  --format terraform \
  --target-tenant-id TARGET_TENANT_ID \
  --target-subscription TARGET_SUB_ID \
  --auto-import-existing

# Smart import: Scan target first (recommended for cross-tenant)
uv run atg generate-iac \
  --format terraform \
  --target-tenant-id TARGET_TENANT_ID \
  --scan-target \
  --auto-import-existing
```

---

## Verify Coverage

**One-liner check:**
```bash
python3 -c "import json; c=json.load(open('main.tf.json')); i=len(c.get('import',[])); r=sum(len(x) for x in c.get('resource',{}).values()); print(f'{i}/{r} ({100*i/r:.1f}%)')"
```

**Expected:** `177/177 (100.0%)` for full coverage.

---

## Check Import ID Quality

**No variables:**
```bash
grep -o '"id": "[^"]*"' main.tf.json | grep '\$' && echo "❌ Variables found" || echo "✅ Clean IDs"
```

**Correct subscription:**
```bash
grep -o '"id": "[^"]*"' main.tf.json | head -3
# Should show: /subscriptions/TARGET_SUB_ID/...
```

---

## Troubleshoot Missing Imports

**Check SCAN_SOURCE_NODE:**
```cypher
MATCH (r:Resource)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN count(r)
```
Expected: Equal to total resource count.

**If missing:** Re-scan tenant or see [migration guide](../guides/scan-source-node-migration.md).

---

## Test Import Blocks

```bash
cd /path/to/terraform/output
terraform init
terraform plan

# Exit codes:
#   0 = No changes (perfect match)
#   2 = Changes needed (drift detected - expected)
#   1 = Error (bad import ID)
```

---

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| `67/177 (37.9%)` | Missing SCAN_SOURCE_NODE | Re-scan tenant |
| Variables in IDs | Old version or missing original_id | Update and regenerate |
| Wrong subscription | Missing --target-subscription | Add flag |
| Resource not found | Resource only in source | Use --scan-target |

---

## Python API

**Generate with imports:**
```python
from src.iac.cli_handler import IaCCLIHandler

handler = IaCCLIHandler(neo4j_driver)
handler.generate_iac(
    format_type="terraform",
    output_dir="/tmp/output",
    auto_import_existing=True,
    target_subscription_id="TARGET_SUB_ID"
)
```

**Check coverage:**
```python
import json

with open('main.tf.json') as f:
    config = json.load(f)

import_count = len(config.get('import', []))
resource_count = sum(len(r) for r in config.get('resource', {}).values())
coverage = 100 * import_count / resource_count

print(f"Coverage: {coverage:.1f}%")
```

---

## Neo4j Query Template

**Get resources with original IDs:**
```cypher
MATCH (r:Resource)
OPTIONAL MATCH (r)-[:SCAN_SOURCE_NODE]->(o:Resource:Original)
RETURN
  r.id as abstracted_id,
  o.id as original_id,
  r.name as name,
  r.type as type
ORDER BY r.name
```

**Essential:** Always include `o.id as original_id` for import generation.

---

## Debugging

**Enable debug logs:**
```bash
uv run atg generate-iac --auto-import-existing --debug 2>&1 | tee debug.log
```

**Search logs:**
```bash
grep "import block" debug.log
grep "original_id" debug.log
grep "ResourceIDBuilder" debug.log
```

---

## Related Docs

- **Detailed guide:** [Terraform Import Troubleshooting](../guides/TERRAFORM_IMPORT_TROUBLESHOOTING.md)
- **Bug fix:** [Bug #10 Documentation](../BUG_10_DOCUMENTATION.md)
- **Pattern:** [Import-First Strategy](../patterns/IMPORT_FIRST_STRATEGY.md)
