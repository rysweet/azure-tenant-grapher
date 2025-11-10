# Azure Resource Provider Manager

## Overview

The Provider Manager automatically detects and registers Azure resource providers required for IaC deployments. Many Azure resource providers are NotRegistered by default in new/empty tenants and must be registered before deploying resources.

## Features

- **Automatic Detection**: Scans Terraform files to detect required Azure providers
- **Status Checking**: Checks current registration status in target subscription
- **Smart Registration**: Prompts for confirmation or auto-registers with flag
- **Comprehensive Mapping**: Supports 50+ Azure resource types across all major services
- **Non-Blocking**: Gracefully handles errors without blocking IaC generation

## Usage

### CLI Integration

The provider manager is automatically invoked during `generate-iac`:

```bash
# Interactive mode (prompts before registering)
uv run atg generate-iac

# Auto-registration mode (no prompts)
uv run atg generate-iac --auto-register-providers
```

### Programmatic Usage

```python
from src.iac.provider_manager import ProviderManager
from pathlib import Path

# Initialize manager
manager = ProviderManager(subscription_id="your-subscription-id")

# Detect required providers from Terraform files
terraform_path = Path("outputs/iac-out-20250101_120000")
required_providers = manager.get_required_providers(terraform_path=terraform_path)

# Check status and register if needed
report = await manager.check_and_register_providers(
    required_providers=required_providers,
    auto=True  # or False to prompt user
)

# Display results
print(report.format_report())
```

## Resource Type Mappings

The provider manager includes mappings for:

- **Microsoft.Compute**: VMs, disks, availability sets, images
- **Microsoft.Network**: VNets, subnets, NSGs, load balancers, firewalls
- **Microsoft.Storage**: Storage accounts, containers, blobs, queues
- **Microsoft.KeyVault**: Key vaults, secrets, keys, certificates
- **Microsoft.Sql**: SQL servers and databases
- **Microsoft.Web**: App Services, Function Apps
- **Microsoft.ContainerService**: AKS clusters
- **Microsoft.Insights**: Monitoring and diagnostics
- **Microsoft.ApiManagement**: API Management services
- **Microsoft.DocumentDB**: Cosmos DB
- And many more...

## Provider Registration States

- **Registered**: Provider is registered and ready to use
- **NotRegistered**: Provider needs to be registered
- **Registering**: Registration in progress
- **Unregistered**: Provider was previously registered but is now unregistered
- **Unknown**: Status could not be determined

## Example Report

```
============================================================
AZURE RESOURCE PROVIDER CHECK REPORT
============================================================
Subscription: a1b2c3d4-e5f6-4321-abcd-ef1234567890
Required Providers: 5
Already Registered: 3
Newly Registered: 2
Failed: 0
Skipped: 0

Provider Status                          State
------------------------------------------------------------
Microsoft.Authorization                  Registered
Microsoft.Compute                        Registered
Microsoft.KeyVault                       Registered
Microsoft.Network                        Registered
Microsoft.Resources                      Registered

Newly Registered (2):
  ✓ Microsoft.KeyVault
  ✓ Microsoft.Network
============================================================
```

## Error Handling

The provider manager is designed to be non-blocking:
- If provider detection fails, it logs a warning and continues
- If registration fails, it reports the failure but doesn't block IaC generation
- If Azure credentials are missing/invalid, it gracefully skips provider checks

## Testing

Comprehensive test suite located in `tests/iac/test_provider_manager.py`:

```bash
# Run provider manager tests
uv run pytest tests/iac/test_provider_manager.py -v

# Run with coverage
uv run pytest tests/iac/test_provider_manager.py --cov=src/iac/provider_manager
```

## Implementation Details

- Uses `azure-mgmt-resource` SDK for provider operations
- Lazy-loads Azure client for efficiency
- Scans `.tf` files with regex patterns for resource types
- Supports both parsed Terraform configs and file-based detection
- Always includes core providers (Microsoft.Resources, Microsoft.Authorization)
