# Deployment Module

This module provides orchestration for deploying Infrastructure-as-Code (IaC) templates to Azure tenants.

## Features

- **Multi-Format Support**: Deploy Terraform, Bicep, and ARM templates
- **Auto-Detection**: Automatically detect IaC format from directory contents
- **Dry-Run Mode**: Validate/plan deployments without applying changes
- **Multi-Tenant**: Deploy to any target Azure tenant
- **Error Handling**: Comprehensive error reporting for all deployment stages

## Architecture

```
src/deployment/
├── __init__.py          # Public API exports
├── orchestrator.py      # Main deployment orchestration logic
└── README.md           # This file
```

## Public API

### `detect_iac_format(iac_dir: Path) -> Optional[IaCFormat]`

Auto-detects the IaC format from a directory.

**Supported Formats:**
- `terraform`: Detects `.tf` files
- `bicep`: Detects `.bicep` files
- `arm`: Detects JSON files with ARM deployment schema

**Example:**
```python
from pathlib import Path
from src.deployment import detect_iac_format

format = detect_iac_format(Path("./output/iac"))
print(f"Detected format: {format}")  # "terraform"
```

### `deploy_iac(...) -> dict`

Main deployment function that orchestrates the entire deployment process.

**Parameters:**
- `iac_dir`: Directory containing IaC files
- `target_tenant_id`: Target Azure tenant ID
- `resource_group`: Target resource group name
- `location`: Azure region (default: "eastus")
- `subscription_id`: Optional subscription ID (for bicep/arm)
- `iac_format`: IaC format (auto-detected if None)
- `dry_run`: If True, only validate/plan without deploying

**Returns:**
Dictionary with:
- `status`: Deployment status ("planned", "validated", "deployed")
- `format`: IaC format used
- `output`: Command output

**Example:**
```python
from pathlib import Path
from src.deployment import deploy_iac

result = deploy_iac(
    iac_dir=Path("./output/iac"),
    target_tenant_id="your-tenant-id",
    resource_group="my-resource-group",
    location="eastus",
    dry_run=True
)

print(f"Status: {result['status']}")
print(f"Format: {result['format']}")
```

## CLI Usage

The deployment module is accessible via the `atg deploy` CLI command:

### Basic Usage

```bash
# Deploy with auto-detection
atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg

# Dry-run (plan/validate only)
atg deploy \
  --iac-dir ./output/iac \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --dry-run
```

### Format-Specific Deployment

```bash
# Deploy Terraform explicitly
atg deploy \
  --iac-dir ./terraform \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --format terraform

# Deploy Bicep with subscription
atg deploy \
  --iac-dir ./bicep \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --subscription-id <SUB_ID> \
  --format bicep

# Deploy ARM template
atg deploy \
  --iac-dir ./arm \
  --target-tenant-id <TENANT_ID> \
  --resource-group my-rg \
  --format arm
```

## Format-Specific Behavior

### Terraform

**Detection:** Looks for `.tf` files in directory

**Dry-run:**
1. Runs `terraform init`
2. Runs `terraform plan`

**Deployment:**
1. Runs `terraform init`
2. Runs `terraform apply -auto-approve`

**Requirements:**
- Terraform CLI must be installed
- Valid Terraform configuration files

### Bicep

**Detection:** Looks for `.bicep` files in directory

**Dry-run:**
1. Validates template with `az deployment group validate`

**Deployment:**
1. Deploys with `az deployment group create`

**Requirements:**
- Azure CLI must be installed
- Valid Bicep template files
- Prefers `main.bicep` if multiple files exist

### ARM

**Detection:** Looks for JSON files with ARM template schema

**Dry-run:**
1. Validates template with `az deployment group validate`

**Deployment:**
1. Deploys with `az deployment group create`

**Requirements:**
- Azure CLI must be installed
- Valid ARM template JSON files

## Authentication

The module uses Azure CLI authentication. Ensure you're authenticated before deployment:

```bash
# Login to target tenant
az login --tenant <TENANT_ID>

# Set subscription (optional, for bicep/arm)
az account set --subscription <SUBSCRIPTION_ID>
```

The `deploy_iac` function will attempt to authenticate automatically, but may use cached credentials.

## Error Handling

All deployment functions raise `RuntimeError` with detailed messages on failure:

```python
try:
    result = deploy_iac(...)
except RuntimeError as e:
    print(f"Deployment failed: {e}")
except ValueError as e:
    print(f"Invalid configuration: {e}")
```

Common errors:
- `ValueError`: Format cannot be detected or is invalid
- `RuntimeError`: CLI tool not found or command failed
- `RuntimeError`: Authentication failed

## Testing

The module includes comprehensive unit tests:

```bash
# Run all deployment tests
uv run pytest tests/deployment/ -v

# Run with coverage
uv run pytest tests/deployment/ --cov=src/deployment --cov-report=term-missing
```

Tests use mocking to avoid actual deployments.

## Demo Scripts

See `demos/cross_tenant_cli/02_deploy.sh` for a complete deployment workflow example.

## Future Enhancements

Potential improvements for future versions:

1. **State Management**: Track deployment state in database
2. **Rollback Support**: Automatic rollback on failure
3. **Parallel Deployments**: Deploy to multiple tenants simultaneously
4. **Progress Tracking**: Real-time deployment progress
5. **Pulumi Support**: Add Pulumi deployment backend
6. **CloudFormation**: Support AWS CloudFormation templates

## Related Modules

- `src/iac/`: IaC generation from Neo4j graph
- `src/commands/undeploy.py`: Teardown deployed resources
- `src/deployment_registry.py`: Track deployment metadata
