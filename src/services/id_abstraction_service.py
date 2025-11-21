"""
ID Abstraction Service - Dual Graph Architecture (Issue #420)

This service generates deterministic, type-prefixed hash IDs for Azure resources
to enable the dual-graph architecture where resources exist as both Original
nodes (with real Azure IDs) and Abstracted nodes (with hashed IDs).

Key Features:
- Deterministic: Same input + seed = same output
- Type-prefixed: vm-a1b2c3d4, storage-e5f6g7h8, etc.
- Secure: One-way hashing with tenant-specific seed
- Fast: Caching for repeated lookups
"""

import hashlib
import logging
from functools import lru_cache
from typing import Dict, List

logger = logging.getLogger(__name__)


class IDAbstractionService:
    """
    Generates deterministic, type-prefixed hash IDs for Azure resources.

    This service is the core of the dual-graph architecture, translating real
    Azure resource IDs into abstracted, privacy-preserving identifiers while
    maintaining deterministic reproducibility through tenant-specific seeds.

    Examples:
        >>> service = IDAbstractionService("tenant-seed-123")
        >>> vm_id = "/subscriptions/abc123/resourceGroups/rg1/providers/Microsoft.Compute/virtualMachines/vm1"
        >>> abstracted = service.abstract_resource_name("vm1", "Microsoft.Compute/virtualMachines")
        >>> print(abstracted)  # vm-a1b2c3d4e5f6g7h8
    """

    # Type prefix mapping for common Azure resource types
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
        "Microsoft.Network/virtualNetworks/subnets": "subnet",  # Child resource path
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
        "Microsoft.Management/managementGroups": "mg",
        "Microsoft.Resources/resourceGroups": "rg",
    }

    def __init__(self, tenant_seed: str, hash_length: int = 16):
        """
        Initialize the ID Abstraction Service.

        Args:
            tenant_seed: Unique seed for this tenant (from Tenant node)
            hash_length: Length of hash suffix (default: 16 characters)

        Raises:
            ValueError: If tenant_seed is empty or invalid
        """
        if not tenant_seed:
            raise ValueError("tenant_seed must be a non-empty string")

        if hash_length < 8 or hash_length > 64:
            raise ValueError("hash_length must be between 8 and 64")

        self.tenant_seed = tenant_seed
        self.hash_length = hash_length

        logger.debug(
            f"Initialized IDAbstractionService with seed length {len(tenant_seed)}, "
            f"hash length {hash_length}"
        )

    def abstract_resource_id(self, original_id: str) -> str:
        """
        Translate full Azure resource ID to abstracted format.

        This method parses the Azure resource ID and abstracts each component
        (subscription, resource group, resource name) while maintaining the
        overall structure.

        Args:
            original_id: Full Azure resource ID
                Example: /subscriptions/12345678-1234.../resourceGroups/my-rg/providers/Microsoft.Compute/virtualMachines/my-vm

        Returns:
            Abstracted resource ID with type-prefixed hash
                Example: vm-a1b2c3d4e5f6g7h8

        Raises:
            ValueError: If original_id is invalid or cannot be parsed

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> service.abstract_resource_id("/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1")
            'vm-...'
        """
        if not original_id:
            raise ValueError("original_id cannot be empty")

        # Parse the Azure resource ID
        parsed = self._parse_azure_resource_id(original_id)

        # Extract resource type and name (cast to str since we know these are strings)
        resource_type = str(parsed.get("resource_type", ""))
        resource_name = str(parsed.get("resource_name", ""))

        if not resource_type or not resource_name:
            # Fallback: just hash the entire ID with a generic prefix
            logger.warning(
                f"Could not parse resource type/name from {original_id}, using fallback"
            )
            return f"resource-{self._hash(original_id)}"

        # Generate abstracted ID using resource name and type
        return self.abstract_resource_name(resource_name, resource_type)

    def abstract_subscription_id(self, sub_id: str) -> str:
        """
        Abstract subscription GUID.

        Args:
            sub_id: Subscription ID (GUID)
                Example: 12345678-1234-1234-1234-123456789012

        Returns:
            Abstracted subscription ID
                Example: sub-a1b2c3d4e5f6g7h8

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> service.abstract_subscription_id("12345678-1234-1234-1234-123456789012")
            'sub-...'
        """
        if not sub_id:
            raise ValueError("sub_id cannot be empty")

        return f"sub-{self._hash(sub_id)}"

    def abstract_resource_group_name(self, rg_name: str) -> str:
        """
        Abstract resource group name.

        Args:
            rg_name: Resource group name
                Example: my-rg

        Returns:
            Abstracted resource group name
                Example: rg-a1b2c3d4e5f6g7h8

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> service.abstract_resource_group_name("my-rg")
            'rg-...'
        """
        if not rg_name:
            raise ValueError("rg_name cannot be empty")

        return f"rg-{self._hash(rg_name)}"

    def abstract_resource_name(self, resource_name: str, resource_type: str) -> str:
        """
        Abstract resource name with type prefix.

        Args:
            resource_name: Resource name
                Example: my-vm
            resource_type: Azure resource type
                Example: Microsoft.Compute/virtualMachines

        Returns:
            Abstracted resource name with type prefix
                Example: vm-a1b2c3d4e5f6g7h8

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> service.abstract_resource_name("my-vm", "Microsoft.Compute/virtualMachines")
            'vm-...'
        """
        if not resource_name:
            raise ValueError("resource_name cannot be empty")

        if not resource_type:
            raise ValueError("resource_type cannot be empty")

        # Get type prefix
        prefix = self._extract_type_prefix(resource_type)

        # Hash the resource name
        hash_value = self._hash(resource_name)

        return f"{prefix}-{hash_value}"

    def abstract_resource_ids_bulk(self, resource_ids: List[str]) -> List[str]:
        """
        Abstract multiple resource IDs in bulk.

        This method is optimized for processing large batches of resource IDs.

        Args:
            resource_ids: List of Azure resource IDs

        Returns:
            List of abstracted resource IDs in the same order

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> ids = ["/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1"]
            >>> service.abstract_resource_ids_bulk(ids)
            ['vm-...']
        """
        return [self.abstract_resource_id(rid) for rid in resource_ids]

    def abstract_principal_id(self, principal_id: str) -> str:
        """
        Abstract principal ID (GUID) to hash-based ID.

        This method abstracts Entra ID principal GUIDs (user, service principal, or managed identity)
        to privacy-preserving hash-based identifiers. This is critical for role assignments where
        principal IDs from the source tenant must be abstracted for cross-tenant deployment.

        Args:
            principal_id: Principal ID (GUID)
                Example: 12345678-1234-1234-1234-123456789012

        Returns:
            Abstracted principal ID with 'principal-' prefix
                Example: principal-a1b2c3d4e5f6g7h8

        Raises:
            ValueError: If principal_id is empty or invalid

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> service.abstract_principal_id("12345678-1234-1234-1234-123456789012")
            'principal-...'
        """
        if not principal_id:
            raise ValueError("principal_id cannot be empty")

        return f"principal-{self._hash(principal_id)}"

    def _extract_type_prefix(self, resource_type: str) -> str:
        """
        Extract short type prefix from Azure resource type.

        Args:
            resource_type: Azure resource type
                Example: Microsoft.Compute/virtualMachines

        Returns:
            Type prefix
                Example: vm

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> service._extract_type_prefix("Microsoft.Compute/virtualMachines")
            'vm'
            >>> service._extract_type_prefix("Microsoft.Storage/storageAccounts")
            'storage'
        """
        # Check if we have a predefined prefix
        prefix = self.TYPE_PREFIXES.get(resource_type)

        if prefix:
            return prefix

        # Fallback: extract last segment and sanitize
        # Example: "Microsoft.Network/privateEndpoints" -> "privateendpoints"
        last_segment = resource_type.split("/")[-1]

        # Convert to lowercase and remove special characters
        sanitized = "".join(c.lower() for c in last_segment if c.isalnum())

        # Truncate if too long (keep first 15 chars)
        if len(sanitized) > 15:
            sanitized = sanitized[:15]

        logger.debug(f"Using fallback prefix '{sanitized}' for type {resource_type}")

        return sanitized

    def _hash(self, value: str) -> str:
        """
        Generate deterministic hash with tenant seed.

        Args:
            value: String to hash

        Returns:
            Truncated hash (lowercase hex)

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> hash1 = service._hash("test")
            >>> hash2 = service._hash("test")
            >>> hash1 == hash2
            True
        """
        # Combine value with tenant seed for uniqueness
        hash_input = f"{value}:{self.tenant_seed}"

        # Generate SHA256 hash
        hash_obj = hashlib.sha256(hash_input.encode("utf-8"))
        hash_hex = hash_obj.hexdigest()

        # Return truncated hash (lowercase)
        return hash_hex[: self.hash_length]

    def _parse_azure_resource_id(self, resource_id: str) -> dict[str, str | bool]:
        """
        Parse Azure resource ID into components.

        Azure resource IDs follow this format:
        /subscriptions/{subscription-id}/resourceGroups/{resource-group-name}/providers/{resource-provider}/{resource-type}/{resource-name}

        For child resources (e.g., subnets):
        /subscriptions/{subscription-id}/resourceGroups/{resource-group-name}/providers/{resource-provider}/{parent-type}/{parent-name}/{child-type}/{child-name}

        Args:
            resource_id: Full Azure resource ID

        Returns:
            Dictionary with parsed components:
                - subscription_id: Subscription GUID
                - resource_group: Resource group name
                - resource_type: Full resource type (e.g., Microsoft.Compute/virtualMachines)
                - resource_name: Resource name
                - is_child_resource: Boolean indicating if this is a child resource

        Examples:
            >>> service = IDAbstractionService("seed")
            >>> parsed = service._parse_azure_resource_id("/subscriptions/abc/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm1")
            >>> parsed["resource_name"]
            'vm1'
            >>> parsed["resource_type"]
            'Microsoft.Compute/virtualMachines'
        """
        result: dict[str, str | bool] = {
            "subscription_id": "",
            "resource_group": "",
            "resource_type": "",
            "resource_name": "",
            "is_child_resource": False,
        }

        # Normalize the ID (remove trailing slashes)
        resource_id = resource_id.rstrip("/")

        # Split by '/'
        parts = [p for p in resource_id.split("/") if p]

        # Find key indices
        try:
            # Find 'subscriptions' index
            if "subscriptions" in parts:
                sub_idx = parts.index("subscriptions")
                result["subscription_id"] = (
                    parts[sub_idx + 1] if sub_idx + 1 < len(parts) else ""
                )

            # Find 'resourceGroups' index
            if "resourceGroups" in parts:
                rg_idx = parts.index("resourceGroups")
                result["resource_group"] = (
                    parts[rg_idx + 1] if rg_idx + 1 < len(parts) else ""
                )

            # Find 'providers' index
            if "providers" in parts:
                prov_idx = parts.index("providers")

                # Everything after 'providers' is the resource path
                # Format: {provider}/{type}/{name}/{child-type}/{child-name}/...
                if prov_idx + 1 < len(parts):
                    provider = parts[prov_idx + 1]  # e.g., Microsoft.Compute

                    # Collect type/name pairs
                    resource_parts = parts[prov_idx + 2 :]

                    if len(resource_parts) >= 2:
                        # For non-child resources, take the last type/name pair
                        # For child resources, we still want the last type/name pair
                        resource_type_segment = resource_parts[-2]
                        resource_name = resource_parts[-1]

                        # Build full resource type
                        # For child resources: Microsoft.Network/virtualNetworks/subnets
                        # For simple resources: Microsoft.Compute/virtualMachines
                        if len(resource_parts) > 2:
                            # This is a child resource
                            result["is_child_resource"] = True
                            # Build type path: provider/parent_type/child_type
                            # Example: Microsoft.Network/virtualNetworks/subnets
                            type_segments = [provider]
                            # Take every other part (types, not names)
                            for i in range(0, len(resource_parts) - 1, 2):
                                type_segments.append(resource_parts[i])
                            result["resource_type"] = "/".join(type_segments)
                        else:
                            # Simple resource
                            result["resource_type"] = (
                                f"{provider}/{resource_type_segment}"
                            )

                        result["resource_name"] = resource_name

        except (ValueError, IndexError) as e:
            logger.warning(f"Failed to parse resource ID {resource_id}: {e}")

        return result


# Singleton pattern helpers for common use cases
@lru_cache(maxsize=128)
def get_id_abstraction_service(
    tenant_seed: str, hash_length: int = 16
) -> IDAbstractionService:
    """
    Get or create a cached IDAbstractionService instance.

    This function provides caching for service instances to avoid
    recreating them repeatedly with the same seed.

    Args:
        tenant_seed: Tenant-specific seed
        hash_length: Hash length (default: 16)

    Returns:
        IDAbstractionService instance
    """
    return IDAbstractionService(tenant_seed, hash_length)
