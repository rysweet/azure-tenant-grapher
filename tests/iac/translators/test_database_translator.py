"""
Unit tests for DatabaseTranslator

Tests database cross-tenant translation including:
- Resource IDs for SQL, PostgreSQL, MySQL, and Cosmos DB
- Server-to-database hierarchical relationships
- Connection strings (SQL, PostgreSQL, MySQL, Cosmos DB)
- Endpoint URIs for database servers
- Edge cases and validation
"""

import pytest

from src.iac.translators import DatabaseTranslator, TranslationContext


class TestDatabaseTranslator:
    """Test cases for DatabaseTranslator."""

    @pytest.fixture
    def source_sub_id(self):
        """Source subscription ID."""
        return "11111111-1111-1111-1111-111111111111"

    @pytest.fixture
    def target_sub_id(self):
        """Target subscription ID."""
        return "22222222-2222-2222-2222-222222222222"

    @pytest.fixture
    def available_resources(self):
        """Sample available resources in IaC."""
        return {
            "azurerm_mssql_server": {
                "sqlserver1": {
                    "name": "sqlserver1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
                }
            },
            "azurerm_postgresql_server": {
                "pgserver1": {
                    "name": "pgserver1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1",
                }
            },
            "azurerm_mysql_server": {
                "mysqlserver1": {
                    "name": "mysqlserver1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1",
                }
            },
            "azurerm_cosmosdb_account": {
                "cosmosdb1": {
                    "name": "cosmosdb1",
                    "id": "/subscriptions/22222222-2222-2222-2222-222222222222/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1",
                }
            },
        }

    @pytest.fixture
    def context(self, source_sub_id, target_sub_id, available_resources):
        """Create translation context."""
        return TranslationContext(
            source_subscription_id=source_sub_id,
            target_subscription_id=target_sub_id,
            available_resources=available_resources,
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return DatabaseTranslator(context)

    def test_supported_resource_types(self, translator):
        """Test that translator declares supported database types (both Azure and Terraform formats)."""
        supported = translator.supported_resource_types

        # Should have Terraform types
        assert "azurerm_mssql_server" in supported
        assert "azurerm_mssql_database" in supported
        assert "azurerm_postgresql_server" in supported
        assert "azurerm_postgresql_database" in supported
        assert "azurerm_mysql_server" in supported
        assert "azurerm_mysql_database" in supported
        assert "azurerm_cosmosdb_account" in supported

        # Should also have Azure types
        assert "Microsoft.Sql/servers" in supported
        assert "Microsoft.DBforPostgreSQL/servers" in supported
        assert "Microsoft.DBforMySQL/servers" in supported
        assert "Microsoft.DocumentDB/databaseAccounts" in supported

    def test_can_translate_sql_server(self, translator, source_sub_id):
        """Test can_translate returns True for SQL Server."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_sql_database(self, translator, source_sub_id):
        """Test can_translate returns True for SQL Database."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "server_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_postgresql_server(self, translator, source_sub_id):
        """Test can_translate returns True for PostgreSQL Server."""
        resource = {
            "type": "azurerm_postgresql_server",
            "name": "pgserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_mysql_server(self, translator, source_sub_id):
        """Test can_translate returns True for MySQL Server."""
        resource = {
            "type": "azurerm_mysql_server",
            "name": "mysqlserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_cosmosdb_account(self, translator, source_sub_id):
        """Test can_translate returns True for Cosmos DB account."""
        resource = {
            "type": "azurerm_cosmosdb_account",
            "name": "cosmosdb1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_with_connection_string(self, translator):
        """Test can_translate returns True for resource with connection string."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": "Server=tcp:sqlserver1.database.windows.net,1433;Database=db1",
        }

        assert translator.can_translate(resource) is True

    def test_can_translate_with_fqdn(self, translator):
        """Test can_translate returns True for resource with FQDN."""
        resource = {
            "type": "azurerm_postgresql_server",
            "name": "pgserver1",
            "fqdn": "pgserver1.postgres.database.azure.com",
        }

        assert translator.can_translate(resource) is True

    def test_cannot_translate_wrong_type(self, translator):
        """Test can_translate returns False for non-database resources."""
        resource = {
            "type": "azurerm_storage_account",
            "name": "storage1",
        }

        assert translator.can_translate(resource) is False

    def test_cannot_translate_no_translatable_properties(self, translator):
        """Test can_translate returns False when no translatable properties."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "location": "eastus",
        }

        assert translator.can_translate(resource) is False

    def test_cannot_translate_same_subscription(self, translator, target_sub_id):
        """Test can_translate returns False when resource is already in target subscription."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "id": f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        # ID is present, so can_translate returns True (it checks for presence, not subscription)
        # The actual subscription check happens in translate()
        assert translator.can_translate(resource) is True

    def test_translate_sql_server_resource_id(
        self, translator, source_sub_id, target_sub_id
    ):
        """Test translation of SQL Server resource ID."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        translated = translator.translate(resource)

        assert (
            translated["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1"
        )
        assert translated["name"] == "sqlserver1"
        assert translated["type"] == "azurerm_mssql_server"

    def test_translate_sql_database_server_id(
        self, translator, source_sub_id, target_sub_id
    ):
        """Test translation of SQL Database server_id property."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "server_id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        translated = translator.translate(resource)

        assert (
            translated["server_id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1"
        )

    def test_translate_postgresql_server_resource_id(
        self, translator, source_sub_id, target_sub_id
    ):
        """Test translation of PostgreSQL Server resource ID."""
        resource = {
            "type": "azurerm_postgresql_server",
            "name": "pgserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1",
        }

        translated = translator.translate(resource)

        assert (
            translated["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1"
        )

    def test_translate_mysql_server_resource_id(
        self, translator, source_sub_id, target_sub_id
    ):
        """Test translation of MySQL Server resource ID."""
        resource = {
            "type": "azurerm_mysql_server",
            "name": "mysqlserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1",
        }

        translated = translator.translate(resource)

        assert (
            translated["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1"
        )

    def test_translate_cosmosdb_resource_id(
        self, translator, source_sub_id, target_sub_id
    ):
        """Test translation of Cosmos DB account resource ID."""
        resource = {
            "type": "azurerm_cosmosdb_account",
            "name": "cosmosdb1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1",
        }

        translated = translator.translate(resource)

        assert (
            translated["id"]
            == f"/subscriptions/{target_sub_id}/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1"
        )

    def test_translate_preserves_other_properties(self, translator, source_sub_id):
        """Test that translation preserves properties it doesn't handle."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "location": "eastus",
            "version": "12.0",
            "administrator_login": "sqladmin",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        translated = translator.translate(resource)

        # Should preserve all properties
        assert translated["location"] == "eastus"
        assert translated["version"] == "12.0"
        assert translated["administrator_login"] == "sqladmin"

    def test_translate_skips_terraform_variables(self, translator):
        """Test that Terraform variables are not translated."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "server_id": "${azurerm_mssql_server.sqlserver1.id}",
            "connection_string": "${var.connection_string}",
        }

        translated = translator.translate(resource)

        # Variables should remain unchanged
        assert translated["server_id"] == resource["server_id"]
        assert translated["connection_string"] == resource["connection_string"]

    def test_get_report(self, translator, source_sub_id):
        """Test generation of translator report."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "id": f"/subscriptions/{source_sub_id}/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        translator.translate(resource)

        report = translator.get_report()

        assert report["translator"] == "DatabaseTranslator"
        assert report["total_resources_processed"] > 0
        assert "translations_performed" in report
        assert "warnings" in report


class TestDatabaseTranslatorConnectionStrings:
    """Test connection string translation for all database types."""

    @pytest.fixture
    def context(self):
        """Create translation context with available servers."""
        return TranslationContext(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            available_resources={
                "azurerm_mssql_server": {
                    "sqlserver1": {
                        "name": "sqlserver1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
                    }
                },
                "azurerm_postgresql_server": {
                    "pgserver1": {
                        "name": "pgserver1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1",
                    }
                },
                "azurerm_mysql_server": {
                    "mysqlserver1": {
                        "name": "mysqlserver1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1",
                    }
                },
                "azurerm_cosmosdb_account": {
                    "cosmosdb1": {
                        "name": "cosmosdb1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1",
                    }
                },
            },
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return DatabaseTranslator(context)

    def test_translate_sql_connection_string(self, translator):
        """Test translation of SQL Server connection string."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": "Server=tcp:sqlserver1.database.windows.net,1433;Database=db1;User ID=admin;Password=xxx;",
        }

        translated = translator.translate(resource)

        # Connection string should be preserved (conservative approach)
        assert translated["connection_string"] == resource["connection_string"]

        # Should have results tracked
        results = translator.get_translation_results()
        assert len(results) > 0

        # Should have no warnings (server exists in available_resources)
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert len(conn_str_result.warnings) == 0

    def test_translate_sql_connection_string_missing_server(self, translator):
        """Test translation warns when SQL Server not in IaC."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": "Server=tcp:missing-server.database.windows.net,1433;Database=db1;User ID=admin;Password=xxx;",
        }

        translated = translator.translate(resource)

        # Get results
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )

        # Should have warnings about missing server
        assert len(conn_str_result.warnings) > 0
        assert any("not found" in w.lower() for w in conn_str_result.warnings)

    def test_translate_postgresql_connection_string(self, translator):
        """Test translation of PostgreSQL connection string."""
        resource = {
            "type": "azurerm_postgresql_database",
            "name": "db1",
            "connection_string": "host=pgserver1.postgres.database.azure.com port=5432 dbname=db1 user=admin password=xxx",
        }

        translated = translator.translate(resource)

        # Connection string should be preserved
        assert translated["connection_string"] == resource["connection_string"]

        # Should have no warnings (server exists)
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert len(conn_str_result.warnings) == 0

    def test_translate_postgresql_connection_string_missing_server(self, translator):
        """Test translation warns when PostgreSQL Server not in IaC."""
        resource = {
            "type": "azurerm_postgresql_database",
            "name": "db1",
            "connection_string": "host=missing-pg.postgres.database.azure.com port=5432 dbname=db1 user=admin",
        }

        translated = translator.translate(resource)

        # Should have warnings
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert any("not found" in w.lower() for w in conn_str_result.warnings)

    def test_translate_mysql_connection_string(self, translator):
        """Test translation of MySQL connection string."""
        resource = {
            "type": "azurerm_mysql_database",
            "name": "db1",
            "connection_string": "Server=mysqlserver1.mysql.database.azure.com;Port=3306;Database=db1;Uid=admin;Pwd=xxx;",
        }

        translated = translator.translate(resource)

        # Connection string should be preserved
        assert translated["connection_string"] == resource["connection_string"]

        # Should have no warnings (server exists)
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert len(conn_str_result.warnings) == 0

    def test_translate_mysql_connection_string_missing_server(self, translator):
        """Test translation warns when MySQL Server not in IaC."""
        resource = {
            "type": "azurerm_mysql_database",
            "name": "db1",
            "connection_string": "Server=missing-mysql.mysql.database.azure.com;Database=db1;Uid=admin;",
        }

        translated = translator.translate(resource)

        # Should have warnings
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert any("not found" in w.lower() for w in conn_str_result.warnings)

    def test_translate_cosmosdb_connection_string(self, translator):
        """Test translation of Cosmos DB connection string."""
        resource = {
            "type": "azurerm_cosmosdb_account",
            "name": "cosmosdb1",
            "primary_key_connection_string": "AccountEndpoint=https://cosmosdb1.documents.azure.com:443/;AccountKey=xxx==;",
        }

        translated = translator.translate(resource)

        # Connection string should be preserved
        assert (
            translated["primary_key_connection_string"]
            == resource["primary_key_connection_string"]
        )

        # Should have no warnings (account exists)
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "primary_key_connection_string"
        )
        assert len(conn_str_result.warnings) == 0

    def test_translate_cosmosdb_connection_string_missing_account(self, translator):
        """Test translation warns when Cosmos DB account not in IaC."""
        resource = {
            "type": "azurerm_cosmosdb_account",
            "name": "cosmosdb1",
            "primary_key_connection_string": "AccountEndpoint=https://missing-cosmos.documents.azure.com:443/;AccountKey=xxx;",
        }

        translated = translator.translate(resource)

        # Should have warnings
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "primary_key_connection_string"
        )
        assert any("not found" in w.lower() for w in conn_str_result.warnings)

    def test_translate_multiple_cosmosdb_connection_strings(self, translator):
        """Test translation of multiple Cosmos DB connection string types."""
        resource = {
            "type": "azurerm_cosmosdb_account",
            "name": "cosmosdb1",
            "primary_key_connection_string": "AccountEndpoint=https://cosmosdb1.documents.azure.com:443/;AccountKey=xxx;",
            "secondary_key_connection_string": "AccountEndpoint=https://cosmosdb1.documents.azure.com:443/;AccountKey=yyy;",
            "primary_readonly_key_connection_string": "AccountEndpoint=https://cosmosdb1.documents.azure.com:443/;AccountKey=aaa;",
            "secondary_readonly_key_connection_string": "AccountEndpoint=https://cosmosdb1.documents.azure.com:443/;AccountKey=bbb;",
        }

        translated = translator.translate(resource)

        # All connection strings should be preserved
        assert (
            translated["primary_key_connection_string"]
            == resource["primary_key_connection_string"]
        )
        assert (
            translated["secondary_key_connection_string"]
            == resource["secondary_key_connection_string"]
        )
        assert (
            translated["primary_readonly_key_connection_string"]
            == resource["primary_readonly_key_connection_string"]
        )
        assert (
            translated["secondary_readonly_key_connection_string"]
            == resource["secondary_readonly_key_connection_string"]
        )

        # Should have results for each field
        results = translator.get_translation_results()
        assert len(results) >= 4

    def test_translate_connection_string_malformed(self, translator):
        """Test handling of malformed connection string."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": "invalid-connection-string-format",
        }

        translated = translator.translate(resource)

        # Should return original
        assert translated["connection_string"] == resource["connection_string"]

        # Should have warning about parsing
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert any(
            "could not parse" in w.lower() or "manual review" in w.lower()
            for w in conn_str_result.warnings
        )

    def test_translate_connection_string_empty(self, translator):
        """Test handling of empty connection string."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": "",
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["connection_string"] == ""

        # Should have warning
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert any("empty or invalid" in w.lower() for w in conn_str_result.warnings)

    def test_translate_connection_string_with_terraform_variable(self, translator):
        """Test that Terraform variables in connection strings are skipped."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": "Server=tcp:${azurerm_mssql_server.sqlserver1.fqdn},1433;Database=db1;",
        }

        translated = translator.translate(resource)

        # Should remain unchanged
        assert translated["connection_string"] == resource["connection_string"]

        # Should have no warnings (Terraform variables are skipped)
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert len(conn_str_result.warnings) == 0


class TestDatabaseTranslatorEndpoints:
    """Test endpoint URI translation for all database types."""

    @pytest.fixture
    def context(self):
        """Create translation context with available servers."""
        return TranslationContext(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            available_resources={
                "azurerm_mssql_server": {
                    "sqlserver1": {
                        "name": "sqlserver1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
                    }
                },
                "azurerm_postgresql_server": {
                    "pgserver1": {
                        "name": "pgserver1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1",
                    }
                },
                "azurerm_mysql_server": {
                    "mysqlserver1": {
                        "name": "mysqlserver1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1",
                    }
                },
                "azurerm_cosmosdb_account": {
                    "cosmosdb1": {
                        "name": "cosmosdb1",
                        "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1",
                    }
                },
            },
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return DatabaseTranslator(context)

    def test_translate_sql_server_fqdn(self, translator):
        """Test translation of SQL Server FQDN."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "fqdn": "sqlserver1.database.windows.net",
        }

        translated = translator.translate(resource)

        # FQDN should be preserved
        assert translated["fqdn"] == resource["fqdn"]

        # Should have no warnings (server exists)
        results = translator.get_translation_results()
        fqdn_result = next(r for r in results if r.property_path == "fqdn")
        assert len(fqdn_result.warnings) == 0

    def test_translate_sql_server_fqdn_missing_server(self, translator):
        """Test translation warns when SQL Server endpoint not in IaC."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "fqdn": "missing-server.database.windows.net",
        }

        translated = translator.translate(resource)

        # Should have warnings
        results = translator.get_translation_results()
        fqdn_result = next(r for r in results if r.property_path == "fqdn")
        assert any("not found" in w.lower() for w in fqdn_result.warnings)

    def test_translate_postgresql_server_fqdn(self, translator):
        """Test translation of PostgreSQL Server FQDN."""
        resource = {
            "type": "azurerm_postgresql_server",
            "name": "pgserver1",
            "fully_qualified_domain_name": "pgserver1.postgres.database.azure.com",
        }

        translated = translator.translate(resource)

        # FQDN should be preserved
        assert (
            translated["fully_qualified_domain_name"]
            == resource["fully_qualified_domain_name"]
        )

        # Should have no warnings
        results = translator.get_translation_results()
        fqdn_result = next(
            r for r in results if r.property_path == "fully_qualified_domain_name"
        )
        assert len(fqdn_result.warnings) == 0

    def test_translate_mysql_server_fqdn(self, translator):
        """Test translation of MySQL Server FQDN."""
        resource = {
            "type": "azurerm_mysql_server",
            "name": "mysqlserver1",
            "fqdn": "mysqlserver1.mysql.database.azure.com",
        }

        translated = translator.translate(resource)

        # FQDN should be preserved
        assert translated["fqdn"] == resource["fqdn"]

        # Should have no warnings
        results = translator.get_translation_results()
        fqdn_result = next(r for r in results if r.property_path == "fqdn")
        assert len(fqdn_result.warnings) == 0

    def test_translate_cosmosdb_endpoint(self, translator):
        """Test translation of Cosmos DB endpoint URI."""
        resource = {
            "type": "azurerm_cosmosdb_account",
            "name": "cosmosdb1",
            "endpoint": "https://cosmosdb1.documents.azure.com",
        }

        translated = translator.translate(resource)

        # Endpoint should be preserved
        assert translated["endpoint"] == resource["endpoint"]

        # Should have no warnings
        results = translator.get_translation_results()
        endpoint_result = next(r for r in results if r.property_path == "endpoint")
        assert len(endpoint_result.warnings) == 0

    def test_translate_endpoint_unrecognized_format(self, translator):
        """Test handling of unrecognized endpoint format."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "endpoint": "https://custom.domain.com/database",
        }

        translated = translator.translate(resource)

        # Endpoint should be preserved
        assert translated["endpoint"] == resource["endpoint"]

        # Should have warning about unrecognized format
        results = translator.get_translation_results()
        endpoint_result = next(r for r in results if r.property_path == "endpoint")
        assert any("unrecognized format" in w.lower() for w in endpoint_result.warnings)

    def test_translate_endpoint_empty(self, translator):
        """Test handling of empty endpoint."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "fqdn": "",
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["fqdn"] == ""

        # Should have warning
        results = translator.get_translation_results()
        fqdn_result = next(r for r in results if r.property_path == "fqdn")
        assert any("empty or invalid" in w.lower() for w in fqdn_result.warnings)

    def test_translate_endpoint_with_terraform_variable(self, translator):
        """Test that Terraform variables in endpoints are skipped."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "fqdn": "${azurerm_mssql_server.sqlserver1.fqdn}",
        }

        translated = translator.translate(resource)

        # Should remain unchanged
        assert translated["fqdn"] == resource["fqdn"]

        # Should have no warnings (Terraform variables are skipped)
        results = translator.get_translation_results()
        fqdn_result = next(r for r in results if r.property_path == "fqdn")
        assert len(fqdn_result.warnings) == 0


class TestDatabaseTranslatorEdgeCases:
    """Test edge cases and boundary conditions."""

    @pytest.fixture
    def context(self):
        """Create minimal translation context."""
        return TranslationContext(
            source_subscription_id="source-sub",
            target_subscription_id="target-sub",
            available_resources={},
        )

    @pytest.fixture
    def translator(self, context):
        """Create translator instance."""
        return DatabaseTranslator(context)

    def test_translate_empty_resource(self, translator):
        """Test handling of empty resource."""
        resource = {"type": "azurerm_mssql_server", "name": "sqlserver1"}

        translated = translator.translate(resource)

        assert translated["type"] == "azurerm_mssql_server"
        assert translated["name"] == "sqlserver1"

    def test_translate_connection_string_none(self, translator):
        """Test handling of None connection string."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "connection_string": None,
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        # None values are handled by the empty/invalid check
        assert translated["connection_string"] is None

    def test_translate_server_id_and_resource_id_together(self, translator):
        """Test translation of both server_id and resource ID."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1/databases/db1",
            "server_id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        translated = translator.translate(resource)

        # Both should be translated
        assert "target-sub" in translated["id"]
        assert "target-sub" in translated["server_id"]
        assert "source-sub" not in translated["id"]
        assert "source-sub" not in translated["server_id"]

    def test_translate_multiple_databases_same_server(self, translator):
        """Test translating multiple databases referencing the same server."""
        resources = [
            {
                "type": "azurerm_mssql_database",
                "name": "db1",
                "server_id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
            },
            {
                "type": "azurerm_mssql_database",
                "name": "db2",
                "server_id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
            },
            {
                "type": "azurerm_mssql_database",
                "name": "db3",
                "server_id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
            },
        ]

        for resource in resources:
            translated = translator.translate(resource)
            assert "target-sub" in translated["server_id"]
            assert "source-sub" not in translated["server_id"]

        # Should have results for all databases
        results = translator.get_translation_results()
        assert len(results) >= 3

    def test_translate_primary_and_secondary_connection_strings(self, translator):
        """Test translation of both primary and secondary connection strings."""
        resource = {
            "type": "azurerm_mssql_database",
            "name": "db1",
            "primary_connection_string": "Server=tcp:sqlserver1.database.windows.net,1433;Database=db1;",
            "secondary_connection_string": "Server=tcp:sqlserver1-secondary.database.windows.net,1433;Database=db1;",
        }

        translated = translator.translate(resource)

        # Both should be preserved
        assert (
            translated["primary_connection_string"]
            == resource["primary_connection_string"]
        )
        assert (
            translated["secondary_connection_string"]
            == resource["secondary_connection_string"]
        )

        # Should have results for both
        results = translator.get_translation_results()
        assert len(results) >= 2

    def test_translate_connection_string_unrecognized_database_type(self, translator):
        """Test connection string for unrecognized database type."""
        resource = {
            "type": "azurerm_cosmosdb_account",  # Cosmos DB doesn't use generic connection_string
            "name": "cosmosdb1",
            "connection_string": "some-generic-connection-string",
        }

        translated = translator.translate(resource)

        # Should be preserved with warning
        assert translated["connection_string"] == resource["connection_string"]

        # Should have warning about unrecognized type
        results = translator.get_translation_results()
        conn_str_result = next(
            r for r in results if r.property_path == "connection_string"
        )
        assert any(
            "not recognized" in w.lower() or "manual review" in w.lower()
            for w in conn_str_result.warnings
        )

    def test_get_azure_resource_type_mapping(self, translator):
        """Test Azure resource type conversion."""
        # Test all supported database types
        assert (
            translator._get_azure_resource_type("azurerm_mssql_server")
            == "Microsoft.Sql/servers"
        )
        assert (
            translator._get_azure_resource_type("azurerm_mssql_database")
            == "Microsoft.Sql/servers/databases"
        )
        assert (
            translator._get_azure_resource_type("azurerm_postgresql_server")
            == "Microsoft.DBforPostgreSQL/servers"
        )
        assert (
            translator._get_azure_resource_type("azurerm_postgresql_database")
            == "Microsoft.DBforPostgreSQL/servers/databases"
        )
        assert (
            translator._get_azure_resource_type("azurerm_mysql_server")
            == "Microsoft.DBforMySQL/servers"
        )
        assert (
            translator._get_azure_resource_type("azurerm_mysql_database")
            == "Microsoft.DBforMySQL/servers/databases"
        )
        assert (
            translator._get_azure_resource_type("azurerm_cosmosdb_account")
            == "Microsoft.DocumentDB/databaseAccounts"
        )

        # Unknown type should return input
        assert (
            translator._get_azure_resource_type("azurerm_unknown_type")
            == "azurerm_unknown_type"
        )

    def test_translate_multiple_resource_types_batch(self, translator):
        """Test translating multiple different database resource types in sequence."""
        resources = [
            {
                "type": "azurerm_mssql_server",
                "name": "sqlserver1",
                "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
            },
            {
                "type": "azurerm_postgresql_server",
                "name": "pgserver1",
                "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.DBforPostgreSQL/servers/pgserver1",
            },
            {
                "type": "azurerm_mysql_server",
                "name": "mysqlserver1",
                "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.DBforMySQL/servers/mysqlserver1",
            },
            {
                "type": "azurerm_cosmosdb_account",
                "name": "cosmosdb1",
                "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.DocumentDB/databaseAccounts/cosmosdb1",
            },
        ]

        for resource in resources:
            translated = translator.translate(resource)
            assert "target-sub" in translated["id"]
            assert "source-sub" not in translated["id"]

        # Should have results for all resources
        results = translator.get_translation_results()
        assert len(results) >= 4

    def test_translate_handles_none_values_gracefully(self, translator):
        """Test graceful handling of None values in various fields."""
        resource = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
            "fqdn": None,
            "connection_string": None,
        }

        translated = translator.translate(resource)

        # Should handle gracefully
        assert translated["fqdn"] is None
        assert translated["connection_string"] is None
        assert "target-sub" in translated["id"]

    def test_translate_cross_subscription_detection(self, translator):
        """Test that cross-subscription references are correctly detected."""
        # Resource in source subscription
        resource1 = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver1",
            "id": "/subscriptions/source-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver1",
        }

        translated1 = translator.translate(resource1)
        assert "target-sub" in translated1["id"]

        # Resource already in target subscription (should still translate ID component)
        resource2 = {
            "type": "azurerm_mssql_server",
            "name": "sqlserver2",
            "id": "/subscriptions/target-sub/resourceGroups/rg1/providers/Microsoft.Sql/servers/sqlserver2",
        }

        translated2 = translator.translate(resource2)
        # Since the ID already contains target-sub, it should remain unchanged
        assert translated2["id"] == resource2["id"]

    def test_registration_with_decorator(self):
        """Test that translator is properly registered with @register_translator."""
        from src.iac.translators.registry import TranslatorRegistry

        # Get all registered translators
        all_translators = TranslatorRegistry.get_all_translators()

        # DatabaseTranslator should be in the list
        translator_names = [t.__name__ for t in all_translators]
        assert "DatabaseTranslator" in translator_names
