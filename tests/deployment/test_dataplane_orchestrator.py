"""
Tests for data plane orchestration.

Tests data plane replication modes, resource discovery from Neo4j,
plugin execution, and error handling for replication operations.

Philosophy:
- Test replication mode logic (NONE/TEMPLATE/REPLICATION)
- Verify resource discovery and mapping
- Test plugin invocation and results aggregation
- Error handling for failed replications
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.deployment.dataplane_orchestrator import (
    SUPPORTED_RESOURCE_TYPES,
    ReplicationMode,
    _map_resource_id,
    _query_resources_for_replication,
    orchestrate_dataplane_replication,
)


class TestReplicationMode:
    """Test replication mode enum."""

    def test_replication_mode_values(self) -> None:
        """Replication mode enum has expected values."""
        assert ReplicationMode.NONE.value == "none"
        assert ReplicationMode.TEMPLATE.value == "template"
        assert ReplicationMode.REPLICATION.value == "replication"


class TestMapResourceId:
    """Test resource ID mapping between subscriptions."""

    def test_map_resource_id_replaces_subscription(self) -> None:
        """Subscription ID is replaced in resource ID."""
        target_resource_id = "/subscriptions/target-sub-123/resourceGroups/rg-test/providers/Microsoft.Compute/virtualMachines/vm-1"
        source_sub = "source-sub-456"
        target_sub = "target-sub-123"

        source_resource_id = _map_resource_id(
            target_resource_id, source_sub, target_sub
        )

        assert "source-sub-456" in source_resource_id
        assert "target-sub-123" not in source_resource_id
        assert "/resourceGroups/rg-test/" in source_resource_id

    def test_map_resource_id_preserves_resource_structure(self) -> None:
        """Resource ID structure is preserved after mapping."""
        target_resource_id = "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/storage1"
        source_sub = "source-sub"
        target_sub = "target-sub"

        source_resource_id = _map_resource_id(
            target_resource_id, source_sub, target_sub
        )

        # Verify structure preserved
        assert "/resourceGroups/rg/" in source_resource_id
        assert (
            "/providers/Microsoft.Storage/storageAccounts/storage1"
            in source_resource_id
        )


class TestQueryResourcesForReplication:
    """Test Neo4j resource querying."""

    def test_query_resources_returns_supported_resources(self) -> None:
        """Query returns only supported resource types."""
        mock_session = Mock()

        # Mock Neo4j result
        mock_records = []
        for i, resource_type in enumerate(SUPPORTED_RESOURCE_TYPES[:3]):
            mock_record = Mock()
            mock_node = {
                "id": f"/subscriptions/sub-123/resourceGroups/rg/providers/{resource_type}/resource-{i}",
                "type": resource_type,
                "name": f"resource-{i}",
                "location": "eastus",
            }
            mock_record.__getitem__ = lambda self, key, node=mock_node: node
            mock_records.append(mock_record)

        mock_result = Mock()
        mock_result.__iter__ = lambda self: iter(mock_records)
        mock_session.run.return_value = mock_result

        resources = _query_resources_for_replication(mock_session, "sub-123")

        assert len(resources) == 3
        assert all(r["type"] in SUPPORTED_RESOURCE_TYPES for r in resources)

    def test_query_resources_filters_by_subscription(self) -> None:
        """Query filters resources by subscription ID."""
        mock_session = Mock()
        mock_session.run.return_value = []

        _query_resources_for_replication(mock_session, "target-sub-123")

        # Verify query was called with subscription_id parameter
        mock_session.run.assert_called_once()
        call_args = mock_session.run.call_args
        assert call_args[1]["subscription_id"] == "target-sub-123"

    def test_query_resources_handles_neo4j_error(self) -> None:
        """Neo4j query error is propagated."""
        mock_session = Mock()
        mock_session.run.side_effect = Exception("Neo4j connection error")

        with pytest.raises(Exception, match="Neo4j connection error"):
            _query_resources_for_replication(mock_session, "sub-123")


class TestOrchestrateDatplaneReplicationNoneMode:
    """Test orchestration with NONE replication mode."""

    def test_none_mode_returns_success_immediately(self, tmp_path: Path) -> None:
        """NONE mode returns success without processing."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        result = orchestrate_dataplane_replication(
            iac_dir=iac_dir,
            mode=ReplicationMode.NONE,
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

        assert result["status"] == "success"
        assert result["resources_processed"] == 0
        assert len(result["plugins_executed"]) == 0
        assert len(result["errors"]) == 0
        assert any("skipped" in w.lower() for w in result["warnings"])


class TestOrchestrateDatplaneReplicationWithCredentials:
    """Test orchestration with different credential types."""

    @patch("src.deployment.dataplane_orchestrator.ClientSecretCredential")
    @patch("src.deployment.dataplane_orchestrator.get_session")
    def test_uses_service_principal_when_provided(
        self,
        mock_get_session: Mock,
        mock_client_secret_cred: Mock,
        tmp_path: Path,
    ) -> None:
        """Service principal credentials are used when provided."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session (no resources)
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_session.run.return_value = []
        mock_get_session.return_value = mock_session

        orchestrate_dataplane_replication(
            iac_dir=iac_dir,
            mode=ReplicationMode.TEMPLATE,
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            sp_client_id="client-id",
            sp_client_secret="client-secret",  # pragma: allowlist secret
        )

        # Verify ClientSecretCredential was created
        mock_client_secret_cred.assert_called_once_with(
            tenant_id="target-tenant",
            client_id="client-id",
            client_secret="client-secret",  # pragma: allowlist secret
        )

    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    @patch("src.deployment.dataplane_orchestrator.get_session")
    def test_uses_default_credential_when_sp_not_provided(
        self,
        mock_get_session: Mock,
        mock_default_cred: Mock,
        tmp_path: Path,
    ) -> None:
        """DefaultAzureCredential is used when no service principal provided."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session (no resources)
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)
        mock_session.run.return_value = []
        mock_get_session.return_value = mock_session

        orchestrate_dataplane_replication(
            iac_dir=iac_dir,
            mode=ReplicationMode.TEMPLATE,
            source_tenant_id="source-tenant",
            target_tenant_id="target-tenant",
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
        )

        # Verify DefaultAzureCredential was created
        mock_default_cred.assert_called_once()


class TestOrchestrateDatplaneReplicationPluginLoading:
    """Test plugin import and initialization."""

    @patch("src.deployment.dataplane_orchestrator.get_session")
    def test_handles_plugin_import_failure(
        self, mock_get_session: Mock, tmp_path: Path
    ) -> None:
        """Plugin import failure returns failed status."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock plugin import failure
        with patch(
            "src.deployment.dataplane_orchestrator.VMPlugin",
            side_effect=ImportError("Plugin not found"),
        ):
            result = orchestrate_dataplane_replication(
                iac_dir=iac_dir,
                mode=ReplicationMode.TEMPLATE,
                source_tenant_id="source-tenant",
                target_tenant_id="target-tenant",
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

        assert result["status"] == "failed"
        assert result["resources_processed"] == 0
        assert any("Plugin import failed" in e for e in result["errors"])


class TestOrchestrateDatplaneReplicationResourceDiscovery:
    """Test resource discovery from Neo4j."""

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_discovers_resources_from_neo4j(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Resources are discovered from Neo4j successfully."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session with resources
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        # Mock resources
        mock_resources = [
            {
                "id": "/subscriptions/sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
            }
        ]

        def mock_run(query, **kwargs):
            mock_result = []
            for res in mock_resources:
                mock_record = Mock()
                mock_record.__getitem__ = lambda self, key, r=res: r
                mock_result.append(mock_record)
            return mock_result

        mock_session.run = mock_run
        mock_get_session.return_value = mock_session

        # Mock plugins
        with patch("src.deployment.dataplane_orchestrator.VMPlugin") as mock_vm_plugin:
            mock_plugin_instance = Mock()
            mock_plugin_instance.can_handle.return_value = True
            mock_plugin_instance.replicate.return_value = True
            mock_vm_plugin.return_value = mock_plugin_instance

            # Patch other plugins to avoid import errors
            with patch(
                "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
            ), patch("src.deployment.dataplane_orchestrator.CosmosDBPlugin"), patch(
                "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
            ), patch("src.deployment.dataplane_orchestrator.KeyVaultPlugin"), patch(
                "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
            ), patch("src.deployment.dataplane_orchestrator.AppServicePlugin"), patch(
                "src.deployment.dataplane_orchestrator.APIManagementPlugin"
            ):
                result = orchestrate_dataplane_replication(
                    iac_dir=iac_dir,
                    mode=ReplicationMode.REPLICATION,
                    source_tenant_id="source-tenant",
                    target_tenant_id="target-tenant",
                    source_subscription_id="source-sub",
                    target_subscription_id="target-sub",
                )

        assert result["status"] == "success"
        assert result["resources_processed"] > 0

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_handles_neo4j_unavailable_gracefully(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Neo4j unavailable is handled gracefully with warning."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j import failure
        mock_get_session.side_effect = ImportError("Neo4j not available")

        # Mock plugins to avoid import errors
        with patch("src.deployment.dataplane_orchestrator.VMPlugin"), patch(
            "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
        ), patch("src.deployment.dataplane_orchestrator.CosmosDBPlugin"), patch(
            "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
        ), patch("src.deployment.dataplane_orchestrator.KeyVaultPlugin"), patch(
            "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
        ), patch("src.deployment.dataplane_orchestrator.AppServicePlugin"), patch(
            "src.deployment.dataplane_orchestrator.APIManagementPlugin"
        ):
            result = orchestrate_dataplane_replication(
                iac_dir=iac_dir,
                mode=ReplicationMode.TEMPLATE,
                source_tenant_id="source-tenant",
                target_tenant_id="target-tenant",
                source_subscription_id="source-sub",
                target_subscription_id="target-sub",
            )

        assert result["status"] == "success"
        assert result["resources_processed"] == 0
        assert any("No resources discovered" in w for w in result["warnings"])


class TestOrchestrateDatplaneReplicationPluginExecution:
    """Test plugin matching and execution."""

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_executes_matching_plugin_for_resource(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Matching plugin is executed for each resource."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session with VM resource
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_resources = [
            {
                "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
            }
        ]

        def mock_run(query, **kwargs):
            mock_result = []
            for res in mock_resources:
                mock_record = Mock()
                mock_record.__getitem__ = lambda self, key, r=res: r
                mock_result.append(mock_record)
            return mock_result

        mock_session.run = mock_run
        mock_get_session.return_value = mock_session

        # Mock VM plugin
        with patch("src.deployment.dataplane_orchestrator.VMPlugin") as mock_vm_plugin:
            mock_plugin_instance = Mock()
            mock_plugin_instance.can_handle.return_value = True
            mock_plugin_instance.replicate.return_value = True
            mock_vm_plugin.return_value = mock_plugin_instance

            # Patch other plugins
            with patch(
                "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
            ), patch("src.deployment.dataplane_orchestrator.CosmosDBPlugin"), patch(
                "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
            ), patch("src.deployment.dataplane_orchestrator.KeyVaultPlugin"), patch(
                "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
            ), patch("src.deployment.dataplane_orchestrator.AppServicePlugin"), patch(
                "src.deployment.dataplane_orchestrator.APIManagementPlugin"
            ):
                result = orchestrate_dataplane_replication(
                    iac_dir=iac_dir,
                    mode=ReplicationMode.REPLICATION,
                    source_tenant_id="source-tenant",
                    target_tenant_id="target-tenant",
                    source_subscription_id="source-sub",
                    target_subscription_id="target-sub",
                )

        # Verify plugin was invoked
        mock_plugin_instance.replicate.assert_called_once()
        assert result["status"] == "success"
        assert result["resources_processed"] == 1
        assert "VM" in result["plugins_executed"]

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_handles_plugin_replication_failure(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Plugin replication failure is recorded in errors."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session with resource
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_resources = [
            {
                "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
            }
        ]

        def mock_run(query, **kwargs):
            mock_result = []
            for res in mock_resources:
                mock_record = Mock()
                mock_record.__getitem__ = lambda self, key, r=res: r
                mock_result.append(mock_record)
            return mock_result

        mock_session.run = mock_run
        mock_get_session.return_value = mock_session

        # Mock VM plugin that fails
        with patch("src.deployment.dataplane_orchestrator.VMPlugin") as mock_vm_plugin:
            mock_plugin_instance = Mock()
            mock_plugin_instance.can_handle.return_value = True
            mock_plugin_instance.replicate.return_value = False  # Replication fails
            mock_vm_plugin.return_value = mock_plugin_instance

            # Patch other plugins
            with patch(
                "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
            ), patch("src.deployment.dataplane_orchestrator.CosmosDBPlugin"), patch(
                "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
            ), patch("src.deployment.dataplane_orchestrator.KeyVaultPlugin"), patch(
                "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
            ), patch("src.deployment.dataplane_orchestrator.AppServicePlugin"), patch(
                "src.deployment.dataplane_orchestrator.APIManagementPlugin"
            ):
                result = orchestrate_dataplane_replication(
                    iac_dir=iac_dir,
                    mode=ReplicationMode.REPLICATION,
                    source_tenant_id="source-tenant",
                    target_tenant_id="target-tenant",
                    source_subscription_id="source-sub",
                    target_subscription_id="target-sub",
                )

        assert result["status"] == "failed"
        assert result["resources_processed"] == 0
        assert len(result["errors"]) > 0

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_handles_plugin_exception(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Plugin exception is caught and recorded."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session with resource
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_resources = [
            {
                "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
            }
        ]

        def mock_run(query, **kwargs):
            mock_result = []
            for res in mock_resources:
                mock_record = Mock()
                mock_record.__getitem__ = lambda self, key, r=res: r
                mock_result.append(mock_record)
            return mock_result

        mock_session.run = mock_run
        mock_get_session.return_value = mock_session

        # Mock VM plugin that raises exception
        with patch("src.deployment.dataplane_orchestrator.VMPlugin") as mock_vm_plugin:
            mock_plugin_instance = Mock()
            mock_plugin_instance.can_handle.return_value = True
            mock_plugin_instance.replicate.side_effect = Exception("API error")
            mock_vm_plugin.return_value = mock_plugin_instance

            # Patch other plugins
            with patch(
                "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
            ), patch("src.deployment.dataplane_orchestrator.CosmosDBPlugin"), patch(
                "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
            ), patch("src.deployment.dataplane_orchestrator.KeyVaultPlugin"), patch(
                "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
            ), patch("src.deployment.dataplane_orchestrator.AppServicePlugin"), patch(
                "src.deployment.dataplane_orchestrator.APIManagementPlugin"
            ):
                result = orchestrate_dataplane_replication(
                    iac_dir=iac_dir,
                    mode=ReplicationMode.REPLICATION,
                    source_tenant_id="source-tenant",
                    target_tenant_id="target-tenant",
                    source_subscription_id="source-sub",
                    target_subscription_id="target-sub",
                )

        # Exception should not propagate
        assert result["status"] == "failed"
        assert len(result["errors"]) > 0
        assert any("API error" in str(e) for e in result["errors"])

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_warns_when_no_plugin_found(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Warning issued when no plugin found for resource type."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session with unsupported resource
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_resources = [
            {
                "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
            }
        ]

        def mock_run(query, **kwargs):
            mock_result = []
            for res in mock_resources:
                mock_record = Mock()
                mock_record.__getitem__ = lambda self, key, r=res: r
                mock_result.append(mock_record)
            return mock_result

        mock_session.run = mock_run
        mock_get_session.return_value = mock_session

        # Mock plugins that don't handle this resource
        with patch("src.deployment.dataplane_orchestrator.VMPlugin") as mock_vm_plugin:
            mock_plugin_instance = Mock()
            mock_plugin_instance.can_handle.return_value = False  # Can't handle
            mock_vm_plugin.return_value = mock_plugin_instance

            # Patch other plugins
            with patch(
                "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
            ) as mock_acr, patch(
                "src.deployment.dataplane_orchestrator.CosmosDBPlugin"
            ) as mock_cosmos, patch(
                "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
            ) as mock_storage, patch(
                "src.deployment.dataplane_orchestrator.KeyVaultPlugin"
            ) as mock_kv, patch(
                "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
            ) as mock_sql, patch(
                "src.deployment.dataplane_orchestrator.AppServicePlugin"
            ) as mock_app, patch(
                "src.deployment.dataplane_orchestrator.APIManagementPlugin"
            ) as mock_apim:
                # Make all plugins return False for can_handle
                for mock_plugin in [
                    mock_acr,
                    mock_cosmos,
                    mock_storage,
                    mock_kv,
                    mock_sql,
                    mock_app,
                    mock_apim,
                ]:
                    mock_instance = Mock()
                    mock_instance.can_handle.return_value = False
                    mock_plugin.return_value = mock_instance

                result = orchestrate_dataplane_replication(
                    iac_dir=iac_dir,
                    mode=ReplicationMode.REPLICATION,
                    source_tenant_id="source-tenant",
                    target_tenant_id="target-tenant",
                    source_subscription_id="source-sub",
                    target_subscription_id="target-sub",
                )

        assert result["status"] == "success"  # No errors, but warning
        assert result["resources_processed"] == 0
        assert any("No plugin for" in w for w in result["warnings"])


class TestOrchestrateDatplaneReplicationStatusDetermination:
    """Test overall status determination logic."""

    @patch("src.deployment.dataplane_orchestrator.get_session")
    @patch("src.deployment.dataplane_orchestrator.DefaultAzureCredential")
    def test_status_partial_when_some_resources_fail(
        self,
        mock_default_cred: Mock,
        mock_get_session: Mock,
        tmp_path: Path,
    ) -> None:
        """Status is 'partial' when some resources processed but errors exist."""
        iac_dir = tmp_path / "iac"
        iac_dir.mkdir()

        # Mock Neo4j session with 2 resources
        mock_session = Mock()
        mock_session.__enter__ = Mock(return_value=mock_session)
        mock_session.__exit__ = Mock(return_value=None)

        mock_resources = [
            {
                "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-1",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-1",
                "location": "eastus",
            },
            {
                "id": "/subscriptions/target-sub/resourceGroups/rg/providers/Microsoft.Compute/virtualMachines/vm-2",
                "type": "Microsoft.Compute/virtualMachines",
                "name": "vm-2",
                "location": "eastus",
            },
        ]

        def mock_run(query, **kwargs):
            mock_result = []
            for res in mock_resources:
                mock_record = Mock()
                mock_record.__getitem__ = lambda self, key, r=res: r
                mock_result.append(mock_record)
            return mock_result

        mock_session.run = mock_run
        mock_get_session.return_value = mock_session

        # Mock VM plugin: first succeeds, second fails
        with patch("src.deployment.dataplane_orchestrator.VMPlugin") as mock_vm_plugin:
            mock_plugin_instance = Mock()
            mock_plugin_instance.can_handle.return_value = True
            mock_plugin_instance.replicate.side_effect = [
                True,
                False,
            ]  # First succeeds, second fails
            mock_vm_plugin.return_value = mock_plugin_instance

            # Patch other plugins
            with patch(
                "src.deployment.dataplane_orchestrator.ContainerRegistryPlugin"
            ), patch("src.deployment.dataplane_orchestrator.CosmosDBPlugin"), patch(
                "src.deployment.dataplane_orchestrator.StorageAccountPlugin"
            ), patch("src.deployment.dataplane_orchestrator.KeyVaultPlugin"), patch(
                "src.deployment.dataplane_orchestrator.SQLDatabasePlugin"
            ), patch("src.deployment.dataplane_orchestrator.AppServicePlugin"), patch(
                "src.deployment.dataplane_orchestrator.APIManagementPlugin"
            ):
                result = orchestrate_dataplane_replication(
                    iac_dir=iac_dir,
                    mode=ReplicationMode.REPLICATION,
                    source_tenant_id="source-tenant",
                    target_tenant_id="target-tenant",
                    source_subscription_id="source-sub",
                    target_subscription_id="target-sub",
                )

        assert result["status"] == "partial"
        assert result["resources_processed"] == 1  # One succeeded
        assert len(result["errors"]) == 1  # One failed
