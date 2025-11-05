"""Shared Test Fixtures for Dual Graph Architecture Tests (Issue #420).

This module provides reusable fixtures for testing the dual graph architecture
feature across multiple test files.

Fixtures provided:
- Mock Neo4j connections
- Sample Azure resources
- Graph comparison utilities
- ID abstraction service mocks
- Tenant seed fixtures
"""

from typing import Any, Dict, List, Set, Tuple
from unittest.mock import MagicMock, Mock

import pytest


# ============================================================================
# Mock Neo4j Fixtures
# ============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Provide a mock Neo4j driver with session management.

    Returns:
        MagicMock: Mocked Neo4j driver with session support
    """
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    return driver


@pytest.fixture
def mock_neo4j_session():
    """Provide a mock Neo4j session for direct use.

    Returns:
        MagicMock: Mocked Neo4j session with run() method
    """
    session = MagicMock()
    session.run = MagicMock(return_value=MagicMock())
    return session


@pytest.fixture
def mock_neo4j_transaction():
    """Provide a mock Neo4j transaction.

    Returns:
        MagicMock: Mocked Neo4j transaction
    """
    transaction = MagicMock()
    transaction.run = MagicMock(return_value=MagicMock())
    transaction.commit = MagicMock()
    transaction.rollback = MagicMock()
    return transaction


# ============================================================================
# Azure Resource Fixtures
# ============================================================================


@pytest.fixture
def sample_azure_vm() -> Dict[str, Any]:
    """Provide a sample Azure VM resource.

    Returns:
        Dict: Azure VM resource dictionary
    """
    return {
        "id": "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm-web-001",
        "name": "vm-web-001",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "properties": {
            "hardwareProfile": {"vmSize": "Standard_D2s_v3"},
            "osProfile": {
                "computerName": "vm-web-001",
                "adminUsername": "azureuser",
            },
            "storageProfile": {
                "imageReference": {
                    "publisher": "Canonical",
                    "offer": "UbuntuServer",
                    "sku": "18.04-LTS",
                }
            },
        },
        "tags": {"environment": "production", "owner": "team-platform"},
    }


@pytest.fixture
def sample_azure_storage() -> Dict[str, Any]:
    """Provide a sample Azure Storage Account resource.

    Returns:
        Dict: Azure Storage Account resource dictionary
    """
    return {
        "id": "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststore001",
        "name": "teststore001",
        "type": "Microsoft.Storage/storageAccounts",
        "location": "eastus",
        "sku": {"name": "Standard_LRS", "tier": "Standard"},
        "kind": "StorageV2",
        "properties": {
            "supportsHttpsTrafficOnly": True,
            "encryption": {
                "services": {
                    "blob": {"enabled": True},
                    "file": {"enabled": True},
                }
            },
        },
    }


@pytest.fixture
def sample_azure_vnet() -> Dict[str, Any]:
    """Provide a sample Azure Virtual Network resource.

    Returns:
        Dict: Azure VNet resource dictionary
    """
    return {
        "id": "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod",
        "name": "vnet-prod",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "properties": {
            "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
            "dhcpOptions": {"dnsServers": []},
            "subnets": [
                {
                    "name": "subnet-web",
                    "properties": {
                        "addressPrefix": "10.0.1.0/24",
                        "privateEndpointNetworkPolicies": "Disabled",
                    },
                },
                {
                    "name": "subnet-db",
                    "properties": {
                        "addressPrefix": "10.0.2.0/24",
                    },
                },
            ],
        },
    }


@pytest.fixture
def sample_azure_subnet() -> Dict[str, Any]:
    """Provide a sample Azure Subnet resource.

    Returns:
        Dict: Azure Subnet resource dictionary
    """
    return {
        "id": "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-web",
        "name": "subnet-web",
        "type": "Microsoft.Network/virtualNetworks/subnets",
        "properties": {
            "addressPrefix": "10.0.1.0/24",
            "privateEndpointNetworkPolicies": "Disabled",
        },
    }


@pytest.fixture
def sample_azure_keyvault() -> Dict[str, Any]:
    """Provide a sample Azure Key Vault resource.

    Returns:
        Dict: Azure Key Vault resource dictionary
    """
    return {
        "id": "/subscriptions/abc123/resourceGroups/security-rg/providers/Microsoft.KeyVault/vaults/kv-prod-001",
        "name": "kv-prod-001",
        "type": "Microsoft.KeyVault/vaults",
        "location": "eastus",
        "properties": {
            "tenantId": "tenant-abc-123",
            "sku": {"family": "A", "name": "standard"},
            "enabledForDeployment": True,
            "enabledForDiskEncryption": True,
            "enabledForTemplateDeployment": True,
        },
    }


@pytest.fixture
def complex_resource_topology() -> List[Dict[str, Any]]:
    """Provide a complex resource topology with multiple resource types.

    Returns:
        List[Dict]: List of Azure resources forming a topology
    """
    return [
        # Subscription
        {
            "id": "/subscriptions/sub-12345",
            "name": "Production Subscription",
            "type": "Microsoft.Subscription",
        },
        # Resource Groups
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-network",
            "name": "rg-network",
            "type": "Microsoft.Resources/resourceGroups",
            "location": "eastus",
        },
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-compute",
            "name": "rg-compute",
            "type": "Microsoft.Resources/resourceGroups",
            "location": "eastus",
        },
        # VNet
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-prod",
            "name": "vnet-prod",
            "type": "Microsoft.Network/virtualNetworks",
            "location": "eastus",
            "properties": {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}},
        },
        # Subnets
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-web",
            "name": "subnet-web",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {"addressPrefix": "10.0.1.0/24"},
        },
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-db",
            "name": "subnet-db",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "properties": {"addressPrefix": "10.0.2.0/24"},
        },
        # NSG
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-network/providers/Microsoft.Network/networkSecurityGroups/nsg-web",
            "name": "nsg-web",
            "type": "Microsoft.Network/networkSecurityGroups",
            "location": "eastus",
        },
        # VMs
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm-web-001",
            "name": "vm-web-001",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
        },
        {
            "id": "/subscriptions/sub-12345/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm-web-002",
            "name": "vm-web-002",
            "type": "Microsoft.Compute/virtualMachines",
            "location": "eastus",
        },
    ]


# ============================================================================
# Tenant Seed Fixtures
# ============================================================================


@pytest.fixture
def tenant_seed_alpha() -> str:
    """Provide a consistent tenant seed for testing.

    Returns:
        str: Tenant seed string
    """
    return "tenant-seed-alpha-12345678901234567890"


@pytest.fixture
def tenant_seed_beta() -> str:
    """Provide a different tenant seed for testing.

    Returns:
        str: Tenant seed string
    """
    return "tenant-seed-beta-98765432109876543210"


@pytest.fixture
def sample_tenant_info() -> Dict[str, Any]:
    """Provide sample tenant information.

    Returns:
        Dict: Tenant information dictionary
    """
    return {
        "tenant_id": "tenant-abc-123-def-456",
        "display_name": "Contoso Production Tenant",
        "domain": "contoso.com",
        "country": "US",
    }


# ============================================================================
# ID Abstraction Fixtures
# ============================================================================


@pytest.fixture
def mock_id_abstraction_service():
    """Provide a mock ID abstraction service.

    Returns:
        MagicMock: Mocked IDAbstractionService
    """
    service = MagicMock()

    # Mock abstract_resource_id to return type-prefixed hash
    def mock_abstract_id(resource_id: str) -> str:
        # Extract resource type from ID
        if "virtualMachines" in resource_id:
            prefix = "vm"
        elif "storageAccounts" in resource_id:
            prefix = "storage"
        elif "virtualNetworks/vnet" in resource_id and "subnets" not in resource_id:
            prefix = "vnet"
        elif "subnets" in resource_id:
            prefix = "subnet"
        elif "networkSecurityGroups" in resource_id:
            prefix = "nsg"
        elif "KeyVault" in resource_id:
            prefix = "kv"
        else:
            prefix = "resource"

        # Generate simple hash from resource_id
        hash_val = hash(resource_id) & 0xFFFFFFFF
        return f"{prefix}-{hash_val:08x}"

    service.abstract_resource_id = MagicMock(side_effect=mock_abstract_id)

    # Mock subscription and RG abstraction
    service.abstract_subscription_id = MagicMock(
        side_effect=lambda sid: f"sub-{hash(sid) & 0xFFFFFFFF:08x}"
    )
    service.abstract_resource_group_name = MagicMock(
        side_effect=lambda rg: f"rg-{hash(rg) & 0xFFFFFFFF:08x}"
    )

    return service


@pytest.fixture
def abstracted_resource_ids() -> Dict[str, str]:
    """Provide mapping of original to abstracted resource IDs.

    Returns:
        Dict: Mapping of original IDs to abstracted IDs
    """
    return {
        "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/vm-web-001": "vm-a1b2c3d4",
        "/subscriptions/abc123/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststore001": "storage-e5f6g7h8",
        "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod": "vnet-i9j0k1l2",
        "/subscriptions/abc123/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/vnet-prod/subnets/subnet-web": "subnet-m3n4o5p6",
    }


# ============================================================================
# Graph Comparison Utilities
# ============================================================================


class GraphComparisonHelper:
    """Helper class for comparing graph structures."""

    @staticmethod
    def extract_node_structure(nodes: List[Dict[str, Any]]) -> Set[Tuple[str, str]]:
        """Extract node structure as set of (type, name) tuples.

        Args:
            nodes: List of node dictionaries

        Returns:
            Set of (type, name) tuples
        """
        return {(node.get("type", ""), node.get("name", "")) for node in nodes}

    @staticmethod
    def extract_relationship_structure(
        relationships: List[Dict[str, Any]],
    ) -> Set[Tuple[str, str, str]]:
        """Extract relationship structure as set of (source, type, target) tuples.

        Args:
            relationships: List of relationship dictionaries

        Returns:
            Set of (source, type, target) tuples
        """
        return {
            (rel.get("source", ""), rel.get("type", ""), rel.get("target", ""))
            for rel in relationships
        }

    @staticmethod
    def compare_graph_structures(
        original_nodes: List[Dict[str, Any]],
        original_rels: List[Dict[str, Any]],
        abstracted_nodes: List[Dict[str, Any]],
        abstracted_rels: List[Dict[str, Any]],
    ) -> Tuple[bool, str]:
        """Compare two graph structures for isomorphism.

        Args:
            original_nodes: Nodes from original graph
            original_rels: Relationships from original graph
            abstracted_nodes: Nodes from abstracted graph
            abstracted_rels: Relationships from abstracted graph

        Returns:
            Tuple of (is_isomorphic, difference_message)
        """
        # Compare node counts
        if len(original_nodes) != len(abstracted_nodes):
            return (
                False,
                f"Node count mismatch: {len(original_nodes)} vs {len(abstracted_nodes)}",
            )

        # Compare relationship counts
        if len(original_rels) != len(abstracted_rels):
            return (
                False,
                f"Relationship count mismatch: {len(original_rels)} vs {len(abstracted_rels)}",
            )

        # Compare node structures (by type and name, ignoring IDs)
        original_structure = GraphComparisonHelper.extract_node_structure(
            original_nodes
        )
        abstracted_structure = GraphComparisonHelper.extract_node_structure(
            abstracted_nodes
        )

        if original_structure != abstracted_structure:
            return False, "Node structures differ"

        # Compare relationship counts by type
        original_rel_types = {}
        for rel in original_rels:
            rel_type = rel.get("type", "")
            original_rel_types[rel_type] = original_rel_types.get(rel_type, 0) + 1

        abstracted_rel_types = {}
        for rel in abstracted_rels:
            rel_type = rel.get("type", "")
            abstracted_rel_types[rel_type] = abstracted_rel_types.get(rel_type, 0) + 1

        if original_rel_types != abstracted_rel_types:
            return (
                False,
                f"Relationship type counts differ: {original_rel_types} vs {abstracted_rel_types}",
            )

        return True, "Graphs are isomorphic"


@pytest.fixture
def graph_comparison_helper():
    """Provide a graph comparison helper instance.

    Returns:
        GraphComparisonHelper: Helper for comparing graphs
    """
    return GraphComparisonHelper()


# ============================================================================
# Pytest Markers
# ============================================================================


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line(
        "markers",
        "dual_graph: mark test as part of dual graph architecture feature (Issue #420)",
    )
