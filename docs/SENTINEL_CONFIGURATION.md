# Azure Sentinel Configuration Guide

Complete configuration reference for Azure Sentinel and Log Analytics automation.

## Configuration Methods

Azure Sentinel automation supports three configuration methods, listed in priority order:

1. **Command-line flags**: Highest priority, override all other settings
2. **Configuration file**: Medium priority, overrides environment variables
3. **Environment variables**: Lowest priority, provide defaults

## Configuration File Schema

### Complete Configuration Example

```json
{
  "workspace": {
    "name": "sentinel-workspace",
    "location": "eastus",
    "resource_group": "sentinel-rg",
    "retention_days": 90,
    "sku": "PerGB2018",
    "daily_quota_gb": null,
    "tags": {
      "Environment": "Production",
      "ManagedBy": "azure-tenant-grapher",
      "CostCenter": "IT-Security"
    }
  },
  "sentinel": {
    "enable": true,
    "solutions": ["SecurityInsights", "AzureActivity"],
    "data_connectors": ["AzureActiveDirectory", "AzureActivity"]
  },
  "diagnostic_settings": {
    "name_pattern": "sentinel-diag-{resource_name}",
    "logs": {
      "enabled": true,
      "retention_days": 90,
      "categories": ["all"]
    },
    "metrics": {
      "enabled": true,
      "retention_days": 30,
      "categories": ["AllMetrics"]
    }
  },
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.Network/networkSecurityGroups",
      "Microsoft.KeyVault/vaults",
      "Microsoft.Storage/storageAccounts",
      "Microsoft.Sql/servers"
    ],
    "exclude_types": [],
    "include_resource_groups": [],
    "exclude_resource_groups": ["test-rg", "dev-temp-rg"],
    "include_tags": {},
    "exclude_tags": {
      "Environment": "Development"
    }
  },
  "azure": {
    "tenant_id": "12345678-1234-1234-1234-123456789abc",
    "target_tenant_id": null,
    "subscription_id": null,
    "providers_required": [
      "Microsoft.OperationalInsights",
      "Microsoft.Insights",
      "Microsoft.SecurityInsights"
    ]
  },
  "execution": {
    "dry_run": false,
    "strict_mode": false,
    "skip_provider_check": false,
    "skip_sentinel": false,
    "parallel_operations": 5,
    "retry_attempts": 3,
    "retry_delay_seconds": 5
  }
}
```

### Field Definitions

#### Workspace Configuration

| Field              | Type    | Required | Default            | Description                                    |
| ------------------ | ------- | -------- | ------------------ | ---------------------------------------------- |
| `name`             | string  | Yes      | sentinel-workspace | Log Analytics workspace name                   |
| `location`         | string  | Yes      | eastus             | Azure region (e.g., eastus, westus2, westeu)   |
| `resource_group`   | string  | Yes      | sentinel-rg        | Resource group for workspace                   |
| `retention_days`   | integer | No       | 90                 | Log retention period (30-730 days)             |
| `sku`              | string  | No       | PerGB2018          | Pricing tier (PerGB2018, CapacityReservation)  |
| `daily_quota_gb`   | integer | No       | null               | Daily ingestion limit in GB (null = unlimited) |
| `tags`             | object  | No       | {}                 | Azure resource tags                            |

#### Sentinel Configuration

| Field             | Type    | Required | Default            | Description                                 |
| ----------------- | ------- | -------- | ------------------ | ------------------------------------------- |
| `enable`          | boolean | No       | true               | Enable Sentinel on workspace                |
| `solutions`       | array   | No       | [SecurityInsights] | Sentinel solutions to install               |
| `data_connectors` | array   | No       | []                 | Data connectors to configure automatically  |

#### Diagnostic Settings

| Field          | Type   | Required | Default                            | Description                                 |
| -------------- | ------ | -------- | ---------------------------------- | ------------------------------------------- |
| `name_pattern` | string | No       | sentinel-diag-{resource_name}      | Naming pattern for diagnostic settings      |
| `logs`         | object | No       | See below                          | Log configuration                           |
| `metrics`      | object | No       | See below                          | Metrics configuration                       |

**Logs Configuration:**

| Field            | Type    | Required | Default | Description                             |
| ---------------- | ------- | -------- | ------- | --------------------------------------- |
| `enabled`        | boolean | No       | true    | Enable log collection                   |
| `retention_days` | integer | No       | 90      | Log retention period                    |
| `categories`     | array   | No       | [all]   | Log categories (all or specific names)  |

**Metrics Configuration:**

| Field            | Type    | Required | Default       | Description                                |
| ---------------- | ------- | -------- | ------------- | ------------------------------------------ |
| `enabled`        | boolean | No       | true          | Enable metrics collection                  |
| `retention_days` | integer | No       | 30            | Metrics retention period                   |
| `categories`     | array   | No       | [AllMetrics]  | Metric categories                          |

#### Resource Filters

| Field                     | Type   | Required | Default | Description                                    |
| ------------------------- | ------ | -------- | ------- | ---------------------------------------------- |
| `include_types`           | array  | No       | []      | Only process these resource types (empty=all)  |
| `exclude_types`           | array  | No       | []      | Skip these resource types                      |
| `include_resource_groups` | array  | No       | []      | Only process these resource groups (empty=all) |
| `exclude_resource_groups` | array  | No       | []      | Skip these resource groups                     |
| `include_tags`            | object | No       | {}      | Only process resources with these tags         |
| `exclude_tags`            | object | No       | {}      | Skip resources with these tags                 |

#### Azure Configuration

| Field                | Type   | Required | Default | Description                             |
| -------------------- | ------ | -------- | ------- | --------------------------------------- |
| `tenant_id`          | string | Yes      | -       | Source Azure tenant ID                  |
| `target_tenant_id`   | string | No       | null    | Target tenant (cross-tenant scenarios)  |
| `subscription_id`    | string | No       | null    | Target subscription (null=first sub)    |
| `providers_required` | array  | No       | See def | Required Azure resource providers       |

#### Execution Configuration

| Field                  | Type    | Required | Default | Description                                  |
| ---------------------- | ------- | -------- | ------- | -------------------------------------------- |
| `dry_run`              | boolean | No       | false   | Preview changes without applying             |
| `strict_mode`          | boolean | No       | false   | Fail on any error vs. continue               |
| `skip_provider_check`  | boolean | No       | false   | Skip provider registration validation        |
| `skip_sentinel`        | boolean | No       | false   | Create workspace only, skip Sentinel         |
| `parallel_operations`  | integer | No       | 5       | Max concurrent diagnostic settings creation  |
| `retry_attempts`       | integer | No       | 3       | Number of retry attempts for failed ops      |
| `retry_delay_seconds`  | integer | No       | 5       | Delay between retry attempts                 |

## Configuration File Formats

### JSON Format

```json
{
  "workspace": {
    "name": "my-sentinel-workspace",
    "location": "eastus"
  }
}
```

### YAML Format

```yaml
workspace:
  name: my-sentinel-workspace
  location: eastus

sentinel:
  enable: true
  solutions:
    - SecurityInsights
    - AzureActivity

resource_filters:
  exclude_resource_groups:
    - test-rg
    - dev-rg
```

Both formats are supported. Use `--config-file` flag:

```bash
uv run atg setup-sentinel --config-file config.json
uv run atg setup-sentinel --config-file config.yaml
```

## Environment Variables

All configuration options can be set via environment variables using the `SENTINEL_` prefix:

### Workspace Configuration

```bash
export SENTINEL_WORKSPACE_NAME="my-sentinel-workspace"
export SENTINEL_LOCATION="eastus"
export SENTINEL_RESOURCE_GROUP="monitoring-rg"
export SENTINEL_RETENTION_DAYS="180"
export SENTINEL_SKU="PerGB2018"
```

### Azure Configuration

```bash
export AZURE_TENANT_ID="12345678-1234-1234-1234-123456789abc"
export AZURE_SUBSCRIPTION_ID="87654321-4321-4321-4321-210987654321"
```

### Execution Configuration

```bash
export SENTINEL_DRY_RUN="true"
export SENTINEL_STRICT_MODE="false"
export SENTINEL_SKIP_SENTINEL="false"
```

## Configuration Patterns

### Development Environment

**dev_sentinel.json:**

```json
{
  "workspace": {
    "name": "dev-sentinel",
    "location": "eastus",
    "resource_group": "dev-monitoring-rg",
    "retention_days": 30,
    "sku": "PerGB2018",
    "daily_quota_gb": 5,
    "tags": {
      "Environment": "Development"
    }
  },
  "resource_filters": {
    "include_resource_groups": ["dev-rg"]
  },
  "execution": {
    "strict_mode": false
  }
}
```

### Production Environment

**prod_sentinel.json:**

```json
{
  "workspace": {
    "name": "prod-sentinel",
    "location": "eastus2",
    "resource_group": "prod-monitoring-rg",
    "retention_days": 365,
    "sku": "CapacityReservation",
    "tags": {
      "Environment": "Production",
      "Compliance": "Required",
      "CostCenter": "IT-Security"
    }
  },
  "sentinel": {
    "enable": true,
    "solutions": [
      "SecurityInsights",
      "AzureActivity",
      "AzureSecurityCenter"
    ]
  },
  "resource_filters": {
    "exclude_resource_groups": ["dev-rg", "test-rg"],
    "exclude_tags": {
      "Monitoring": "Disabled"
    }
  },
  "execution": {
    "strict_mode": true,
    "parallel_operations": 10
  }
}
```

### Cross-Tenant Deployment

**cross_tenant_sentinel.json:**

```json
{
  "workspace": {
    "name": "central-sentinel",
    "location": "centralus",
    "resource_group": "central-monitoring-rg",
    "retention_days": 180
  },
  "azure": {
    "tenant_id": "source-tenant-id",
    "target_tenant_id": "target-tenant-id",
    "subscription_id": "target-subscription-id"
  },
  "sentinel": {
    "enable": true
  }
}
```

**Usage:**

```bash
uv run atg setup-sentinel --config-file cross_tenant_sentinel.json
```

### Selective Resource Monitoring

**selective_monitoring.json:**

```json
{
  "workspace": {
    "name": "selective-sentinel",
    "location": "eastus"
  },
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.KeyVault/vaults",
      "Microsoft.Network/networkSecurityGroups",
      "Microsoft.Sql/servers"
    ]
  }
}
```

### High-Security Configuration

**high_security_sentinel.json:**

```json
{
  "workspace": {
    "name": "high-security-sentinel",
    "location": "eastus",
    "retention_days": 730,
    "tags": {
      "Classification": "HighSecurity",
      "Compliance": "HIPAA,SOC2"
    }
  },
  "sentinel": {
    "enable": true,
    "solutions": [
      "SecurityInsights",
      "AzureActivity",
      "AzureSecurityCenter",
      "Threat Intelligence"
    ]
  },
  "diagnostic_settings": {
    "logs": {
      "enabled": true,
      "retention_days": 730,
      "categories": ["all"]
    },
    "metrics": {
      "enabled": true,
      "retention_days": 365,
      "categories": ["AllMetrics"]
    }
  },
  "execution": {
    "strict_mode": true
  }
}
```

## Configuration Validation

The tool validates configuration before execution:

### Validation Checks

- **Workspace name**: 4-63 characters, alphanumeric and hyphens
- **Location**: Valid Azure region
- **Retention days**: 30-730 days
- **SKU**: Valid pricing tier
- **Tenant ID**: Valid GUID format
- **Resource types**: Valid Azure resource type format

### Validation Errors

```bash
# Invalid retention period
ERROR: retention_days must be between 30 and 730 (got: 15)

# Invalid workspace name
ERROR: workspace name must be 4-63 characters, alphanumeric and hyphens only

# Invalid location
ERROR: location 'invalid-region' is not a valid Azure region
```

## Cross-Tenant Configuration

### Authentication Requirements

For cross-tenant deployments:

1. **Source tenant**: Read permissions to discover resources
2. **Target tenant**: Workspace creation and diagnostic settings permissions

### Configuration Example

```bash
# Set up authentication for both tenants
az login --tenant source-tenant-id
az login --tenant target-tenant-id --allow-no-subscriptions

# Use configuration file
uv run atg setup-sentinel --config-file cross_tenant_config.json
```

### Identity Mapping

For cross-tenant scenarios, you may need to map identities:

**identity_mappings.json:**

```json
{
  "users": {
    "source-user-id": "target-user-id"
  },
  "groups": {
    "source-group-id": "target-group-id"
  },
  "service_principals": {
    "source-sp-id": "target-sp-id"
  }
}
```

**Usage:**

```bash
uv run atg setup-sentinel \
  --config-file cross_tenant_config.json \
  --identity-mapping-file identity_mappings.json
```

## Security Best Practices

### Credential Management

**Don't hardcode credentials in config files:**

```json
// ❌ BAD - Credentials in config file
{
  "azure": {
    "client_secret": "my-secret-value"
  }
}
```

**Use Azure Key Vault or environment variables:**

```bash
# ✅ GOOD - Credentials from environment
export AZURE_CLIENT_ID="..."
export AZURE_CLIENT_SECRET="..."
export AZURE_TENANT_ID="..."

uv run atg setup-sentinel --config-file config.json
```

### Least Privilege Permissions

Grant only required permissions:

```json
{
  "workspace": {
    "resource_group": "dedicated-monitoring-rg"
  }
}
```

Create a custom role:

```bash
az role definition create --role-definition '{
  "Name": "Sentinel Automation",
  "Description": "Permissions for Sentinel automation",
  "Actions": [
    "Microsoft.OperationalInsights/workspaces/write",
    "Microsoft.OperationalInsights/workspaces/read",
    "Microsoft.Insights/diagnosticSettings/write",
    "Microsoft.Insights/diagnosticSettings/read",
    "Microsoft.SecurityInsights/*/write",
    "Microsoft.Resources/subscriptions/resourceGroups/read"
  ],
  "AssignableScopes": ["/subscriptions/{subscription-id}"]
}'
```

### Configuration File Permissions

Protect configuration files:

```bash
# Set restrictive permissions
chmod 600 sentinel_config.json

# Store in secure location
mv sentinel_config.json ~/.config/azure-tenant-grapher/
```

### Audit Configuration

Enable auditing for compliance:

```json
{
  "workspace": {
    "tags": {
      "ConfiguredBy": "automation",
      "ConfigDate": "2025-12-01",
      "ConfigVersion": "1.0.0"
    }
  }
}
```

## Troubleshooting Configuration

### Debug Configuration Loading

```bash
# Enable debug mode to see configuration resolution
uv run atg setup-sentinel \
  --config-file config.json \
  --debug

# Output shows:
# Loading configuration from: config.json
# Merging with environment variables
# Final configuration: {...}
```

### Validate Configuration

```bash
# Dry-run to validate without making changes
uv run atg setup-sentinel \
  --config-file config.json \
  --dry-run

# Output shows:
# Configuration validation: PASSED
# Would create workspace: my-sentinel-workspace
# Would configure 127 resources
```

### Common Configuration Errors

**Missing required field:**

```
ERROR: Missing required field 'workspace.name' in configuration
```

**Invalid JSON/YAML:**

```
ERROR: Failed to parse configuration file: Unexpected token at line 5
```

**Type mismatch:**

```
ERROR: Field 'retention_days' must be integer, got string
```

## Configuration Schema Validation

The tool includes a JSON schema for validation:

```bash
# Validate against schema
uv run atg validate-sentinel-config --config-file config.json

# Output:
# Configuration validation: PASSED
# All required fields present
# All field types correct
# All values within valid ranges
```

## Migration from Other Tools

### From Azure Portal

Export existing workspace configuration:

```bash
az monitor log-analytics workspace show \
  --resource-group monitoring-rg \
  --workspace-name existing-workspace \
  --output json > existing_config.json
```

Convert to Sentinel config format (manual step - adapt fields).

### From ARM Templates

Extract workspace configuration from ARM template and convert to JSON config format.

## Advanced Configuration

### Custom Log Categories

```json
{
  "diagnostic_settings": {
    "logs": {
      "categories": [
        "Administrative",
        "Security",
        "ServiceHealth",
        "Alert",
        "Policy"
      ]
    }
  }
}
```

### Regional Redundancy

```json
{
  "workspaces": [
    {
      "name": "sentinel-primary",
      "location": "eastus",
      "role": "primary"
    },
    {
      "name": "sentinel-secondary",
      "location": "westus",
      "role": "secondary"
    }
  ]
}
```

Note: Multi-workspace configuration requires separate runs.

## Configuration Version Control

Store configurations in version control:

```bash
# Directory structure
configs/
├── dev.json
├── staging.json
├── prod.json
└── templates/
    ├── base.json
    └── high-security.json
```

Use environment-specific configs:

```bash
# Development
uv run atg setup-sentinel --config-file configs/dev.json

# Production
uv run atg setup-sentinel --config-file configs/prod.json
```

## Support

For configuration questions:

- See [scripts/sentinel/README.md](../scripts/sentinel/README.md) for command reference
- See [SENTINEL_TROUBLESHOOTING.md](./SENTINEL_TROUBLESHOOTING.md) for error resolution
- See [SENTINEL_INTEGRATION_EXAMPLES.md](./SENTINEL_INTEGRATION_EXAMPLES.md) for usage patterns
