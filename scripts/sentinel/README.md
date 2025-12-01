# Azure Sentinel and Log Analytics Automation

Automated setup and configuration of Azure Sentinel and Log Analytics for Azure Tenant Grapher deployments.

## Overview

This feature automates the deployment of Azure Sentinel (Microsoft Defender for Cloud) and Log Analytics workspaces across your Azure environment. It discovers all resources in your tenant, creates a centralized Log Analytics workspace, configures diagnostic settings to stream logs, and enables Sentinel for threat detection and security monitoring.

**Key Capabilities:**

- **Automated Discovery**: Finds all Azure resources requiring monitoring via Neo4j graph or Azure API
- **Workspace Creation**: Creates Log Analytics workspace with optimal configuration
- **Diagnostic Settings**: Configures log streaming for all supported resource types
- **Sentinel Enablement**: Activates Microsoft Defender for Cloud on the workspace
- **Cross-Tenant Support**: Deploy monitoring for resources across multiple tenants
- **Idempotent Operations**: Safe to run multiple times without errors
- **Configuration Management**: Flexible config via files or environment variables

## Quick Start

### Basic Setup

```bash
# Set up Sentinel with default configuration
uv run atg setup-sentinel --tenant-id <TENANT_ID>

# Use custom workspace name and location
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --workspace-name my-sentinel-workspace \
  --location eastus
```

### Integrated with IaC Generation

```bash
# Generate IaC and set up Sentinel in one command
uv run atg generate-iac \
  --tenant-id <TENANT_ID> \
  --setup-sentinel \
  --workspace-name production-sentinel
```

### Cross-Tenant Deployment

```bash
# Deploy Sentinel in a different tenant
uv run atg setup-sentinel \
  --tenant-id <SOURCE_TENANT_ID> \
  --target-tenant-id <TARGET_TENANT_ID> \
  --workspace-name cross-tenant-sentinel
```

## Prerequisites

### Required Software

- **Azure CLI**: Version 2.50.0 or higher
- **Azure Tenant Grapher**: Latest version with Sentinel support
- **Python**: 3.11 or higher (for orchestration)

### Required Azure Permissions

The service principal or user must have:

- **Microsoft.OperationalInsights/workspaces/write**: Create/update workspaces
- **Microsoft.Insights/diagnosticSettings/write**: Configure diagnostic settings
- **Microsoft.SecurityInsights/\***: Enable Sentinel
- **Reader role**: On all resource groups being monitored

### Required Azure Resource Providers

The following providers must be registered:

- `Microsoft.OperationalInsights`
- `Microsoft.Insights`
- `Microsoft.SecurityInsights`

The tool will validate and offer to register missing providers automatically.

## Command Reference

### Primary Command

```bash
uv run atg setup-sentinel [OPTIONS]
```

### Options

| Option                          | Description                                          | Default            |
| ------------------------------- | ---------------------------------------------------- | ------------------ |
| `--tenant-id TEXT`              | Source tenant ID (required)                          | -                  |
| `--target-tenant-id TEXT`       | Target tenant for cross-tenant deployments           | Same as tenant-id  |
| `--subscription-id TEXT`        | Target subscription for workspace                    | First subscription |
| `--workspace-name TEXT`         | Log Analytics workspace name                         | sentinel-workspace |
| `--location TEXT`               | Azure region for workspace                           | eastus             |
| `--resource-group TEXT`         | Resource group for workspace                         | sentinel-rg        |
| `--retention-days INTEGER`      | Log retention period (30-730 days)                   | 90                 |
| `--sku TEXT`                    | Workspace pricing tier (PerGB2018, CapacityRes)      | PerGB2018          |
| `--config-file PATH`            | Path to configuration JSON/YAML file                 | -                  |
| `--dry-run`                     | Preview changes without applying                     | False              |
| `--strict / --no-strict`        | Fail on any error vs. continue on non-critical       | --no-strict        |
| `--skip-provider-check`         | Skip provider registration validation                | False              |
| `--skip-sentinel`               | Create workspace only, don't enable Sentinel         | False              |
| `--resource-types TEXT`         | Comma-separated list of resource types to configure  | all                |
| `--generate-script`             | Generate bash script instead of executing            | False              |
| `--output-dir PATH`             | Directory for generated scripts (with --gen-script)  | ./sentinel_scripts |
| `--debug`                       | Enable verbose debug logging                         | False              |

### Integration Flags

Add `--setup-sentinel` to existing commands:

```bash
# With generate-iac
uv run atg generate-iac --tenant-id <ID> --setup-sentinel

# With create-tenant
uv run atg create-tenant --spec spec.md --setup-sentinel
```

## Configuration

### Configuration File

Create a configuration file for repeatable deployments:

**sentinel_config.json:**

```json
{
  "workspace": {
    "name": "production-sentinel",
    "location": "eastus",
    "resource_group": "monitoring-rg",
    "retention_days": 180,
    "sku": "PerGB2018"
  },
  "sentinel": {
    "enable": true,
    "solutions": ["SecurityInsights"]
  },
  "diagnostic_settings": {
    "logs": {
      "enabled": true,
      "retention_days": 90
    },
    "metrics": {
      "enabled": true,
      "retention_days": 30
    }
  },
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.Network/networkSecurityGroups",
      "Microsoft.KeyVault/vaults"
    ],
    "exclude_resource_groups": ["test-rg", "dev-rg"]
  }
}
```

**Usage:**

```bash
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --config-file sentinel_config.json
```

See [docs/SENTINEL_CONFIGURATION.md](../../docs/SENTINEL_CONFIGURATION.md) for complete configuration reference.

### Environment Variables

Configure defaults via environment:

```bash
export AZURE_TENANT_ID="your-tenant-id"
export SENTINEL_WORKSPACE_NAME="my-sentinel-workspace"
export SENTINEL_LOCATION="eastus"
export SENTINEL_RETENTION_DAYS="90"
```

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   atg setup-sentinel                        │
│                 (src/commands/sentinel.py)                  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Bash Script Modules                            │
│              (scripts/sentinel/)                            │
├─────────────────────────────────────────────────────────────┤
│  1. validate_prerequisites.sh  → Check Azure CLI, providers │
│  2. create_workspace.sh        → Create Log Analytics WS    │
│  3. configure_diagnostics.sh   → Set up log streaming       │
│  4. enable_sentinel.sh         → Activate Sentinel          │
│  5. verify_deployment.sh       → Validate configuration     │
│  common.sh                     → Shared utilities           │
└─────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│              Resource Discovery                             │
│                                                             │
│  Neo4j Graph Query (Primary) ────────┐                     │
│  Azure Resource Graph API (Fallback) │                     │
└───────────────────────────────────────┼─────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────┐
│              Azure Resources                                │
│  VMs, NSGs, Key Vaults, Storage, Databases, etc.           │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow

1. **Prerequisites Validation**: Check Azure CLI version, authentication, and provider registration
2. **Resource Discovery**: Query Neo4j graph or Azure API to find all monitorable resources
3. **Workspace Creation**: Create or update Log Analytics workspace with specified configuration
4. **Diagnostic Configuration**: For each resource, create diagnostic settings pointing to workspace
5. **Sentinel Enablement**: Install Sentinel solution on the workspace
6. **Verification**: Validate workspace, diagnostic settings, and Sentinel are operational

### Modular Design

Each bash script module is:

- **Self-contained**: Can run independently with proper inputs
- **Idempotent**: Safe to execute multiple times
- **Error-handled**: Validates preconditions and handles failures gracefully
- **Testable**: Can be tested in isolation

## Integration Examples

### Example 1: Standalone Deployment

```bash
# Full Sentinel setup with custom configuration
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --workspace-name prod-sentinel \
  --location eastus2 \
  --retention-days 180 \
  --resource-group monitoring-prod-rg
```

### Example 2: Integrated with IaC Generation

```bash
# Scan tenant, generate Terraform, and set up Sentinel
uv run atg scan --tenant-id <TENANT_ID>
uv run atg generate-iac \
  --tenant-id <TENANT_ID> \
  --format terraform \
  --setup-sentinel \
  --workspace-name infrastructure-sentinel
```

### Example 3: Dry Run Preview

```bash
# Preview what would be created without making changes
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --dry-run \
  --debug
```

### Example 4: Selective Resource Monitoring

```bash
# Monitor only specific resource types
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --resource-types "Microsoft.Compute/virtualMachines,Microsoft.KeyVault/vaults"
```

### Example 5: Script Generation for Restricted Environments

```bash
# Generate scripts to run manually (for environments with restricted permissions)
uv run atg setup-sentinel \
  --tenant-id <TENANT_ID> \
  --generate-script \
  --output-dir ./my-sentinel-scripts

# Then manually review and execute:
cd ./my-sentinel-scripts
bash 1_validate_prerequisites.sh
bash 2_create_workspace.sh
# ... etc
```

See [docs/SENTINEL_INTEGRATION_EXAMPLES.md](../../docs/SENTINEL_INTEGRATION_EXAMPLES.md) for more examples.

## Troubleshooting

### Common Issues

**Problem: "Provider not registered"**

```
Error: The subscription is not registered to use namespace 'Microsoft.SecurityInsights'
```

**Solution:**

```bash
# Register provider manually
az provider register --namespace Microsoft.SecurityInsights
az provider show --namespace Microsoft.SecurityInsights --query "registrationState"

# Or let the tool register automatically
uv run atg setup-sentinel --tenant-id <ID>  # Will prompt to register
```

**Problem: "Insufficient permissions"**

```
Error: Authorization failed for workspace creation
```

**Solution:** Ensure your service principal has:

- `Contributor` or `Owner` role on the target subscription/resource group
- `Microsoft.OperationalInsights/workspaces/write` permission

**Problem: "Resource type doesn't support diagnostic settings"**

```
Warning: Resource type Microsoft.Example/resources doesn't support diagnostics
```

**Solution:** This is expected for certain resource types. Use `--no-strict` mode to continue:

```bash
uv run atg setup-sentinel --tenant-id <ID> --no-strict
```

See [docs/SENTINEL_TROUBLESHOOTING.md](../../docs/SENTINEL_TROUBLESHOOTING.md) for complete troubleshooting guide.

## Advanced Usage

### Custom Configuration for Different Environments

**Development:**

```json
{
  "workspace": {
    "name": "dev-sentinel",
    "retention_days": 30,
    "sku": "PerGB2018"
  }
}
```

**Production:**

```json
{
  "workspace": {
    "name": "prod-sentinel",
    "retention_days": 365,
    "sku": "CapacityReservation"
  },
  "sentinel": {
    "enable": true,
    "solutions": ["SecurityInsights", "AzureActivity"]
  }
}
```

### Monitoring Specific Resource Groups

```bash
# Create config with resource group filters
cat > sentinel_config.json <<EOF
{
  "resource_filters": {
    "include_resource_groups": ["production-rg", "infrastructure-rg"]
  }
}
EOF

uv run atg setup-sentinel \
  --tenant-id <ID> \
  --config-file sentinel_config.json
```

### Multi-Region Deployments

```bash
# East US workspace
uv run atg setup-sentinel \
  --tenant-id <ID> \
  --workspace-name sentinel-eastus \
  --location eastus \
  --resource-group sentinel-eastus-rg

# West US workspace
uv run atg setup-sentinel \
  --tenant-id <ID> \
  --workspace-name sentinel-westus \
  --location westus \
  --resource-group sentinel-westus-rg
```

## Security Best Practices

1. **Use Service Principals**: Don't use personal accounts for automation
2. **Least Privilege**: Grant only required permissions
3. **Separate Subscriptions**: Consider dedicated subscription for monitoring resources
4. **Retention Policies**: Configure based on compliance requirements
5. **Access Control**: Use RBAC to limit workspace access
6. **Audit Logging**: Enable audit logs for the workspace itself

## Performance Considerations

- **Large Tenants**: For tenants with 1000+ resources, expect 15-30 minutes for full setup
- **Parallel Execution**: The tool batches diagnostic settings creation for efficiency
- **Rate Limiting**: Automatically handles Azure API rate limits with exponential backoff
- **Resume Capability**: Failed operations can be retried without duplicating successful work

## Migration from Manual Configuration

If you have existing Log Analytics workspaces:

```bash
# Reuse existing workspace
uv run atg setup-sentinel \
  --tenant-id <ID> \
  --workspace-name existing-workspace \
  --resource-group existing-rg \
  --skip-sentinel  # If Sentinel already enabled
```

The tool will:

- Detect existing workspace and update configuration
- Skip diagnostic settings that already exist
- Only create missing configurations

## Contributing

To extend or modify this feature:

1. **Bash modules**: Edit files in `scripts/sentinel/`
2. **Python orchestration**: Edit `src/commands/sentinel.py`
3. **Tests**: Add tests in `tests/test_sentinel.py`
4. **Documentation**: Update this README and related docs

## Support

- **Documentation**: [docs/SENTINEL_CONFIGURATION.md](../../docs/SENTINEL_CONFIGURATION.md)
- **Examples**: [docs/SENTINEL_INTEGRATION_EXAMPLES.md](../../docs/SENTINEL_INTEGRATION_EXAMPLES.md)
- **Troubleshooting**: [docs/SENTINEL_TROUBLESHOOTING.md](../../docs/SENTINEL_TROUBLESHOOTING.md)
- **GitHub Issues**: Report bugs and request features

## Version History

- **1.0.0** (2025-12): Initial release with full automation support
