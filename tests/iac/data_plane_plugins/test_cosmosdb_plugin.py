"""
Unit tests for CosmosDB data plane plugin.

This module tests the CosmosDBPlugin class covering:
- Plugin initialization
- Resource validation
- Database and container discovery
- Code generation
- Template mode replication
- Full mode replication
- Error handling
- Permission checking
- Utility functions
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.iac.data_plane_plugins.cosmosdb_plugin import CosmosDBPlugin
from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    ReplicationMode,
    ReplicationResult,
)


@pytest.fixture
def plugin():
    """Create CosmosDB plugin instance for testing."""
    return CosmosDBPlugin()


@pytest.fixture
def cosmos_resource():
    """Create sample Cosmos DB resource dictionary."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.DocumentDB/databaseAccounts/test-cosmos",
        "type": "Microsoft.DocumentDB/databaseAccounts",
        "name": "test-cosmos",
        "location": "eastus",
        "properties": {
            "documentEndpoint": "https://test-cosmos.documents.azure.com:443/"
        },
    }


@pytest.fixture
def cosmos_resource_alt_case():
    """Create sample Cosmos DB resource with alternate case."""
    return {
        "id": "/subscriptions/test-sub/resourceGroups/test-rg/providers/Microsoft.DocumentDb/databaseAccounts/test-cosmos",
        "type": "Microsoft.DocumentDb/databaseAccounts",  # Note: lowercase 'b'
        "name": "test-cosmos",
        "location": "eastus",
        "properties": {
            "documentEndpoint": "https://test-cosmos.documents.azure.com:443/"
        },
    }


class TestPluginInitialization:
    """Test plugin initialization and basic properties."""

    def test_plugin_initialization(self, plugin):
        """Test plugin can be instantiated."""
        assert plugin is not None
        assert isinstance(plugin, CosmosDBPlugin)

    def test_supported_resource_type(self, plugin):
        """Test supported resource type property."""
        assert plugin.supported_resource_type == "Microsoft.DocumentDB/databaseAccounts"

    def test_plugin_name(self, plugin):
        """Test plugin name derived from class."""
        assert plugin.plugin_name == "CosmosDBPlugin"

    def test_credential_provider(self):
        """Test plugin initialization with credential provider."""
        mock_provider = Mock()
        plugin = CosmosDBPlugin(credential_provider=mock_provider)
        assert plugin.credential_provider == mock_provider

    def test_progress_reporter(self):
        """Test plugin initialization with progress reporter."""
        mock_reporter = Mock()
        plugin = CosmosDBPlugin(progress_reporter=mock_reporter)
        assert plugin.progress_reporter == mock_reporter


class TestResourceValidation:
    """Test resource validation methods."""

    def test_can_handle_valid_resource(self, plugin, cosmos_resource):
        """Test can_handle returns True for valid Cosmos DB resource."""
        assert plugin.can_handle(cosmos_resource) is True

    def test_can_handle_alternate_case(self, plugin, cosmos_resource_alt_case):
        """Test can_handle handles case variations in resource type."""
        assert plugin.can_handle(cosmos_resource_alt_case) is True

    def test_can_handle_none_resource(self, plugin):
        """Test can_handle returns False for None resource."""
        assert plugin.can_handle(None) is False

    def test_can_handle_empty_resource(self, plugin):
        """Test can_handle returns False for empty resource."""
        assert plugin.can_handle({}) is False

    def test_can_handle_wrong_type(self, plugin):
        """Test can_handle returns False for wrong resource type."""
        resource = {
            "id": "/subscriptions/test/resourceGroups/rg/providers/Microsoft.Storage/storageAccounts/test",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "test-storage",
        }
        assert plugin.can_handle(resource) is False

    def test_validate_resource_valid(self, plugin, cosmos_resource):
        """Test validate_resource with valid resource."""
        assert plugin.validate_resource(cosmos_resource) is True

    def test_validate_resource_missing_id(self, plugin):
        """Test validate_resource fails when ID is missing."""
        resource = {
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "name": "test-cosmos",
        }
        assert plugin.validate_resource(resource) is False

    def test_validate_resource_wrong_type(self, plugin):
        """Test validate_resource fails with wrong type."""
        resource = {
            "id": "/subscriptions/test/providers/Microsoft.Storage/storageAccounts/test",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "test",
        }
        assert plugin.validate_resource(resource) is False


class TestDiscovery:
    """Test Cosmos DB discovery functionality."""

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_databases_and_containers(
        self, mock_credential, mock_cosmos_client, plugin, cosmos_resource
    ):
        """Test discovering databases and containers."""
        # Setup mocks
        mock_client_instance = MagicMock()
        mock_cosmos_client.return_value = mock_client_instance

        # Mock list_databases
        mock_client_instance.list_databases.return_value = [
            {"id": "database1", "_rid": "rid1", "_ts": 123456},
            {"id": "database2", "_rid": "rid2", "_ts": 123457},
        ]

        # Mock database clients and containers
        mock_db1 = MagicMock()
        mock_db2 = MagicMock()
        mock_client_instance.get_database_client.side_effect = [mock_db1, mock_db2]

        mock_db1.list_containers.return_value = [
            {
                "id": "container1",
                "partitionKey": {"paths": ["/pk1"]},
                "_rid": "crid1",
            }
        ]

        mock_db2.list_containers.return_value = [
            {
                "id": "container2",
                "partitionKey": {"paths": ["/pk2"]},
                "_rid": "crid2",
            }
        ]

        # Mock container clients for throughput/count
        mock_container1 = MagicMock()
        mock_container2 = MagicMock()
        mock_db1.get_container_client.return_value = mock_container1
        mock_db2.get_container_client.return_value = mock_container2

        mock_container1.read_offer.return_value = {"content": {"offerThroughput": 400}}
        mock_container2.read_offer.return_value = {"content": {"offerThroughput": 1000}}

        mock_container1.query_items.return_value = [10]  # 10 documents
        mock_container2.query_items.return_value = [5]  # 5 documents

        # Execute discovery
        items = plugin.discover(cosmos_resource)

        # Verify results
        assert len(items) == 4  # 2 databases + 2 containers

        # Check databases
        db_items = [item for item in items if item.item_type == "database"]
        assert len(db_items) == 2
        assert db_items[0].name == "database1"
        assert db_items[1].name == "database2"

        # Check containers
        container_items = [item for item in items if item.item_type == "container"]
        assert len(container_items) == 2
        assert container_items[0].name == "container1"
        assert container_items[0].properties["partitionKey"] == "/pk1"
        assert container_items[0].properties["throughput"] == 400
        assert container_items[0].properties["document_count"] == 10

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_empty_account(
        self, mock_credential, mock_cosmos_client, plugin, cosmos_resource
    ):
        """Test discovering empty Cosmos DB account."""
        mock_client_instance = MagicMock()
        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.list_databases.return_value = []

        items = plugin.discover(cosmos_resource)

        assert len(items) == 0

    def test_discover_invalid_resource(self, plugin):
        """Test discover raises error for invalid resource."""
        invalid_resource = {
            "id": "/subscriptions/test/providers/Microsoft.Storage/storageAccounts/test",
            "type": "Microsoft.Storage/storageAccounts",
            "name": "test",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)

    def test_discover_missing_endpoint(self, plugin):
        """Test discover handles missing document endpoint."""
        resource = {
            "id": "/subscriptions/test/providers/Microsoft.DocumentDB/databaseAccounts/test",
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "name": "test-cosmos",
            "properties": {},  # Missing documentEndpoint
        }

        items = plugin.discover(resource)
        assert len(items) == 0

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_with_credential_provider(
        self, mock_credential, mock_cosmos_client, cosmos_resource
    ):
        """Test discovery with custom credential provider."""
        mock_provider = Mock()
        mock_provider.get_credential.return_value = Mock()
        mock_provider.get_connection_string.return_value = None

        plugin = CosmosDBPlugin(credential_provider=mock_provider)

        mock_client_instance = MagicMock()
        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.list_databases.return_value = []

        plugin.discover(cosmos_resource)

        # Verify credential provider was called
        mock_provider.get_credential.assert_called_once()

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_with_progress_reporter(
        self, mock_credential, mock_cosmos_client, cosmos_resource
    ):
        """Test discovery reports progress."""
        mock_reporter = Mock()
        plugin = CosmosDBPlugin(progress_reporter=mock_reporter)

        mock_client_instance = MagicMock()
        mock_cosmos_client.return_value = mock_client_instance
        mock_client_instance.list_databases.return_value = [{"id": "db1"}]

        mock_db = MagicMock()
        mock_client_instance.get_database_client.return_value = mock_db
        mock_db.list_containers.return_value = []

        plugin.discover(cosmos_resource)

        # Verify progress was reported
        mock_reporter.report_discovery.assert_called_once()
        assert mock_reporter.report_discovery.call_args[0][0] == cosmos_resource["id"]


class TestCodeGeneration:
    """Test Terraform code generation."""

    def test_generate_code_empty_items(self, plugin):
        """Test code generation with no items."""
        code = plugin.generate_replication_code([])
        assert "No Cosmos DB data plane items" in code

    def test_generate_code_databases_only(self, plugin):
        """Test code generation for databases only."""
        items = [
            DataPlaneItem(
                name="testdb",
                item_type="database",
                properties={"id": "testdb"},
                source_resource_id="/test/resource",
            )
        ]

        code = plugin.generate_replication_code(items)

        assert "azurerm_cosmosdb_sql_database" in code
        assert '"testdb"' in code
        assert "REPLACE_ME" in code

    def test_generate_code_containers(self, plugin):
        """Test code generation for containers."""
        items = [
            DataPlaneItem(
                name="testdb",
                item_type="database",
                properties={"id": "testdb"},
                source_resource_id="/test/resource",
            ),
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={
                    "id": "container1",
                    "database_id": "testdb",
                    "partitionKey": "/partitionKey",
                    "throughput": 400,
                    "document_count": 100,
                },
                source_resource_id="/test/resource",
                metadata={"indexingPolicy": {"automatic": True}},
            ),
        ]

        code = plugin.generate_replication_code(items)

        assert "azurerm_cosmosdb_sql_database" in code
        assert "azurerm_cosmosdb_sql_container" in code
        assert "partition_key_path" in code
        assert '"/partitionKey"' in code
        assert "throughput          = 400" in code
        assert "100 documents" in code

    def test_generate_code_unsupported_format(self, plugin):
        """Test code generation fails for unsupported format."""
        items = [
            DataPlaneItem(
                name="testdb",
                item_type="database",
                properties={},
                source_resource_id="/test",
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, output_format="bicep")

    def test_generate_code_with_indexing_policy(self, plugin):
        """Test code generation includes indexing policy comments."""
        items = [
            DataPlaneItem(
                name="testdb",
                item_type="database",
                properties={"id": "testdb"},
                source_resource_id="/test/resource",
            ),
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={
                    "id": "container1",
                    "database_id": "testdb",
                    "partitionKey": "/pk",
                },
                source_resource_id="/test/resource",
                metadata={
                    "indexingPolicy": {
                        "indexingMode": "consistent",
                        "automatic": True,
                    }
                },
            ),
        ]

        code = plugin.generate_replication_code(items)

        assert "Indexing policy" in code
        assert "indexingMode" in code


class TestReplication:
    """Test replication functionality."""

    def test_replicate_template_mode(self, plugin, cosmos_resource):
        """Test replication in template mode."""
        with patch.object(plugin, "discover") as mock_discover:
            with patch.object(plugin, "_create_cosmos_client") as mock_create_client:
                # Mock discovery to return sample items
                mock_discover.return_value = [
                    DataPlaneItem(
                        name="db1",
                        item_type="database",
                        properties={"id": "db1"},
                        source_resource_id=cosmos_resource["id"],
                    ),
                    DataPlaneItem(
                        name="container1",
                        item_type="container",
                        properties={
                            "id": "container1",
                            "database_id": "db1",
                            "partitionKey": "/pk",
                        },
                        source_resource_id=cosmos_resource["id"],
                    ),
                ]

                # Mock Cosmos client creation
                mock_create_client.return_value = MagicMock()

                target_resource = cosmos_resource.copy()
                target_resource["name"] = "target-cosmos"

                # Execute replication
                result = plugin.replicate_with_mode(
                    cosmos_resource, target_resource, ReplicationMode.TEMPLATE
                )

                # Verify results
                assert result.success is True
                assert result.items_discovered == 2  # 1 database + 1 container
                assert result.items_replicated == 2
                assert len(result.errors) == 0

    @patch("azure.cosmos.PartitionKey")
    @patch("azure.cosmos.CosmosClient")
    def test_replicate_full_mode(
        self, mock_cosmos_client, mock_partition_key, plugin, cosmos_resource
    ):
        """Test replication in full mode."""
        # Mock the clients
        mock_source_client = MagicMock()
        mock_target_client = MagicMock()
        mock_cosmos_client.side_effect = [mock_source_client, mock_target_client]

        # Mock target database for replication
        mock_target_db = MagicMock()
        mock_target_client.get_database_client.return_value = mock_target_db

        target_resource = cosmos_resource.copy()
        target_resource["name"] = "target-cosmos"

        with patch.object(plugin, "discover") as mock_discover:
            # Mock discovery to return sample items
            mock_discover.return_value = [
                DataPlaneItem(
                    name="db1",
                    item_type="database",
                    properties={"id": "db1"},
                    source_resource_id=cosmos_resource["id"],
                ),
                DataPlaneItem(
                    name="container1",
                    item_type="container",
                    properties={
                        "id": "container1",
                        "database_id": "db1",
                        "partitionKey": "/pk",
                        "document_count": 0,
                    },
                    source_resource_id=cosmos_resource["id"],
                ),
            ]

            # Execute replication
            result = plugin.replicate_with_mode(
                cosmos_resource, target_resource, ReplicationMode.REPLICATION
            )

            # Verify results
            assert result.success is True
            assert result.items_replicated > 0

            # Verify databases and containers were created
            mock_target_client.create_database_if_not_exists.assert_called_once()
            mock_target_db.create_container_if_not_exists.assert_called_once()

    def test_replicate_invalid_source(self, plugin, cosmos_resource):
        """Test replication fails with invalid source resource."""
        invalid_source = {"type": "Microsoft.Storage/storageAccounts"}

        with pytest.raises(ValueError, match="Invalid source"):
            plugin.replicate_with_mode(
                invalid_source, cosmos_resource, ReplicationMode.TEMPLATE
            )

    def test_replicate_invalid_target(self, plugin, cosmos_resource):
        """Test replication fails with invalid target resource."""
        invalid_target = {"type": "Microsoft.Storage/storageAccounts"}

        with pytest.raises(ValueError, match="Invalid target"):
            plugin.replicate_with_mode(
                cosmos_resource, invalid_target, ReplicationMode.TEMPLATE
            )

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_replicate_missing_endpoint(
        self, mock_credential, mock_cosmos_client, plugin
    ):
        """Test replication handles missing endpoints."""
        source = {
            "id": "/test/source",
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "name": "source",
            "properties": {},  # Missing endpoint
        }
        target = {
            "id": "/test/target",
            "type": "Microsoft.DocumentDB/databaseAccounts",
            "name": "target",
            "properties": {},
        }

        result = plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)

        assert result.success is False
        assert "Missing documentEndpoint" in result.errors[0]

    def test_replicate_with_progress_reporter(self, cosmos_resource):
        """Test replication reports progress."""
        mock_reporter = Mock()
        plugin = CosmosDBPlugin(progress_reporter=mock_reporter)

        target_resource = cosmos_resource.copy()
        target_resource["name"] = "target"

        with patch.object(plugin, "discover") as mock_discover:
            # Mock discovery to return sample items
            mock_discover.return_value = [
                DataPlaneItem(
                    name="db1",
                    item_type="database",
                    properties={"id": "db1"},
                    source_resource_id=cosmos_resource["id"],
                ),
            ]

            plugin.replicate_with_mode(
                cosmos_resource, target_resource, ReplicationMode.TEMPLATE
            )

            # Verify progress was reported
            assert mock_reporter.report_completion.called


class TestPermissions:
    """Test permission requirement methods."""

    def test_get_required_permissions_template_mode(self, plugin):
        """Test permissions for template mode."""
        perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(perms) == 1
        assert "read" in perms[0].actions[0].lower()
        assert "readMetadata" in perms[0].data_actions[0]

    def test_get_required_permissions_replication_mode(self, plugin):
        """Test permissions for replication mode."""
        perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(perms) == 1
        assert any("readwrite" in action.lower() for action in perms[0].actions)
        assert any("read" in action for action in perms[0].data_actions)
        assert any("create" in action for action in perms[0].data_actions)


class TestModeSupport:
    """Test mode support methods."""

    def test_supports_mode_template(self, plugin):
        """Test plugin supports template mode."""
        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True

    def test_supports_mode_replication(self, plugin):
        """Test plugin supports replication mode."""
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True


class TestTimeEstimation:
    """Test operation time estimation."""

    def test_estimate_time_template_mode(self, plugin):
        """Test time estimation for template mode."""
        items = [
            DataPlaneItem(
                name="db1",
                item_type="database",
                properties={},
                source_resource_id="/test",
            ),
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={"database_id": "db1", "document_count": 0},
                source_resource_id="/test",
            ),
        ]

        time_est = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)

        assert time_est > 0
        assert time_est < 100  # Should be quick

    def test_estimate_time_replication_mode(self, plugin):
        """Test time estimation for replication mode with documents."""
        items = [
            DataPlaneItem(
                name="db1",
                item_type="database",
                properties={},
                source_resource_id="/test",
            ),
            DataPlaneItem(
                name="container1",
                item_type="container",
                properties={"database_id": "db1", "document_count": 10000},
                source_resource_id="/test",
            ),
        ]

        time_est = plugin.estimate_operation_time(items, ReplicationMode.REPLICATION)

        assert time_est > 0
        # Should account for 10000 documents
        assert time_est > 5  # At least some time for documents

    def test_estimate_time_empty_items(self, plugin):
        """Test time estimation with no items."""
        time_est = plugin.estimate_operation_time([], ReplicationMode.TEMPLATE)
        assert time_est == 0


class TestUtilityMethods:
    """Test utility and helper methods."""

    def test_sanitize_name_basic(self, plugin):
        """Test name sanitization."""
        assert plugin._sanitize_name("my-database") == "my_database"
        assert plugin._sanitize_name("test.db.v1") == "test_db_v1"
        assert plugin._sanitize_name("db name") == "db_name"

    def test_sanitize_name_with_slash(self, plugin):
        """Test name sanitization with slashes."""
        assert plugin._sanitize_name("db/container") == "db_container"

    def test_sanitize_name_starting_with_number(self, plugin):
        """Test name sanitization for names starting with numbers."""
        result = plugin._sanitize_name("123database")
        assert result.startswith("cosmos_")

    @patch("azure.cosmos.CosmosClient")
    def test_create_cosmos_client_with_connection_string(self, mock_cosmos_client):
        """Test Cosmos client creation with connection string."""
        mock_provider = Mock()
        mock_provider.get_connection_string.return_value = (
            "AccountEndpoint=https://test.documents.azure.com:443/;AccountKey=test=="
        )

        plugin = CosmosDBPlugin(credential_provider=mock_provider)

        resource = {"id": "/test/resource"}
        plugin._create_cosmos_client(
            "https://test.documents.azure.com:443/", Mock(), resource
        )

        # Verify from_connection_string was called
        mock_cosmos_client.from_connection_string.assert_called_once()

    @patch("azure.cosmos.CosmosClient")
    def test_create_cosmos_client_with_credential(self, mock_cosmos_client):
        """Test Cosmos client creation with credential."""
        plugin = CosmosDBPlugin()
        mock_credential = Mock()
        resource = {"id": "/test/resource"}

        plugin._create_cosmos_client(
            "https://test.documents.azure.com:443/", mock_credential, resource
        )

        # Verify credential-based client was created
        mock_cosmos_client.assert_called_once()

    def test_replicate_documents_throttling(self, plugin):
        """Test document replication with RU throttling."""
        # This tests the _replicate_documents method
        mock_source_db = MagicMock()
        mock_target_db = MagicMock()

        mock_source_container = MagicMock()
        mock_target_container = MagicMock()

        mock_source_db.get_container_client.return_value = mock_source_container
        mock_target_db.get_container_client.return_value = mock_target_container

        # Mock query to return documents
        mock_source_container.query_items.return_value = [
            {"id": "doc1", "data": "test1"},
            {"id": "doc2", "data": "test2"},
        ]

        count = plugin._replicate_documents(
            mock_source_db, mock_target_db, "test-container"
        )

        assert count == 2
        assert mock_target_container.create_item.call_count == 2


class TestEdgeCases:
    """Test edge cases and error handling."""

    @patch("azure.cosmos.CosmosClient")
    @patch("azure.identity.DefaultAzureCredential")
    def test_discover_with_azure_error(
        self, mock_credential, mock_cosmos_client, plugin, cosmos_resource
    ):
        """Test discovery handles Azure errors gracefully."""
        from azure.core.exceptions import AzureError

        mock_client = MagicMock()
        mock_cosmos_client.return_value = mock_client
        mock_client.list_databases.side_effect = AzureError("API Error")

        # Should not raise, but return empty list
        items = plugin.discover(cosmos_resource)
        assert len(items) == 0

    def test_supports_output_format(self, plugin):
        """Test output format support checking."""
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False

    def test_replicate_legacy_method(self, plugin, cosmos_resource):
        """Test legacy replicate method delegates to replicate_with_mode."""
        with patch.object(plugin, "replicate_with_mode") as mock_replicate_with_mode:
            mock_replicate_with_mode.return_value = ReplicationResult(
                success=True, items_discovered=0, items_replicated=0
            )

            target = cosmos_resource.copy()
            target["name"] = "target"

            result = plugin.replicate(cosmos_resource, target)

            mock_replicate_with_mode.assert_called_once_with(
                cosmos_resource, target, ReplicationMode.TEMPLATE
            )
            assert result.success is True
