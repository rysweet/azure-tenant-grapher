# Cross-Tenant Translation Features

## Overview

Azure Tenant Grapher supports translating resources from a source tenant to a target tenant, handling:
- Resource ID translation (subscription IDs)
- Entra ID object translation (tenant IDs, object IDs)
- Pre-existing resource handling (Terraform import)

## CLI Flags

### generate-iac Command
```bash
--target-tenant-id TEXT         # Target tenant for deployment
--target-subscription TEXT      # Target subscription
--source-tenant-id TEXT         # Source tenant (auto-detected)
--identity-mapping-file TEXT    # Identity mapping JSON
--strict-translation            # Fail on missing mappings
--auto-import-existing          # Import pre-existing resources
--import-strategy TEXT          # resource_groups|all_resources|selective
```

## Architecture

See `/docs/design/cross-tenant-translation/` for:
- UNIFIED_TRANSLATION_ARCHITECTURE.md
- RESOURCE_TYPES_INVENTORY.md
- Component designs

## Examples

See `/examples/` for:
- cross_tenant_deployment.sh
- test_translation.py
- generate_identity_mapping.md
