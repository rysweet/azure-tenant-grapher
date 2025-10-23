"""Comprehensive TDD tests for Issue #296: Standalone subnet resource generation.

This test suite follows the testing pyramid (60% unit, 30% integration, 10% E2E)
to ensure that standalone Microsoft.Network/subnets resources are properly
converted to azurerm_subnet Terraform resources.

Test Coverage Breakdown:
- Unit Tests (60%): 14 tests covering detection, field extraction, VNet linking, edge cases
- Integration Tests (30%): 6 tests covering full resource generation and multi-resource scenarios
- E2E Tests (10%): 2 tests covering real Neo4j data and complete topology validation

Expected Behavior:
All tests should FAIL initially (RED phase) since the implementation doesn't exist yet.
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
def sample_standalone_subnet() -> Dict[str, Any]:
    """Sample standalone subnet resource from Neo4j."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default",
        "name": "default",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "addressPrefix": "10.0.1.0/24",
                "provisioningState": "Succeeded",
            }
        ),
    }


@pytest.fixture
def sample_subnet_with_nsg() -> Dict[str, Any]:
    """Subnet with network security group association."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/secure-subnet",
        "name": "secure-subnet",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "addressPrefix": "10.0.2.0/24",
                "networkSecurityGroup": {
                    "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/networkSecurityGroups/test-nsg"
                },
            }
        ),
    }


@pytest.fixture
def sample_subnet_with_service_endpoints() -> Dict[str, Any]:
    """Subnet with service endpoints configured."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/service-subnet",
        "name": "service-subnet",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "addressPrefix": "10.0.3.0/24",
                "serviceEndpoints": [
                    {"service": "Microsoft.Storage", "locations": ["eastus"]},
                    {"service": "Microsoft.Sql", "locations": ["eastus"]},
                ],
            }
        ),
    }


@pytest.fixture
def sample_subnet_with_address_prefixes_list() -> Dict[str, Any]:
    """Subnet using addressPrefixes (list format) instead of addressPrefix."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/multi-prefix",
        "name": "multi-prefix",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps({"addressPrefixes": ["10.0.4.0/24", "10.0.5.0/24"]}),
    }


@pytest.fixture
def sample_subnet_special_chars() -> Dict[str, Any]:
    """Subnet with special characters in name."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/my-subnet.prod",
        "name": "my-subnet.prod",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps({"addressPrefix": "10.0.6.0/24"}),
    }


@pytest.fixture
def sample_subnet_missing_properties() -> Dict[str, Any]:
    """Subnet with missing required properties."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/incomplete",
        "name": "incomplete",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": "{}",  # Empty properties
    }


@pytest.fixture
def sample_vnet_with_embedded_subnets() -> Dict[str, Any]:
    """VNet resource with embedded subnet blocks."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet",
        "name": "test-vnet",
        "type": "Microsoft.Network/virtualNetworks",
        "location": "eastus",
        "resource_group": "test-rg",
        "address_space": ["10.0.0.0/16"],
        "properties": json.dumps(
            {
                "addressSpace": {"addressPrefixes": ["10.0.0.0/16"]},
                "subnets": [
                    {
                        "name": "embedded-subnet",
                        "properties": {"addressPrefix": "10.0.0.0/24"},
                    }
                ],
            }
        ),
    }


@pytest.fixture
def sample_network_interface() -> Dict[str, Any]:
    """Network interface that references a subnet."""
    return {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic",
        "name": "test-nic",
        "type": "Microsoft.Network/networkInterfaces",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps(
            {
                "ipConfigurations": [
                    {
                        "name": "ipconfig1",
                        "properties": {
                            "subnet": {
                                "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/default"
                            },
                            "privateIPAllocationMethod": "Dynamic",
                        },
                    }
                ]
            }
        ),
    }


@pytest.fixture
def terraform_emitter() -> TerraformEmitter:
    """Create a TerraformEmitter instance for testing."""
    return TerraformEmitter()


# ============================================================================
# UNIT TESTS (60% - 14 tests)
# Test Group 1: Subnet Resource Detection (3 tests)
# ============================================================================


def test_standalone_subnet_is_detected(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify standalone subnets are identified as separate resources.

    Expected to FAIL: The _convert_resource method currently returns None
    for Microsoft.Network/subnets because there's no handler implemented.
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_standalone_subnet, terraform_config
    )

    # Should return a tuple, not None
    assert result is not None, "Standalone subnet should be detected and converted"
    terraform_type, resource_name, resource_config = result
    assert terraform_type == "azurerm_subnet", (
        f"Expected 'azurerm_subnet', got '{terraform_type}'"
    )


def test_subnet_type_mapping(terraform_emitter: TerraformEmitter) -> None:
    """Verify Microsoft.Network/subnets maps to azurerm_subnet.

    Expected to FAIL: The mapping exists in AZURE_TO_TERRAFORM_MAPPING
    but _convert_resource doesn't have a handler for it.
    """
    # Check mapping exists
    assert "Microsoft.Network/subnets" in terraform_emitter.AZURE_TO_TERRAFORM_MAPPING
    assert (
        terraform_emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Network/subnets"]
        == "azurerm_subnet"
    )

    # Check actual conversion works (this will fail)
    test_subnet = {
        "type": "Microsoft.Network/subnets",
        "name": "test",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps({"addressPrefix": "10.0.0.0/24"}),
    }
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(test_subnet, terraform_config)

    assert result is not None, "Subnet conversion should return a result"


def test_subnet_with_missing_properties_handled(
    terraform_emitter: TerraformEmitter,
    sample_subnet_missing_properties: Dict[str, Any],
) -> None:
    """Verify subnets with missing properties are handled gracefully.

    Expected to FAIL: No handler exists yet, but when implemented,
    it should log a warning and either skip or use defaults.
    """
    terraform_config = {"resource": {}}

    with patch("src.iac.emitters.terraform_emitter.logger") as mock_logger:
        result = terraform_emitter._convert_resource(
            sample_subnet_missing_properties, terraform_config
        )

        # Should either return None (skip) or use default values
        if result is None:
            # If skipped, should log a warning
            assert mock_logger.warning.called, (
                "Should log warning for missing properties"
            )
        else:
            # If using defaults, should have address_prefixes
            _, _, resource_config = result
            assert "address_prefixes" in resource_config


# ============================================================================
# Test Group 2: Required Field Extraction (5 tests)
# ============================================================================


def test_subnet_name_extracted_correctly(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify subnet name is extracted from resource data.

    Note: Since Issue #332, subnet resource names are VNet-scoped to prevent collisions.
    Terraform resource name: {vnet}_{subnet}, Azure name field: original subnet name.
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_standalone_subnet, terraform_config
    )

    assert result is not None
    _, resource_name, resource_config = result

    # Azure resource name should be preserved
    assert resource_config["name"] == "default"
    # Terraform resource name should be VNet-scoped (test_vnet_default)
    assert resource_name == "test_vnet_default"  # VNet-scoped sanitized name


def test_resource_group_extracted_from_properties(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify resource_group_name is extracted correctly.

    Expected to FAIL: No handler implementation exists yet.
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_standalone_subnet, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "resource_group_name" in resource_config
    assert resource_config["resource_group_name"] == "test-rg"


def test_virtual_network_name_extracted_from_id(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify VNet name is extracted from subnet ID.

    Expected to FAIL: No handler implementation exists yet.
    The subnet ID format is:
    /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Network/virtualNetworks/{vnet}/subnets/{subnet}
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_standalone_subnet, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "virtual_network_name" in resource_config
    # Should extract 'test-vnet' from the ID path
    assert (
        "test-vnet" in resource_config["virtual_network_name"]
        or "test_vnet" in resource_config["virtual_network_name"]
    )


def test_address_prefixes_parsed_from_json_string(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify addressPrefix is parsed from JSON properties string.

    Expected to FAIL: No handler implementation exists yet.
    Azure stores single CIDR as 'addressPrefix' (singular).
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_standalone_subnet, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "address_prefixes" in resource_config
    assert isinstance(resource_config["address_prefixes"], list)
    assert "10.0.1.0/24" in resource_config["address_prefixes"]


def test_address_prefixes_parsed_from_list(
    terraform_emitter: TerraformEmitter,
    sample_subnet_with_address_prefixes_list: Dict[str, Any],
) -> None:
    """Verify addressPrefixes (plural) is parsed from properties.

    Expected to FAIL: No handler implementation exists yet.
    Azure supports multiple CIDRs as 'addressPrefixes' (plural).
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_subnet_with_address_prefixes_list, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "address_prefixes" in resource_config
    assert isinstance(resource_config["address_prefixes"], list)
    assert len(resource_config["address_prefixes"]) == 2
    assert "10.0.4.0/24" in resource_config["address_prefixes"]
    assert "10.0.5.0/24" in resource_config["address_prefixes"]


# ============================================================================
# Test Group 3: VNet Linking (3 tests)
# ============================================================================


def test_subnet_references_parent_vnet_correctly(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify subnet uses correct Terraform reference to parent VNet.

    Expected to FAIL: No handler implementation exists yet.
    Should generate: ${azurerm_virtual_network.test_vnet.name}
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_standalone_subnet, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    assert "virtual_network_name" in resource_config

    # Should be a Terraform interpolation reference
    vnet_ref = resource_config["virtual_network_name"]
    assert "${" in vnet_ref and "}" in vnet_ref, "Should be a Terraform interpolation"
    assert "azurerm_virtual_network" in vnet_ref
    assert "test" in vnet_ref.lower() and "vnet" in vnet_ref.lower()


def test_vnet_name_sanitized_for_terraform(
    terraform_emitter: TerraformEmitter, sample_subnet_special_chars: Dict[str, Any]
) -> None:
    """Verify VNet name is sanitized when used in references.

    Expected to FAIL: No handler implementation exists yet.
    VNet name 'test-vnet' should become 'test_vnet' in Terraform.
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_subnet_special_chars, terraform_config
    )

    assert result is not None
    _, resource_name, resource_config = result

    # Resource name itself should be sanitized
    assert "-" not in resource_name
    assert "." not in resource_name

    # VNet reference should also be sanitized
    vnet_ref = resource_config.get("virtual_network_name", "")
    if "${" in vnet_ref:
        # Extract the resource name from ${azurerm_virtual_network.NAME.name}
        assert (
            "_" in vnet_ref
            or vnet_ref.replace("${", "")
            .replace("}", "")
            .replace("azurerm_virtual_network.", "")
            .replace(".name", "")
            .isalnum()
        )


def test_subnet_without_vnet_logs_warning(terraform_emitter: TerraformEmitter) -> None:
    """Verify warning is logged when subnet ID doesn't contain VNet name.

    Expected to FAIL: No handler implementation exists yet.
    Edge case: malformed subnet ID.
    """
    malformed_subnet = {
        "id": "/subscriptions/12345/resourceGroups/test-rg/subnets/orphan",  # Missing virtualNetworks segment
        "name": "orphan",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps({"addressPrefix": "10.0.0.0/24"}),
    }

    terraform_config = {"resource": {}}

    with patch("src.iac.emitters.terraform_emitter.logger") as mock_logger:
        terraform_emitter._convert_resource(malformed_subnet, terraform_config)

        # Should log a warning about missing VNet
        assert mock_logger.warning.called, "Should warn about missing VNet in subnet ID"


# ============================================================================
# Test Group 4: Edge Cases (3 tests)
# ============================================================================


def test_multiple_subnets_in_same_vnet(
    terraform_emitter: TerraformEmitter,
    sample_standalone_subnet: Dict[str, Any],
    sample_subnet_with_nsg: Dict[str, Any],
) -> None:
    """Verify multiple subnets from same VNet are generated correctly.

    Expected to FAIL: No handler implementation exists yet.
    All subnets should reference the same parent VNet.
    """
    graph = TenantGraph()
    graph.resources = [sample_standalone_subnet, sample_subnet_with_nsg]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Should have azurerm_subnet resources
        assert "azurerm_subnet" in terraform_config["resource"]

        subnets = terraform_config["resource"]["azurerm_subnet"]
        assert len(subnets) >= 2  # At least our two test subnets

        # Both should reference the same VNet
        vnet_refs = [subnet["virtual_network_name"] for subnet in subnets.values()]
        # All should contain 'test_vnet' or similar
        assert all("test" in ref.lower() for ref in vnet_refs)


def test_subnet_with_special_characters_in_name(
    terraform_emitter: TerraformEmitter, sample_subnet_special_chars: Dict[str, Any]
) -> None:
    """Verify subnet names with special characters are sanitized.

    Expected to FAIL: No handler implementation exists yet.
    'my-subnet.prod' should become 'my_subnet_prod'.
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_subnet_special_chars, terraform_config
    )

    assert result is not None
    _, resource_name, resource_config = result

    # Sanitized name should not contain hyphens or dots
    assert "-" not in resource_name
    assert "." not in resource_name
    assert "_" in resource_name or resource_name.isalnum()

    # Original name in config should be preserved
    assert resource_config["name"] == "my-subnet.prod"


def test_subnet_with_null_address_prefixes(terraform_emitter: TerraformEmitter) -> None:
    """Verify subnet without address prefixes is handled gracefully.

    Expected to FAIL: No handler implementation exists yet.
    Should either skip the resource or log a warning.
    """
    subnet_no_prefix = {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/no-prefix",
        "name": "no-prefix",
        "type": "Microsoft.Network/subnets",
        "location": "eastus",
        "resource_group": "test-rg",
        "properties": json.dumps({}),  # No addressPrefix or addressPrefixes
    }

    terraform_config = {"resource": {}}

    with patch("src.iac.emitters.terraform_emitter.logger") as mock_logger:
        result = terraform_emitter._convert_resource(subnet_no_prefix, terraform_config)

        # Should log a warning
        assert mock_logger.warning.called, "Should warn about missing address prefix"

        # Result should either be None (skipped) or have a default value
        if result is not None:
            _, _, resource_config = result
            assert "address_prefixes" in resource_config


# ============================================================================
# INTEGRATION TESTS (30% - 6 tests)
# Test Group 5: End-to-End Subnet Generation
# ============================================================================


def test_full_subnet_resource_block_generated(
    terraform_emitter: TerraformEmitter, sample_standalone_subnet: Dict[str, Any]
) -> None:
    """Verify complete Terraform JSON structure for subnet is generated.

    Note: Since Issue #332, subnet resource names are VNet-scoped.
    """
    graph = TenantGraph()
    graph.resources = [sample_standalone_subnet]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Check top-level structure
        assert "resource" in terraform_config
        assert "azurerm_subnet" in terraform_config["resource"]

        # Check subnet resource (VNet-scoped name: test_vnet_default)
        subnets = terraform_config["resource"]["azurerm_subnet"]
        assert "test_vnet_default" in subnets

        subnet = subnets["test_vnet_default"]

        # Verify all required fields
        assert subnet["name"] == "default"  # Azure name preserved
        assert subnet["resource_group_name"] == "test-rg"
        assert "virtual_network_name" in subnet
        assert "address_prefixes" in subnet
        assert isinstance(subnet["address_prefixes"], list)
        assert len(subnet["address_prefixes"]) == 1
        assert subnet["address_prefixes"][0] == "10.0.1.0/24"


def test_nic_references_generated_subnet_correctly(
    terraform_emitter: TerraformEmitter,
    sample_standalone_subnet: Dict[str, Any],
    sample_network_interface: Dict[str, Any],
) -> None:
    """Verify NIC can reference the generated subnet resource.

    Note: Since Issue #332, subnet references use VNet-scoped names.
    """
    graph = TenantGraph()
    graph.resources = [sample_standalone_subnet, sample_network_interface]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify subnet exists (VNet-scoped name)
        assert "azurerm_subnet" in terraform_config["resource"]
        assert "test_vnet_default" in terraform_config["resource"]["azurerm_subnet"]

        # Verify NIC exists
        assert "azurerm_network_interface" in terraform_config["resource"]

        # Verify NIC references the subnet (with VNet-scoped name)
        nic = next(
            iter(terraform_config["resource"]["azurerm_network_interface"].values())
        )
        subnet_id = nic["ip_configuration"]["subnet_id"]

        # Should be a Terraform reference with VNet-scoped name
        assert "${azurerm_subnet.test_vnet_default.id}" in subnet_id


@pytest.mark.skipif(
    not Path("/usr/local/bin/terraform").exists()
    and not Path("/usr/bin/terraform").exists(),
    reason="Terraform CLI not installed",
)
def test_terraform_validate_passes_with_subnets(
    terraform_emitter: TerraformEmitter,
    sample_standalone_subnet: Dict[str, Any],
    sample_network_interface: Dict[str, Any],
    sample_vnet_with_embedded_subnets: Dict[str, Any],
) -> None:
    """Verify generated Terraform passes terraform validate.

    Includes VNet resource so subnet can reference it.
    """
    graph = TenantGraph()
    graph.resources = [sample_vnet_with_embedded_subnets, sample_standalone_subnet, sample_network_interface]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        terraform_emitter.emit(graph, out_dir)

        # Run terraform init and validate
        import subprocess

        init_result = subprocess.run(
            ["terraform", "init"],
            cwd=out_dir,
            capture_output=True,
            text=True,
        )
        assert init_result.returncode == 0, (
            f"Terraform init failed: {init_result.stderr}"
        )

        validate_result = subprocess.run(
            ["terraform", "validate"],
            cwd=out_dir,
            capture_output=True,
            text=True,
        )

        # Should pass validation
        assert validate_result.returncode == 0, (
            f"Terraform validation failed: {validate_result.stdout}\n{validate_result.stderr}"
        )


# ============================================================================
# Test Group 6: Multi-Resource Scenarios
# ============================================================================


def test_vnet_with_embedded_and_standalone_subnets(
    terraform_emitter: TerraformEmitter,
    sample_vnet_with_embedded_subnets: Dict[str, Any],
    sample_standalone_subnet: Dict[str, Any],
) -> None:
    """Verify both embedded and standalone subnets can coexist.

    Expected to FAIL: Currently only embedded subnets are generated.
    After fix, both types should appear in azurerm_subnet resources.
    """
    graph = TenantGraph()
    graph.resources = [sample_vnet_with_embedded_subnets, sample_standalone_subnet]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Should have azurerm_subnet resources
        assert "azurerm_subnet" in terraform_config["resource"]

        subnets = terraform_config["resource"]["azurerm_subnet"]

        # Should have at least 2 subnets: 1 embedded + 1 standalone
        assert len(subnets) >= 2

        # Check for embedded subnet
        assert any("embedded" in name for name in subnets.keys())

        # Check for standalone subnet
        assert any("default" in name for name in subnets.keys())


def test_subnet_nsg_associations(
    terraform_emitter: TerraformEmitter, sample_subnet_with_nsg: Dict[str, Any]
) -> None:
    """Verify subnet with NSG association generates separate association resource.

    Since azurerm v3.0+, NSG associations must be separate resources, not inline.
    This test verifies the NSG association is tracked and will be emitted separately.
    """
    # Create a full graph to trigger the emit logic
    graph = TenantGraph()
    graph.resources = [
        sample_subnet_with_nsg,
        {
            "type": "Microsoft.Network/networkSecurityGroups",
            "name": "test-nsg",
            "location": "eastus",
            "resource_group": "test-rg",
        }
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Subnet should NOT have inline network_security_group_id (deprecated in v3.0+)
        subnet = terraform_config["resource"]["azurerm_subnet"]["test_vnet_secure_subnet"]
        assert "network_security_group_id" not in subnet, (
            "Subnet should not have deprecated inline network_security_group_id"
        )

        # Should have separate NSG association resource
        assert "azurerm_subnet_network_security_group_association" in terraform_config["resource"]

        nsg_associations = terraform_config["resource"]["azurerm_subnet_network_security_group_association"]
        assert len(nsg_associations) == 1

        # Get the association resource
        assoc = next(iter(nsg_associations.values()))

        # Verify it references both subnet and NSG correctly
        assert "subnet_id" in assoc
        assert "${azurerm_subnet.test_vnet_secure_subnet.id}" in assoc["subnet_id"]
        assert "network_security_group_id" in assoc
        assert "${azurerm_network_security_group.test_nsg.id}" in assoc["network_security_group_id"]


def test_subnet_service_endpoints(
    terraform_emitter: TerraformEmitter,
    sample_subnet_with_service_endpoints: Dict[str, Any],
) -> None:
    """Verify subnet with service endpoints includes them in config.

    Expected to FAIL: No handler implementation exists yet.
    Should extract service endpoints array from properties.
    """
    terraform_config = {"resource": {}}
    result = terraform_emitter._convert_resource(
        sample_subnet_with_service_endpoints, terraform_config
    )

    assert result is not None
    _, _, resource_config = result

    # Should include service endpoints
    assert "service_endpoints" in resource_config

    endpoints = resource_config["service_endpoints"]
    assert isinstance(endpoints, list)
    assert len(endpoints) == 2
    assert "Microsoft.Storage" in endpoints
    assert "Microsoft.Sql" in endpoints


# ============================================================================
# E2E TESTS (10% - 2 tests)
# ============================================================================


@pytest.mark.integration
def test_real_azure_subnet_data_generates_valid_terraform(
    terraform_emitter: TerraformEmitter,
) -> None:
    """Test with realistic Azure subnet data from Neo4j.

    Note: Since Issue #332, subnet resource names are VNet-scoped.
    """
    # Realistic subnet data as it would come from Azure API
    realistic_subnet = {
        "id": "/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/resourceGroups/production-rg/providers/Microsoft.Network/virtualNetworks/prod-vnet/subnets/app-subnet",
        "name": "app-subnet",
        "type": "Microsoft.Network/subnets",
        "location": "eastus2",
        "resource_group": "production-rg",
        "properties": json.dumps(
            {
                "provisioningState": "Succeeded",
                "addressPrefix": "10.10.1.0/24",
                "networkSecurityGroup": {
                    "id": "/subscriptions/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee/resourceGroups/production-rg/providers/Microsoft.Network/networkSecurityGroups/app-nsg"
                },
                "serviceEndpoints": [
                    {
                        "service": "Microsoft.Storage",
                        "locations": ["eastus2", "westus2"],
                    },
                    {
                        "service": "Microsoft.KeyVault",
                        "locations": ["eastus2"],
                    },
                ],
                "delegations": [],
                "privateEndpointNetworkPolicies": "Enabled",
                "privateLinkServiceNetworkPolicies": "Enabled",
            }
        ),
    }

    graph = TenantGraph()
    graph.resources = [realistic_subnet]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify structure
        assert "azurerm_subnet" in terraform_config["resource"]

        # VNet-scoped name: prod_vnet_app_subnet
        subnet = terraform_config["resource"]["azurerm_subnet"]["prod_vnet_app_subnet"]

        # Verify all fields
        assert subnet["name"] == "app-subnet"  # Azure name preserved
        assert subnet["resource_group_name"] == "production-rg"
        assert "10.10.1.0/24" in subnet["address_prefixes"]
        assert "service_endpoints" in subnet
        assert "Microsoft.Storage" in subnet["service_endpoints"]
        assert "Microsoft.KeyVault" in subnet["service_endpoints"]


@pytest.mark.integration
def test_complete_vnet_topology_with_subnets_nics_vms(
    terraform_emitter: TerraformEmitter,
    sample_vnet_with_embedded_subnets: Dict[str, Any],
    sample_standalone_subnet: Dict[str, Any],
    sample_network_interface: Dict[str, Any],
) -> None:
    """Test complete network topology: VNet -> Subnets -> NICs -> VMs.

    Expected to FAIL: Without standalone subnet generation, the dependency
    chain is broken and Terraform validation will fail.
    """
    # Add a VM that uses the NIC
    vm_resource = {
        "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/test-vm",
        "name": "test-vm",
        "type": "Microsoft.Compute/virtualMachines",
        "location": "eastus",
        "resource_group": "test-rg",
        "size": "Standard_B2s",
        "properties": json.dumps(
            {
                "hardwareProfile": {"vmSize": "Standard_B2s"},
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/12345/resourceGroups/test-rg/providers/Microsoft.Network/networkInterfaces/test-nic"
                        }
                    ]
                },
            }
        ),
    }

    graph = TenantGraph()
    graph.resources = [
        sample_vnet_with_embedded_subnets,
        sample_standalone_subnet,
        sample_network_interface,
        vm_resource,
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        out_dir = Path(temp_dir)
        written_files = terraform_emitter.emit(graph, out_dir)

        with open(written_files[0]) as f:
            terraform_config = json.load(f)

        # Verify all resource types exist
        assert "azurerm_virtual_network" in terraform_config["resource"]
        assert "azurerm_subnet" in terraform_config["resource"]
        assert "azurerm_network_interface" in terraform_config["resource"]
        assert "azurerm_linux_virtual_machine" in terraform_config["resource"]

        # Verify dependency chain
        terraform_config["resource"]["azurerm_subnet"]
        nics = terraform_config["resource"]["azurerm_network_interface"]
        vms = terraform_config["resource"]["azurerm_linux_virtual_machine"]

        # NICs should reference subnets
        nic = next(iter(nics.values()))
        assert "${azurerm_subnet." in nic["ip_configuration"]["subnet_id"]

        # VMs should reference NICs
        vm = next(iter(vms.values()))
        assert "${azurerm_network_interface." in str(vm["network_interface_ids"])


# ============================================================================
# EXPECTED FAILURE MESSAGES
# ============================================================================


"""
EXPECTED FAILURE MESSAGES WHEN RUNNING THESE TESTS (RED PHASE):

1. test_standalone_subnet_is_detected:
   AssertionError: Standalone subnet should be detected and converted

2. test_subnet_type_mapping:
   AssertionError: Subnet conversion should return a result

3. test_subnet_with_missing_properties_handled:
   AssertionError: result is None and no warning was logged

4. test_subnet_name_extracted_correctly:
   AssertionError: result is None (cannot unpack)

5. test_resource_group_extracted_from_properties:
   AssertionError: result is None (cannot unpack)

6. test_virtual_network_name_extracted_from_id:
   AssertionError: result is None (cannot unpack)

7. test_address_prefixes_parsed_from_json_string:
   AssertionError: result is None (cannot unpack)

8. test_address_prefixes_parsed_from_list:
   AssertionError: result is None (cannot unpack)

9. test_subnet_references_parent_vnet_correctly:
   AssertionError: result is None (cannot unpack)

10. test_vnet_name_sanitized_for_terraform:
    AssertionError: result is None (cannot unpack)

11. test_subnet_without_vnet_logs_warning:
    AssertionError: Should warn about missing VNet in subnet ID

12. test_multiple_subnets_in_same_vnet:
    KeyError: 'azurerm_subnet' (not in terraform_config["resource"])

13. test_subnet_with_special_characters_in_name:
    AssertionError: result is None (cannot unpack)

14. test_subnet_with_null_address_prefixes:
    AssertionError: Should warn about missing address prefix

15. test_full_subnet_resource_block_generated:
    KeyError: 'azurerm_subnet' (not in terraform_config["resource"])

16. test_nic_references_generated_subnet_correctly:
    KeyError: 'azurerm_subnet' (not in terraform_config["resource"])

17. test_terraform_validate_passes_with_subnets:
    AssertionError: Terraform validation failed: Error: Reference to undeclared resource

18. test_vnet_with_embedded_and_standalone_subnets:
    AssertionError: len(subnets) >= 2 failed (only 1 embedded subnet exists)

19. test_subnet_nsg_associations:
    AssertionError: result is None (cannot unpack)

20. test_subnet_service_endpoints:
    AssertionError: result is None (cannot unpack)

21. test_real_azure_subnet_data_generates_valid_terraform:
    KeyError: 'azurerm_subnet' (not in terraform_config["resource"])

22. test_complete_vnet_topology_with_subnets_nics_vms:
    KeyError: 'azurerm_subnet' (not in terraform_config["resource"])

ROOT CAUSE:
All failures trace back to the fact that TerraformEmitter._convert_resource()
has no handler for Microsoft.Network/subnets. The method returns None on line
180-185 because there's no elif branch for subnet processing.

The mapping exists in AZURE_TO_TERRAFORM_MAPPING (line 27), but without
a handler implementation, subnets are skipped during IaC generation.
"""
