"""
Unit tests for RelationshipRule.extract_target_ids() method.

Tests verify that relationship rules correctly extract target resource IDs
from resource properties for cross-RG dependency collection.

Following TDD methodology - these tests will FAIL until implementation is complete.
"""

from typing import Any, Dict, Set

from src.relationship_rules.relationship_rule import RelationshipRule


class NetworkRule(RelationshipRule):
    """Concrete implementation for testing network relationships."""

    def applies(self, resource: Dict[str, Any]) -> bool:
        """Check if resource has network dependencies."""
        return resource.get("type") in [
            "Microsoft.Compute/virtualMachines",
            "Microsoft.Network/networkInterfaces",
            "Microsoft.Network/virtualNetworks/subnets",
        ]

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """Emit network relationships."""
        pass

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """Extract target resource IDs for network relationships.

        This method must be implemented by RelationshipRule base class
        to support relationship-driven dependency collection.
        """
        raise NotImplementedError("extract_target_ids() not yet implemented")


class IdentityRule(RelationshipRule):
    """Concrete implementation for testing identity relationships."""

    def applies(self, resource: Dict[str, Any]) -> bool:
        """Check if resource has identity dependencies."""
        return "identity" in resource

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """Emit identity relationships."""
        pass

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """Extract target resource IDs for identity relationships."""
        raise NotImplementedError("extract_target_ids() not yet implemented")


class DiagnosticRule(RelationshipRule):
    """Concrete implementation for testing diagnostic relationships."""

    def applies(self, resource: Dict[str, Any]) -> bool:
        """Check if resource has diagnostic dependencies."""
        return "properties" in resource and "diagnosticSettings" in resource.get(
            "properties", {}
        )

    def emit(self, resource: Dict[str, Any], db_ops: Any) -> None:
        """Emit diagnostic relationships."""
        pass

    def extract_target_ids(self, resource: Dict[str, Any]) -> Set[str]:
        """Extract target resource IDs for diagnostic relationships."""
        raise NotImplementedError("extract_target_ids() not yet implemented")


class TestNetworkRuleExtract:
    """Tests for extracting network dependency target IDs."""

    def test_network_rule_extract_subnet_ids(self):
        """Test extracting subnet IDs from VM with multiple NICs."""
        rule = NetworkRule()

        # VM with 2 NICs, each in different subnet
        vm_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                        },
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic2"
                        },
                    ]
                }
            },
        }

        target_ids = rule.extract_target_ids(vm_resource)

        assert len(target_ids) == 2, "Should extract both NIC IDs"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic2"
            in target_ids
        )

    def test_network_rule_extract_nsg_ids(self):
        """Test extracting NSG IDs from subnet with network security group."""
        rule = NetworkRule()

        subnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "name": "subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "resource_group": "rg-network",
            "properties": {
                "networkSecurityGroup": {
                    "id": "/subscriptions/sub1/resourceGroups/rg-security/providers/Microsoft.Network/networkSecurityGroups/nsg1"
                }
            },
        }

        target_ids = rule.extract_target_ids(subnet_resource)

        assert len(target_ids) == 1, "Should extract NSG ID"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-security/providers/Microsoft.Network/networkSecurityGroups/nsg1"
            in target_ids
        )

    def test_network_rule_extract_private_endpoint_ids(self):
        """Test extracting private endpoint IDs from subnet."""
        rule = NetworkRule()

        subnet_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/virtualNetworks/vnet1/subnets/subnet1",
            "name": "subnet1",
            "type": "Microsoft.Network/virtualNetworks/subnets",
            "resource_group": "rg-network",
            "properties": {
                "privateEndpoints": [
                    {
                        "id": "/subscriptions/sub1/resourceGroups/rg-data/providers/Microsoft.Network/privateEndpoints/pe-storage"
                    },
                    {
                        "id": "/subscriptions/sub1/resourceGroups/rg-data/providers/Microsoft.Network/privateEndpoints/pe-sql"
                    },
                ]
            },
        }

        target_ids = rule.extract_target_ids(subnet_resource)

        assert len(target_ids) == 2, "Should extract both private endpoint IDs"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-data/providers/Microsoft.Network/privateEndpoints/pe-storage"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg-data/providers/Microsoft.Network/privateEndpoints/pe-sql"
            in target_ids
        )


class TestIdentityRuleExtract:
    """Tests for extracting identity dependency target IDs."""

    def test_identity_rule_extract_user_assigned_identity_ids(self):
        """Test extracting user-assigned identity IDs from resource."""
        rule = IdentityRule()

        # Web app with multiple user-assigned identities
        webapp_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-apps/providers/Microsoft.Web/sites/webapp1",
            "name": "webapp1",
            "type": "Microsoft.Web/sites",
            "resource_group": "rg-apps",
            "identity": {
                "type": "UserAssigned",
                "userAssignedIdentities": {
                    "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1": {},
                    "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity2": {},
                },
            },
        }

        target_ids = rule.extract_target_ids(webapp_resource)

        assert len(target_ids) == 2, "Should extract both user-assigned identity IDs"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg-identity/providers/Microsoft.ManagedIdentity/userAssignedIdentities/identity2"
            in target_ids
        )


class TestDiagnosticRuleExtract:
    """Tests for extracting diagnostic dependency target IDs."""

    def test_diagnostic_rule_extract_workspace_ids(self):
        """Test extracting Log Analytics workspace IDs from diagnostic settings."""
        rule = DiagnosticRule()

        storage_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-storage/providers/Microsoft.Storage/storageAccounts/storage1",
            "name": "storage1",
            "type": "Microsoft.Storage/storageAccounts",
            "resource_group": "rg-storage",
            "properties": {
                "diagnosticSettings": [
                    {
                        "workspaceId": "/subscriptions/sub1/resourceGroups/rg-monitoring/providers/Microsoft.OperationalInsights/workspaces/workspace1"
                    }
                ]
            },
        }

        target_ids = rule.extract_target_ids(storage_resource)

        assert len(target_ids) == 1, "Should extract workspace ID"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-monitoring/providers/Microsoft.OperationalInsights/workspaces/workspace1"
            in target_ids
        )


class TestTagRuleExtract:
    """Tests for tag rule - should return empty set."""

    def test_tag_rule_extract_returns_empty_set(self):
        """Test that tag rule returns empty set - tags are shared nodes."""
        # Tag relationships don't require cross-RG dependency collection
        # because Tag nodes are shared across all resource groups
        from src.relationship_rules.tag_rule import TagRule

        rule = TagRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "tags": {
                "environment": "production",
                "owner": "team-platform",
            },
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 0, (
            "Tag rule should return empty set - tags are shared nodes"
        )


class TestRegionRuleExtract:
    """Tests for region rule - should return empty set."""

    def test_region_rule_extract_returns_empty_set(self):
        """Test that region rule returns empty set - regions are shared nodes."""
        # Region relationships don't require cross-RG dependency collection
        # because Region nodes are shared across all resource groups
        from src.relationship_rules.region_rule import RegionRule

        rule = RegionRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "location": "eastus",
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 0, (
            "Region rule should return empty set - regions are shared nodes"
        )


class TestCreatorRuleExtract:
    """Tests for creator rule - should return empty set."""

    def test_creator_rule_extract_returns_empty_set(self):
        """Test that creator rule returns empty set - creator is metadata."""
        # Creator relationships don't require cross-RG dependency collection
        # because creator is metadata, not a resource dependency
        from src.relationship_rules.creator_rule import CreatorRule

        rule = CreatorRule()

        resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "created_by": "user@example.com",
        }

        target_ids = rule.extract_target_ids(resource)

        assert len(target_ids) == 0, (
            "Creator rule should return empty set - creator is metadata"
        )


class TestMonitoringRuleExtract:
    """Tests for extracting monitoring dependency target IDs."""

    def test_monitoring_rule_extract_targets(self):
        """Test extracting monitoring target IDs from alert rules."""
        from src.relationship_rules.monitoring_rule import MonitoringRule

        rule = MonitoringRule()

        alert_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-monitoring/providers/Microsoft.Insights/metricAlerts/alert1",
            "name": "alert1",
            "type": "Microsoft.Insights/metricAlerts",
            "resource_group": "rg-monitoring",
            "properties": {
                "scopes": [
                    "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
                    "/subscriptions/sub1/resourceGroups/rg-apps/providers/Microsoft.Web/sites/webapp1",
                ]
            },
        }

        target_ids = rule.extract_target_ids(alert_resource)

        assert len(target_ids) == 2, "Should extract both monitored resource IDs"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg-apps/providers/Microsoft.Web/sites/webapp1"
            in target_ids
        )


class TestSecretRuleExtract:
    """Tests for extracting Key Vault secret dependency target IDs."""

    def test_secret_rule_extract_key_vault_ids(self):
        """Test extracting Key Vault IDs from resources with secret references."""
        from src.relationship_rules.secret_rule import SecretRule

        rule = SecretRule()

        webapp_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-apps/providers/Microsoft.Web/sites/webapp1",
            "name": "webapp1",
            "type": "Microsoft.Web/sites",
            "resource_group": "rg-apps",
            "properties": {
                "siteConfig": {
                    "appSettings": [
                        {
                            "name": "ConnectionString",
                            "value": "@Microsoft.KeyVault(SecretUri=https://kv1.vault.azure.net/secrets/connection-string)",
                        },
                        {
                            "name": "ApiKey",
                            "value": "@Microsoft.KeyVault(SecretUri=https://kv2.vault.azure.net/secrets/api-key)",
                        },
                    ]
                }
            },
        }

        target_ids = rule.extract_target_ids(webapp_resource)

        # Should extract Key Vault resource IDs from vault DNS names
        assert len(target_ids) >= 2, "Should extract at least 2 Key Vault IDs"


class TestDependsOnRuleExtract:
    """Tests for extracting explicit dependsOn dependency target IDs."""

    def test_depends_on_rule_extract_dependency_ids(self):
        """Test extracting explicit dependsOn IDs from ARM template metadata."""
        from src.relationship_rules.depends_on_rule import DependsOnRule

        rule = DependsOnRule()

        vm_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "dependsOn": [
                    "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1",
                    "/subscriptions/sub1/resourceGroups/rg-storage/providers/Microsoft.Storage/storageAccounts/storage1",
                ]
            },
        }

        target_ids = rule.extract_target_ids(vm_resource)

        assert len(target_ids) == 2, "Should extract both dependency IDs"
        assert (
            "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
            in target_ids
        )
        assert (
            "/subscriptions/sub1/resourceGroups/rg-storage/providers/Microsoft.Storage/storageAccounts/storage1"
            in target_ids
        )


class TestExtractConsistencyWithEmit:
    """Critical test: Verify extract_target_ids() matches emit() relationships."""

    def test_extract_matches_emit_relationships(self):
        """
        CRITICAL: Verify that extract_target_ids() returns the same target IDs
        that emit() would create relationships to.

        This ensures relationship-driven dependency collection is complete and accurate.
        """
        rule = NetworkRule()

        vm_resource = {
            "id": "/subscriptions/sub1/resourceGroups/rg-compute/providers/Microsoft.Compute/virtualMachines/vm1",
            "name": "vm1",
            "type": "Microsoft.Compute/virtualMachines",
            "resource_group": "rg-compute",
            "properties": {
                "networkProfile": {
                    "networkInterfaces": [
                        {
                            "id": "/subscriptions/sub1/resourceGroups/rg-network/providers/Microsoft.Network/networkInterfaces/nic1"
                        }
                    ]
                }
            },
        }

        # Mock db_ops to track relationship creation
        class MockDbOps:
            def __init__(self):
                self.relationships = []

            def create_generic_rel(self, src_id, rel_type, tgt_id, tgt_label, tgt_key):
                self.relationships.append((src_id, rel_type, tgt_id))
                return True

        mock_db_ops = MockDbOps()

        # Extract target IDs
        extracted_ids = rule.extract_target_ids(vm_resource)

        # Get relationship targets from emit()
        rule.emit(vm_resource, mock_db_ops)
        emitted_target_ids = {rel[2] for rel in mock_db_ops.relationships}

        # CRITICAL: Extracted IDs must match emitted relationship targets
        assert extracted_ids == emitted_target_ids, (
            f"extract_target_ids() must return the same IDs that emit() creates relationships to.\n"
            f"Extracted: {extracted_ids}\n"
            f"Emitted: {emitted_target_ids}\n"
            f"Difference: {extracted_ids.symmetric_difference(emitted_target_ids)}"
        )
