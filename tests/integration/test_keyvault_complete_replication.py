"""Integration test for complete Key Vault replication.

This test verifies that a Key Vault with Private Endpoint, Diagnostic Settings,
and RBAC role assignments is correctly discovered, stored in Neo4j with proper
relationships, and emitted as valid Terraform configuration.

This is the comprehensive integration test for Issue #886 - ensuring all three
phases work together end-to-end.

Test coverage:
- Key Vault with Private Endpoint discovered and stored
- Diagnostic Settings discovered and linked to Key Vault
- Resource-scoped role assignments discovered and linked
- Neo4j relationships preserved (HAS_PRIVATE_ENDPOINT, HAS_DIAGNOSTIC_SETTINGS, HAS_ROLE_ASSIGNMENT)
- Terraform emission generates valid configuration
- Generated Terraform includes all resources and references
"""

import json
from typing import Any, Dict, List
from unittest.mock import Mock

import pytest

from src.config_manager import AzureTenantGrapherConfig
from src.iac.emitters.terraform.context import EmitterContext
from src.iac.emitters.terraform.handlers import ensure_handlers_registered


class TestKeyVaultCompleteReplication:
    """Integration tests for complete Key Vault replication."""

    @pytest.fixture
    def mock_config(self) -> Mock:
        """Provide a mock configuration."""
        config = Mock(spec=AzureTenantGrapherConfig)
        config.tenant_id = "test-tenant-id"
        config.processing = Mock()
        config.processing.max_build_threads = 0
        config.processing.max_retries = 3
        return config

    @pytest.fixture
    def mock_credential(self) -> Mock:
        """Provide a mock Azure credential."""
        credential = Mock()
        credential.get_token.return_value = Mock(token="test-token")
        return credential

    @pytest.fixture
    def mock_graph_service(self) -> Mock:
        """Provide a mock Neo4j graph service."""
        graph = Mock()

        # Mock Key Vault node
        mock_kv_node = Mock()
        mock_kv_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
            "name": "test-kv",
            "type": "Microsoft.KeyVault/vaults",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "tenantId": "test-tenant-id",
                    "sku": {"family": "A", "name": "standard"},
                    "enabledForDeployment": True,
                    "enabledForDiskEncryption": True,
                    "enabledForTemplateDeployment": True,
                    "enableSoftDelete": True,
                    "softDeleteRetentionInDays": 90,
                    "enableRbacAuthorization": True,
                }
            ),
        }.get(key, default)

        # Mock Private Endpoint node
        mock_pe_node = Mock()
        mock_pe_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe",
            "name": "kv-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "kv-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
                                "groupIds": ["vault"],
                            },
                        }
                    ],
                }
            ),
        }.get(key, default)

        # Mock Diagnostic Settings node
        mock_diag_node = Mock()
        mock_diag_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv/providers/microsoft.insights/diagnosticSettings/test-diag",
            "name": "test-diag",
            "type": "Microsoft.Insights/diagnosticSettings",
            "properties": json.dumps(
                {
                    "logs": [
                        {
                            "category": "AuditEvent",
                            "enabled": True,
                            "retentionPolicy": {"enabled": False, "days": 0},
                        }
                    ],
                    "metrics": [
                        {
                            "category": "AllMetrics",
                            "enabled": True,
                            "retentionPolicy": {"enabled": False, "days": 0},
                        }
                    ],
                    "workspaceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/microsoft.operationalinsights/workspaces/test-ws",
                }
            ),
        }.get(key, default)

        # Mock Role Assignment node
        mock_role_node = Mock()
        mock_role_node.get.side_effect = lambda key, default=None: {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv/providers/Microsoft.Authorization/roleAssignments/test-assignment",
            "name": "test-assignment",
            "type": "Microsoft.Authorization/roleAssignments",
            "properties": json.dumps(
                {
                    "scope": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
                    "roleDefinitionId": "/subscriptions/test-sub/providers/Microsoft.Authorization/roleDefinitions/key-vault-secrets-user",
                    "principalId": "principal-id-123",
                    "principalType": "User",
                }
            ),
        }.get(key, default)

        # Mock graph query to return all related nodes
        def mock_cypher_query(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
            if "MATCH (kv:Resource {type: 'Microsoft.KeyVault/vaults'})" in query:
                # Return Key Vault with all relationships
                return [
                    {
                        "kv": mock_kv_node,
                        "pe": mock_pe_node,
                        "diag": mock_diag_node,
                        "role": mock_role_node,
                    }
                ]
            return []

        graph.cypher_query = mock_cypher_query
        return graph

    @pytest.mark.asyncio
    async def test_key_vault_complete_replication_end_to_end(
        self,
        mock_config: Mock,
        mock_credential: Mock,
        mock_graph_service: Mock,
    ) -> None:
        """Test complete Key Vault replication from discovery to Terraform emission.

        This test verifies:
        1. Discovery captures Key Vault, Private Endpoint, Diagnostic Settings, and RBAC
        2. Neo4j stores all resources with proper relationships
        3. Terraform emission generates valid configuration for all components
        """
        # Setup handlers
        ensure_handlers_registered()

        # Create Azure Discovery Service with mocked clients
        mock_resource_client = Mock()
        mock_authorization_client = Mock()
        mock_monitor_client = Mock()

        # Mock Key Vault discovery
        mock_kv_resource = Mock()
        mock_kv_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv"
        mock_kv_resource.name = "test-kv"
        mock_kv_resource.type = "Microsoft.KeyVault/vaults"
        mock_kv_resource.location = "eastus"

        mock_resource_client.resources.list.return_value = [mock_kv_resource]

        # Mock Private Endpoint discovery
        mock_pe_resource = Mock()
        mock_pe_resource.id = "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe"
        mock_pe_resource.name = "kv-pe"
        mock_pe_resource.type = "Microsoft.Network/privateEndpoints"

        # This test will fail until implementation exists
        # Expected behavior: Discovery service finds all related resources
        # and stores them in Neo4j with proper relationships

        # Verify Neo4j relationships
        # Key Vault -[:HAS_PRIVATE_ENDPOINT]-> Private Endpoint
        # Key Vault -[:HAS_DIAGNOSTIC_SETTINGS]-> Diagnostic Settings
        # Key Vault -[:HAS_ROLE_ASSIGNMENT]-> Role Assignment

        # Create Terraform context and emit
        context = EmitterContext(
            target_subscription_id="test-sub",
            target_tenant_id="test-tenant-id",
            graph=mock_graph_service,
        )

        # This will fail until handlers are implemented
        # Expected: All resources emitted with correct Terraform references

        # ASSERTIONS (will fail until implementation):
        # 1. Terraform config includes azurerm_key_vault
        # 2. Terraform config includes azurerm_private_endpoint
        # 3. Terraform config includes azurerm_monitor_diagnostic_setting
        # 4. Terraform config includes azurerm_role_assignment
        # 5. All references between resources are correct

        # Placeholder assertion that will fail
        assert False, "Implementation not yet complete - this test should fail"

    @pytest.mark.asyncio
    async def test_key_vault_private_endpoint_terraform_reference(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test that Private Endpoint correctly references Key Vault in Terraform."""
        ensure_handlers_registered()

        context = EmitterContext(
            target_subscription_id="test-sub",
            graph=mock_graph_service,
        )

        # Add Key Vault to context
        context.add_resource("azurerm_key_vault", "test_kv")
        context.add_resource("azurerm_subnet", "test_vnet_pe_subnet")

        # Mock Private Endpoint resource
        pe_resource = {
            "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/privateEndpoints/kv-pe",
            "name": "kv-pe",
            "type": "Microsoft.Network/privateEndpoints",
            "location": "eastus",
            "resource_group": "test-rg",
            "properties": json.dumps(
                {
                    "subnet": {
                        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.Network/virtualNetworks/test-vnet/subnets/pe-subnet"
                    },
                    "privateLinkServiceConnections": [
                        {
                            "name": "kv-connection",
                            "properties": {
                                "privateLinkServiceId": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
                                "groupIds": ["vault"],
                            },
                        }
                    ],
                }
            ),
        }

        # Import handler (will fail until implemented)
        from src.iac.emitters.terraform.handlers.network.private_endpoint import (
            PrivateEndpointHandler,
        )

        handler = PrivateEndpointHandler()
        result = handler.emit(pe_resource, context)

        # This will fail until implementation exists
        assert result is not None
        _, _, config = result

        # Verify private_connection_resource_id references Key Vault
        psc = config["private_service_connection"]
        assert (
            "${azurerm_key_vault.test_kv.id}" in psc["private_connection_resource_id"]
        )

    @pytest.mark.asyncio
    async def test_neo4j_relationships_preserved_in_terraform(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test that Neo4j relationships are correctly reflected in Terraform."""
        # Query Neo4j for Key Vault and related resources
        result = mock_graph_service.cypher_query(
            """
            MATCH (kv:Resource {type: 'Microsoft.KeyVault/vaults'})
            OPTIONAL MATCH (kv)-[:HAS_PRIVATE_ENDPOINT]->(pe:Resource)
            OPTIONAL MATCH (kv)-[:HAS_DIAGNOSTIC_SETTINGS]->(diag:Resource)
            OPTIONAL MATCH (kv)-[:HAS_ROLE_ASSIGNMENT]->(role:Resource)
            RETURN kv, pe, diag, role
            """
        )

        # Verify relationships exist
        assert len(result) > 0
        kv_data = result[0]
        assert kv_data["kv"] is not None
        assert kv_data["pe"] is not None
        assert kv_data["diag"] is not None
        assert kv_data["role"] is not None

        # This test will fail until Neo4j storage is implemented
        # Expected: Discovery service creates these relationships
        assert False, "Neo4j relationship storage not yet implemented"

    @pytest.mark.asyncio
    async def test_generated_terraform_is_syntactically_valid(
        self,
        mock_graph_service: Mock,
    ) -> None:
        """Test that generated Terraform configuration is syntactically valid."""
        ensure_handlers_registered()

        context = EmitterContext(
            target_subscription_id="test-sub",
            target_tenant_id="test-tenant-id",
            graph=mock_graph_service,
        )

        # Generate Terraform for Key Vault and related resources
        # (Implementation will be added in Phase 1-3)

        # Verify Terraform syntax
        # 1. All resource blocks are properly formatted
        # 2. All references use correct interpolation syntax
        # 3. Required fields are present
        # 4. No invalid characters or syntax errors

        # This test will fail until emission is implemented
        assert False, "Terraform emission not yet complete"


class TestStorageAccountPrivateEndpointReplication:
    """Integration tests for Storage Account with multiple Private Endpoints."""

    @pytest.mark.asyncio
    async def test_storage_account_with_two_private_endpoints(self) -> None:
        """Test Storage Account with 2 Private Endpoints (blob and file).

        This verifies:
        1. Multiple Private Endpoints can be associated with one resource
        2. Each Private Endpoint has correct groupIds (subresource_names)
        3. Neo4j relationships are correct (2 HAS_PRIVATE_ENDPOINT edges)
        4. Terraform emits both Private Endpoints correctly
        """
        # Mock Storage Account with 2 Private Endpoints
        # - PE 1: blob subresource
        # - PE 2: file subresource

        # This test will fail until implementation exists
        assert False, "Storage Account multi-PE replication not yet implemented"

    @pytest.mark.asyncio
    async def test_storage_account_private_endpoints_terraform_references(
        self,
    ) -> None:
        """Test that both Private Endpoints correctly reference Storage Account."""
        # Verify both Private Endpoints emit with correct references to Storage Account
        # PE 1: private_connection_resource_id = "${azurerm_storage_account.test_storage.id}"
        # PE 2: private_connection_resource_id = "${azurerm_storage_account.test_storage.id}"

        # This test will fail until implementation exists
        assert False, "Storage Account PE references not yet implemented"
