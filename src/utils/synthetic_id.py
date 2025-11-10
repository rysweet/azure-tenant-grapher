"""
Synthetic ID Generator for Scale Operations

This module generates collision-free synthetic IDs for scale operations
that create synthetic resources in the abstracted graph layer.

Synthetic IDs are distinct from abstracted IDs:
- Abstracted IDs: Deterministic hashes of real Azure resource IDs
- Synthetic IDs: Random UUIDs for synthetic resources with no Azure counterpart

Format: synthetic-{type_short}-{uuid8}
Example: synthetic-vm-a1b2c3d4
"""

import uuid
from typing import Dict

# Type prefix mapping for common Azure resource types
# This mirrors the prefixes used in IDAbstractionService for consistency
TYPE_PREFIXES: Dict[str, str] = {
    # Compute
    "Microsoft.Compute/virtualMachines": "vm",
    "Microsoft.Compute/disks": "disk",
    "Microsoft.Compute/availabilitySets": "avset",
    "Microsoft.Compute/virtualMachineScaleSets": "vmss",
    "Microsoft.Compute/images": "image",
    "Microsoft.Compute/snapshots": "snapshot",
    # Network
    "Microsoft.Network/virtualNetworks": "vnet",
    "Microsoft.Network/subnets": "subnet",
    "Microsoft.Network/virtualNetworks/subnets": "subnet",
    "Microsoft.Network/networkSecurityGroups": "nsg",
    "Microsoft.Network/publicIPAddresses": "pip",
    "Microsoft.Network/networkInterfaces": "nic",
    "Microsoft.Network/loadBalancers": "lb",
    "Microsoft.Network/applicationGateways": "appgw",
    "Microsoft.Network/virtualNetworkGateways": "vnetgw",
    "Microsoft.Network/localNetworkGateways": "localgw",
    "Microsoft.Network/connections": "conn",
    "Microsoft.Network/routeTables": "rt",
    "Microsoft.Network/privateDnsZones": "pdns",
    "Microsoft.Network/privateEndpoints": "pe",
    # Storage
    "Microsoft.Storage/storageAccounts": "storage",
    "Microsoft.Storage/storageAccounts/blobServices": "blob",
    "Microsoft.Storage/storageAccounts/fileServices": "file",
    "Microsoft.Storage/storageAccounts/queueServices": "queue",
    "Microsoft.Storage/storageAccounts/tableServices": "table",
    # Database
    "Microsoft.Sql/servers": "sql",
    "Microsoft.Sql/servers/databases": "sqldb",
    "Microsoft.DBforMySQL/servers": "mysql",
    "Microsoft.DBforPostgreSQL/servers": "postgres",
    "Microsoft.DocumentDB/databaseAccounts": "cosmos",
    "Microsoft.Cache/redis": "redis",
    # Security & Identity
    "Microsoft.KeyVault/vaults": "kv",
    "Microsoft.ManagedIdentity/userAssignedIdentities": "identity",
    "Microsoft.Security/securityContacts": "seccontact",
    # Web & App Services
    "Microsoft.Web/sites": "app",
    "Microsoft.Web/serverfarms": "appplan",
    "Microsoft.Web/hostingEnvironments": "ase",
    # Containers
    "Microsoft.ContainerRegistry/registries": "acr",
    "Microsoft.ContainerService/managedClusters": "aks",
    "Microsoft.ContainerInstance/containerGroups": "aci",
    # Monitoring & Management
    "Microsoft.Insights/components": "appinsights",
    "Microsoft.Insights/workspaces": "workspace",
    "Microsoft.OperationalInsights/workspaces": "loganalytics",
    "Microsoft.Automation/automationAccounts": "automation",
    # Analytics
    "Microsoft.DataFactory/factories": "adf",
    "Microsoft.Databricks/workspaces": "databricks",
    "Microsoft.Synapse/workspaces": "synapse",
    # IoT
    "Microsoft.Devices/IotHubs": "iothub",
    "Microsoft.EventHub/namespaces": "eventhub",
    "Microsoft.ServiceBus/namespaces": "servicebus",
    # Management
    "Microsoft.Resources/resourceGroups": "rg",
    "Microsoft.Resources/subscriptions": "sub",
    "Microsoft.Resources/deployments": "deployment",
    # Default fallback
    "default": "resource",
}


def generate_synthetic_id(resource_type: str) -> str:
    """
    Generate a collision-free synthetic ID for a scale operation resource.

    The ID format is: synthetic-{type_short}-{uuid8}
    where uuid8 is the first 8 characters of a UUID v4.

    This ensures:
    - Global uniqueness through UUID v4
    - Human readability through type prefix
    - Clear distinction from abstracted IDs

    Args:
        resource_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

    Returns:
        str: Synthetic ID in format synthetic-{type_short}-{uuid8}

    Examples:
        >>> generate_synthetic_id("Microsoft.Compute/virtualMachines")
        'synthetic-vm-a1b2c3d4'

        >>> generate_synthetic_id("Microsoft.Network/virtualNetworks")
        'synthetic-vnet-e5f6g7h8'

        >>> generate_synthetic_id("Unknown.Type")
        'synthetic-resource-i9j0k1l2'
    """
    # Get type prefix or use default
    type_prefix = TYPE_PREFIXES.get(resource_type, TYPE_PREFIXES["default"])

    # Generate UUID and take first 8 characters
    unique_id = str(uuid.uuid4()).replace("-", "")[:8]

    # Construct synthetic ID
    synthetic_id = f"synthetic-{type_prefix}-{unique_id}"

    return synthetic_id


def is_synthetic_id(resource_id: str) -> bool:
    """
    Check if a resource ID is a synthetic ID.

    Args:
        resource_id: Resource identifier to check

    Returns:
        bool: True if the ID is a synthetic ID, False otherwise

    Examples:
        >>> is_synthetic_id("synthetic-vm-a1b2c3d4")
        True

        >>> is_synthetic_id("vm-a1b2c3d4")
        False

        >>> is_synthetic_id("/subscriptions/abc/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1")
        False
    """
    return resource_id.startswith("synthetic-")


def extract_type_from_synthetic_id(synthetic_id: str) -> str:
    """
    Extract the type prefix from a synthetic ID.

    Args:
        synthetic_id: Synthetic ID to parse

    Returns:
        str: Type prefix or "unknown" if not a valid synthetic ID

    Examples:
        >>> extract_type_from_synthetic_id("synthetic-vm-a1b2c3d4")
        'vm'

        >>> extract_type_from_synthetic_id("synthetic-vnet-e5f6g7h8")
        'vnet'

        >>> extract_type_from_synthetic_id("not-synthetic")
        'unknown'
    """
    if not is_synthetic_id(synthetic_id):
        return "unknown"

    parts = synthetic_id.split("-")
    if len(parts) >= 2:
        return parts[1]

    return "unknown"


def get_resource_type_from_prefix(prefix: str) -> str:
    """
    Get the full resource type from a prefix.

    Args:
        prefix: Type prefix (e.g., "vm", "vnet")

    Returns:
        str: Full resource type or "Unknown" if prefix not found

    Examples:
        >>> get_resource_type_from_prefix("vm")
        'Microsoft.Compute/virtualMachines'

        >>> get_resource_type_from_prefix("vnet")
        'Microsoft.Network/virtualNetworks'

        >>> get_resource_type_from_prefix("unknown")
        'Unknown'
    """
    # Reverse lookup in TYPE_PREFIXES
    for resource_type, type_prefix in TYPE_PREFIXES.items():
        if type_prefix == prefix and resource_type != "default":
            return resource_type

    return "Unknown"
