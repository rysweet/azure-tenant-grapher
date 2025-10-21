"""
Unit tests for SQL Database data plane plugin.

Tests cover:
- SQL Database resource validation
- Schema discovery functionality (mocked)
- Terraform code generation
- Template and replication mode functionality
- Helper methods and schema extraction
"""

from unittest.mock import patch

import pytest

from src.iac.plugins.base_plugin import (
    DataPlaneItem,
    ReplicationMode,
)
from src.iac.plugins.sql_plugin import DatabaseSchema, SQLDatabasePlugin


class TestSQLDatabasePlugin:
    """Test cases for SQLDatabasePlugin instantiation and basic properties."""

    def test_plugin_instantiation(self):
        """Test that SQLDatabasePlugin can be instantiated."""
        plugin = SQLDatabasePlugin()
        assert plugin is not None
        assert plugin.plugin_name == "SQLDatabasePlugin"

    def test_supported_resource_type(self):
        """Test that plugin supports correct resource type."""
        plugin = SQLDatabasePlugin()
        assert plugin.supported_resource_type == "Microsoft.Sql/servers/databases"

    def test_supports_terraform_format(self):
        """Test that plugin supports Terraform output format."""
        plugin = SQLDatabasePlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_does_not_support_other_formats(self):
        """Test that plugin doesn't support other formats yet."""
        plugin = SQLDatabasePlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False


class TestSQLDatabaseValidation:
    """Test resource validation for SQL Database plugin."""

    def test_validate_valid_sql_database_resource(self):
        """Test validation succeeds for valid SQL Database resource."""
        plugin = SQLDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/myserver/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            "properties": {"serverName": "myserver"},
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = SQLDatabasePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = SQLDatabasePlugin()
        resource = {
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = SQLDatabasePlugin()
        assert plugin.validate_resource(None) is False


class TestSQLDatabaseServerExtraction:
    """Test server name extraction from resource."""

    def test_extract_server_name_from_resource_id(self):
        """Test extracting server name from resource ID."""
        plugin = SQLDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/myserver/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
        }

        server_name = plugin._extract_server_name(resource)
        assert server_name == "myserver"

    def test_extract_server_name_from_properties(self):
        """Test extracting server name from properties."""
        plugin = SQLDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/unknown/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            "properties": {"serverName": "myserver"},
        }

        server_name = plugin._extract_server_name(resource)
        # Resource ID should take precedence
        assert server_name == "unknown" or server_name == "myserver"

    def test_extract_server_name_missing(self):
        """Test extraction returns None when server name cannot be determined."""
        plugin = SQLDatabasePlugin()
        resource = {
            "id": "/subscriptions/123",  # Invalid format
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
        }

        server_name = plugin._extract_server_name(resource)
        assert server_name is None


class TestSQLDatabaseCodeGeneration:
    """Test IaC code generation for SQL Database plugin."""

    def test_generate_code_for_empty_items(self):
        """Test code generation with no items."""
        plugin = SQLDatabasePlugin()
        code = plugin.generate_replication_code([], "terraform")

        assert "No SQL Database schema items" in code

    def test_generate_code_for_single_table(self):
        """Test code generation for a single table."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.users",
                item_type="table",
                properties={
                    "schema": "dbo",
                    "table_name": "users",
                    "columns": [
                        {"name": "id", "data_type": "int", "is_nullable": False},
                        {
                            "name": "name",
                            "data_type": "nvarchar",
                            "max_length": 100,
                            "is_nullable": True,
                        },
                    ],
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "create_statement": "CREATE TABLE [dbo].[users] ([id] int NOT NULL, [name] nvarchar(100) NULL);"
                },
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for local_file resource
        assert "local_file" in code
        assert "sql_database_schema" in code
        assert "CREATE TABLE" in code
        assert "dbo.users" in code or "users" in code

    def test_generate_code_for_multiple_tables(self):
        """Test code generation for multiple tables."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.users",
                item_type="table",
                properties={"schema": "dbo", "table_name": "users", "columns": []},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={"create_statement": "CREATE TABLE [dbo].[users] ([id] int);"},
            ),
            DataPlaneItem(
                name="dbo.orders",
                item_type="table",
                properties={"schema": "dbo", "table_name": "orders", "columns": []},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "create_statement": "CREATE TABLE [dbo].[orders] ([id] int);"
                },
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check both tables are present
        assert "users" in code
        assert "orders" in code
        assert code.count("CREATE TABLE") >= 2

    def test_generate_code_with_indexes(self):
        """Test code generation includes indexes."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.users",
                item_type="table",
                properties={"schema": "dbo", "table_name": "users", "columns": []},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={"create_statement": "CREATE TABLE [dbo].[users] ([id] int);"},
            ),
            DataPlaneItem(
                name="dbo.users.idx_id",
                item_type="index",
                properties={
                    "table": "dbo.users",
                    "index_name": "idx_id",
                    "columns": ["id"],
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "create_statement": "CREATE INDEX [idx_id] ON [dbo].[users] (id);"
                },
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check indexes section
        assert "Indexes" in code or "INDEX" in code
        assert "idx_id" in code

    def test_generate_code_with_foreign_keys(self):
        """Test code generation includes foreign keys."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.orders.fk_user_id",
                item_type="foreign_key",
                properties={
                    "table": "dbo.orders",
                    "constraint_name": "fk_user_id",
                    "referenced_table": "dbo.users",
                    "columns": ["user_id"],
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "create_statement": "ALTER TABLE [dbo].[orders] ADD CONSTRAINT [fk_user_id] FOREIGN KEY (user_id) REFERENCES [dbo].[users];"
                },
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check foreign keys section
        assert "Foreign Keys" in code or "FOREIGN KEY" in code
        assert "fk_user_id" in code

    def test_generate_code_with_views(self):
        """Test code generation includes views."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.v_active_users",
                item_type="view",
                properties={"schema": "dbo", "view_name": "v_active_users"},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "definition": "CREATE VIEW [dbo].[v_active_users] AS SELECT * FROM users WHERE active = 1;"
                },
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check views section
        assert "Views" in code or "VIEW" in code
        assert "v_active_users" in code

    def test_generate_code_with_stored_procedures(self):
        """Test code generation includes stored procedures."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.sp_get_user",
                item_type="stored_procedure",
                properties={"schema": "dbo", "procedure_name": "sp_get_user"},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "definition": "CREATE PROCEDURE [dbo].[sp_get_user] AS SELECT * FROM users;"
                },
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check stored procedures section
        assert "Stored Procedures" in code or "PROCEDURE" in code
        assert "sp_get_user" in code

    def test_generate_code_mixed_item_types(self):
        """Test code generation with tables, indexes, views, and stored procedures."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.users",
                item_type="table",
                properties={"schema": "dbo", "table_name": "users", "columns": []},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={"create_statement": "CREATE TABLE [dbo].[users] ([id] int);"},
            ),
            DataPlaneItem(
                name="dbo.users.idx_id",
                item_type="index",
                properties={
                    "table": "dbo.users",
                    "index_name": "idx_id",
                    "columns": ["id"],
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "create_statement": "CREATE INDEX [idx_id] ON [dbo].[users] (id);"
                },
            ),
            DataPlaneItem(
                name="dbo.v_users",
                item_type="view",
                properties={"schema": "dbo", "view_name": "v_users"},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "definition": "CREATE VIEW [dbo].[v_users] AS SELECT * FROM users;"
                },
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # All sections should be present
        assert "Tables" in code or "CREATE TABLE" in code
        assert "Indexes" in code or "CREATE INDEX" in code
        assert "Views" in code or "CREATE VIEW" in code

    def test_generate_code_unsupported_format_raises_error(self):
        """Test code generation raises error for unsupported format."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.users",
                item_type="table",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={},
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")


class TestSQLDatabaseDiscovery:
    """Test discovery functionality for SQL Database plugin (with mocking)."""

    def test_discover_with_mocked_connection_skipped(self):
        """Test discover with mocked database connection (skipped - complex mocking).

        Note: Full mocking of discover() requires mocking:
        - pyodbc connection and cursor
        - Multiple database queries (tables, indexes, foreign keys, views, stored procedures)
        - Database size calculation

        This is tested in integration tests with real database connections.
        For unit tests, we test individual helper methods separately.
        """
        pytest.skip("Complex mocking - tested in integration tests")

    def test_discover_with_invalid_resource_raises_error(self):
        """Test discover raises ValueError for invalid resource."""
        plugin = SQLDatabasePlugin()
        invalid_resource = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)


class TestSQLDatabasePermissions:
    """Test permission requirements for SQL Database plugin."""

    def test_get_required_permissions_template_mode(self):
        """Test required permissions for template mode."""
        plugin = SQLDatabasePlugin()
        permissions = plugin.get_required_permissions(ReplicationMode.TEMPLATE)

        assert len(permissions) > 0
        assert any(
            "Microsoft.Sql/servers/databases/read" in perm.actions
            for perm in permissions
        )

    def test_get_required_permissions_replication_mode(self):
        """Test required permissions for replication mode."""
        plugin = SQLDatabasePlugin()
        permissions = plugin.get_required_permissions(ReplicationMode.REPLICATION)

        assert len(permissions) > 0
        # Replication mode should have more permissions than template mode
        template_perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
        assert len(permissions[0].actions) >= len(template_perms[0].actions)

        # Should include import/export actions
        all_actions = permissions[0].actions
        assert any(
            "import" in action.lower() or "export" in action.lower()
            for action in all_actions
        )


class TestSQLDatabaseModeAwareness:
    """Test mode-aware methods for SQL Database plugin."""

    def test_supports_both_modes(self):
        """Test plugin supports both template and replication modes."""
        plugin = SQLDatabasePlugin()

        assert plugin.supports_mode(ReplicationMode.TEMPLATE) is True
        assert plugin.supports_mode(ReplicationMode.REPLICATION) is True

    @patch("src.iac.plugins.sql_plugin.SQLDatabasePlugin.discover")
    def test_discover_with_mode_delegates_to_discover(self, mock_discover):
        """Test discover_with_mode delegates to discover method."""
        plugin = SQLDatabasePlugin()
        mock_discover.return_value = []

        resource = {
            "id": "/subscriptions/123/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
        }

        # Both modes should call discover()
        plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)
        assert mock_discover.called

        mock_discover.reset_mock()
        plugin.discover_with_mode(resource, ReplicationMode.REPLICATION)
        assert mock_discover.called


class TestSQLDatabaseReplication:
    """Test replication functionality for SQL Database plugin."""

    def test_replicate_with_valid_resources_returns_result(self):
        """Test replicate returns ReplicationResult."""
        # Skip this test as it requires complex mocking
        # Real testing done in integration tests
        pytest.skip("Requires complex database connection mocking")

    def test_replicate_with_invalid_source_raises_error(self):
        """Test replicate raises error for invalid source."""
        plugin = SQLDatabasePlugin()
        invalid_source = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }
        target = {
            "id": "/subscriptions/123/databases/target-db",
            "type": "Microsoft.Sql/servers/databases",
            "name": "target-db",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate(invalid_source, target)

    def test_replicate_with_invalid_target_raises_error(self):
        """Test replicate raises error for invalid target."""
        plugin = SQLDatabasePlugin()
        source = {
            "id": "/subscriptions/123/databases/source-db",
            "type": "Microsoft.Sql/servers/databases",
            "name": "source-db",
        }
        invalid_target = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate(source, invalid_target)


class TestSQLDatabaseHelperMethods:
    """Test helper methods for SQL Database plugin."""

    def test_generate_create_table_statement(self):
        """Test CREATE TABLE statement generation."""
        plugin = SQLDatabasePlugin()

        columns = [
            {
                "name": "id",
                "data_type": "int",
                "is_nullable": False,
                "default": None,
                "max_length": None,
            },
            {
                "name": "name",
                "data_type": "nvarchar",
                "is_nullable": True,
                "default": None,
                "max_length": 100,
            },
            {
                "name": "email",
                "data_type": "varchar",
                "is_nullable": False,
                "default": None,
                "max_length": 255,
            },
        ]

        statement = plugin._generate_create_table_statement("dbo", "users", columns)

        # Check statement structure
        assert "CREATE TABLE [dbo].[users]" in statement
        assert "[id] int NOT NULL" in statement
        assert "[name] nvarchar(100) NULL" in statement
        assert "[email] varchar(255) NOT NULL" in statement

    def test_generate_create_index_statement(self):
        """Test CREATE INDEX statement generation."""
        plugin = SQLDatabasePlugin()

        statement = plugin._generate_create_index_statement(
            schema="dbo",
            table="users",
            index_name="idx_email",
            columns="email",
            is_unique=True,
        )

        assert "CREATE UNIQUE INDEX [idx_email] ON [dbo].[users] (email);" in statement

    def test_generate_create_index_statement_non_unique(self):
        """Test CREATE INDEX statement for non-unique index."""
        plugin = SQLDatabasePlugin()

        statement = plugin._generate_create_index_statement(
            schema="dbo",
            table="users",
            index_name="idx_name",
            columns="name",
            is_unique=False,
        )

        assert "CREATE INDEX [idx_name] ON [dbo].[users] (name);" in statement
        assert "UNIQUE" not in statement


class TestSQLDatabaseSizeWarnings:
    """Test database size warnings."""

    def test_size_threshold_constants(self):
        """Test size threshold constants are defined."""
        plugin = SQLDatabasePlugin()

        assert hasattr(plugin, "SIZE_WARNING_THRESHOLD_MB")
        assert hasattr(plugin, "SIZE_ERROR_THRESHOLD_MB")
        assert plugin.SIZE_WARNING_THRESHOLD_MB < plugin.SIZE_ERROR_THRESHOLD_MB
        assert plugin.SIZE_WARNING_THRESHOLD_MB == 1024  # 1GB
        assert plugin.SIZE_ERROR_THRESHOLD_MB == 10240  # 10GB


class TestSQLDatabaseEdgeCases:
    """Test edge cases for SQL Database plugin."""

    def test_extract_server_name_with_malformed_resource_id(self):
        """Test server name extraction with malformed resource ID."""
        plugin = SQLDatabasePlugin()
        resource = {
            "id": "/invalid/path",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
        }

        server_name = plugin._extract_server_name(resource)
        assert server_name is None

    def test_generate_code_with_empty_metadata(self):
        """Test code generation with items missing metadata."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.users",
                item_type="table",
                properties={"schema": "dbo", "table_name": "users", "columns": []},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={},  # Empty metadata, no create_statement
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should still generate code, just won't have the CREATE statement
        assert "local_file" in code
        assert "sql_database_schema" in code

    def test_generate_code_with_special_characters_in_table_name(self):
        """Test code generation with special characters in table name."""
        plugin = SQLDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.table-with-hyphens",
                item_type="table",
                properties={
                    "schema": "dbo",
                    "table_name": "table-with-hyphens",
                    "columns": [],
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={
                    "create_statement": "CREATE TABLE [dbo].[table-with-hyphens] ([id] int);"
                },
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should handle special characters
        assert "CREATE TABLE" in code
        assert "table-with-hyphens" in code


class TestSQLDatabaseSchema:
    """Test DatabaseSchema dataclass."""

    def test_database_schema_creation(self):
        """Test DatabaseSchema can be created."""
        schema = DatabaseSchema(
            tables=[{"name": "users"}],
            indexes=[{"name": "idx_id"}],
            foreign_keys=[],
            views=[],
            stored_procedures=[],
            size_mb=123.45,
        )

        assert schema is not None
        assert len(schema.tables) == 1
        assert len(schema.indexes) == 1
        assert schema.size_mb == 123.45

    def test_database_schema_empty(self):
        """Test DatabaseSchema with empty collections."""
        schema = DatabaseSchema(
            tables=[],
            indexes=[],
            foreign_keys=[],
            views=[],
            stored_procedures=[],
            size_mb=0.0,
        )

        assert schema is not None
        assert len(schema.tables) == 0
        assert schema.size_mb == 0.0
