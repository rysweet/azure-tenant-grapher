"""Tests for VNet Link dependency validator."""

import pytest

from src.iac.validators.vnet_link_validator import (
    VNetLinkDependencyValidator,
    VNetLinkValidationResult,
)


class TestVNetLinkDependencyValidator:
    """Test suite for VNetLinkDependencyValidator."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return VNetLinkDependencyValidator()

    def test_initialization(self, validator):
        """Test validator initialization."""
        assert validator is not None

    def test_validate_valid_vnet_link(self, validator):
        """Test validation of valid VNet Link with DNS Zone."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
                "type": "Microsoft.Network/privateDnsZones",
                "name": "privatelink.blob.core.windows.net",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net/virtualNetworkLinks/link1",
                "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                "name": "privatelink.blob.core.windows.net/link1",
            },
        ]

        result = validator.validate_and_fix_dependencies(resources)

        assert result.total_vnet_links == 1
        assert result.valid_links == 1
        assert result.invalid_links == 0
        assert result.is_valid

    def test_validate_missing_dns_zone(self, validator):
        """Test validation of VNet Link with missing DNS Zone."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net/virtualNetworkLinks/link1",
                "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                "name": "privatelink.blob.core.windows.net/link1",
            }
        ]

        result = validator.validate_and_fix_dependencies(resources)

        assert result.total_vnet_links == 1
        assert result.valid_links == 0
        assert result.invalid_links == 1
        assert not result.is_valid
        assert "privatelink.blob.core.windows.net" in result.missing_dns_zones

    def test_add_dependency_to_vnet_link(self, validator):
        """Test adding dependency to VNet Link."""
        dns_zone = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
            "type": "Microsoft.Network/privateDnsZones",
            "name": "privatelink.blob.core.windows.net",
        }

        vnet_link = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net/virtualNetworkLinks/link1",
            "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
            "name": "privatelink.blob.core.windows.net/link1",
        }

        resources = [dns_zone, vnet_link]

        result = validator.validate_and_fix_dependencies(resources)

        # Check dependency was added
        assert "terraform_depends_on" in vnet_link
        assert dns_zone["id"] in vnet_link["terraform_depends_on"]

    def test_multiple_vnet_links(self, validator):
        """Test validation of multiple VNet Links."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
                "type": "Microsoft.Network/privateDnsZones",
                "name": "privatelink.blob.core.windows.net",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.file.core.windows.net",
                "type": "Microsoft.Network/privateDnsZones",
                "name": "privatelink.file.core.windows.net",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net/virtualNetworkLinks/link1",
                "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                "name": "privatelink.blob.core.windows.net/link1",
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.file.core.windows.net/virtualNetworkLinks/link2",
                "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                "name": "privatelink.file.core.windows.net/link2",
            },
        ]

        result = validator.validate_and_fix_dependencies(resources)

        assert result.total_vnet_links == 2
        assert result.valid_links == 2
        assert result.invalid_links == 0
        assert result.is_valid

    def test_extract_parent_zone_from_id(self, validator):
        """Test extracting parent zone name from resource ID."""
        vnet_link = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.database.windows.net/virtualNetworkLinks/mylink",
            "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
            "name": "mylink",
        }

        zone_name = validator._extract_parent_zone_name(vnet_link)
        assert zone_name == "privatelink.database.windows.net"

    def test_extract_parent_zone_from_name(self, validator):
        """Test extracting parent zone name from resource name."""
        vnet_link = {
            "id": "some-id",
            "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
            "name": "privatelink.blob.core.windows.net/link1",
        }

        zone_name = validator._extract_parent_zone_name(vnet_link)
        assert zone_name == "privatelink.blob.core.windows.net"

    def test_get_validation_summary(self, validator):
        """Test validation summary generation."""
        result = VNetLinkValidationResult(
            total_vnet_links=5,
            valid_links=3,
            invalid_links=2,
            missing_dns_zones={"zone1.private", "zone2.private"},
            validation_messages=[
                "VNet Link 'link1' references missing DNS zone 'zone1.private'",
                "VNet Link 'link2' references missing DNS zone 'zone2.private'",
            ],
        )

        summary = validator.get_validation_summary(result)

        assert "Total VNet Links: 5" in summary
        assert "Valid Links: 3" in summary
        assert "Invalid Links: 2" in summary
        assert "zone1.private" in summary
        assert "zone2.private" in summary

    def test_no_vnet_links(self, validator):
        """Test validation with no VNet Links."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
                "type": "Microsoft.Network/privateDnsZones",
                "name": "privatelink.blob.core.windows.net",
            }
        ]

        result = validator.validate_and_fix_dependencies(resources)

        assert result.total_vnet_links == 0
        assert result.valid_links == 0
        assert result.invalid_links == 0
        assert result.is_valid

    def test_empty_resources_list(self, validator):
        """Test validation with empty resources list."""
        result = validator.validate_and_fix_dependencies([])

        assert result.total_vnet_links == 0
        assert result.is_valid

    def test_vnet_link_no_parent_reference(self, validator):
        """Test VNet Link with no parent reference."""
        resources = [
            {
                "id": "/subscriptions/sub1/some/invalid/path",
                "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
                "name": "link1",
            }
        ]

        result = validator.validate_and_fix_dependencies(resources)

        assert result.total_vnet_links == 1
        assert result.valid_links == 0
        assert result.invalid_links == 1

    def test_dependency_not_duplicated(self, validator):
        """Test that dependencies are not duplicated."""
        dns_zone = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net",
            "type": "Microsoft.Network/privateDnsZones",
            "name": "privatelink.blob.core.windows.net",
        }

        vnet_link = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net/virtualNetworkLinks/link1",
            "type": "Microsoft.Network/privateDnsZones/virtualNetworkLinks",
            "name": "privatelink.blob.core.windows.net/link1",
            "terraform_depends_on": [dns_zone["id"]],  # Already has dependency
        }

        resources = [dns_zone, vnet_link]

        validator.validate_and_fix_dependencies(resources)

        # Should not duplicate
        assert vnet_link["terraform_depends_on"].count(dns_zone["id"]) == 1
