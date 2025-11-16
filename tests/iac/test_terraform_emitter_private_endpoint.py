"""TDD tests for Private Endpoint and Private DNS Zone resource generation (GAP-015).

This test suite ensures that Private Endpoint, Private DNS Zone, and
Virtual Network Link resources are properly converted to Terraform resources.

Test Coverage:
- Unit Tests (60%): Detection, field extraction, reference validation
- Integration Tests (30%): Full resource generation and multi-resource scenarios
- E2E Tests (10%): Real Neo4j data validation

Expected Impact: 2.5% fidelity increase (14 resources: 7 PEs + 7 DNS zones)
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest

from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.traverser import TenantGraph

# ============================================================================
# FIXTURES - Test Data and Common Setup
# ============================================================================


@pytest.fixture
def sample_private_endpoint() -> Dict[str, Any]:
    """Sample Private Endpoint resource from Neo4j."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe",
        "name": "kv-pe",
        "type": "Microsoft.Network/privateEndpoints",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "provisioningState": "Succeeded",
                "subnet": {
                    "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                },
                "privateLinkServiceConnections": [
                    {
                        "name": "KeyVaultConnection",
                        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe/privateLinkServiceConnections/KeyVaultConnection",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "privateLinkServiceId": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
                            "groupIds": ["vault"],
                            "privateLinkServiceConnectionState": {
                                "status": "Approved",
                                "actionsRequired": "None",
                            },
                        },
                    }
                ],
            }
        ),
    }


@pytest.fixture
def sample_private_dns_zone() -> Dict[str, Any]:
    """Sample Private DNS Zone resource from Neo4j."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net",
        "name": "privatelink.vaultcore.azure.net",
        "type": "Microsoft.Network/privateDnsZones",
        "location": "global",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "provisioningState": "Succeeded",
                "maxNumberOfRecordSets": 25000,
                "numberOfRecordSets": 1,
            }
        ),
    }


@pytest.fixture
def sample_vnet_link() -> Dict[str, Any]:
    """Sample Virtual Network Link resource from Neo4j."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net/virtualNetworkLinks/test-link",
        "name": "privatelink.vaultcore.azure.net/test-link",
        "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
        "location": "global",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "provisioningState": "Succeeded",
                "registrationEnabled": False,
                "virtualNetwork": {
                    "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet"
                },
                "virtualNetworkLinkState": "Completed",
            }
        ),
    }


@pytest.fixture
def sample_subnet() -> Dict[str, Any]:
    """Sample subnet for testing references."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet",
        "name": "pe-subnet",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resourceGroup": "test-rg",
        "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
    }


@pytest.fixture
def sample_vnet() -> Dict[str, Any]:
    """Sample VNet for testing references."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
        "name": "test-vnet",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resourceGroup": "test-rg",
        "address_space": ["10.0.0.0/16"],
        "properties": json.dumps(
            {"addressSpace": {"addressPrefixes": ["10.0.0.0/16"]}}
        ),
    }


@pytest.fixture
def terraform_emitter() -> TerraformEmitter:
    """Create a TerraformEmitter instance for testing."""
    return TerraformEmitter()


# ============================================================================
# UNIT TESTS (60%)
# Test Group 1: Resource Detection and Type Mapping (3 tests)
# ============================================================================


def test_private_endpoint_is_detected(
    terraform_emitter: TerraformEmitter, sample_private_endpoint: Dict[str, Any]
) -> None:
    """Verify Private Endpoints are identified as separate resources."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_endpoint, terraform_config
    )

    assert result is not None, "Private Endpoint should be detected and converted"
    terraform_type, resource_name, resource_config = result
    assert terraform_type == "azurerm_private_endpoint", (
        f"Expected 'azurerm_private_endpoint', got '{terraform_type}'"
    )


def test_private_dns_zone_is_detected(
    terraform_emitter: TerraformEmitter, sample_private_dns_zone: Dict[str, Any]
) -> None:
    """Verify Private DNS Zones are identified as separate resources."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_dns_zone, terraform_config
    )

    assert result is not None, "Private DNS Zone should be detected and converted"
    terraform_type, resource_name, resource_config = result
    assert terraform_type == "azurerm_private_dns_zone", (
        f"Expected 'azurerm_private_dns_zone', got '{terraform_type}'"
    )


def test_vnet_link_is_detected(
    terraform_emitter: TerraformEmitter, sample_vnet_link: Dict[str, Any]
) -> None:
    """Verify Virtual Network Links are identified as separate resources."""
    terraform_config = {"resource": {}}
    # Need to add VNet and DNS Zone to available resources for validation
    terraform_emitter._available_resources = {
        "azurerm_virtual_network": {"test_vnet"},
        "azurerm_private_dns_zone": {"privatelink_vaultcore_azure_net"}
    }
    result = terraform_emitter._convert_resource(sample_vnet_link, terraform_config)

    assert result is not None, "VNet Link should be detected and converted"
    terraform_type, resource_name, resource_config = result
    assert terraform_type == "azurerm_private_dns_zone_virtual_network_link", (
        f"Expected 'azurerm_private_dns_zone_virtual_network_link', got '{terraform_type}'"
    )


# ============================================================================
# Test Group 2: Private Endpoint Field Extraction (5 tests)
# ============================================================================


def test_private_endpoint_name_extracted(
    terraform_emitter: TerraformEmitter, sample_private_endpoint: Dict[str, Any]
) -> None:
    """Verify Private Endpoint name is extracted correctly."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_endpoint, terraform_config
    )

    assert result is not None
    _, resource_name, resource_config = result

    assert resource_config["name"] == "kv-pe"
    assert resource_name == "kv_pe"  # Sanitized name


def test_private_endpoint_subnet_reference_extracted(
    terraform_emitter: TerraformEmitter,
    sample_private_endpoint: Dict[str, Any],
    sample_subnet: Dict[str, Any],
) -> None:
    """Verify Private Endpoint references subnet correctly."""
    # Set up available subnets for validation
    terraform_emitter._available_subnets = {"test_vnet_pe_subnet"}
    terraform_config = {"resource": {}}

    result = terraform_emitter._convert_resource(
        sample_private_endpoint, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "subnet_id" in resource_config
    subnet_ref = resource_config["subnet_id"]
    assert "${azurerm_subnet.test_vnet_pe_subnet.id}" in subnet_ref


def test_private_endpoint_service_connection_extracted(
    terraform_emitter: TerraformEmitter, sample_private_endpoint: Dict[str, Any]
) -> None:
    """Verify Private Endpoint service connection is extracted correctly."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_endpoint, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "private_service_connection" in resource_config
    connections = resource_config["private_service_connection"]

    assert isinstance(connections, list)
    assert len(connections) == 1

    connection = connections[0]
    assert connection["name"] == "KeyVaultConnection"
    assert connection["is_manual_connection"] == False
    assert "private_connection_resource_id" in connection
    assert "test-kv" in connection["private_connection_resource_id"]
    assert "subresource_names" in connection
    assert connection["subresource_names"] == ["vault"]


def test_private_endpoint_location_and_rg_extracted(
    terraform_emitter: TerraformEmitter, sample_private_endpoint: Dict[str, Any]
) -> None:
    """Verify Private Endpoint location and resource group are extracted."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_endpoint, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert resource_config["location"] == "eastus"
    assert resource_config["resource_group_name"] == "test-rg"


def test_private_endpoint_missing_subnet_logs_error(
    terraform_emitter: TerraformEmitter, sample_private_endpoint: Dict[str, Any]
) -> None:
    """Verify error is logged when Private Endpoint references missing subnet."""
    # Set up empty available subnets (subnet doesn't exist)
    terraform_emitter._available_subnets = set()
    terraform_emitter._missing_references = []
    terraform_config = {"resource": {}}

    with patch("src.iac.emitters.private_endpoint_emitter.logger") as mock_logger:
        result = terraform_emitter._convert_resource(
            sample_private_endpoint, terraform_config
        )

        # Should still return a result (with placeholder reference)
        assert result is not None

        # Should log an error
        assert mock_logger.error.called

        # Should track missing reference
        assert len(terraform_emitter._missing_references) > 0


# ============================================================================
# Test Group 3: Private DNS Zone Field Extraction (3 tests)
# ============================================================================


def test_private_dns_zone_name_extracted(
    terraform_emitter: TerraformEmitter, sample_private_dns_zone: Dict[str, Any]
) -> None:
    """Verify Private DNS Zone name is extracted correctly."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_dns_zone, terraform_config
    )

    assert result is not None
    _, resource_name, resource_config = result

    assert resource_config["name"] == "privatelink.vaultcore.azure.net"
    # Sanitized name with dots replaced
    assert resource_name == "privatelink_vaultcore_azure_net"


def test_private_dns_zone_resource_group_extracted(
    terraform_emitter: TerraformEmitter, sample_private_dns_zone: Dict[str, Any]
) -> None:
    """Verify Private DNS Zone resource group is extracted."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_dns_zone, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert resource_config["resource_group_name"] == "test-rg"


def test_private_dns_zone_location_is_global(
    terraform_emitter: TerraformEmitter, sample_private_dns_zone: Dict[str, Any]
) -> None:
    """Verify Private DNS Zone does not include location (it's global in Azure)."""
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_private_dns_zone, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    # azurerm_private_dns_zone doesn't have a location parameter
    # (it's inherently global) so it should NOT be in the config
    assert "location" not in resource_config


# ============================================================================
# Test Group 4: VNet Link Field Extraction (4 tests)
# ============================================================================


def test_vnet_link_name_extracted(
    terraform_emitter: TerraformEmitter, sample_vnet_link: Dict[str, Any]
) -> None:
    """Verify VNet Link name is extracted from zone/link format."""
    terraform_emitter._available_resources = {
        "azurerm_virtual_network": {"test_vnet"},
        "azurerm_private_dns_zone": {"privatelink_vaultcore_azure_net"}
    }
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(sample_vnet_link, terraform_config)

    assert result is not None
    _, resource_name, resource_config = result

    # Name should be constructed from zone and VNet
    assert "privatelink" in resource_name.lower()
    assert "test_vnet" in resource_name


def test_vnet_link_dns_zone_reference(
    terraform_emitter: TerraformEmitter, sample_vnet_link: Dict[str, Any]
) -> None:
    """Verify VNet Link references DNS zone correctly."""
    terraform_emitter._available_resources = {
        "azurerm_virtual_network": {"test_vnet"},
        "azurerm_private_dns_zone": {"privatelink_vaultcore_azure_net"}
    }
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(sample_vnet_link, terraform_config)

    assert result is not None
    _, _, resource_config = result

    assert "private_dns_zone_name" in resource_config
    zone_ref = resource_config["private_dns_zone_name"]
    assert "${azurerm_private_dns_zone." in zone_ref
    assert "privatelink" in zone_ref


def test_vnet_link_virtual_network_reference(
    terraform_emitter: TerraformEmitter, sample_vnet_link: Dict[str, Any]
) -> None:
    """Verify VNet Link references virtual network correctly."""
    terraform_emitter._available_resources = {
        "azurerm_virtual_network": {"test_vnet"},
        "azurerm_private_dns_zone": {"privatelink_vaultcore_azure_net"}
    }
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(sample_vnet_link, terraform_config)

    assert result is not None
    _, _, resource_config = result

    assert "virtual_network_id" in resource_config
    vnet_ref = resource_config["virtual_network_id"]
    assert "${azurerm_virtual_network.test_vnet.id}" in vnet_ref


def test_vnet_link_registration_enabled_flag(
    terraform_emitter: TerraformEmitter, sample_vnet_link: Dict[str, Any]
) -> None:
    """Verify VNet Link registration_enabled flag is extracted."""
    terraform_emitter._available_resources = {
        "azurerm_virtual_network": {"test_vnet"},
        "azurerm_private_dns_zone": {"privatelink_vaultcore_azure_net"}
    }
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(sample_vnet_link, terraform_config)

    assert result is not None
    _, _, resource_config = result

    # Should not have registration_enabled if false (default)
    # Only add if true
    if "registration_enabled" in resource_config:
        assert resource_config["registration_enabled"] == True


# ============================================================================
# INTEGRATION TESTS (30%)
# Test Group 5: Full Resource Generation (3 tests)
# ============================================================================


def test_full_private_endpoint_resource_generated(
    terraform_emitter: TerraformEmitter,
    sample_private_endpoint: Dict[str, Any],
    sample_subnet: Dict[str, Any],
    sample_vnet: Dict[str, Any],
) -> None:
    """Verify complete Terraform JSON structure for Private Endpoint."""
    graph = TenantGraph()
    graph.resources = [sample_vnet, sample_subnet, sample_private_endpoint]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Check Private Endpoint exists
        assert "azurerm_private_endpoint" in terraform_config["resource"]
        pe = terraform_config["resource"]["azurerm_private_endpoint"]["kv_pe"]

        # Verify all required fields
        assert pe["name"] == "kv-pe"
        assert pe["location"] == "eastus"
        assert pe["resource_group_name"] == "test-rg"
        assert "subnet_id" in pe
        assert "private_service_connection" in pe
        assert len(pe["private_service_connection"]) == 1


def test_full_private_dns_zone_resource_generated(
    terraform_emitter: TerraformEmitter, sample_private_dns_zone: Dict[str, Any]
) -> None:
    """Verify complete Terraform JSON structure for Private DNS Zone."""
    graph = TenantGraph()
    graph.resources = [sample_private_dns_zone]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Check Private DNS Zone exists
        assert "azurerm_private_dns_zone" in terraform_config["resource"]

        zones = terraform_config["resource"]["azurerm_private_dns_zone"]
        # Find our zone (sanitized name)
        zone = None
        for zone_name, zone_config in zones.items():
            if "vaultcore" in zone_name:
                zone = zone_config
                break

        assert zone is not None
        assert zone["name"] == "privatelink.vaultcore.azure.net"
        assert zone["resource_group_name"] == "test-rg"


def test_full_vnet_link_resource_generated(
    terraform_emitter: TerraformEmitter,
    sample_vnet_link: Dict[str, Any],
    sample_vnet: Dict[str, Any],
    sample_private_dns_zone: Dict[str, Any],
) -> None:
    """Verify complete Terraform JSON structure for VNet Link."""
    graph = TenantGraph()
    graph.resources = [sample_vnet, sample_private_dns_zone, sample_vnet_link]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Check VNet Link exists
        assert (
            "azurerm_private_dns_zone_virtual_network_link"
            in terraform_config["resource"]
        )

        links = terraform_config["resource"][
            "azurerm_private_dns_zone_virtual_network_link"
        ]
        # Should have at least one link
        assert len(links) >= 1

        # Get the first link
        link = next(iter(links.values()))

        assert "private_dns_zone_name" in link
        assert "virtual_network_id" in link
        assert "${azurerm_private_dns_zone." in link["private_dns_zone_name"]
        assert "${azurerm_virtual_network." in link["virtual_network_id"]


# ============================================================================
# Test Group 6: Multi-Resource Scenarios (2 tests)
# ============================================================================


def test_private_endpoint_with_dns_zone_and_link(
    terraform_emitter: TerraformEmitter,
    sample_private_endpoint: Dict[str, Any],
    sample_private_dns_zone: Dict[str, Any],
    sample_vnet_link: Dict[str, Any],
    sample_subnet: Dict[str, Any],
    sample_vnet: Dict[str, Any],
) -> None:
    """Verify complete Private Endpoint setup with DNS integration."""
    graph = TenantGraph()
    graph.resources = [
        sample_vnet,
        sample_subnet,
        sample_private_endpoint,
        sample_private_dns_zone,
        sample_vnet_link,
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify all three resource types exist
        assert "azurerm_private_endpoint" in terraform_config["resource"]
        assert "azurerm_private_dns_zone" in terraform_config["resource"]
        assert (
            "azurerm_private_dns_zone_virtual_network_link"
            in terraform_config["resource"]
        )

        # Verify counts
        assert len(terraform_config["resource"]["azurerm_private_endpoint"]) >= 1
        assert len(terraform_config["resource"]["azurerm_private_dns_zone"]) >= 1
        assert (
            len(
                terraform_config["resource"][
                    "azurerm_private_dns_zone_virtual_network_link"
                ]
            )
            >= 1
        )


def test_multiple_private_endpoints_same_subnet(
    terraform_emitter: TerraformEmitter,
    sample_subnet: Dict[str, Any],
    sample_vnet: Dict[str, Any],
) -> None:
    """Verify multiple Private Endpoints can reference the same subnet."""
    # Create two Private Endpoints
    pe1 = {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe-1",
        "name": "kv-pe-1",
        "type": "Microsoft.Network/privateEndpoints",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "subnet": {
                    "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                },
                "privateLinkServiceConnections": [
                    {
                        "name": "Connection1",
                        "properties": {
                            "privateLinkServiceId": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/kv1",
                            "groupIds": ["vault"],
                        },
                    }
                ],
            }
        ),
    }

    pe2 = {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe-2",
        "name": "kv-pe-2",
        "type": "Microsoft.Network/privateEndpoints",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "subnet": {
                    "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                },
                "privateLinkServiceConnections": [
                    {
                        "name": "Connection2",
                        "properties": {
                            "privateLinkServiceId": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/st1",
                            "groupIds": ["blob"],
                        },
                    }
                ],
            }
        ),
    }

    graph = TenantGraph()
    graph.resources = [sample_vnet, sample_subnet, pe1, pe2]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Should have two Private Endpoints
        assert "azurerm_private_endpoint" in terraform_config["resource"]
        pes = terraform_config["resource"]["azurerm_private_endpoint"]
        assert len(pes) == 2

        # Both should reference the same subnet
        pe1_subnet = pes["kv_pe_1"]["subnet_id"]
        pe2_subnet = pes["kv_pe_2"]["subnet_id"]
        assert pe1_subnet == pe2_subnet
        assert "${azurerm_subnet.test_vnet_pe_subnet.id}" in pe1_subnet


# ============================================================================
# E2E TESTS (10%)
# ============================================================================


@pytest.mark.integration
def test_real_private_endpoint_data_from_neo4j(
    terraform_emitter: TerraformEmitter,
) -> None:
    """Test with realistic Private Endpoint data from Neo4j."""
    # Realistic data as it would come from Azure API
    realistic_vnet = {
        "id": "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y",
        "name": "vnet-ljio3xx7w6o6y",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "northcentralus",
        "resourceGroup": "ARTBAS-160224hpcp4rein6",
        "address_space": ["10.0.0.0/16"],
        "properties": json.dumps(
            {
                "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                "subnets": [
                    {"name": "snet-pe", "properties": {"addressPrefix": "10.0.1.0/24"}}
                ],
            }
        ),
    }

    realistic_pe = {
        "id": "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/simKV160224hpcp4rein6-keyvault-private-endpoint",
        "name": "simKV160224hpcp4rein6-keyvault-private-endpoint",
        "type": "Microsoft.Network/privateEndpoints",
        "location": "northcentralus",
        "resource_group": "ARTBAS-160224hpcp4rein6",
        "properties": json.dumps(
            {
                "provisioningState": "Succeeded",
                "resourceGuid": "bc2ce3ba-591a-45cf-bd50-7412ba5029ea",
                "privateLinkServiceConnections": [
                    {
                        "name": "KeyVaultPrivateLinkConnection",
                        "id": "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateEndpoints/simKV160224hpcp4rein6-keyvault-private-endpoint/privateLinkServiceConnections/KeyVaultPrivateLinkConnection",
                        "properties": {
                            "provisioningState": "Succeeded",
                            "privateLinkServiceId": "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.KeyVault/vaults/simKV160224hpcp4rein6",
                            "groupIds": ["vault"],
                            "privateLinkServiceConnectionState": {
                                "status": "Approved",
                                "description": "",
                                "actionsRequired": "None",
                            },
                        },
                    }
                ],
                "subnet": {
                    "id": "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/virtualNetworks/vnet-ljio3xx7w6o6y/subnets/snet-pe"
                },
            }
        ),
    }

    realistic_dns_zone = {
        "id": "/subscriptions/9b00bc5e-9abc-45de-9958-02a9d9277b16/resourceGroups/ARTBAS-160224hpcp4rein6/providers/Microsoft.Network/privateDnsZones/privatelink.vaultcore.azure.net",
        "name": "privatelink.vaultcore.azure.net",
        "type": "Microsoft.Network/privateDnsZones",
        "location": "global",
        "resource_group": "ARTBAS-160224hpcp4rein6",
        "properties": json.dumps(
            {
                "maxNumberOfRecordSets": 25000,
                "numberOfRecordSets": 2,
                "provisioningState": "Succeeded",
            }
        ),
    }

    graph = TenantGraph()
    graph.resources = [realistic_vnet, realistic_pe, realistic_dns_zone]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify Private Endpoint exists
        assert "azurerm_private_endpoint" in terraform_config["resource"]
        pes = terraform_config["resource"]["azurerm_private_endpoint"]

        # Find our PE (sanitized name)
        pe_key = None
        for key in pes.keys():
            if "simKV160224hpcp4rein6" in key and "keyvault" in key:
                pe_key = key
                break

        assert pe_key is not None, (
            f"Private Endpoint not found. Available keys: {list(pes.keys())}"
        )
        pe = pes[pe_key]

        # Verify all critical fields
        assert "simKV160224hpcp4rein6-keyvault-private-endpoint" in pe["name"]
        assert pe["location"] == "northcentralus"
        assert pe["resource_group_name"] == "ARTBAS-160224hpcp4rein6"
        assert "subnet_id" in pe
        assert "private_service_connection" in pe
        assert len(pe["private_service_connection"]) == 1
        assert pe["private_service_connection"][0]["subresource_names"] == ["vault"]

        # Verify DNS Zone exists
        assert "azurerm_private_dns_zone" in terraform_config["resource"]
        zones = terraform_config["resource"]["azurerm_private_dns_zone"]
        assert any("vaultcore" in name for name in zones.keys())


def test_cross_subscription_translation_e2e(terraform_emitter):
    """End-to-end test for cross-subscription resource ID translation.

    This test addresses reviewer concern #4: lack of integration test showing
    cross-subscription translation happening in the full emit pipeline.

    Scenario:
    - Resources discovered from source subscription
    - IaC generated for different target subscription
    - Private endpoint connection resource IDs should be translated
    """
    source_sub = "11111111-1111-1111-1111-111111111111"
    target_sub = "22222222-2222-2222-2222-222222222222"

    # Create resources with source subscription IDs
    vnet = {
        "id": f"/subscriptions/{source_sub}/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
        "name": "test-vnet",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resource_group": "network-rg",
        "properties": json.dumps(
            {
                "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                "subnets": [
                    {
                        "id": f"/subscriptions/{source_sub}/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet",
                        "name": "pe-subnet",
                        "properties": {"addressPrefix": "10.0.1.0/24"},
                    }
                ],
            }
        ),
    }

    subnet = {
        "id": f"/subscriptions/{source_sub}/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet",
        "name": "test-vnet/pe-subnet",
        "type": "Microsoft.Network/virtualNetworks/subnets",
        "location": "eastus",
        "resource_group": "network-rg",
        "properties": json.dumps({"addressPrefix": "10.0.1.0/24"}),
    }

    storage_account = {
        "id": f"/subscriptions/{source_sub}/resourceGroups/storage-rg/providers/Microsoft.Storage/storageAccounts/crosssubsa",
        "name": "crosssubsa",
        "type": "Microsoft.Storage/storageAccounts",
        "location": "eastus",
        "resource_group": "storage-rg",
        "properties": json.dumps({}),
    }

    # Private endpoint with cross-subscription storage account reference
    private_endpoint = {
        "id": f"/subscriptions/{source_sub}/resourceGroups/network-rg/providers/Microsoft.Network/privateEndpoints/sa-pe",
        "name": "sa-pe",
        "type": "Microsoft.Network/privateEndpoints",
        "location": "eastus",
        "resource_group": "network-rg",
        "properties": json.dumps(
            {
                "subnet": {
                    "id": f"/subscriptions/{source_sub}/resourceGroups/network-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                },
                "privateLinkServiceConnections": [
                    {
                        "name": "StorageConnection",
                        "properties": {
                            "privateLinkServiceId": f"/subscriptions/{source_sub}/resourceGroups/storage-rg/providers/Microsoft.Storage/storageAccounts/crosssubsa",
                            "groupIds": ["blob"],
                        },
                    }
                ],
            }
        ),
    }

    graph = TenantGraph()
    graph.resources = [vnet, subnet, storage_account, private_endpoint]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)

        # Emit with DIFFERENT target subscription (passed as parameter)
        written_files = terraform_emitter.emit(
            graph, out_dir, subscription_id=target_sub
        )

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify private endpoint was emitted
        assert "azurerm_private_endpoint" in terraform_config["resource"]
        pes = terraform_config["resource"]["azurerm_private_endpoint"]

        # Find the PE (name may be sanitized)
        pe_key = None
        for key in pes.keys():
            if "sa_pe" in key.lower():
                pe_key = key
                break

        assert pe_key is not None, f"PE not found. Keys: {list(pes.keys())}"
        pe = pes[pe_key]

        # CRITICAL VERIFICATION: Resource ID should be translated
        conn = pe["private_service_connection"][0]
        resource_id = conn["private_connection_resource_id"]

        # The key assertion: resource ID should have target subscription, not source
        assert target_sub in resource_id, (
            f"Expected target subscription {target_sub} in resource ID, "
            f"but got: {resource_id}"
        )
        assert source_sub not in resource_id, (
            f"Source subscription {source_sub} should not be in resource ID, "
            f"but got: {resource_id}"
        )

        # Verify the resource name and type are preserved
        assert "crosssubsa" in resource_id
        assert "Microsoft.Storage/storageAccounts" in resource_id

        # Verify subnet reference (should NOT be translated - it's a Terraform reference)
        assert "${azurerm_subnet" in pe["subnet_id"]
