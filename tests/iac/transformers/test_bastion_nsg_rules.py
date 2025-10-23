"""Tests for Bastion NSG rule generator."""

import pytest

from src.iac.transformers.bastion_nsg_rules import (
    BastionNSGRuleGenerator,
    BastionRuleGenerationResult,
)


class TestBastionNSGRuleGenerator:
    """Test suite for BastionNSGRuleGenerator."""

    @pytest.fixture
    def generator(self):
        """Create generator instance."""
        return BastionNSGRuleGenerator()

    def test_initialization(self, generator):
        """Test generator initialization."""
        assert generator is not None

    def test_add_bastion_rules_to_empty_nsg(self, generator):
        """Test adding Bastion rules to NSG with no existing rules."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "properties": {
                    "subnets": [
                        {
                            "name": "AzureBastionSubnet",
                            "properties": {
                                "addressPrefix": "10.0.1.0/24",
                                "networkSecurityGroup": {
                                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg"
                                },
                            },
                        }
                    ]
                },
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg",
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "bastion-nsg",
                "properties": {"securityRules": []},
            },
        ]

        result = generator.transform_resources(resources)

        assert result.nsgs_processed == 1
        assert result.nsgs_modified == 1
        assert result.rules_added > 0

        # Check that rules were added
        nsg = resources[1]
        security_rules = nsg["properties"]["securityRules"]
        assert len(security_rules) == result.rules_added

    def test_required_inbound_rules_added(self, generator):
        """Test that all required inbound rules are added."""
        nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg",
            "type": "Microsoft.Network/networkSecurityGroups",
            "name": "bastion-nsg",
            "properties": {"securityRules": []},
        }

        vnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "properties": {
                "subnets": [
                    {
                        "name": "AzureBastionSubnet",
                        "properties": {
                            "networkSecurityGroup": {"id": nsg["id"]},
                        },
                    }
                ]
            },
        }

        resources = [vnet, nsg]
        result = generator.transform_resources(resources)

        security_rules = nsg["properties"]["securityRules"]
        rule_names = {rule["name"] for rule in security_rules}

        # Check required inbound rules
        assert "AllowHttpsInbound" in rule_names
        assert "AllowGatewayManagerInbound" in rule_names
        assert "AllowAzureLoadBalancerInbound" in rule_names
        assert "AllowBastionHostCommunication" in rule_names

    def test_required_outbound_rules_added(self, generator):
        """Test that all required outbound rules are added."""
        nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg",
            "type": "Microsoft.Network/networkSecurityGroups",
            "name": "bastion-nsg",
            "properties": {"securityRules": []},
        }

        vnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "properties": {
                "subnets": [
                    {
                        "name": "AzureBastionSubnet",
                        "properties": {
                            "networkSecurityGroup": {"id": nsg["id"]},
                        },
                    }
                ]
            },
        }

        resources = [vnet, nsg]
        result = generator.transform_resources(resources)

        security_rules = nsg["properties"]["securityRules"]
        rule_names = {rule["name"] for rule in security_rules}

        # Check required outbound rules
        assert "AllowSshRdpOutbound" in rule_names
        assert "AllowAzureCloudOutbound" in rule_names
        assert "AllowBastionCommunication" in rule_names
        assert "AllowGetSessionInformation" in rule_names

    def test_preserve_existing_rules(self, generator):
        """Test that existing rules are preserved."""
        nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg",
            "type": "Microsoft.Network/networkSecurityGroups",
            "name": "bastion-nsg",
            "properties": {
                "securityRules": [
                    {
                        "name": "CustomRule",
                        "properties": {
                            "priority": 200,
                            "direction": "Inbound",
                            "access": "Allow",
                            "protocol": "Tcp",
                            "sourcePortRange": "*",
                            "destinationPortRange": "8080",
                            "sourceAddressPrefix": "*",
                            "destinationAddressPrefix": "*",
                        },
                    }
                ]
            },
        }

        vnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "properties": {
                "subnets": [
                    {
                        "name": "AzureBastionSubnet",
                        "properties": {
                            "networkSecurityGroup": {"id": nsg["id"]},
                        },
                    }
                ]
            },
        }

        resources = [vnet, nsg]
        result = generator.transform_resources(resources)

        security_rules = nsg["properties"]["securityRules"]
        rule_names = {rule["name"] for rule in security_rules}

        # Custom rule should still be present
        assert "CustomRule" in rule_names
        assert len(security_rules) > 1

    def test_no_duplicate_rules(self, generator):
        """Test that rules are not duplicated if already present."""
        nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg",
            "type": "Microsoft.Network/networkSecurityGroups",
            "name": "bastion-nsg",
            "properties": {
                "securityRules": [
                    {
                        "name": "AllowHttpsInbound",
                        "properties": {
                            "priority": 120,
                            "direction": "Inbound",
                            "access": "Allow",
                            "protocol": "Tcp",
                            "sourcePortRange": "*",
                            "destinationPortRange": "443",
                            "sourceAddressPrefix": "Internet",
                            "destinationAddressPrefix": "*",
                        },
                    }
                ]
            },
        }

        vnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "properties": {
                "subnets": [
                    {
                        "name": "AzureBastionSubnet",
                        "properties": {
                            "networkSecurityGroup": {"id": nsg["id"]},
                        },
                    }
                ]
            },
        }

        initial_rule_count = len(nsg["properties"]["securityRules"])

        resources = [vnet, nsg]
        result = generator.transform_resources(resources)

        security_rules = nsg["properties"]["securityRules"]

        # Should not duplicate AllowHttpsInbound
        https_rules = [r for r in security_rules if r["name"] == "AllowHttpsInbound"]
        assert len(https_rules) == 1

    def test_no_bastion_subnet(self, generator):
        """Test with no Bastion subnet (no rules should be added)."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "properties": {
                    "subnets": [
                        {
                            "name": "default",
                            "properties": {"addressPrefix": "10.0.0.0/24"},
                        }
                    ]
                },
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/nsg1",
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "nsg1",
                "properties": {"securityRules": []},
            },
        ]

        result = generator.transform_resources(resources)

        assert result.nsgs_processed == 0
        assert result.nsgs_modified == 0
        assert result.rules_added == 0

    def test_case_insensitive_bastion_subnet(self, generator):
        """Test case-insensitive Bastion subnet name matching."""
        nsg = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg",
            "type": "Microsoft.Network/networkSecurityGroups",
            "name": "bastion-nsg",
            "properties": {"securityRules": []},
        }

        vnet = {
            "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
            "type": "Microsoft.Network/virtualNetworks",
            "properties": {
                "subnets": [
                    {
                        "name": "AZUREBASTIONSUBNET",  # Uppercase
                        "properties": {
                            "networkSecurityGroup": {"id": nsg["id"]},
                        },
                    }
                ]
            },
        }

        resources = [vnet, nsg]
        result = generator.transform_resources(resources)

        assert result.nsgs_modified == 1
        assert result.rules_added > 0

    def test_get_generation_summary(self, generator):
        """Test generation summary."""
        result = BastionRuleGenerationResult(
            nsgs_processed=3,
            nsgs_modified=2,
            rules_added=16,
            modifications=[
                ("bastion-nsg-1", 8),
                ("bastion-nsg-2", 8),
            ],
        )

        summary = generator.get_generation_summary(result)

        assert "NSGs processed: 3" in summary
        assert "NSGs modified: 2" in summary
        assert "Rules added: 16" in summary
        assert "bastion-nsg-1: 8 rules added" in summary
        assert "bastion-nsg-2: 8 rules added" in summary

    def test_multiple_bastion_subnets(self, generator):
        """Test multiple Bastion subnets in different VNets."""
        resources = [
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/virtualNetworks/vnet1",
                "type": "Microsoft.Network/virtualNetworks",
                "properties": {
                    "subnets": [
                        {
                            "name": "AzureBastionSubnet",
                            "properties": {
                                "networkSecurityGroup": {
                                    "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg-1"
                                }
                            },
                        }
                    ]
                },
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/virtualNetworks/vnet2",
                "type": "Microsoft.Network/virtualNetworks",
                "properties": {
                    "subnets": [
                        {
                            "name": "AzureBastionSubnet",
                            "properties": {
                                "networkSecurityGroup": {
                                    "id": "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg-2"
                                }
                            },
                        }
                    ]
                },
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg1/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg-1",
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "bastion-nsg-1",
                "properties": {"securityRules": []},
            },
            {
                "id": "/subscriptions/sub1/resourceGroups/rg2/providers/Microsoft.Network/networkSecurityGroups/bastion-nsg-2",
                "type": "Microsoft.Network/networkSecurityGroups",
                "name": "bastion-nsg-2",
                "properties": {"securityRules": []},
            },
        ]

        result = generator.transform_resources(resources)

        assert result.nsgs_processed == 2
        assert result.nsgs_modified == 2
