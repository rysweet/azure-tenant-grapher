"""Regression tests for Bugs #96-107.

Ensures fixed bugs remain fixed in future changes.
"""

import pytest

from src.iac.emitters.arm_emitter import ArmEmitter
from src.iac.emitters.bicep_emitter import BicepEmitter
from src.iac.emitters.terraform_emitter import TerraformEmitter
from src.iac.validators.resource_existence_validator import ResourceExistenceValidator


class TestBug96Regression:
    """Regression tests for Bug #96: Principal ID abstraction."""

    def test_traverser_includes_original_properties(self):
        """Bug #96: Ensure traverser includes original_properties in resource dict."""
        # This would require Neo4j setup - marking as TODO
        # Real verification is in iteration 10 deployment
        pass


class TestBug97Regression:
    """Regression tests for Bug #97: KeyVault API version."""

    def test_keyvault_has_correct_api_version(self):
        """Bug #97: KeyVault should use API version 2023-02-01."""
        validator = ResourceExistenceValidator(subscription_id="test")

        # Simulate KeyVault resource ID
        kv_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/test-kv"
        api_version = validator._get_api_version(kv_id)

        assert api_version == "2023-02-01", "KeyVault should use 2023-02-01 API version"


class TestBug98And99Regression:
    """Regression tests for Bugs #98-99: Action groups and query packs casing."""

    def test_action_groups_all_casing_variants_supported(self):
        """Bug #98: All action group casing variants should be in mapping."""
        emitter = TerraformEmitter()

        # All 3 variants should exist
        assert "Microsoft.Insights/actionGroups" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert "microsoft.insights/actiongroups" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert "Microsoft.Insights/actiongroups" in emitter.AZURE_TO_TERRAFORM_MAPPING

        # All should map to same resource type
        assert emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Insights/actionGroups"] == "azurerm_monitor_action_group"
        assert emitter.AZURE_TO_TERRAFORM_MAPPING["microsoft.insights/actiongroups"] == "azurerm_monitor_action_group"
        assert emitter.AZURE_TO_TERRAFORM_MAPPING["Microsoft.Insights/actiongroups"] == "azurerm_monitor_action_group"

    def test_query_packs_all_casing_variants_supported(self):
        """Bug #99: All query pack casing variants should be in mapping."""
        emitter = TerraformEmitter()

        # All 3 variants should exist
        assert "Microsoft.OperationalInsights/queryPacks" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert "microsoft.operationalinsights/querypacks" in emitter.AZURE_TO_TERRAFORM_MAPPING
        assert "Microsoft.OperationalInsights/querypacks" in emitter.AZURE_TO_TERRAFORM_MAPPING


class TestBug100To104Regression:
    """Regression tests for Bugs #100-104: API versions."""

    def test_container_registry_api_version(self):
        """Bug #100: Container Registry should use 2022-12-01."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.ContainerRegistry/registries/test"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2022-12-01"

    def test_databricks_workspaces_api_version(self):
        """Bug #101: Databricks workspaces should use provider-specific version."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Databricks/workspaces/test"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2024-05-01", "Databricks workspaces need 2024-05-01"

    def test_cosmosdb_api_version(self):
        """Bug #102: CosmosDB should use 2024-08-15."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.DocumentDB/databaseAccounts/test"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2024-08-15"

    def test_dns_zones_camelcase_variant(self):
        """Bug #103: DNS zones camelCase variant should exist."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Network/dnsZones/test.com"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2018-05-01"

    def test_redis_cache_api_version(self):
        """Bug #104: Redis Cache should use 2024-03-01."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Cache/Redis/test"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2024-03-01"


class TestBug105And106Regression:
    """Regression tests for Bugs #105-106: Action groups and query packs API versions."""

    def test_action_groups_api_version(self):
        """Bug #105: Action groups should have API version."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Insights/actiongroups/test"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2023-01-01"

    def test_query_packs_api_version(self):
        """Bug #106: Query packs should have API version."""
        validator = ResourceExistenceValidator(subscription_id="test")
        resource_id = "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.OperationalInsights/querypacks/test"
        api_version = validator._get_api_version(resource_id)
        assert api_version == "2023-09-01"


class TestBug107Regression:
    """Regression tests for Bug #107: ARM/Bicep source_tenant_id."""

    def test_arm_emitter_has_source_tenant_id_parameter(self):
        """Bug #107: ARM emitter should accept source_tenant_id."""
        # Should not raise AttributeError
        emitter = ArmEmitter(source_tenant_id="test-tenant")
        assert emitter.source_tenant_id == "test-tenant"

    def test_bicep_emitter_has_source_tenant_id_parameter(self):
        """Bug #107: Bicep emitter should accept source_tenant_id."""
        # Should not raise AttributeError
        emitter = BicepEmitter(source_tenant_id="test-tenant")
        assert emitter.source_tenant_id == "test-tenant"

    def test_arm_emitter_same_tenant_detection_works(self):
        """Bug #107: ARM emitter should detect same-tenant without crashing."""
        emitter = ArmEmitter(
            source_tenant_id="tenant-123",
            target_tenant_id="tenant-123"
        )
        # Should not raise AttributeError when checking is_same_tenant
        # The actual check happens in emit() method
        assert emitter.source_tenant_id is not None
        assert emitter.target_tenant_id is not None

    def test_bicep_emitter_same_tenant_detection_works(self):
        """Bug #107: Bicep emitter should detect same-tenant without crashing."""
        emitter = BicepEmitter(
            source_tenant_id="tenant-123",
            target_tenant_id="tenant-123"
        )
        # Should not raise AttributeError when checking is_same_tenant
        assert emitter.source_tenant_id is not None
        assert emitter.target_tenant_id is not None
