---
last_updated: 2026-02-06
status: current
category: guides
issue: #888
---

# NSG Association & Diagnostic Settings Fix

Complete guide to the handler-based architecture that preserves NIC-NSG associations and diagnostic settings during tenant replication.

## Overview

This fix addresses critical data loss issues during Azure tenant replication where network security group associations and diagnostic settings were not being preserved in the replicated environment.

**What was fixed:**
- NIC-NSG associations were lost (1 → 0 associations after replication)
- Diagnostic settings were not replicated (2 → 0 settings after replication)

**Root causes:**
1. Diagnostic settings handler existed but was never registered (missing import)
2. Duplicate NSG association code created conflicts between legacy code and handler system

## The Solution: Handler-Based Architecture

The fix consolidates all relationship emission logic into ATG's handler-based architecture, removing legacy duplicate code and properly registering all handlers.

### What Changed

#### 1. Diagnostic Settings Handler Registration

**File:** `src/iac/emitters/terraform/handlers/__init__.py`

```python
# Import all resource-specific handlers
from .diagnostic_settings import DiagnosticSettingsHandler
from .network_interface import NetworkInterfaceHandler
from .network_security_group import NetworkSecurityGroupHandler
# ... other handlers ...

# Register handlers with emitter
HANDLER_REGISTRY = {
    "microsoft.insights/diagnosticsettings": DiagnosticSettingsHandler,
    "microsoft.network/networkinterfaces": NetworkInterfaceHandler,
    "microsoft.network/networksecuritygroups": NetworkSecurityGroupHandler,
    # ... other handlers ...
}
```

**What this does:** The diagnostic settings handler now gets automatically invoked during IaC generation, ensuring all diagnostic settings are emitted to Terraform.

#### 2. Removed Legacy NSG Association Code

**File:** `src/iac/emitters/terraform/terraform_emitter.py`

**Before (problematic):**
```python
def emit_terraform(self, resources):
    # ... resource emission ...

    # Legacy code that duplicated handler logic
    self._emit_deferred_resources()  # ❌ Duplicates handler work

def _emit_deferred_resources(self):
    """Legacy method that re-emitted NSG associations"""
    # This code duplicated what NetworkSecurityGroupHandler already did
    # Caused conflicts and missed associations
```

**After (clean):**
```python
def emit_terraform(self, resources):
    # ... resource emission ...

    # Handlers emit all relationships - no legacy code needed
    # ✅ NetworkSecurityGroupHandler handles NSG associations
    # ✅ DiagnosticSettingsHandler handles diagnostic settings
```

**What this does:** Removes duplicate emission code that conflicted with the handler system, allowing handlers to do their job cleanly.

## How It Works

### Handler-Based Architecture (Bricks & Studs Pattern)

ATG uses a modular handler architecture where each Azure resource type has a dedicated handler that knows how to:

1. **Transform** the resource from Azure format to Terraform
2. **Emit relationships** (NSG associations, diagnostic settings, etc.)
3. **Handle dependencies** between resources

```
┌─────────────────────────────────────────┐
│     TerraformEmitter (Orchestrator)     │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌────────────────────────────────────────────────────┐
│              Handler Registry                       │
│  (Maps resource type → handler instance)           │
└────┬──────────┬──────────────┬─────────────────┬───┘
     │          │              │                 │
     ▼          ▼              ▼                 ▼
┌─────────┐ ┌────────┐ ┌──────────────┐ ┌──────────┐
│   NIC   │ │  NSG   │ │  Diagnostic  │ │  Other   │
│ Handler │ │Handler │ │   Settings   │ │ Handlers │
│         │ │        │ │   Handler    │ │          │
└─────────┘ └────────┘ └──────────────┘ └──────────┘
```

### Example: NIC-NSG Association Flow

1. **Discovery Phase:** ATG scans Azure and stores NIC with NSG reference in Neo4j
   ```cypher
   (:NetworkInterface {id: "/subscriptions/.../nic1"})-[:USES_NSG]->
   (:NetworkSecurityGroup {id: "/subscriptions/.../nsg1"})
   ```

2. **IaC Generation Phase:**
   - `NetworkInterfaceHandler` processes the NIC node
   - Handler sees `USES_NSG` relationship in graph
   - Handler emits Terraform with `network_security_group_id` property
   ```hcl
   resource "azurerm_network_interface" "nic1" {
     name = "nic1"
     # ... other properties ...

     # Handler emits this association from graph relationship
     network_security_group_id = azurerm_network_security_group.nsg1.id
   }
   ```

3. **Deployment Phase:** Terraform creates NIC with NSG association intact

### Example: Diagnostic Settings Flow

1. **Discovery Phase:** ATG finds diagnostic settings attached to a resource
   ```cypher
   (:StorageAccount {id: "/subscriptions/.../storage1"})-[:HAS_DIAGNOSTIC_SETTING]->
   (:DiagnosticSetting {name: "diagnostics1", logs: [...], metrics: [...]})
   ```

2. **IaC Generation Phase:**
   - `DiagnosticSettingsHandler` processes diagnostic setting nodes
   - Handler emits Terraform diagnostic setting resource
   ```hcl
   resource "azurerm_monitor_diagnostic_setting" "diagnostics1" {
     name               = "diagnostics1"
     target_resource_id = azurerm_storage_account.storage1.id

     log_analytics_workspace_id = var.log_analytics_workspace_id

     # Logs and metrics from graph data
     enabled_log {
       category = "StorageRead"
     }
     metric {
       category = "Transaction"
     }
   }
   ```

3. **Deployment Phase:** Terraform creates diagnostic setting with correct configuration

## Why Handler-Based is Better

### Before (Legacy Code)

**Problems:**
- Duplicate emission logic scattered across codebase
- Hard to track what gets emitted when
- Handlers and legacy code conflicted
- Missing registrations meant some handlers never ran
- Difficult to add new resource types

**Code smell:**
```python
# Three different places could emit NSG associations:
# 1. NetworkInterfaceHandler (correct)
# 2. NetworkSecurityGroupHandler (also correct?)
# 3. _emit_deferred_resources() (legacy, wrong)

# Which one wins? Nobody knows! 🎲
```

### After (Handler Architecture)

**Benefits:**
- ✅ **Single responsibility:** Each handler knows its resource type
- ✅ **No conflicts:** Only one place emits each relationship
- ✅ **Easy to extend:** Add new resource type = add new handler
- ✅ **Testable:** Test each handler independently
- ✅ **Discoverable:** All handlers registered in one place

**Clean code:**
```python
# NetworkInterfaceHandler emits NIC with NSG reference
# NetworkSecurityGroupHandler emits NSG resource
# No conflicts, no duplication, crystal clear
```

## Migration Notes

### For Developers

**If you're adding a new relationship type:**

1. Create handler in `src/iac/emitters/terraform/handlers/`
   ```python
   class NewResourceHandler(ResourceHandler):
       def handle(self, node):
           # Transform resource
           # Emit relationships
           pass
   ```

2. Register handler in `handlers/__init__.py`
   ```python
   from .new_resource import NewResourceHandler

   HANDLER_REGISTRY = {
       "microsoft.newservice/newresource": NewResourceHandler,
   }
   ```

3. That's it! Handler automatically called during emission

**If you find legacy emission code:**

1. Check if a handler already exists for that resource type
2. If yes: Remove legacy code, handler handles it
3. If no: Create handler, then remove legacy code

### For Users

**No migration needed!** This is a bug fix that makes replication work correctly.

**Verification:**
```bash
# After deploying replicated tenant, verify:

# 1. NIC-NSG associations preserved
az network nic show --name <nic-name> --resource-group <rg> \
  --query "networkSecurityGroup.id" -o tsv

# 2. Diagnostic settings preserved
az monitor diagnostic-settings list \
  --resource <resource-id> -o table
```

## Testing Approach

### Unit Tests

Each handler has dedicated unit tests:

```python
# tests/iac/emitters/terraform/handlers/test_diagnostic_settings.py

def test_diagnostic_settings_handler_emits_logs():
    """Verify handler emits log configuration correctly"""
    handler = DiagnosticSettingsHandler()
    node = create_diagnostic_setting_node(logs=[...])

    result = handler.handle(node)

    assert "enabled_log" in result
    assert result["enabled_log"][0]["category"] == "StorageRead"

def test_diagnostic_settings_handler_emits_metrics():
    """Verify handler emits metric configuration correctly"""
    # Similar test for metrics
    pass
```

### Integration Tests

End-to-end replication test:

```python
# tests/integration/test_nsg_diagnostic_replication.py

def test_replicate_tenant_preserves_nsg_associations():
    """Verify NIC-NSG associations survive replication"""
    # 1. Scan source tenant
    source_nics = scan_nics_with_nsg()
    assert len(source_nics) == 1
    assert source_nics[0].nsg_id is not None

    # 2. Generate IaC
    generate_iac(source_tenant)

    # 3. Deploy to target tenant
    deploy_terraform(target_tenant)

    # 4. Verify associations preserved
    target_nics = scan_nics_with_nsg(target_tenant)
    assert len(target_nics) == 1
    assert target_nics[0].nsg_id is not None  # ✅ Preserved!

def test_replicate_tenant_preserves_diagnostic_settings():
    """Verify diagnostic settings survive replication"""
    # Similar test for diagnostic settings
    pass
```

### Manual Testing

1. **Scan source tenant with known NSG associations and diagnostic settings:**
   ```bash
   azure-tenant-grapher scan --tenant-id <source-tenant>
   ```

2. **Generate IaC and verify handler output:**
   ```bash
   azure-tenant-grapher generate-iac --format terraform

   # Check generated files for:
   # - network_security_group_id in NIC resources
   # - azurerm_monitor_diagnostic_setting resources
   ```

3. **Deploy to target tenant:**
   ```bash
   cd terraform-output
   terraform init
   terraform plan  # Verify associations in plan
   terraform apply
   ```

4. **Verify in Azure Portal:**
   - Navigate to NIC → check "Network security group" field
   - Navigate to resource → "Diagnostic settings" → verify logs/metrics

## Related Documentation

- [Handler Architecture Overview](../architecture/HANDLER_ARCHITECTURE.md) - Complete handler system design
- [Terraform Emitter Reference](../reference/TERRAFORM_EMITTER_REFERENCE.md) - Emitter internals
- [Neo4j Schema Reference](../NEO4J_SCHEMA_REFERENCE.md) - Graph relationships used by handlers

## Troubleshooting

### NSG Association Still Missing

**Symptom:** NIC deployed without NSG association

**Check:**
1. Verify NSG relationship exists in graph:
   ```cypher
   MATCH (nic:NetworkInterface {name: "your-nic-name"})-[r:USES_NSG]->(nsg)
   RETURN nic.name, nsg.name, type(r)
   ```

2. Verify handler is registered:
   ```python
   from src.iac.emitters.terraform.handlers import HANDLER_REGISTRY
   print(HANDLER_REGISTRY.get("microsoft.network/networkinterfaces"))
   # Should show NetworkInterfaceHandler class
   ```

3. Check handler logs during emission (enable debug logging)

### Diagnostic Settings Not Emitted

**Symptom:** No `azurerm_monitor_diagnostic_setting` resources in generated Terraform

**Check:**
1. Verify diagnostic setting nodes exist in graph:
   ```cypher
   MATCH (ds:DiagnosticSetting)
   RETURN ds.name, ds.target_resource_id
   LIMIT 10
   ```

2. Verify handler is registered:
   ```python
   from src.iac.emitters.terraform.handlers import HANDLER_REGISTRY
   print(HANDLER_REGISTRY.get("microsoft.insights/diagnosticsettings"))
   # Should show DiagnosticSettingsHandler class
   ```

3. Check if diagnostic settings were filtered out during scan

## Key Takeaways

1. **Handler architecture is the single source of truth** for IaC emission
2. **All handlers must be registered** in `handlers/__init__.py` to work
3. **Legacy emission code should be removed** to avoid conflicts
4. **Graph relationships drive handler behavior** - relationships must exist in Neo4j
5. **Bricks & Studs pattern** keeps code modular and regeneratable

---

**Issue:** #888
**Status:** Fixed
**Architecture:** Handler-based (Bricks & Studs)
**Verification:** Manual testing + integration tests required
