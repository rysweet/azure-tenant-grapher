# Diagnostic Settings Handler

## Overview

The Diagnostic Settings handler converts Azure Monitor Diagnostic Settings from your scanned Azure tenant into Terraform `azurerm_monitor_diagnostic_setting` resources. This enables you to recreate monitoring and logging configurations when deploying infrastructure to new environments.

**Handler**: `DiagnosticSettingHandler`
**Location**: `src/iac/emitters/terraform/handlers/monitoring/diagnostic_settings.py`
**Azure Resource Type**: `Microsoft.Insights/diagnosticSettings`
**Terraform Resource**: `azurerm_monitor_diagnostic_setting`

## What are Diagnostic Settings?

Azure Monitor Diagnostic Settings control where platform logs and metrics are sent for Azure resources. They enable you to:

- Send logs to Log Analytics workspaces for querying and analysis
- Archive logs to Storage Accounts for long-term retention
- Stream logs to Event Hubs for real-time processing
- Configure which log categories and metrics are collected

Diagnostic settings can be attached to:
- Individual resources (VMs, Storage Accounts, Key Vaults, etc.)
- Resource Groups
- Subscriptions

## When to Use This Handler

The Diagnostic Settings handler is automatically invoked during IaC generation when:

1. You've scanned an Azure tenant with `azure-tenant-grapher scan`
2. The scanned resources have diagnostic settings configured
3. You run `azure-tenant-grapher generate-iac --format terraform`

## How It Works

### Discovery Phase
During Azure tenant scanning, the `DiagnosticRule` relationship rule identifies diagnostic settings on resources and creates:
- **Nodes**: `DiagnosticSetting` nodes in Neo4j graph
- **Relationships**: `Resource -[:SENDS_DIAG_TO]-> DiagnosticSetting -[:LOGS_TO]-> LogAnalyticsWorkspace`

### Generation Phase
When generating Terraform IaC, the Diagnostic Settings handler:

1. **Reads** diagnostic setting nodes from Neo4j
2. **Extracts** the target resource ID from the diagnostic setting's ARM ID
3. **Identifies** destination(s): Log Analytics workspace, Storage Account, or Event Hub
4. **Filters** log categories to include only enabled logs
5. **Formats** metrics with their enabled state
6. **Emits** `azurerm_monitor_diagnostic_setting` Terraform resource

## Generated Terraform Structure

### Basic Example
```hcl
resource "azurerm_monitor_diagnostic_setting" "vm1_diagnostics" {
  name               = "diagnosticSetting1"
  target_resource_id = azurerm_virtual_machine.vm1.id

  log_analytics_workspace_id = azurerm_log_analytics_workspace.law1.id

  enabled_log {
    category = "AuditLogs"
  }

  enabled_log {
    category = "SecurityLogs"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
```

### Multiple Destinations Example
```hcl
resource "azurerm_monitor_diagnostic_setting" "keyvault1_diagnostics" {
  name               = "comprehensive-diagnostics"
  target_resource_id = azurerm_key_vault.keyvault1.id

  log_analytics_workspace_id = azurerm_log_analytics_workspace.law1.id
  storage_account_id         = azurerm_storage_account.logs.id
  eventhub_authorization_rule_id = azurerm_eventhub_namespace_authorization_rule.logs.id

  enabled_log {
    category = "AuditEvent"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
```

### Subscription-Level Example
```hcl
resource "azurerm_monitor_diagnostic_setting" "subscription_diagnostics" {
  name               = "subscription-logs"
  target_resource_id = "/subscriptions/12345678-1234-1234-1234-123456789012"

  log_analytics_workspace_id = azurerm_log_analytics_workspace.law1.id

  enabled_log {
    category = "Administrative"
  }

  enabled_log {
    category = "Security"
  }

  enabled_log {
    category = "ServiceHealth"
  }
}
```

## Supported Scenarios

### ✅ Supported
- Resource-level diagnostic settings (VMs, Storage, Key Vaults, etc.)
- Subscription-level diagnostic settings
- Resource Group-level diagnostic settings
- Log Analytics workspace destinations
- Storage Account destinations
- Event Hub destinations
- Multiple simultaneous destinations
- Enabled log category filtering
- Metric collection with enabled/disabled state

### ⚠️ Limitations
- Diagnostic settings without any destination (workspace, storage, eventhub) are skipped
- Retention policies are not currently mapped (Azure is deprecating these in favor of workspace retention)
- Partner solutions (third-party monitoring) are not yet supported

## Configuration Details

### Log Categories
The handler automatically:
- **Includes** only logs where `enabled: true` in Azure
- **Excludes** disabled log categories
- **Formats** as `enabled_log { category = "CategoryName" }` blocks

Example Azure logs array:
```json
{
  "logs": [
    {"category": "AuditLogs", "enabled": true},
    {"category": "SignInLogs", "enabled": false}
  ]
}
```

Generated Terraform (only enabled logs):
```hcl
enabled_log {
  category = "AuditLogs"
}
```

### Metrics
The handler:
- **Includes** all metric categories
- **Preserves** the enabled/disabled state
- **Formats** as `metric { category = "...", enabled = true/false }` blocks

### Target Resource Resolution
The diagnostic setting's target resource is automatically resolved from its ARM resource ID:

```
Diagnostic Setting ID:
/subscriptions/abc/.../vm1/providers/Microsoft.Insights/diagnosticSettings/diag1
                                    ↓ (extract target)
Target Resource ID:
/subscriptions/abc/.../vm1
```

## Troubleshooting

### Diagnostic Settings Not Generated

**Symptom**: Expected diagnostic settings missing from Terraform output

**Causes**:
1. **No destination configured**: Diagnostic setting has no workspace, storage, or eventhub
   - **Solution**: Azure diagnostic settings require at least one destination
2. **Resource not scanned**: Target resource not included in scan scope
   - **Solution**: Rescan with broader scope or include specific resource groups
3. **Orphaned diagnostic setting**: Target resource was deleted but diagnostic setting remains
   - **Solution**: Clean up orphaned diagnostic settings in Azure portal

**Check logs**:
```bash
# Look for skip messages during IaC generation
azure-tenant-grapher generate-iac --format terraform 2>&1 | grep -i "diagnostic"
```

### Target Resource ID Not Found

**Symptom**: Error or warning about unable to extract target resource ID

**Cause**: Malformed diagnostic setting ARM ID

**Solution**:
1. Verify diagnostic setting ID format in Neo4j:
   ```cypher
   MATCH (d:DiagnosticSetting)
   RETURN d.id, d.name
   ```
2. Check that ID follows standard ARM format:
   ```
   /{scope}/providers/Microsoft.Insights/diagnosticSettings/{name}
   ```

### Generated Terraform Fails Validation

**Symptom**: `terraform validate` fails on generated diagnostic settings

**Causes**:
1. **Missing workspace reference**: Log Analytics workspace not in generated Terraform
   - **Solution**: Ensure workspace was scanned and included in IaC generation
2. **Invalid log category**: Log category not supported by target resource type
   - **Solution**: Review Azure diagnostic settings, remove unsupported categories

## Integration with Other Handlers

The Diagnostic Settings handler works alongside:

- **Log Analytics Workspace Handler**: Generates workspace resources referenced by diagnostic settings
- **Storage Account Handler**: Generates storage accounts for log archival
- **Event Hub Handler**: Generates event hubs for log streaming
- **Resource Handlers**: All resource handlers (VM, Key Vault, etc.) that diagnostic settings attach to

## Examples

### Scan and Generate with Diagnostic Settings

```bash
# 1. Scan Azure tenant
azure-tenant-grapher scan --tenant-id YOUR_TENANT_ID

# 2. Generate Terraform IaC
azure-tenant-grapher generate-iac --format terraform --output-dir ./terraform-output

# 3. Review generated diagnostic settings
ls ./terraform-output/monitoring/diagnostic_settings/

# 4. Validate Terraform
cd ./terraform-output
terraform init
terraform validate
```

### Query Diagnostic Settings in Neo4j

```cypher
// Find all diagnostic settings and their targets
MATCH (r:Resource)-[:SENDS_DIAG_TO]->(d:DiagnosticSetting)-[:LOGS_TO]->(w:LogAnalyticsWorkspace)
RETURN r.name AS Resource, d.name AS DiagnosticSetting, w.name AS Workspace

// Find subscription-level diagnostic settings
MATCH (d:DiagnosticSetting)
WHERE d.id CONTAINS '/subscriptions/' AND NOT d.id CONTAINS '/resourceGroups/'
RETURN d.name, d.id

// Count diagnostic settings by destination type
MATCH (d:DiagnosticSetting)
RETURN
  COUNT(CASE WHEN d.properties CONTAINS 'workspaceId' THEN 1 END) AS LogAnalytics,
  COUNT(CASE WHEN d.properties CONTAINS 'storageAccountId' THEN 1 END) AS Storage,
  COUNT(CASE WHEN d.properties CONTAINS 'eventHubAuthorizationRuleId' THEN 1 END) AS EventHub
```

## Best Practices

1. **Always configure destinations**: Diagnostic settings without destinations are useless and will be skipped
2. **Use Log Analytics for querying**: Most flexible destination for log analysis and alerting
3. **Use Storage for archival**: Long-term retention of logs for compliance
4. **Use Event Hub for streaming**: Real-time log processing and SIEM integration
5. **Enable relevant categories**: Don't blindly enable all logs - select categories you'll actually use
6. **Subscription-level diagnostics**: Capture administrative and service health events
7. **Resource Group diagnostics**: Useful for governance and compliance tracking

## Related Documentation

- [Azure Monitor Diagnostic Settings Overview](https://learn.microsoft.com/en-us/azure/azure-monitor/essentials/diagnostic-settings)
- [Terraform azurerm_monitor_diagnostic_setting](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/monitor_diagnostic_setting)
- [ATG IaC Generation Guide](../iac-generation.md)
- [ATG Relationship Rules](../../scanning/relationship-rules.md)
- [Log Analytics Handler](./log-analytics.md)

## Changelog

### v1.0.0 (2026-01-15)
- Initial implementation
- Support for resource, resource group, and subscription-level diagnostic settings
- Support for Log Analytics, Storage Account, and Event Hub destinations
- Automatic enabled log filtering
- Metric collection with enabled state

## Support

If you encounter issues with the Diagnostic Settings handler:

1. Check the [Troubleshooting](#troubleshooting) section above
2. Review logs during IaC generation
3. Query Neo4j to verify diagnostic settings were captured during scan
4. File an issue on GitHub with:
   - Diagnostic setting ARM ID
   - Expected vs actual Terraform output
   - Relevant log messages
