# Dual Tenant Configuration Module

## Overview

This module provides support for dual-tenant operations in Azure Tenant Grapher, enabling automatic credential switching based on operation context. It addresses Issue #387 by implementing the architecture specified in `Specs/ServicePrincipalSwitching.md`.

## Purpose

Enable automatic switching between source and target tenant credentials:
- **Source Tenant**: Used for discovery/read operations (requires Reader role)
- **Target Tenant**: Used for deployment/write operations (requires Contributor role)

## Modules

### 1. `dual_tenant_config.py`

Core configuration dataclasses for dual-tenant support.

**Classes:**
- `TenantCredentials`: Stores credentials for a single tenant
- `DualTenantConfig`: Configuration for single or dual-tenant operations
- `create_dual_tenant_config_from_env()`: Factory function to load config from environment

**Example Usage:**
```python
from src.dual_tenant_config import create_dual_tenant_config_from_env

# Load configuration from environment variables
config = create_dual_tenant_config_from_env()

if config.is_dual_tenant_mode():
    print(f"Operating in dual-tenant mode")
    print(f"Source: {config.source_tenant.tenant_id}")
    print(f"Target: {config.target_tenant.tenant_id}")
else:
    print(f"Operating in single-tenant mode")
```

### 2. `credential_provider.py`

Credential selection based on operation type.

**Classes:**
- `OperationType`: Enum for operation types (DISCOVERY, DEPLOYMENT, VALIDATION)
- `TenantCredentialProvider`: Provides credentials based on operation context

**Example Usage:**
```python
from src.credential_provider import TenantCredentialProvider, OperationType
from src.dual_tenant_config import create_dual_tenant_config_from_env

# Create provider
config = create_dual_tenant_config_from_env()
provider = TenantCredentialProvider(config)

# Get credentials for discovery operation
credential, tenant_id = provider.get_credential(OperationType.DISCOVERY)

# Get credentials for deployment operation
credential, tenant_id = provider.get_credential(OperationType.DEPLOYMENT)
```

### 3. `config_manager.py` Extensions

Added backward-compatible helper functions:
- `get_source_credentials()`: Get source tenant credentials with fallback
- `get_target_credentials()`: Get target tenant credentials with fallback

**Example Usage:**
```python
from src.config_manager import get_source_credentials, get_target_credentials

# These functions automatically fall back to single-tenant env vars
source = get_source_credentials()
target = get_target_credentials()

print(f"Source tenant: {source['tenant_id']}")
print(f"Target tenant: {target['tenant_id']}")
```

## Configuration

### Environment Variables

#### Dual-Tenant Mode (New)

```bash
# Enable dual-tenant mode
AZTG_DUAL_TENANT_MODE=true
AZTG_AUTO_SWITCH=true  # Optional, default: true

# Source tenant (discovery/read operations)
AZURE_SOURCE_TENANT_ID=<source-tenant-id>
AZURE_SOURCE_TENANT_CLIENT_ID=<source-client-id>
AZURE_SOURCE_TENANT_CLIENT_SECRET=<source-secret>
AZURE_SOURCE_TENANT_SUBSCRIPTION_ID=<source-subscription-id>

# Target tenant (deployment/write operations)
AZURE_TARGET_TENANT_ID=<target-tenant-id>
AZURE_TARGET_TENANT_CLIENT_ID=<target-client-id>
AZURE_TARGET_TENANT_CLIENT_SECRET=<target-secret>
AZURE_TARGET_TENANT_SUBSCRIPTION_ID=<target-subscription-id>
```

#### Single-Tenant Mode (Backward Compatible)

```bash
# Standard single-tenant configuration (unchanged)
AZURE_TENANT_ID=<tenant-id>
AZURE_CLIENT_ID=<client-id>
AZURE_CLIENT_SECRET=<secret>
AZURE_SUBSCRIPTION_ID=<subscription-id>
```

## Operation Types

### DISCOVERY
- Read operations on Azure resources
- Used during `atg scan` command
- Requires Reader role on source tenant

### DEPLOYMENT
- Write operations (creating/updating resources)
- Used during `atg deploy-iac` command
- Requires Contributor role on target tenant

### VALIDATION
- Validation operations (read-only)
- Uses source tenant credentials
- Requires Reader role

## Backward Compatibility

The implementation maintains 100% backward compatibility:

1. **Existing single-tenant setups work unchanged**
   - If only `AZURE_TENANT_ID` is set, operates in single-tenant mode
   - No code changes required for existing deployments

2. **Graceful fallback**
   - If source/target vars not set, falls back to single-tenant vars
   - Partial configuration supported (mix of source/target and single vars)

3. **No breaking changes**
   - All existing APIs remain unchanged
   - New functionality is opt-in via environment variables

## Testing

Comprehensive test suites cover:
- Single-tenant configuration (backward compatibility)
- Dual-tenant configuration
- Credential selection logic
- Caching behavior
- Error handling
- Logging

**Run tests:**
```bash
# Run all dual-tenant tests
uv run pytest tests/test_dual_tenant_config.py -v
uv run pytest tests/test_credential_provider.py -v
uv run pytest tests/test_config_manager_credentials.py -v
```

## Security Considerations

1. **Credential Isolation**: Source and target credentials never mixed
2. **Least Privilege**: Source uses Reader, target uses Contributor
3. **Audit Trail**: All credential switches are logged
4. **Secret Protection**: Credentials never logged or exposed

## Implementation Status

- ✅ Core configuration module (`dual_tenant_config.py`)
- ✅ Credential provider (`credential_provider.py`)
- ✅ Config manager extensions (`config_manager.py`)
- ✅ Comprehensive test suite
- ✅ Environment variable documentation
- ⏳ Integration with discovery service (future)
- ⏳ Integration with deployment orchestrator (future)
- ⏳ CLI integration (future)

## Future Integration Points

The architecture specification (`Specs/ServicePrincipalSwitching.md`) defines integration points for:

1. **Discovery Service** (`src/services/azure_discovery_service.py`)
   - Accept `TenantCredentialProvider` in constructor
   - Use `OperationType.DISCOVERY` for operations

2. **Deployment Orchestrator** (`src/deployment/orchestrator.py`)
   - Accept `TenantCredentialProvider` in `deploy_iac()`
   - Use `OperationType.DEPLOYMENT` for operations

3. **CLI Commands** (`src/cli_commands.py`)
   - Load dual-tenant config at startup
   - Pass credential provider to services

## References

- Architecture Specification: `Specs/ServicePrincipalSwitching.md`
- Issue: #387
- Branch: `feat/issue-387-auto-sp-switching`
