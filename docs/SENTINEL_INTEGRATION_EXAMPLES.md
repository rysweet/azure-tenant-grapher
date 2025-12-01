# Azure Sentinel Integration Examples

Real-world examples and integration patterns for Azure Sentinel and Log Analytics automation.

## Quick Start Examples

### Example 1: Basic Sentinel Setup

The simplest way to set up Sentinel with default configuration:

```bash
# Set up Sentinel with defaults
uv run atg setup-sentinel --tenant-id 12345678-1234-1234-1234-123456789abc

# Output:
# ✓ Validating prerequisites...
# ✓ Creating Log Analytics workspace: sentinel-workspace
# ✓ Configuring diagnostic settings for 127 resources...
# ✓ Enabling Sentinel solution...
# ✓ Deployment complete!
#
# Workspace: sentinel-workspace
# Resource Group: sentinel-rg
# Location: eastus
# Resources monitored: 127
```

**What it does:**

- Creates workspace named "sentinel-workspace" in eastus
- Configures diagnostic settings for all discovered resources
- Enables Sentinel with SecurityInsights solution
- Uses 90-day retention period

---

### Example 2: Custom Workspace Configuration

Set up Sentinel with custom workspace settings:

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --workspace-name prod-security-hub \
  --location eastus2 \
  --resource-group security-monitoring-rg \
  --retention-days 180 \
  --sku PerGB2018
```

**What it does:**

- Creates workspace in eastus2 region
- Uses custom resource group for organization
- Sets 180-day retention for compliance
- Uses pay-per-GB pricing tier

---

### Example 3: Dry Run Preview

Preview changes before applying:

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --dry-run \
  --debug

# Output:
# DRY RUN MODE - No changes will be applied
#
# Would create:
# - Workspace: sentinel-workspace in eastus
# - Resource Group: sentinel-rg
#
# Would configure diagnostic settings for:
# - 45 Virtual Machines
# - 23 Network Security Groups
# - 15 Key Vaults
# - 12 Storage Accounts
# - 32 Other resources
#
# Total resources: 127
# Estimated monthly cost: $450-600 (based on 10GB/day ingestion)
```

**Use cases:**

- Validate configuration before production deployment
- Estimate costs
- Review what resources would be affected
- Debug configuration issues

---

## Integration with Existing Workflows

### Example 4: Integrated with Tenant Scanning

Scan tenant and set up monitoring in one workflow:

```bash
# Step 1: Scan tenant to discover resources
uv run atg scan --tenant-id 12345678-1234-1234-1234-123456789abc

# Output:
# Scanning tenant...
# Discovered 127 resources
# Stored in Neo4j graph database

# Step 2: Set up Sentinel using discovered resources
uv run atg setup-sentinel --tenant-id 12345678-1234-1234-1234-123456789abc

# Sentinel setup will use Neo4j graph for resource discovery
```

**Benefits:**

- Faster resource discovery (uses cached graph data)
- Accurate resource topology
- Can filter resources based on graph relationships

---

### Example 5: Integrated with IaC Generation

Generate Terraform and set up monitoring together:

```bash
# Generate Terraform IaC with Sentinel setup
uv run atg generate-iac \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --format terraform \
  --setup-sentinel \
  --workspace-name infra-sentinel \
  --output-dir ./terraform-output

# Output:
# Generating Terraform configuration...
# ✓ Generated main.tf
# ✓ Generated variables.tf
# ✓ Generated outputs.tf
#
# Setting up Sentinel monitoring...
# ✓ Created workspace: infra-sentinel
# ✓ Configured diagnostic settings for 127 resources
# ✓ Enabled Sentinel
#
# Terraform files: ./terraform-output
# Sentinel workspace: infra-sentinel
```

**What it does:**

1. Generates complete Terraform IaC for your infrastructure
2. Creates Log Analytics workspace
3. Configures diagnostic settings for all resources
4. Enables Sentinel monitoring

**Use case:** Infrastructure-as-Code deployments with built-in security monitoring.

---

### Example 6: Integrated with Tenant Creation

Create new tenant with monitoring enabled:

```bash
# Create tenant specification
cat > tenant_spec.md <<EOF
# New Production Tenant

## Virtual Machines
- prod-web-01: Standard_D2s_v3, eastus
- prod-db-01: Standard_D4s_v3, eastus

## Network
- VNet: prod-vnet (10.0.0.0/16)
- Subnet: prod-subnet (10.0.1.0/24)

## Security
- NSG: prod-nsg
- Key Vault: prod-keyvault
EOF

# Create tenant with Sentinel enabled
uv run atg create-tenant \
  --spec tenant_spec.md \
  --setup-sentinel \
  --workspace-name new-tenant-sentinel

# Output:
# Creating tenant from specification...
# ✓ Created resource group
# ✓ Created VNet and subnet
# ✓ Created VMs: prod-web-01, prod-db-01
# ✓ Created NSG and Key Vault
#
# Setting up Sentinel monitoring...
# ✓ Created workspace: new-tenant-sentinel
# ✓ Configured monitoring for all resources
#
# Tenant created successfully!
```

**Use case:** New environment provisioning with security monitoring from day one.

---

## Configuration-Based Examples

### Example 7: Using Configuration File

Create reusable configuration for consistent deployments:

**prod_sentinel.json:**

```json
{
  "workspace": {
    "name": "prod-sentinel-hub",
    "location": "eastus2",
    "resource_group": "prod-monitoring-rg",
    "retention_days": 365,
    "sku": "PerGB2018",
    "tags": {
      "Environment": "Production",
      "CostCenter": "IT-Security",
      "Compliance": "Required"
    }
  },
  "sentinel": {
    "enable": true,
    "solutions": ["SecurityInsights", "AzureActivity"]
  },
  "diagnostic_settings": {
    "logs": {
      "retention_days": 365
    },
    "metrics": {
      "retention_days": 90
    }
  }
}
```

**Deploy:**

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --config-file prod_sentinel.json

# Configuration is repeatable and version-controlled
```

**Benefits:**

- Consistent configuration across environments
- Version control for security settings
- Easy to review and audit
- Repeatable deployments

---

### Example 8: Environment-Specific Configurations

Maintain separate configs for dev, staging, and production:

**Directory structure:**

```
configs/
├── dev_sentinel.json
├── staging_sentinel.json
└── prod_sentinel.json
```

**dev_sentinel.json:**

```json
{
  "workspace": {
    "name": "dev-sentinel",
    "retention_days": 30,
    "daily_quota_gb": 5
  },
  "resource_filters": {
    "include_resource_groups": ["dev-rg"]
  }
}
```

**prod_sentinel.json:**

```json
{
  "workspace": {
    "name": "prod-sentinel",
    "retention_days": 365,
    "sku": "CapacityReservation"
  },
  "execution": {
    "strict_mode": true
  }
}
```

**Deploy to each environment:**

```bash
# Development
uv run atg setup-sentinel \
  --tenant-id <DEV_TENANT_ID> \
  --config-file configs/dev_sentinel.json

# Staging
uv run atg setup-sentinel \
  --tenant-id <STAGING_TENANT_ID> \
  --config-file configs/staging_sentinel.json

# Production
uv run atg setup-sentinel \
  --tenant-id <PROD_TENANT_ID> \
  --config-file configs/prod_sentinel.json
```

---

## Cross-Tenant Examples

### Example 9: Cross-Tenant Monitoring

Monitor resources from one tenant in another tenant's workspace:

```bash
# Set up cross-tenant monitoring
uv run atg setup-sentinel \
  --tenant-id source-tenant-123 \
  --target-tenant-id monitoring-tenant-456 \
  --subscription-id monitoring-subscription-789 \
  --workspace-name central-sentinel-hub

# What happens:
# 1. Discovers resources in source-tenant-123
# 2. Creates workspace in monitoring-tenant-456
# 3. Configures diagnostic settings to stream to central workspace
```

**Use case:** Central security operations center (SOC) monitoring multiple tenants.

**Configuration file:**

```json
{
  "workspace": {
    "name": "central-soc-sentinel",
    "location": "centralus",
    "resource_group": "central-monitoring-rg"
  },
  "azure": {
    "tenant_id": "source-tenant-123",
    "target_tenant_id": "monitoring-tenant-456",
    "subscription_id": "monitoring-subscription-789"
  }
}
```

---

### Example 10: Multi-Tenant Aggregation

Monitor multiple source tenants in one central workspace:

```bash
# Monitor Tenant A
uv run atg setup-sentinel \
  --tenant-id tenant-a-123 \
  --target-tenant-id central-tenant-999 \
  --workspace-name multi-tenant-sentinel

# Monitor Tenant B (same workspace)
uv run atg setup-sentinel \
  --tenant-id tenant-b-456 \
  --target-tenant-id central-tenant-999 \
  --workspace-name multi-tenant-sentinel

# Monitor Tenant C (same workspace)
uv run atg setup-sentinel \
  --tenant-id tenant-c-789 \
  --target-tenant-id central-tenant-999 \
  --workspace-name multi-tenant-sentinel

# Result: All three tenants stream logs to one central workspace
```

**Benefits:**

- Single pane of glass for security monitoring
- Reduced costs (one workspace instead of three)
- Centralized threat detection
- Cross-tenant correlation

---

## Selective Monitoring Examples

### Example 11: Monitor Specific Resource Types

Monitor only critical resource types:

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --resource-types "Microsoft.Compute/virtualMachines,Microsoft.KeyVault/vaults,Microsoft.Network/networkSecurityGroups"

# Only configures monitoring for VMs, Key Vaults, and NSGs
```

**Configuration file version:**

```json
{
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.KeyVault/vaults",
      "Microsoft.Network/networkSecurityGroups"
    ]
  }
}
```

**Use case:** Cost optimization by monitoring only security-critical resources.

---

### Example 12: Monitor Specific Resource Groups

Monitor only production resource groups:

```json
{
  "resource_filters": {
    "include_resource_groups": [
      "prod-web-rg",
      "prod-db-rg",
      "prod-network-rg"
    ]
  }
}
```

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --config-file selective_monitoring.json
```

**Use case:** Separate monitoring for production vs. development environments.

---

### Example 13: Exclude Development Resources

Monitor everything except development:

```json
{
  "resource_filters": {
    "exclude_resource_groups": ["dev-rg", "test-rg", "sandbox-rg"],
    "exclude_tags": {
      "Environment": "Development"
    }
  }
}
```

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --config-file exclude_dev.json
```

**Benefits:**

- Reduced log volume and costs
- Focus on production monitoring
- Cleaner security alerts

---

## Advanced Integration Examples

### Example 14: CI/CD Pipeline Integration

Integrate Sentinel setup into CI/CD pipeline:

**GitHub Actions workflow:**

```yaml
name: Deploy Infrastructure with Monitoring

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Azure Login
        uses: azure/login@v1
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.11"

      - name: Install Azure Tenant Grapher
        run: |
          pip install uv
          uv pip install azure-tenant-grapher

      - name: Deploy Infrastructure
        run: |
          uv run atg create-tenant \
            --spec infrastructure.md \
            --tenant-id ${{ secrets.AZURE_TENANT_ID }}

      - name: Set Up Security Monitoring
        run: |
          uv run atg setup-sentinel \
            --tenant-id ${{ secrets.AZURE_TENANT_ID }} \
            --config-file .github/configs/sentinel.json

      - name: Verify Deployment
        run: |
          uv run atg verify-sentinel \
            --workspace-name prod-sentinel \
            --resource-group monitoring-rg
```

**Use case:** Automated security monitoring setup as part of infrastructure deployment.

---

### Example 15: Script Generation for Restricted Environments

Generate bash scripts for manual execution in restricted environments:

```bash
# Generate scripts
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --generate-script \
  --output-dir ./sentinel-scripts \
  --config-file high_security_config.json

# Output:
# Generated scripts in: ./sentinel-scripts
# - 1_validate_prerequisites.sh
# - 2_create_workspace.sh
# - 3_configure_diagnostics.sh
# - 4_enable_sentinel.sh
# - 5_verify_deployment.sh
# - common.sh
# - config.env

# Review scripts
cd ./sentinel-scripts
cat config.env

# Execute manually
bash 1_validate_prerequisites.sh
bash 2_create_workspace.sh
bash 3_configure_diagnostics.sh
bash 4_enable_sentinel.sh
bash 5_verify_deployment.sh
```

**Use case:**

- Environments with limited permissions requiring approval
- Air-gapped networks needing script transfer
- Audit trails requiring manual execution records

---

### Example 16: Regional Redundancy

Set up Sentinel in multiple regions for redundancy:

```bash
# Primary region (East US)
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --workspace-name sentinel-primary \
  --location eastus \
  --resource-group monitoring-eastus-rg

# Secondary region (West US)
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --workspace-name sentinel-secondary \
  --location westus \
  --resource-group monitoring-westus-rg

# Configure resources to send logs to both workspaces
# (requires manual diagnostic settings configuration)
```

**Use case:** High-availability security monitoring with geographic redundancy.

---

## Compliance and Governance Examples

### Example 17: HIPAA Compliance Configuration

Configure Sentinel for HIPAA compliance requirements:

**hipaa_sentinel.json:**

```json
{
  "workspace": {
    "name": "hipaa-sentinel",
    "location": "eastus2",
    "retention_days": 2555,
    "tags": {
      "Compliance": "HIPAA",
      "DataClassification": "PHI",
      "RetentionPolicy": "7-years"
    }
  },
  "diagnostic_settings": {
    "logs": {
      "enabled": true,
      "retention_days": 2555,
      "categories": ["all"]
    },
    "metrics": {
      "enabled": true,
      "retention_days": 2555
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
  "execution": {
    "strict_mode": true
  }
}
```

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --config-file hipaa_sentinel.json
```

**Features:**

- 7-year retention (2555 days) for HIPAA compliance
- All log categories enabled
- Strict mode (fails on any error)
- Compliance tags for auditing

---

### Example 18: PCI DSS Configuration

Configure for PCI DSS compliance:

**pci_sentinel.json:**

```json
{
  "workspace": {
    "name": "pci-sentinel",
    "retention_days": 365,
    "tags": {
      "Compliance": "PCI-DSS",
      "DataClassification": "CardholderData"
    }
  },
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.Network/networkSecurityGroups",
      "Microsoft.Network/applicationGateways",
      "Microsoft.Sql/servers",
      "Microsoft.Storage/storageAccounts"
    ]
  },
  "diagnostic_settings": {
    "logs": {
      "retention_days": 365,
      "categories": ["all"]
    }
  }
}
```

**Use case:** Payment card industry compliance monitoring.

---

### Example 19: Custom Log Categories

Configure specific log categories for fine-grained control:

```json
{
  "diagnostic_settings": {
    "logs": {
      "enabled": true,
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

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --config-file custom_logs.json
```

**Use case:** Reduce log volume by collecting only security-relevant categories.

---

## Cost Optimization Examples

### Example 20: Cost-Optimized Configuration

Minimize costs while maintaining security visibility:

**cost_optimized.json:**

```json
{
  "workspace": {
    "name": "cost-opt-sentinel",
    "retention_days": 30,
    "daily_quota_gb": 10,
    "sku": "PerGB2018"
  },
  "resource_filters": {
    "include_types": [
      "Microsoft.Compute/virtualMachines",
      "Microsoft.KeyVault/vaults",
      "Microsoft.Network/networkSecurityGroups"
    ]
  },
  "diagnostic_settings": {
    "logs": {
      "retention_days": 30,
      "categories": ["Security", "Alert"]
    },
    "metrics": {
      "enabled": false
    }
  }
}
```

**Cost-saving measures:**

- 30-day retention (minimum)
- 10 GB daily cap
- Security-critical resources only
- Security and alert logs only
- Metrics disabled

---

### Example 21: Capacity Reservation for High Volume

Use capacity reservation for predictable high-volume logging:

```json
{
  "workspace": {
    "name": "high-volume-sentinel",
    "sku": "CapacityReservation",
    "daily_quota_gb": 100,
    "location": "eastus2"
  }
}
```

```bash
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --config-file high_volume.json
```

**Benefits:**

- Fixed predictable costs
- Better for large-scale deployments
- Cost savings at high volumes (>100 GB/day)

---

## Testing and Validation Examples

### Example 22: Pre-Production Validation

Validate Sentinel setup before production deployment:

```bash
# Step 1: Dry run in production config
uv run atg setup-sentinel \
  --tenant-id <PROD_TENANT_ID> \
  --config-file prod_sentinel.json \
  --dry-run

# Step 2: Deploy to test environment first
uv run atg setup-sentinel \
  --tenant-id <TEST_TENANT_ID> \
  --config-file test_sentinel.json

# Step 3: Verify test deployment
bash scripts/sentinel/5_verify_deployment.sh

# Step 4: If validation passes, deploy to production
uv run atg setup-sentinel \
  --tenant-id <PROD_TENANT_ID> \
  --config-file prod_sentinel.json
```

---

## Migration Examples

### Example 23: Migrate from Existing Workspace

Reuse and enhance existing Log Analytics workspace:

```bash
# Connect to existing workspace
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --workspace-name existing-workspace \
  --resource-group existing-rg \
  --skip-sentinel

# Tool will:
# - Detect existing workspace
# - Update configuration if needed
# - Add diagnostic settings for new resources
# - Skip Sentinel enablement (already enabled)
```

---

### Example 24: Migrate from Azure Security Center

Migrate from standalone Security Center to Sentinel:

```bash
# Set up Sentinel while preserving Security Center
uv run atg setup-sentinel \
  --tenant-id 12345678-1234-1234-1234-123456789abc \
  --workspace-name security-center-migration

# Sentinel will integrate with existing Security Center configuration
```

---

## Quick Reference

### Common Command Patterns

```bash
# Basic setup
uv run atg setup-sentinel --tenant-id <ID>

# With configuration file
uv run atg setup-sentinel --tenant-id <ID> --config-file config.json

# Dry run preview
uv run atg setup-sentinel --tenant-id <ID> --dry-run

# Cross-tenant
uv run atg setup-sentinel --tenant-id <SRC> --target-tenant-id <TGT>

# Generate scripts
uv run atg setup-sentinel --tenant-id <ID> --generate-script

# Integrated with IaC
uv run atg generate-iac --tenant-id <ID> --setup-sentinel
```

### Configuration Templates

See example configuration files in the repository:

- `configs/templates/dev_sentinel.json`
- `configs/templates/prod_sentinel.json`
- `configs/templates/compliance_hipaa.json`
- `configs/templates/compliance_pci.json`
- `configs/templates/cost_optimized.json`

---

## Additional Resources

- **Main Documentation**: [scripts/sentinel/README.md](../scripts/sentinel/README.md)
- **Configuration Reference**: [SENTINEL_CONFIGURATION.md](./SENTINEL_CONFIGURATION.md)
- **Troubleshooting**: [SENTINEL_TROUBLESHOOTING.md](./SENTINEL_TROUBLESHOOTING.md)
- **GitHub Repository**: Report issues and contribute examples
