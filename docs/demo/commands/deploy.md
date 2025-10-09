# Deploy Command Documentation

## Overview

The `atg deploy` command deploys generated Infrastructure-as-Code (IaC) to a target Azure tenant. It supports multiple IaC formats (Terraform, Bicep, ARM templates) and can auto-detect the format from directory contents.

## Command Syntax

```bash
atg deploy [OPTIONS]
```

## Required Options

- `--iac-dir PATH`: Directory containing IaC templates to deploy
- `--target-tenant-id TEXT`: Target Azure tenant ID where resources will be created
- `--resource-group TEXT`: Target resource group name (will be created if it doesn't exist)

## Optional Options

- `--location TEXT`: Azure region for deployment (default: `eastus`)
- `--subscription-id TEXT`: Azure subscription ID (for Bicep/ARM deployments)
- `--format [terraform|bicep|arm]`: IaC format (auto-detected if not specified)
- `--dry-run`: Plan/validate only, do not perform actual deployment

## Features

### Auto-Detection

The command automatically detects the IaC format based on file extensions:
- Terraform: Looks for `*.tf` files
- Bicep: Looks for `*.bicep` files
- ARM: Looks for `*.json` files with ARM template schema

### Dry-Run Mode

Use `--dry-run` to validate the deployment without making changes:

```bash
atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --dry-run
```

This will:
- Terraform: Run `terraform plan`
- Bicep: Run `az deployment group validate`
- ARM: Run `az deployment group validate`

### Multi-Tenant Support

The command automatically switches Azure CLI context to the target tenant before deploying, making cross-tenant deployments seamless.

## Examples

### Basic Terraform Deployment

```bash
atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id 506f82b2-e2e7-40a2-b0be-ea6f8cb908f8 \
  --resource-group SimuLand-Replica
```

### Bicep Deployment with Custom Location

```bash
atg deploy \
  --iac-dir ./bicep \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --location westus2 \
  --format bicep
```

### ARM Template Deployment with Subscription

```bash
atg deploy \
  --iac-dir ./arm \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --subscription-id <SUB_ID> \
  --format arm
```

### Dry-Run Before Deploying

```bash
# First, validate
atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --dry-run

# If validation succeeds, deploy
atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg
```

## Supported IaC Formats

### Terraform

- Runs `terraform init`, `terraform plan`, and `terraform apply`
- Automatically passes tenant ID and resource group as variables
- Supports auto-approval for non-interactive deployments

### Bicep

- Validates and deploys using `az deployment group create`
- Looks for `main.bicep` or the first `*.bicep` file
- Supports parameter files (`.bicepparam`)
- Automatically creates resource group if it doesn't exist

### ARM Templates

- Validates and deploys using `az deployment group create`
- Looks for `azuredeploy.json` or the first `*.json` file
- Supports parameter files (`*.parameters.json`)
- Automatically creates resource group if it doesn't exist

## Prerequisites

### Azure CLI

Ensure you have the Azure CLI installed and authenticated:

```bash
az login --tenant <TARGET_TENANT_ID>
```

### IaC Tool Installation

Depending on your IaC format, install the appropriate tool:

- **Terraform**: [Install Terraform](https://www.terraform.io/downloads)
- **Bicep**: Included with Azure CLI 2.20.0+
- **ARM**: No additional installation needed (uses Azure CLI)

### Permissions

Ensure your Azure identity has the following permissions in the target tenant:
- `Contributor` role on the target subscription or resource group
- Permissions to create resource groups (if deploying to a new RG)

## Return Values

The command returns a dictionary with deployment information:

```python
{
    "status": "success",          # success, failed, or validated
    "deployment_id": "...",       # Azure deployment ID (if applicable)
    "resource_group": "...",      # Target resource group
    "outputs": {...}              # Deployment outputs (if any)
}
```

## Error Handling

Common errors and solutions:

### "IaC directory not found"

Ensure the `--iac-dir` path exists and contains IaC templates:

```bash
ls -la ./output/iac
```

### "Could not detect IaC format"

Explicitly specify the format:

```bash
atg deploy --iac-dir ./output/iac --format terraform ...
```

### "Authentication failed"

Re-authenticate with Azure CLI:

```bash
az login --tenant <TARGET_TENANT_ID>
az account show
```

### "Terraform not found"

Install Terraform or use a different format:

```bash
brew install terraform  # macOS
# OR
atg deploy --format bicep ...
```

## Related Commands

- `atg generate-iac`: Generate IaC from graph data
- `atg validate-deployment`: Validate deployment fidelity
- `terraform destroy`: Cleanup deployed resources (for Terraform)
- `az group delete`: Cleanup deployed resources (for Bicep/ARM)

## Demo Script

See `demos/cross_tenant_cli/02_deploy.sh` for a complete example demonstrating dry-run and actual deployment.

## Testing

The deployment command has comprehensive test coverage (93%):

```bash
uv run pytest tests/deployment/test_orchestrator.py -v
```

## Issue Reference

Implemented in Issue #278: Add Deployment Command
PR: #282
