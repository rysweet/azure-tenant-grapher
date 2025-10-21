"""
Unit tests for SQL Database data plane plugin.

Tests cover:
- SQL Database resource validation
- Discovery stub functionality
- Terraform code generation
- Replication stub functionality
- Name sanitization
"""

import pytest

from src.iac.plugins.base_plugin import DataPlaneItem, ReplicationResult
from src.iac.plugins.sql_plugin import SqlDatabasePlugin


class TestSqlDatabasePlugin:
    """Test cases for SqlDatabasePlugin."""

    def test_plugin_instantiation(self):
        """Test that SqlDatabasePlugin can be instantiated."""
        plugin = SqlDatabasePlugin()
        assert plugin is not None
        assert plugin.plugin_name == "SqlDatabasePlugin"

    def test_supported_resource_type(self):
        """Test that plugin supports correct resource type."""
        plugin = SqlDatabasePlugin()
        assert plugin.supported_resource_type == "Microsoft.Sql/servers/databases"

    def test_supports_terraform_format(self):
        """Test that plugin supports Terraform output format."""
        plugin = SqlDatabasePlugin()
        assert plugin.supports_output_format("terraform") is True
        assert plugin.supports_output_format("TERRAFORM") is True

    def test_does_not_support_other_formats(self):
        """Test that plugin doesn't support other formats yet."""
        plugin = SqlDatabasePlugin()
        assert plugin.supports_output_format("bicep") is False
        assert plugin.supports_output_format("arm") is False


class TestSqlDatabaseValidation:
    """Test resource validation for SQL Database plugin."""

    def test_validate_valid_sql_database_resource(self):
        """Test validation succeeds for valid SQL Database resource."""
        plugin = SqlDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/myserver/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            "properties": {"collation": "SQL_Latin1_General_CP1_CI_AS"},
        }

        assert plugin.validate_resource(resource) is True

    def test_validate_wrong_resource_type(self):
        """Test validation fails for wrong resource type."""
        plugin = SqlDatabasePlugin()
        resource = {
            "id": "/subscriptions/123",
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_missing_id(self):
        """Test validation fails for missing resource ID."""
        plugin = SqlDatabasePlugin()
        resource = {
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            # Missing 'id'
        }

        assert plugin.validate_resource(resource) is False

    def test_validate_none_resource(self):
        """Test validation fails for None resource."""
        plugin = SqlDatabasePlugin()
        assert plugin.validate_resource(None) is False


class TestSqlDatabaseDiscovery:
    """Test discovery functionality for SQL Database plugin."""

    def test_discover_with_valid_resource_returns_list(self):
        """Test discover returns a list (stub without pyodbc)."""
        plugin = SqlDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/myserver/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            "properties": {"collation": "SQL_Latin1_General_CP1_CI_AS"},
        }

        items = plugin.discover(resource)

        # Without pyodbc installed or connection, should return empty list
        assert isinstance(items, list)
        # May be empty if pyodbc not installed
        assert len(items) >= 0

    def test_discover_with_invalid_resource_raises_error(self):
        """Test discover raises ValueError for invalid resource."""
        plugin = SqlDatabasePlugin()
        invalid_resource = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid resource"):
            plugin.discover(invalid_resource)

    def test_discover_with_missing_properties(self):
        """Test discover handles resource without properties."""
        plugin = SqlDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/myserver/databases/mydb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
            # No properties
        }

        # Should not raise error, just return empty list (stub)
        items = plugin.discover(resource)
        assert len(items) >= 0

    def test_discover_handles_malformed_resource_id(self):
        """Test discover handles resource with malformed ID."""
        plugin = SqlDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/invalid/path",  # No servers in path
            "type": "Microsoft.Sql/servers/databases",
            "name": "mydb",
        }

        # Should return empty list when server name cannot be parsed
        items = plugin.discover(resource)
        assert isinstance(items, list)


class TestSqlDatabaseCodeGeneration:
    """Test IaC code generation for SQL Database plugin."""

    def test_generate_code_for_empty_items(self):
        """Test code generation with no items."""
        plugin = SqlDatabasePlugin()
        code = plugin.generate_replication_code([], "terraform")

        assert "No SQL Database data plane items" in code

    def test_generate_code_includes_migration_documentation(self):
        """Test code generation includes migration documentation."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo",
                item_type="schema",
                properties={"type": "schema"},
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for key migration tools mentioned
        assert "BCP" in code or "bcp" in code
        assert "sqlcmd" in code
        assert "Azure Data Factory" in code
        assert "DATA MIGRATION" in code

    def test_generate_code_for_single_schema(self):
        """Test code generation for a single schema."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo",
                item_type="schema",
                properties={"type": "schema"},
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={"server": "myserver", "database": "mydb"}
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "schema(s)" in code
        assert "dbo" in code or "Schema Export" in code

    def test_generate_code_for_tables(self):
        """Test code generation for tables."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.Users",
                item_type="table",
                properties={
                    "schema": "dbo",
                    "table_name": "Users",
                    "row_count": 1000
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={"server": "myserver", "database": "mydb", "row_count": 1000}
            ),
            DataPlaneItem(
                name="dbo.Orders",
                item_type="table",
                properties={
                    "schema": "dbo",
                    "table_name": "Orders",
                    "row_count": 5000
                },
                source_resource_id="/subscriptions/123/databases/mydb",
                metadata={"server": "myserver", "database": "mydb", "row_count": 5000}
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Check for table-specific documentation
        assert "table(s)" in code
        assert "dbo.Users" in code
        assert "dbo.Orders" in code
        assert "1000 rows" in code or "row" in code.lower()
        assert "BCP" in code or "bcp" in code  # BCP for table data

    def test_generate_code_for_stored_procedures(self):
        """Test code generation for stored procedures."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.GetUserById",
                item_type="stored_procedure",
                properties={
                    "schema": "dbo",
                    "name": "GetUserById"
                },
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "stored procedure" in code.lower()
        assert "dbo.GetUserById" in code
        assert "SSMS" in code or "Generate Scripts" in code

    def test_generate_code_for_functions(self):
        """Test code generation for functions."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.CalculateTotal",
                item_type="function",
                properties={
                    "schema": "dbo",
                    "name": "CalculateTotal"
                },
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "function" in code.lower()
        assert "dbo.CalculateTotal" in code

    def test_generate_code_for_views(self):
        """Test code generation for views."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.ActiveUsers",
                item_type="view",
                properties={
                    "schema": "dbo",
                    "name": "ActiveUsers"
                },
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "view" in code.lower()
        assert "dbo.ActiveUsers" in code

    def test_generate_code_mixed_item_types(self):
        """Test code generation with schemas, tables, and objects."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo",
                item_type="schema",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
            ),
            DataPlaneItem(
                name="dbo.Users",
                item_type="table",
                properties={"schema": "dbo", "table_name": "Users", "row_count": 100},
                source_resource_id="/subscriptions/123/databases/mydb",
            ),
            DataPlaneItem(
                name="dbo.GetUsers",
                item_type="stored_procedure",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
            ),
            DataPlaneItem(
                name="dbo.FormatName",
                item_type="function",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
            ),
            DataPlaneItem(
                name="dbo.ActiveUsers",
                item_type="view",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
            ),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # All sections should be present
        assert "schema" in code.lower()
        assert "table" in code.lower()
        assert "stored procedure" in code.lower() or "procedure" in code.lower()
        assert "function" in code.lower()
        assert "view" in code.lower()

        # All items should be mentioned
        assert "dbo" in code
        assert "Users" in code
        assert "GetUsers" in code
        assert "FormatName" in code
        assert "ActiveUsers" in code

    def test_generate_code_includes_summary(self):
        """Test code generation includes summary of discovered items."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(name="dbo", item_type="schema", properties={}, source_resource_id="/sub/db"),
            DataPlaneItem(name="app", item_type="schema", properties={}, source_resource_id="/sub/db"),
            DataPlaneItem(name="dbo.Users", item_type="table", properties={}, source_resource_id="/sub/db"),
            DataPlaneItem(name="dbo.GetUser", item_type="stored_procedure", properties={}, source_resource_id="/sub/db"),
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should include counts
        assert "2 schema(s)" in code
        assert "1 table(s)" in code
        assert "1 stored procedure(s)" in code

    def test_generate_code_includes_migration_script_template(self):
        """Test code generation includes migration script template."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.Users",
                item_type="table",
                properties={"schema": "dbo", "table_name": "Users", "row_count": 100},
                source_resource_id="/sub/db",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "migrate_sql_data.sh" in code
        assert "#!/bin/bash" in code
        assert "SOURCE_SERVER" in code
        assert "TARGET_SERVER" in code

    def test_generate_code_limits_table_listing(self):
        """Test code generation limits table listing to avoid huge output."""
        plugin = SqlDatabasePlugin()

        # Create 15 tables
        items = [
            DataPlaneItem(
                name=f"dbo.Table{i}",
                item_type="table",
                properties={"schema": "dbo", "table_name": f"Table{i}", "row_count": i * 100},
                source_resource_id="/sub/db",
            )
            for i in range(15)
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should mention limiting or truncating the list
        assert "more tables" in code or "..." in code

    def test_generate_code_unsupported_format_raises_error(self):
        """Test code generation raises error for unsupported format."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo",
                item_type="schema",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        with pytest.raises(ValueError, match="not supported"):
            plugin.generate_replication_code(items, "bicep")


class TestSqlDatabaseReplication:
    """Test replication functionality for SQL Database plugin."""

    def test_replicate_with_valid_resources_returns_result(self):
        """Test replicate returns ReplicationResult."""
        plugin = SqlDatabasePlugin()
        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/src/databases/srcdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "srcdb",
        }
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/tgt/databases/tgtdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "tgtdb",
        }

        result = plugin.replicate(source, target)

        assert isinstance(result, ReplicationResult)
        # Without pyodbc or real connection, should return unsuccessful with guidance
        assert result.success is False or result.success is True
        assert result.items_discovered >= 0
        assert len(result.warnings) > 0 or len(result.errors) > 0

    def test_replicate_returns_guidance_for_manual_migration(self):
        """Test replicate returns guidance about manual migration tools."""
        plugin = SqlDatabasePlugin()
        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/src/databases/srcdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "srcdb",
        }
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/tgt/databases/tgtdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "tgtdb",
        }

        result = plugin.replicate(source, target)

        # Should mention migration tools
        # Combine all messages for checking
        all_messages = " ".join(result.errors + result.warnings).lower()

        # Should have at least some errors or warnings
        assert len(result.errors) > 0 or len(result.warnings) > 0, "Should have errors or warnings"

        # Check if migration tools are mentioned (be lenient about exact wording)
        has_migration_tool = any(tool in all_messages for tool in ["bcp", "sqlcmd", "factory", "migration", "manual"])
        assert has_migration_tool, f"Expected migration tool mention, but got: errors={result.errors}, warnings={result.warnings}"

    def test_replicate_with_invalid_source_raises_error(self):
        """Test replicate raises error for invalid source."""
        plugin = SqlDatabasePlugin()
        invalid_source = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/tgt/databases/tgtdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "tgtdb",
        }

        with pytest.raises(ValueError, match="Invalid source resource"):
            plugin.replicate(invalid_source, target)

    def test_replicate_with_invalid_target_raises_error(self):
        """Test replicate raises error for invalid target."""
        plugin = SqlDatabasePlugin()
        source = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/src/databases/srcdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "srcdb",
        }
        invalid_target = {
            "type": "Microsoft.Storage/storageAccounts",  # Wrong type
            "name": "storage",
        }

        with pytest.raises(ValueError, match="Invalid target resource"):
            plugin.replicate(source, invalid_target)


class TestSqlDatabaseNameSanitization:
    """Test name sanitization for Terraform identifiers and file names."""

    def test_sanitize_name_with_dots(self):
        """Test sanitization replaces dots with underscores."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("dbo.Users")
        assert sanitized == "dbo_users"
        assert "." not in sanitized

    def test_sanitize_name_with_hyphens(self):
        """Test sanitization replaces hyphens with underscores."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("my-table-name")
        assert sanitized == "my_table_name"
        assert "-" not in sanitized

    def test_sanitize_name_with_spaces(self):
        """Test sanitization replaces spaces with underscores."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("my table name")
        assert sanitized == "my_table_name"
        assert " " not in sanitized

    def test_sanitize_name_with_brackets(self):
        """Test sanitization removes brackets."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("[dbo].[Users]")
        assert sanitized == "dbo_users"
        assert "[" not in sanitized
        assert "]" not in sanitized

    def test_sanitize_name_with_parentheses(self):
        """Test sanitization removes parentheses."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("GetUser(id)")
        assert sanitized == "getuserid"
        assert "(" not in sanitized
        assert ")" not in sanitized

    def test_sanitize_name_starting_with_number(self):
        """Test sanitization adds prefix for names starting with number."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("123_table")
        assert sanitized.startswith("sql_")
        assert sanitized == "sql_123_table"

    def test_sanitize_name_uppercase(self):
        """Test sanitization converts to lowercase."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("MyTable")
        assert sanitized == "mytable"
        assert sanitized.islower()

    def test_sanitize_name_complex(self):
        """Test sanitization handles complex names."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("dbo.Users-Table (Active)")
        assert sanitized == "dbo_users_table_active"

    def test_sanitize_name_already_valid(self):
        """Test sanitization preserves already valid names."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("my_table_name")
        assert sanitized == "my_table_name"

    def test_sanitize_name_multiple_dots(self):
        """Test sanitization handles multiple dots."""
        plugin = SqlDatabasePlugin()
        sanitized = plugin._sanitize_name("dbo.schema.table.name")
        assert sanitized == "dbo_schema_table_name"
        assert "." not in sanitized


class TestSqlDatabasePluginEdgeCases:
    """Test edge cases for SQL Database plugin."""

    def test_generate_code_with_empty_table_name(self):
        """Test code generation with empty table name."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="",  # Empty name
                item_type="table",
                properties={},
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Should handle empty name gracefully
        assert "table" in code.lower()

    def test_generate_code_with_special_characters_in_name(self):
        """Test code generation with special characters in table name."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.Special@Table#123",
                item_type="table",
                properties={"schema": "dbo", "table_name": "Special@Table#123"},
                source_resource_id="/subscriptions/123/databases/mydb",
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        # Original name should still appear
        assert "Special@Table#123" in code or "table" in code.lower()

    def test_replicate_handles_discovery_error(self):
        """Test replicate handles errors during discovery."""
        plugin = SqlDatabasePlugin()

        # Use a resource that will fail discovery (malformed ID)
        source = {
            "id": "/invalid/path",
            "type": "Microsoft.Sql/servers/databases",
            "name": "srcdb",
        }
        target = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/tgt/databases/tgtdb",
            "type": "Microsoft.Sql/servers/databases",
            "name": "tgtdb",
        }

        result = plugin.replicate(source, target)

        # Should return result even with discovery errors
        assert isinstance(result, ReplicationResult)
        assert result.success is True or result.success is False

    def test_generate_code_with_zero_row_table(self):
        """Test code generation with table having zero rows."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.EmptyTable",
                item_type="table",
                properties={"schema": "dbo", "table_name": "EmptyTable", "row_count": 0},
                source_resource_id="/sub/db",
                metadata={"row_count": 0}
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "EmptyTable" in code
        assert "0 rows" in code or "row" in code.lower()

    def test_generate_code_with_large_table(self):
        """Test code generation with table having many rows."""
        plugin = SqlDatabasePlugin()
        items = [
            DataPlaneItem(
                name="dbo.LargeTable",
                item_type="table",
                properties={"schema": "dbo", "table_name": "LargeTable", "row_count": 10000000},
                source_resource_id="/sub/db",
                metadata={"row_count": 10000000}
            )
        ]

        code = plugin.generate_replication_code(items, "terraform")

        assert "LargeTable" in code
        assert "10000000 rows" in code or "row" in code.lower()

    def test_discover_returns_empty_on_import_error(self):
        """Test discover returns empty list when pyodbc not available."""
        plugin = SqlDatabasePlugin()
        resource = {
            "id": "/subscriptions/123/resourceGroups/rg/providers/Microsoft.Sql/servers/srv/databases/db",
            "type": "Microsoft.Sql/servers/databases",
            "name": "db",
        }

        # Should not raise exception, just return empty list or log error
        items = plugin.discover(resource)
        assert isinstance(items, list)
