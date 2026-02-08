"""Tests for Public IP Terraform handler with DNS label transformation.

This module tests the PublicIPHandler which converts Azure Public IP Addresses
to Terraform azurerm_public_ip resources with DNS label uniqueness.

Test coverage:
- Handler registration and discovery
- Basic Public IP conversion
- DNS label transformation for global uniqueness (Fix #892)
- Hash suffix generation
- Original label preservation in tags
- Fallback behavior without resource ID
"""

import hashlib
import json

from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import (
    HandlerRegistry,
    ensure_handlers_registered,
)
from src.iac.emitters.terraform.handlers.network.public_ip import PublicIPHandler


class TestPublicIPHandlerRegistration:
    """Test handler registration and discovery."""

    def test_public_ip_handler_registered(self):
        """Verify PublicIPHandler is registered."""
        ensure_handlers_registered()
        handler = HandlerRegistry.get_handler("Microsoft.Network/publicIPAddresses")
        assert handler is not None
        assert isinstance(handler, PublicIPHandler)

    def test_public_ip_handler_handled_types(self):
        """Verify handler declares correct Azure types."""
        assert (
            "Microsoft.Network/publicIPAddresses" in PublicIPHandler.HANDLED_TYPES
        )

    def test_public_ip_handler_terraform_types(self):
        """Verify handler declares correct Terraform types."""
        assert "azurerm_public_ip" in PublicIPHandler.TERRAFORM_TYPES


class TestPublicIPConversion:
    """Test Public IP conversion to Terraform."""

    def test_basic_public_ip_without_dns(self):
        """Test converting a basic Public IP without DNS label."""
        handler = PublicIPHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip",
            "name": "test-pip",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "sku": {"name": "Standard"},
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        assert terraform_type == "azurerm_public_ip"
        assert safe_name == "test_pip"
        assert config["name"] == "test-pip"
        assert config["location"] == "eastus"
        assert config["resource_group_name"] == "test-rg"
        assert config["allocation_method"] == "Static"
        assert config["sku"] == "Standard"
        assert "domain_name_label" not in config

    def test_public_ip_dns_label_transformation(self):
        """Test DNS label gets hash suffix for global uniqueness (Fix #892)."""
        handler = PublicIPHandler()
        context = EmitterContext()

        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
        original_label = "myapp-frontend"

        resource = {
            "id": resource_id,
            "name": "test-pip",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "dnsSettings": {"domainNameLabel": original_label},
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        terraform_type, safe_name, config = result

        # Calculate expected hash
        expected_hash = hashlib.md5(
            resource_id.encode(), usedforsecurity=False
        ).hexdigest()[:6]
        expected_label = f"{original_label.lower()}-{expected_hash}"

        # Verify transformation
        assert "domain_name_label" in config
        assert config["domain_name_label"] == expected_label
        assert config["domain_name_label"].startswith(original_label.lower())
        assert len(config["domain_name_label"]) <= 63  # Azure DNS label max length

        # Verify original label preserved in tags
        assert "tags" in config
        assert config["tags"]["original_dns_label"] == original_label

    def test_public_ip_long_dns_label_truncation(self):
        """Test DNS label truncation when too long (max 63 chars total)."""
        handler = PublicIPHandler()
        context = EmitterContext()

        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
        # Create a very long label (70 chars)
        original_label = "a" * 70

        resource = {
            "id": resource_id,
            "name": "test-pip",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "dnsSettings": {"domainNameLabel": original_label},
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Verify label is truncated (56 chars + hyphen + 6 char hash = 63 chars max)
        assert len(config["domain_name_label"]) <= 63
        assert config["domain_name_label"].endswith(
            hashlib.md5(resource_id.encode(), usedforsecurity=False).hexdigest()[:6]
        )

        # Original label still preserved
        assert config["tags"]["original_dns_label"] == original_label

    def test_public_ip_dns_label_lowercase_conversion(self):
        """Test DNS label is converted to lowercase."""
        handler = PublicIPHandler()
        context = EmitterContext()

        resource_id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip"
        original_label = "MyApp-FrontEnd-123"

        resource = {
            "id": resource_id,
            "name": "test-pip",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "dnsSettings": {"domainNameLabel": original_label},
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Verify lowercase conversion
        assert config["domain_name_label"].startswith(original_label.lower())
        assert config["domain_name_label"].islower()

        # Original case preserved in tags
        assert config["tags"]["original_dns_label"] == original_label

    def test_public_ip_dns_label_fallback_without_resource_id(self):
        """Test DNS label fallback when resource ID is missing."""
        handler = PublicIPHandler()
        context = EmitterContext()

        original_label = "MyApp-Frontend"

        resource = {
            # No 'id' field - should trigger fallback behavior
            "name": "test-pip",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "dnsSettings": {"domainNameLabel": original_label},
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        # Fallback: lowercase original label, no hash suffix
        assert config["domain_name_label"] == original_label.lower()
        assert "-" not in config["domain_name_label"]  # No hash suffix added

    def test_public_ip_with_ip_version(self):
        """Test Public IP with IPv6 version."""
        handler = PublicIPHandler()
        context = EmitterContext()

        resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/publicIPAddresses/test-pip",
            "name": "test-pip-v6",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "publicIPAddressVersion": "IPv6",
                    "sku": {"name": "Standard"},
                }
            ),
        }

        result = handler.emit(resource, context)
        assert result is not None
        _, _, config = result

        assert config["ip_version"] == "IPv6"
        assert config["allocation_method"] == "Static"
        assert config["sku"] == "Standard"


class TestPublicIPDNSUniqueness:
    """Test DNS label uniqueness across multiple Public IPs."""

    def test_different_resource_ids_generate_different_labels(self):
        """Verify different resource IDs generate unique DNS labels."""
        handler = PublicIPHandler()
        context = EmitterContext()

        original_label = "myapp"
        resource_id_1 = "/subscriptions/test-sub/resourceGroups/rg1/providers/Microsoft.Network/publicIPAddresses/pip1"
        resource_id_2 = "/subscriptions/test-sub/resourceGroups/rg2/providers/Microsoft.Network/publicIPAddresses/pip2"

        resource1 = {
            "id": resource_id_1,
            "name": "pip1",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "rg1",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "dnsSettings": {"domainNameLabel": original_label},
                }
            ),
        }

        resource2 = {
            "id": resource_id_2,
            "name": "pip2",
            "type": "Microsoft.Network/publicIPAddresses",
            "location": "eastus",
            "resource_group": "rg2",
            "properties": json.dumps(
                {
                    "publicIPAllocationMethod": "Static",
                    "dnsSettings": {"domainNameLabel": original_label},
                }
            ),
        }

        result1 = handler.emit(resource1, context)
        result2 = handler.emit(resource2, context)

        assert result1 is not None
        assert result2 is not None

        _, _, config1 = result1
        _, _, config2 = result2

        # Both start with same base label
        assert config1["domain_name_label"].startswith(original_label.lower())
        assert config2["domain_name_label"].startswith(original_label.lower())

        # But have different hash suffixes
        assert config1["domain_name_label"] != config2["domain_name_label"]

        # Original label preserved in both
        assert config1["tags"]["original_dns_label"] == original_label
        assert config2["tags"]["original_dns_label"] == original_label
