# Tenant Reset API Reference

Technical reference for Azure Tenant Grapher's Tenant Reset service architecture, APIs, and internal implementation.

## Architecture Overview

The Tenant Reset feature consists of three core components:

1. **TenantResetService** - Calculates scope, preserves ATG SP, orders deletions
2. **ResetConfirmation** - Handles dry-run, confirmation flow, audit logging
3. **CLI Commands** - User-facing commands (`atg reset <scope>`)

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Commands                            │
│  (atg reset tenant|subscription|resource-group|resource)        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ResetConfirmation Service                     │
│  - Dry-run mode                                                 │
│  - Type "DELETE" confirmation                                   │
│  - Audit logging                                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   TenantResetService                            │
│  - Scope calculation (tenant/sub/rg/resource)                   │
│  - ATG Service Principal preservation                           │
│  - Dependency-aware deletion ordering                           │
│  - Concurrent deletion execution                                │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Azure Resource Manager                       │
│  (Azure SDK - resource deletion via REST APIs)                  │
└─────────────────────────────────────────────────────────────────┘
```

## TenantResetService

Core service responsible for scope calculation, ATG SP preservation, and deletion execution.

### Class Definition

```python
from typing import List, Dict, Optional
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient

class TenantResetService:
    """
    Service for safe, controlled Azure resource deletion with automatic
    ATG Service Principal preservation.
    """

    def __init__(
        self,
        credential: DefaultAzureCredential,
        tenant_id: str,
        concurrency: int = 5
    ):
        """
        Initialize TenantResetService.

        Args:
            credential: Azure credential for authentication
            tenant_id: Azure tenant ID
            concurrency: Number of concurrent deletion threads
        """
```

### Methods

#### calculate_scope_tenant

Calculate all resources to delete for tenant scope.

```python
def calculate_scope_tenant(
    self,
    tenant_id: str
) -> Dict[str, List[str]]:
    """
    Calculate deletion scope for entire tenant.

    Args:
        tenant_id: Azure tenant ID

    Returns:
        Dictionary mapping resource types to resource IDs:
        {
            "to_delete": [<resource_ids>],
            "to_preserve": [<atg_sp_id>, <atg_sp_role_assignments>]
        }

    Example:
        >>> service = TenantResetService(credential, tenant_id)
        >>> scope = service.calculate_scope_tenant(tenant_id)
        >>> print(f"Will delete {len(scope['to_delete'])} resources")
        Will delete 845 resources
    """
```

#### calculate_scope_subscription

Calculate all resources to delete for subscription scope.

```python
def calculate_scope_subscription(
    self,
    subscription_ids: List[str]
) -> Dict[str, List[str]]:
    """
    Calculate deletion scope for specific subscriptions.

    Args:
        subscription_ids: List of subscription IDs

    Returns:
        Dictionary mapping resource types to resource IDs:
        {
            "to_delete": [<resource_ids>],
            "to_preserve": [<atg_sp_resources>]
        }

    Example:
        >>> scope = service.calculate_scope_subscription([
        ...     "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        ... ])
        >>> print(scope["to_delete"])
        ['/subscriptions/aaaa.../virtualMachines/vm-1', ...]
    """
```

#### calculate_scope_resource_group

Calculate all resources to delete for resource group scope.

```python
def calculate_scope_resource_group(
    self,
    resource_group_names: List[str],
    subscription_id: str
) -> Dict[str, List[str]]:
    """
    Calculate deletion scope for specific resource groups.

    Args:
        resource_group_names: List of resource group names
        subscription_id: Subscription containing the resource groups

    Returns:
        Dictionary mapping resource types to resource IDs:
        {
            "to_delete": [<resource_ids>],
            "to_preserve": [<atg_sp_resources_if_in_rg>]
        }

    Example:
        >>> scope = service.calculate_scope_resource_group(
        ...     ["test-rg-1", "test-rg-2"],
        ...     "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        ... )
    """
```

#### calculate_scope_resource

Calculate deletion scope for single resource.

```python
def calculate_scope_resource(
    self,
    resource_id: str
) -> Dict[str, List[str]]:
    """
    Calculate deletion scope for single resource.

    Args:
        resource_id: Full Azure resource ID

    Returns:
        Dictionary with resource to delete or preserve:
        {
            "to_delete": [<resource_id>] or [],
            "to_preserve": [<resource_id>] if ATG SP
        }

    Example:
        >>> scope = service.calculate_scope_resource(
        ...     "/subscriptions/aaa.../virtualMachines/vm-1"
        ... )
        >>> if scope["to_delete"]:
        ...     print("Safe to delete")
        Safe to delete
    """
```

#### identify_atg_service_principal

Identify the ATG Service Principal from current authentication context.

```python
def identify_atg_service_principal(self) -> str:
    """
    Identify ATG Service Principal object ID from authentication context.

    Returns:
        ATG Service Principal object ID

    Raises:
        ValueError: If ATG SP cannot be identified

    Example:
        >>> atg_sp_id = service.identify_atg_service_principal()
        >>> print(f"ATG SP: {atg_sp_id}")
        ATG SP: 87654321-4321-4321-4321-210987654321
    """
```

#### order_by_dependencies

Order resources for deletion by dependencies (reverse dependency order).

```python
def order_by_dependencies(
    self,
    resource_ids: List[str]
) -> List[List[str]]:
    """
    Order resources by dependencies for safe deletion.

    Args:
        resource_ids: List of resource IDs to order

    Returns:
        List of deletion waves (lists of resource IDs):
        [
            [<vm_ids>],              # Wave 1: VMs
            [<nic_ids>],             # Wave 2: NICs
            [<vnet_ids>],            # Wave 3: VNets
            ...
        ]

    Example:
        >>> waves = service.order_by_dependencies(resource_ids)
        >>> for i, wave in enumerate(waves, 1):
        ...     print(f"Wave {i}: {len(wave)} resources")
        Wave 1: 45 resources
        Wave 2: 45 resources
        Wave 3: 12 resources
    """
```

#### delete_resources

Execute resource deletion with concurrency.

```python
async def delete_resources(
    self,
    deletion_waves: List[List[str]],
    concurrency: int = 5
) -> Dict[str, List[str]]:
    """
    Delete resources in waves with concurrency control.

    Args:
        deletion_waves: List of deletion waves from order_by_dependencies()
        concurrency: Number of concurrent deletion threads

    Returns:
        Dictionary with deletion results:
        {
            "deleted": [<successfully_deleted_ids>],
            "failed": [<failed_deletion_ids>],
            "errors": {<resource_id>: <error_message>}
        }

    Example:
        >>> results = await service.delete_resources(waves, concurrency=10)
        >>> print(f"Deleted: {len(results['deleted'])}")
        >>> print(f"Failed: {len(results['failed'])}")
        Deleted: 843
        Failed: 2
    """
```

## ResetConfirmation

Handles dry-run mode, user confirmation, and audit logging.

### Class Definition

```python
from typing import Optional, Dict, List
from enum import Enum

class ResetScope(Enum):
    """Enumeration of reset operation scopes."""
    TENANT = "tenant"
    SUBSCRIPTION = "subscription"
    RESOURCE_GROUP = "resource-group"
    RESOURCE = "resource"

class ResetConfirmation:
    """
    Service for handling reset confirmation flow, dry-run, and audit logging.
    """

    def __init__(
        self,
        scope: ResetScope,
        dry_run: bool = False,
        skip_confirmation: bool = False,
        log_dir: str = "~/.atg/logs/tenant-reset"
    ):
        """
        Initialize ResetConfirmation.

        Args:
            scope: Reset operation scope
            dry_run: If True, only preview without deleting
            skip_confirmation: If True, skip "DELETE" confirmation
            log_dir: Directory for audit logs
        """
```

### Methods

#### display_dry_run

Display dry-run output showing what would be deleted.

```python
def display_dry_run(
    self,
    scope_data: Dict[str, List[str]]
) -> None:
    """
    Display dry-run output.

    Args:
        scope_data: Scope calculation from TenantResetService:
            {
                "to_delete": [<resource_ids>],
                "to_preserve": [<atg_sp_resources>]
            }

    Example:
        >>> confirmation = ResetConfirmation(
        ...     scope=ResetScope.TENANT,
        ...     dry_run=True
        ... )
        >>> confirmation.display_dry_run(scope_data)
        === TENANT RESET DRY-RUN ===
        Resources to delete: 845
        Resources to preserve: 2
        [... detailed output ...]
    """
```

#### confirm_deletion

Prompt user to type "DELETE" to confirm operation.

```python
def confirm_deletion(
    self,
    scope_data: Dict[str, List[str]]
) -> bool:
    """
    Prompt user to type "DELETE" to confirm.

    Args:
        scope_data: Scope calculation from TenantResetService

    Returns:
        True if user confirmed, False if cancelled

    Raises:
        KeyboardInterrupt: If user presses Ctrl+C

    Example:
        >>> confirmed = confirmation.confirm_deletion(scope_data)
        About to delete 845 resources across 3 subscriptions.
        This operation cannot be undone.
        Type 'DELETE' to confirm: DELETE
        >>> print(confirmed)
        True
    """
```

#### log_operation

Log reset operation to audit log file.

```python
def log_operation(
    self,
    scope_data: Dict[str, List[str]],
    deletion_results: Optional[Dict[str, List[str]]] = None,
    start_time: float = None,
    end_time: float = None
) -> None:
    """
    Log reset operation to audit log.

    Args:
        scope_data: Scope calculation from TenantResetService
        deletion_results: Results from delete_resources() (None for dry-run)
        start_time: Operation start timestamp
        end_time: Operation end timestamp

    Example:
        >>> import time
        >>> start = time.time()
        >>> # ... perform deletion ...
        >>> end = time.time()
        >>> confirmation.log_operation(
        ...     scope_data,
        ...     deletion_results,
        ...     start,
        ...     end
        ... )
    """
```

## CLI Commands

User-facing commands implemented using Click framework.

### Command: atg reset tenant

```python
@click.command(name="tenant")
@click.option("--tenant-id", required=True, help="Azure tenant ID")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--skip-confirmation", is_flag=True, help="Skip DELETE confirmation")
@click.option("--concurrency", default=5, help="Concurrent deletion threads")
@click.option("--log-level", default="INFO", help="Logging level")
def reset_tenant(
    tenant_id: str,
    dry_run: bool,
    skip_confirmation: bool,
    concurrency: int,
    log_level: str
):
    """
    Reset entire tenant (delete all resources).

    Automatically preserves ATG Service Principal.
    """
```

### Command: atg reset subscription

```python
@click.command(name="subscription")
@click.option("--subscription-ids", multiple=True, required=True,
              help="Subscription IDs to reset")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--skip-confirmation", is_flag=True, help="Skip DELETE confirmation")
@click.option("--concurrency", default=5, help="Concurrent deletion threads")
@click.option("--log-level", default="INFO", help="Logging level")
def reset_subscription(
    subscription_ids: List[str],
    dry_run: bool,
    skip_confirmation: bool,
    concurrency: int,
    log_level: str
):
    """
    Reset specific subscriptions (delete all resources in subscriptions).
    """
```

### Command: atg reset resource-group

```python
@click.command(name="resource-group")
@click.option("--resource-group-names", multiple=True, required=True,
              help="Resource group names to reset")
@click.option("--subscription-id", required=True,
              help="Subscription containing resource groups")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--skip-confirmation", is_flag=True, help="Skip DELETE confirmation")
@click.option("--concurrency", default=5, help="Concurrent deletion threads")
@click.option("--log-level", default="INFO", help="Logging level")
def reset_resource_group(
    resource_group_names: List[str],
    subscription_id: str,
    dry_run: bool,
    skip_confirmation: bool,
    concurrency: int,
    log_level: str
):
    """
    Reset specific resource groups (delete all resources in groups).
    """
```

### Command: atg reset resource

```python
@click.command(name="resource")
@click.option("--resource-id", required=True,
              help="Full Azure resource ID")
@click.option("--dry-run", is_flag=True, help="Preview without deleting")
@click.option("--skip-confirmation", is_flag=True, help="Skip DELETE confirmation")
@click.option("--log-level", default="INFO", help="Logging level")
def reset_resource(
    resource_id: str,
    dry_run: bool,
    skip_confirmation: bool,
    log_level: str
):
    """
    Reset single resource (delete individual resource).

    Rejects operation if resource is ATG Service Principal.
    """
```

## Example Integration

Complete example showing how to use the services programmatically:

```python
import asyncio
from azure.identity import DefaultAzureCredential
from azure_tenant_grapher.services.tenant_reset_service import TenantResetService
from azure_tenant_grapher.services.reset_confirmation import (
    ResetConfirmation,
    ResetScope
)

async def reset_subscription_example():
    """
    Example: Reset subscription with dry-run, confirmation, and logging.
    """
    # Step 1: Initialize services
    credential = DefaultAzureCredential()
    tenant_id = "12345678-1234-1234-1234-123456789abc"
    subscription_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    reset_service = TenantResetService(
        credential=credential,
        tenant_id=tenant_id,
        concurrency=5
    )

    confirmation = ResetConfirmation(
        scope=ResetScope.SUBSCRIPTION,
        dry_run=False,
        skip_confirmation=False
    )

    # Step 2: Calculate scope
    scope_data = reset_service.calculate_scope_subscription([subscription_id])

    print(f"Resources to delete: {len(scope_data['to_delete'])}")
    print(f"Resources to preserve: {len(scope_data['to_preserve'])}")

    # Step 3: Get user confirmation
    if not confirmation.confirm_deletion(scope_data):
        print("Operation cancelled by user")
        return

    # Step 4: Order resources by dependencies
    deletion_waves = reset_service.order_by_dependencies(scope_data['to_delete'])

    # Step 5: Execute deletion
    import time
    start_time = time.time()

    deletion_results = await reset_service.delete_resources(
        deletion_waves,
        concurrency=5
    )

    end_time = time.time()

    # Step 6: Log operation
    confirmation.log_operation(
        scope_data,
        deletion_results,
        start_time,
        end_time
    )

    # Step 7: Display results
    print(f"\nDeleted: {len(deletion_results['deleted'])} resources")
    print(f"Failed: {len(deletion_results['failed'])} resources")
    print(f"Time: {end_time - start_time:.1f} seconds")

    if deletion_results['failed']:
        print("\nFailed resources:")
        for resource_id in deletion_results['failed']:
            error = deletion_results['errors'].get(resource_id, "Unknown error")
            print(f"  - {resource_id}")
            print(f"    Error: {error}")

# Run example
if __name__ == "__main__":
    asyncio.run(reset_subscription_example())
```

Output:

```
Resources to delete: 145
Resources to preserve: 2

About to delete 145 resources in subscription aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.
This operation cannot be undone.

Type 'DELETE' to confirm: DELETE

Deleting resources...
Wave 1: Virtual Machines (15 resources)
Wave 2: Network Interfaces (15 resources)
Wave 3: Disks (15 resources)
Wave 4: Virtual Networks (5 resources)
Wave 5: Storage Accounts (3 resources)
Wave 6: Resource Groups (2 resources)

Deleted: 143 resources
Failed: 2 resources
Time: 87.3 seconds

Failed resources:
  - /subscriptions/aaaa.../resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/nsg-locked
    Error: Resource has delete lock
  - /subscriptions/aaaa.../resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/lockedsa
    Error: Resource has delete lock
```

## Related Documentation

- [Tenant Reset Guide](../guides/TENANT_RESET_GUIDE.md) - User guide and command reference
- [Tenant Reset Safety Guide](../guides/TENANT_RESET_SAFETY.md) - Safety mechanisms
- [Tenant Reset Troubleshooting](./TENANT_RESET_TROUBLESHOOTING.md) - Error resolution

## Metadata

---
last_updated: 2026-01-27
status: current
category: reference
api_version: 1.0.0
related_services: TenantResetService, ResetConfirmation
---
