"""Unit tests for CTFImportService.

Tests Terraform parsing and resource mapping logic following TDD methodology.
These tests should FAIL initially until implementation is complete.

Coverage areas:
- Terraform state file parsing
- Resource mapping from Terraform to Neo4j
- Handling missing resources (warnings, not failures)
- Tag extraction and CTF property mapping
- Error handling for invalid Terraform files
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, mock_open
from typing import Dict, Any, List
import json


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver for testing."""
    driver = Mock()
    driver.execute_query = Mock(return_value=([], None, None))
    return driver


@pytest.fixture
def sample_terraform_state():
    """Sample Terraform state file content."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "azurerm_virtual_machine",
                "name": "target",
                "provider": "provider[\"registry.terraform.io/hashicorp/azurerm\"]",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/target-vm",
                            "name": "target-vm",
                            "location": "eastus",
                            "resource_group_name": "test-rg",
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v2-cert",
                                "ctf_role": "target"
                            }
                        }
                    }
                ]
            },
            {
                "mode": "managed",
                "type": "azurerm_virtual_network",
                "name": "ctf_vnet",
                "provider": "provider[\"registry.terraform.io/hashicorp/azurerm\"]",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/ctf-vnet",
                            "name": "ctf-vnet",
                            "location": "eastus",
                            "resource_group_name": "test-rg",
                            "tags": {
                                "layer_id": "default",
                                "ctf_exercise": "M003",
                                "ctf_scenario": "v2-cert",
                                "ctf_role": "infrastructure"
                            }
                        }
                    }
                ]
            }
        ]
    }


@pytest.fixture
def sample_terraform_state_missing_tags():
    """Terraform state with resources missing CTF tags."""
    return {
        "version": 4,
        "terraform_version": "1.5.0",
        "resources": [
            {
                "mode": "managed",
                "type": "azurerm_storage_account",
                "name": "storage",
                "instances": [
                    {
                        "attributes": {
                            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Storage/storageAccounts/teststorage",
                            "name": "teststorage",
                            "location": "eastus",
                            "tags": {}  # No CTF tags
                        }
                    }
                ]
            }
        ]
    }


# ============================================================================
# CTFImportService Tests (WILL FAIL - No Implementation Yet)
# ============================================================================


class TestCTFImportServiceInit:
    """Test CTFImportService initialization."""

    def test_service_creation_with_driver(self, mock_neo4j_driver):
        """Test service can be created with Neo4j driver."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)
        assert service is not None
        assert service.neo4j_driver == mock_neo4j_driver

    def test_service_creation_without_driver_uses_default(self):
        """Test service can use default driver if none provided."""
        from src.services.ctf_import_service import CTFImportService

        with patch('src.services.ctf_import_service.get_neo4j_driver') as mock_get_driver:
            mock_get_driver.return_value = Mock()
            service = CTFImportService()
            assert service.neo4j_driver is not None


class TestParseTerraformState:
    """Test Terraform state file parsing."""

    def test_parse_valid_terraform_state(self, sample_terraform_state):
        """Test parsing a valid Terraform state file."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        # Mock file reading
        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state))):
            resources = service.parse_terraform_state("terraform.tfstate")

            assert len(resources) == 2
            assert resources[0]["type"] == "azurerm_virtual_machine"
            assert resources[1]["type"] == "azurerm_virtual_network"

    def test_parse_terraform_state_file_not_found(self):
        """Test parsing non-existent Terraform state file."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        with pytest.raises(FileNotFoundError, match="terraform.tfstate"):
            service.parse_terraform_state("nonexistent.tfstate")

    def test_parse_terraform_state_invalid_json(self):
        """Test parsing Terraform state with invalid JSON."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        with patch('builtins.open', mock_open(read_data="invalid json{")):
            with pytest.raises(ValueError, match="Invalid JSON"):
                service.parse_terraform_state("invalid.tfstate")

    def test_parse_terraform_state_missing_resources_key(self):
        """Test parsing Terraform state missing 'resources' key."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        invalid_state = {"version": 4, "terraform_version": "1.5.0"}  # No resources

        with patch('builtins.open', mock_open(read_data=json.dumps(invalid_state))):
            resources = service.parse_terraform_state("terraform.tfstate")
            # Should return empty list, not fail
            assert resources == []

    def test_parse_terraform_state_extracts_instances(self, sample_terraform_state):
        """Test parsing extracts all resource instances."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state))):
            resources = service.parse_terraform_state("terraform.tfstate")

            # Should extract instances from each resource
            for resource in resources:
                assert "attributes" in resource
                assert "id" in resource["attributes"]
                assert "name" in resource["attributes"]

    def test_parse_terraform_state_handles_multiple_instances(self):
        """Test parsing resource with multiple instances (count/for_each)."""
        from src.services.ctf_import_service import CTFImportService

        state_with_multiple = {
            "resources": [
                {
                    "type": "azurerm_virtual_machine",
                    "name": "vm",
                    "instances": [
                        {"attributes": {"id": "vm-1", "name": "vm-1"}},
                        {"attributes": {"id": "vm-2", "name": "vm-2"}},
                        {"attributes": {"id": "vm-3", "name": "vm-3"}},
                    ]
                }
            ]
        }

        service = CTFImportService(neo4j_driver=Mock())

        with patch('builtins.open', mock_open(read_data=json.dumps(state_with_multiple))):
            resources = service.parse_terraform_state("terraform.tfstate")

            # Should return all instances as separate resources
            assert len(resources) == 3
            assert resources[0]["attributes"]["id"] == "vm-1"
            assert resources[1]["attributes"]["id"] == "vm-2"
            assert resources[2]["attributes"]["id"] == "vm-3"


class TestExtractCTFProperties:
    """Test CTF property extraction from Terraform tags."""

    def test_extract_all_ctf_properties_from_tags(self):
        """Test extracting all CTF properties from resource tags."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        resource = {
            "attributes": {
                "tags": {
                    "layer_id": "default",
                    "ctf_exercise": "M003",
                    "ctf_scenario": "v2-cert",
                    "ctf_role": "target"
                }
            }
        }

        ctf_props = service.extract_ctf_properties(resource)

        assert ctf_props["layer_id"] == "default"
        assert ctf_props["ctf_exercise"] == "M003"
        assert ctf_props["ctf_scenario"] == "v2-cert"
        assert ctf_props["ctf_role"] == "target"

    def test_extract_ctf_properties_missing_tags(self):
        """Test extraction when resource has no tags."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        resource = {"attributes": {}}  # No tags

        ctf_props = service.extract_ctf_properties(resource)

        # Should return None for missing properties
        assert ctf_props["layer_id"] is None
        assert ctf_props["ctf_exercise"] is None
        assert ctf_props["ctf_scenario"] is None
        assert ctf_props["ctf_role"] is None

    def test_extract_ctf_properties_partial_tags(self):
        """Test extraction with only some CTF tags present."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        resource = {
            "attributes": {
                "tags": {
                    "layer_id": "default",
                    "ctf_exercise": "M003"
                    # Missing scenario and role
                }
            }
        }

        ctf_props = service.extract_ctf_properties(resource)

        assert ctf_props["layer_id"] == "default"
        assert ctf_props["ctf_exercise"] == "M003"
        assert ctf_props["ctf_scenario"] is None
        assert ctf_props["ctf_role"] is None

    def test_extract_ctf_properties_with_other_tags(self):
        """Test extraction ignores non-CTF tags."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        resource = {
            "attributes": {
                "tags": {
                    "Environment": "Production",
                    "Owner": "Security Team",
                    "layer_id": "default",
                    "ctf_exercise": "M003",
                    "CostCenter": "12345"
                }
            }
        }

        ctf_props = service.extract_ctf_properties(resource)

        # Should only extract CTF properties
        assert "Environment" not in ctf_props
        assert "Owner" not in ctf_props
        assert "CostCenter" not in ctf_props
        assert ctf_props["layer_id"] == "default"
        assert ctf_props["ctf_exercise"] == "M003"


class TestMapResourceToNeo4j:
    """Test mapping Terraform resources to Neo4j format."""

    def test_map_resource_complete_data(self):
        """Test mapping resource with complete data."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        terraform_resource = {
            "type": "azurerm_virtual_machine",
            "name": "target",
            "attributes": {
                "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/target-vm",
                "name": "target-vm",
                "location": "eastus",
                "tags": {
                    "layer_id": "default",
                    "ctf_exercise": "M003",
                    "ctf_scenario": "v2-cert",
                    "ctf_role": "target"
                }
            }
        }

        neo4j_resource = service.map_resource_to_neo4j(terraform_resource)

        assert neo4j_resource["id"] == "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Compute/virtualMachines/target-vm"
        assert neo4j_resource["name"] == "target-vm"
        assert neo4j_resource["resource_type"] == "azurerm_virtual_machine"
        assert neo4j_resource["location"] == "eastus"
        assert neo4j_resource["layer_id"] == "default"
        assert neo4j_resource["ctf_exercise"] == "M003"
        assert neo4j_resource["ctf_scenario"] == "v2-cert"
        assert neo4j_resource["ctf_role"] == "target"

    def test_map_resource_missing_optional_fields(self):
        """Test mapping resource with missing optional fields."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        minimal_resource = {
            "type": "azurerm_resource_group",
            "name": "rg",
            "attributes": {
                "id": "/subscriptions/test-sub/resourceGroups/test-rg",
                "name": "test-rg"
                # Missing location, tags
            }
        }

        neo4j_resource = service.map_resource_to_neo4j(minimal_resource)

        assert neo4j_resource["id"] == "/subscriptions/test-sub/resourceGroups/test-rg"
        assert neo4j_resource["name"] == "test-rg"
        assert neo4j_resource.get("location") is None
        assert neo4j_resource.get("layer_id") is None

    def test_map_resource_normalizes_resource_type(self):
        """Test resource type normalization (Terraform → Azure format)."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=Mock())

        terraform_types_to_azure = [
            ("azurerm_virtual_machine", "Microsoft.Compute/virtualMachines"),
            ("azurerm_virtual_network", "Microsoft.Network/virtualNetworks"),
            ("azurerm_storage_account", "Microsoft.Storage/storageAccounts"),
        ]

        for tf_type, expected_azure_type in terraform_types_to_azure:
            resource = {
                "type": tf_type,
                "attributes": {"id": "test-id", "name": "test-name"}
            }
            mapped = service.map_resource_to_neo4j(resource)
            # Should normalize to Azure format or keep Terraform format consistently
            assert mapped["resource_type"] in [tf_type, expected_azure_type]


class TestImportFromState:
    """Test complete import workflow from Terraform state."""

    def test_import_from_state_success(self, mock_neo4j_driver, sample_terraform_state):
        """Test successful import of Terraform state."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state))):
            stats = service.import_from_state(
                state_file="terraform.tfstate",
                layer_id="default"
            )

            assert stats["resources_created"] == 2
            assert stats["resources_updated"] == 0
            assert stats["errors"] == 0

            # Verify Neo4j query was called
            mock_neo4j_driver.execute_query.assert_called()

    def test_import_from_state_with_layer_id_override(self, mock_neo4j_driver, sample_terraform_state):
        """Test import with layer_id override (overrides Terraform tags)."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state))):
            service.import_from_state(
                state_file="terraform.tfstate",
                layer_id="custom-layer"  # Override
            )

            # Should use custom layer_id, not tag value
            call_args = mock_neo4j_driver.execute_query.call_args
            assert "custom-layer" in str(call_args)

    def test_import_from_state_handles_missing_tags_gracefully(
        self, mock_neo4j_driver, sample_terraform_state_missing_tags
    ):
        """Test import handles resources without CTF tags (warning, not failure)."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state_missing_tags))):
            with patch('logging.warning') as mock_warning:
                stats = service.import_from_state(
                    state_file="terraform.tfstate",
                    layer_id="default"
                )

                # Should succeed but log warning
                assert stats["resources_created"] == 1
                assert stats["warnings"] == 1
                mock_warning.assert_called()

    def test_import_from_state_idempotent(self, mock_neo4j_driver, sample_terraform_state):
        """Test importing same state twice is idempotent."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state))):
            # First import
            stats1 = service.import_from_state(
                state_file="terraform.tfstate",
                layer_id="default"
            )

            # Second import (same data)
            stats2 = service.import_from_state(
                state_file="terraform.tfstate",
                layer_id="default"
            )

            # First creates, second updates
            assert stats1["resources_created"] == 2
            assert stats2["resources_updated"] == 2
            assert stats2["resources_created"] == 0

    def test_import_from_state_batch_operation(self, mock_neo4j_driver, sample_terraform_state):
        """Test import uses batch operation for performance."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        with patch('builtins.open', mock_open(read_data=json.dumps(sample_terraform_state))):
            service.import_from_state(
                state_file="terraform.tfstate",
                layer_id="default"
            )

            # Should use UNWIND for batch operation
            call_args = mock_neo4j_driver.execute_query.call_args
            query = call_args[0][0]
            assert "UNWIND" in query or mock_neo4j_driver.execute_query.call_count == 1


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_import_neo4j_connection_failure(self, mock_neo4j_driver):
        """Test handling Neo4j connection failures during import."""
        from src.services.ctf_import_service import CTFImportService
        from neo4j.exceptions import ServiceUnavailable

        mock_neo4j_driver.execute_query.side_effect = ServiceUnavailable("Connection failed")

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        state = {"resources": [{"type": "test", "instances": [{"attributes": {"id": "1"}}]}]}

        with patch('builtins.open', mock_open(read_data=json.dumps(state))):
            with pytest.raises(ServiceUnavailable):
                service.import_from_state("terraform.tfstate", layer_id="default")

    def test_import_partial_failure_continues(self, mock_neo4j_driver):
        """Test import continues after partial failures."""
        from src.services.ctf_import_service import CTFImportService

        # Simulate one resource failing
        call_count = [0]

        def mock_execute_with_failure(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Simulated failure")
            return ([], None, None)

        mock_neo4j_driver.execute_query.side_effect = mock_execute_with_failure

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        state = {
            "resources": [
                {"type": "test1", "instances": [{"attributes": {"id": "1"}}]},
                {"type": "test2", "instances": [{"attributes": {"id": "2"}}]},
            ]
        }

        with patch('builtins.open', mock_open(read_data=json.dumps(state))):
            stats = service.import_from_state("terraform.tfstate", layer_id="default")

            # Should have some failures but continue
            assert stats["errors"] > 0
            assert stats["resources_created"] >= 0

    def test_import_validates_required_fields(self, mock_neo4j_driver):
        """Test import validates required fields before Neo4j insertion."""
        from src.services.ctf_import_service import CTFImportService

        service = CTFImportService(neo4j_driver=mock_neo4j_driver)

        invalid_resource = {
            "type": "azurerm_vm",
            "instances": [
                {"attributes": {}}  # Missing 'id' and 'name'
            ]
        }

        state = {"resources": [invalid_resource]}

        with patch('builtins.open', mock_open(read_data=json.dumps(state))):
            stats = service.import_from_state("terraform.tfstate", layer_id="default")

            # Should log error but not crash
            assert stats["errors"] == 1
            assert stats["resources_created"] == 0


# ============================================================================
# Test Summary
# ============================================================================
"""
Test Coverage Summary:

✓ Service initialization (2 tests)
✓ Terraform state parsing (6 tests)
✓ CTF property extraction (4 tests)
✓ Resource mapping (3 tests)
✓ Import workflow (6 tests)
✓ Error handling (3 tests)

Total: 24 unit tests

All tests should FAIL initially until CTFImportService is implemented.

Expected test results after implementation:
- 100% should pass
- Coverage target: 90%+ of ctf_import_service.py
"""
