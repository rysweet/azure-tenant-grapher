"""Unit tests for NSG Association handler to verify no duplicate emissions.

Testing Strategy (TDD - 60% Unit Tests):
- Test NSG associations are emitted via handler (not legacy code)
- Test no duplicate NSG association emissions occur
- Test cross-resource-group associations are skipped (Bug #13 preserved)
- Test subnet and NIC associations are properly validated

These tests verify the fix removes legacy _emit_deferred_resources() method
while preserving all functionality through the handler-based architecture.
"""

import logging
from typing import Any, Dict
from unittest.mock import Mock

import pytest

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import HandlerRegistry, ensure_handlers_registered
from src.iac.emitters.terraform.handlers.network.nsg_associations import (
    NSGAssociationHandler,
)


class TestNSGAssociationHandlerBasics:
    """Unit tests for NSG Association handler basics (60% - Unit)."""

    def setup_method(self):
        """Setup test environment."""
        self.handler = NSGAssociationHandler()
        self.context = EmitterContext()

    def test_nsg_association_handler_exists(self):
        """Test that NSGAssociationHandler class exists."""
        assert NSGAssociationHandler is not None
        assert hasattr(NSGAssociationHandler, "HANDLED_TYPES")
        assert len(NSGAssociationHandler.HANDLED_TYPES) == 0  # No direct Azure types

    def test_nsg_association_handler_registered(self):
        """Test that NSGAssociationHandler is registered."""
        ensure_handlers_registered()

        all_handlers = HandlerRegistry.get_all_handlers()
        handler_names = [h.__name__ for h in all_handlers]

        assert "NSGAssociationHandler" in handler_names, (
            f"NSGAssociationHandler not registered. Handlers: {handler_names}"
        )

    def test_nsg_association_handler_has_terraform_types(self):
        """Test that NSGAssociationHandler declares its Terraform types."""
        expected_types = {
            "azurerm_subnet_network_security_group_association",
            "azurerm_network_interface_security_group_association",
        }

        assert NSGAssociationHandler.TERRAFORM_TYPES == expected_types

    def test_emit_returns_none(self):
        """Test that emit() always returns None (associations via post_emit)."""
        resource = {"type": "Microsoft.Network/virtualNetworks"}
        result = self.handler.emit(resource, self.context)
        assert result is None


class TestNSGAssociationHandlerSubnetAssociations:
    """Unit tests for subnet-NSG association emission (60% - Unit)."""

    def setup_method(self):
        """Setup test environment."""
        self.handler = NSGAssociationHandler()
        self.context = EmitterContext()

        # Setup mock terraform config with subnet and NSG
        self.context.terraform_config = {
            "resource": {
                "azurerm_subnet": {
                    "test_subnet": {
                        "name": "test-subnet",
                        "resource_group_name": "test-rg",
                    }
                },
                "azurerm_network_security_group": {
                    "test_nsg": {
                        "name": "test-nsg",
                        "resource_group_name": "test-rg",
                    }
                },
            }
        }

        # Track available subnets
        self.context.available_subnets = {"test_subnet"}

    def test_post_emit_creates_subnet_nsg_association(self):
        """Test that post_emit creates subnet-NSG association resource."""
        # Track an association
        self.context.nsg_associations.append(
            ("test_subnet", "test_nsg", "test-subnet", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify association was added
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        assert len(associations) == 1
        assoc_name = "test_subnet_test_nsg"
        assert assoc_name in associations

        assoc_config = associations[assoc_name]
        assert assoc_config["subnet_id"] == "${azurerm_subnet.test_subnet.id}"
        assert (
            assoc_config["network_security_group_id"]
            == "${azurerm_network_security_group.test_nsg.id}"
        )

    def test_post_emit_skips_cross_resource_group_subnet_associations(self):
        """Test that cross-RG subnet-NSG associations are skipped (Bug #13).

        THIS IS CRITICAL:
        Bug #13 fix must be preserved - cross-RG associations should be skipped.
        """
        # Setup subnet and NSG in different resource groups
        self.context.terraform_config["resource"]["azurerm_subnet"]["test_subnet"][
            "resource_group_name"
        ] = "rg1"
        self.context.terraform_config["resource"]["azurerm_network_security_group"][
            "test_nsg"
        ]["resource_group_name"] = "rg2"

        # Track an association
        self.context.nsg_associations.append(
            ("test_subnet", "test_nsg", "test-subnet", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify NO association was added (cross-RG skipped)
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        assert len(associations) == 0, (
            "Cross-RG subnet-NSG association should be skipped (Bug #13)"
        )

    def test_post_emit_skips_missing_subnet(self):
        """Test that associations with missing subnets are skipped."""
        # Track an association but don't register subnet as available
        self.context.available_subnets = set()  # Empty - subnet not available

        self.context.nsg_associations.append(
            ("missing_subnet", "test_nsg", "missing-subnet", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify NO association was added
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        assert len(associations) == 0

    def test_post_emit_skips_missing_nsg(self):
        """Test that associations with missing NSGs are skipped."""
        # Remove NSG from terraform config
        self.context.terraform_config["resource"]["azurerm_network_security_group"] = {}

        self.context.nsg_associations.append(
            ("test_subnet", "test_nsg", "test-subnet", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify NO association was added
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_subnet_network_security_group_association", {}
        )

        assert len(associations) == 0


class TestNSGAssociationHandlerNICAssociations:
    """Unit tests for NIC-NSG association emission (60% - Unit)."""

    def setup_method(self):
        """Setup test environment."""
        self.handler = NSGAssociationHandler()
        self.context = EmitterContext()

        # Setup mock terraform config with NIC and NSG
        self.context.terraform_config = {
            "resource": {
                "azurerm_network_interface": {
                    "test_nic": {
                        "name": "test-nic",
                        "resource_group_name": "test-rg",
                    }
                },
                "azurerm_network_security_group": {
                    "test_nsg": {
                        "name": "test-nsg",
                        "resource_group_name": "test-rg",
                    }
                },
            }
        }

    def test_post_emit_creates_nic_nsg_association(self):
        """Test that post_emit creates NIC-NSG association resource."""
        # Track an association
        self.context.nic_nsg_associations.append(
            ("test_nic", "test_nsg", "test-nic", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify association was added
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_network_interface_security_group_association", {}
        )

        assert len(associations) == 1
        assoc_name = "test_nic_test_nsg"
        assert assoc_name in associations

        assoc_config = associations[assoc_name]
        assert (
            assoc_config["network_interface_id"]
            == "${azurerm_network_interface.test_nic.id}"
        )
        assert (
            assoc_config["network_security_group_id"]
            == "${azurerm_network_security_group.test_nsg.id}"
        )

    def test_post_emit_skips_cross_resource_group_nic_associations(self):
        """Test that cross-RG NIC-NSG associations are skipped (Bug #13).

        THIS IS CRITICAL:
        Bug #13 fix must be preserved - cross-RG associations should be skipped.
        """
        # Setup NIC and NSG in different resource groups
        self.context.terraform_config["resource"]["azurerm_network_interface"][
            "test_nic"
        ]["resource_group_name"] = "rg1"
        self.context.terraform_config["resource"]["azurerm_network_security_group"][
            "test_nsg"
        ]["resource_group_name"] = "rg2"

        # Track an association
        self.context.nic_nsg_associations.append(
            ("test_nic", "test_nsg", "test-nic", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify NO association was added (cross-RG skipped)
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_network_interface_security_group_association", {}
        )

        assert len(associations) == 0, (
            "Cross-RG NIC-NSG association should be skipped (Bug #13)"
        )

    def test_post_emit_skips_missing_nic(self):
        """Test that associations with missing NICs are skipped."""
        # Remove NIC from terraform config
        self.context.terraform_config["resource"]["azurerm_network_interface"] = {}

        self.context.nic_nsg_associations.append(
            ("test_nic", "test_nsg", "test-nic", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify NO association was added
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_network_interface_security_group_association", {}
        )

        assert len(associations) == 0

    def test_post_emit_skips_missing_nsg(self):
        """Test that associations with missing NSGs are skipped."""
        # Remove NSG from terraform config
        self.context.terraform_config["resource"]["azurerm_network_security_group"] = {}

        self.context.nic_nsg_associations.append(
            ("test_nic", "test_nsg", "test-nic", "test-nsg")
        )

        # Call post_emit
        self.handler.post_emit(self.context)

        # Verify NO association was added
        associations = self.context.terraform_config.get("resource", {}).get(
            "azurerm_network_interface_security_group_association", {}
        )

        assert len(associations) == 0


class TestNSGAssociationValidation:
    """Unit tests for NSG association validation logic (60% - Unit)."""

    def setup_method(self):
        """Setup test environment."""
        self.handler = NSGAssociationHandler()
        self.context = EmitterContext()

        # Setup basic resources
        self.context.terraform_config = {
            "resource": {
                "azurerm_subnet": {"test_subnet": {}},
                "azurerm_network_interface": {"test_nic": {}},
                "azurerm_network_security_group": {"test_nsg": {}},
            }
        }
        self.context.available_subnets = {"test_subnet"}

    def test_validate_association_resources_subnet_success(self):
        """Test validation succeeds for valid subnet association."""
        result = self.handler._validate_association_resources(
            self.context,
            "test_subnet",
            "test_nsg",
            "test-subnet",
            "test-nsg",
            "subnet",
        )

        assert result is True

    def test_validate_association_resources_subnet_missing(self):
        """Test validation fails for missing subnet."""
        result = self.handler._validate_association_resources(
            self.context,
            "missing_subnet",
            "test_nsg",
            "missing-subnet",
            "test-nsg",
            "subnet",
        )

        assert result is False

    def test_validate_association_resources_nic_success(self):
        """Test validation succeeds for valid NIC association."""
        result = self.handler._validate_association_resources(
            self.context, "test_nic", "test_nsg", "test-nic", "test-nsg", "nic"
        )

        assert result is True

    def test_validate_association_resources_nic_missing(self):
        """Test validation fails for missing NIC."""
        self.context.terraform_config["resource"]["azurerm_network_interface"] = {}

        result = self.handler._validate_association_resources(
            self.context, "test_nic", "test_nsg", "test-nic", "test-nsg", "nic"
        )

        assert result is False

    def test_validate_association_resources_nsg_missing(self):
        """Test validation fails for missing NSG (subnet case)."""
        self.context.terraform_config["resource"]["azurerm_network_security_group"] = {}

        result = self.handler._validate_association_resources(
            self.context,
            "test_subnet",
            "test_nsg",
            "test-subnet",
            "test-nsg",
            "subnet",
        )

        assert result is False
