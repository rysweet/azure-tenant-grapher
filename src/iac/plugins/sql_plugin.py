"""
SQL Database data plane replication plugin.

This plugin handles discovery and replication of Azure SQL Database data plane
items including:
- Database schemas
- Tables and data
- Stored procedures, functions, views

The plugin integrates with the IaC generation process to ensure that SQL Database
contents are preserved when deploying to new environments.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .base_plugin import DataPlaneItem, DataPlanePlugin, ReplicationResult

logger = logging.getLogger(__name__)


class SqlDatabasePlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure SQL Database.

    Discovers and replicates database schemas, tables, and data using
    Azure SDK and SQL tools (pyodbc).

    Example:
        plugin = SqlDatabasePlugin()
        items = plugin.discover(sql_database_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for SQL Database."""
        return "Microsoft.Sql/servers/databases"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover SQL Database schemas, tables, and objects.

        Uses Azure SDK and pyodbc to:
        1. Authenticate to the SQL Database
        2. List all user schemas (excluding system schemas)
        3. List all tables with row counts
        4. List stored procedures, functions, views
        5. Return structured DataPlaneItem list

        Args:
            resource: SQL Database resource dictionary containing:
                - id: SQL Database resource ID
                - name: Database name
                - properties: Database properties

        Returns:
            List of DataPlaneItem representing database contents

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../databases/mydb",
            ...     "type": "Microsoft.Sql/servers/databases",
            ...     "name": "mydb"
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of schemas/tables/objects
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for SqlDatabasePlugin: {resource}")

        db_name = resource.get("name", "unknown")
        self.logger.info(f"Discovering data plane items for SQL Database: {db_name}")

        items: List[DataPlaneItem] = []

        try:
            # Import required dependencies
            import pyodbc
            from azure.identity import DefaultAzureCredential

            # Parse server name from resource ID
            # /subscriptions/.../resourceGroups/.../providers/Microsoft.Sql/servers/{server}/databases/{db}
            resource_id = resource.get("id", "")
            parts = resource_id.split("/")

            server_name = None
            if "servers" in parts:
                server_idx = parts.index("servers")
                if server_idx + 1 < len(parts):
                    server_name = parts[server_idx + 1]

            if not server_name:
                self.logger.error("Could not parse server name from resource ID")
                return items

            # Construct server FQDN
            server_fqdn = f"{server_name}.database.windows.net"

            # Get access token for Azure SQL
            # Note: This requires Azure AD authentication to be configured on the SQL Server
            credential = DefaultAzureCredential()
            token_response = credential.get_token("https://database.windows.net/.default")
            access_token = token_response.token

            # Convert token to bytes for SQL Server driver
            token_bytes = bytes(access_token, "utf-8")

            # Connection string format for Azure AD token authentication
            # SQL_COPT_SS_ACCESS_TOKEN is 1256
            conn_str = (
                f"DRIVER={{ODBC Driver 18 for SQL Server}};"
                f"SERVER={server_fqdn};"
                f"DATABASE={db_name};"
                f"Encrypt=yes;"
                f"TrustServerCertificate=no;"
            )

            self.logger.debug(f"Connecting to SQL Database: {server_fqdn}/{db_name}")

            # Create connection with access token
            # The attrs_before parameter allows us to set SQL_COPT_SS_ACCESS_TOKEN before connecting
            connection = pyodbc.connect(
                conn_str,
                attrs_before={1256: token_bytes}  # SQL_COPT_SS_ACCESS_TOKEN
            )

            cursor = connection.cursor()

            # Discover schemas (exclude system schemas)
            try:
                schema_query = """
                    SELECT SCHEMA_NAME
                    FROM INFORMATION_SCHEMA.SCHEMATA
                    WHERE SCHEMA_NAME NOT IN ('sys', 'INFORMATION_SCHEMA', 'guest', 'db_owner',
                                               'db_accessadmin', 'db_securityadmin', 'db_ddladmin',
                                               'db_backupoperator', 'db_datareader', 'db_datawriter',
                                               'db_denydatareader', 'db_denydatawriter')
                    ORDER BY SCHEMA_NAME
                """
                cursor.execute(schema_query)
                schemas = [row.SCHEMA_NAME for row in cursor.fetchall()]

                self.logger.debug(f"Found {len(schemas)} user schemas")

                for schema_name in schemas:
                    items.append(
                        DataPlaneItem(
                            name=schema_name,
                            item_type="schema",
                            properties={"type": "schema"},
                            source_resource_id=resource["id"],
                            metadata={"server": server_name, "database": db_name}
                        )
                    )
            except pyodbc.Error as e:
                self.logger.warning(f"Failed to list schemas: {e}")

            # Discover tables with row counts
            try:
                table_query = """
                    SELECT
                        t.TABLE_SCHEMA,
                        t.TABLE_NAME,
                        p.rows AS row_count
                    FROM INFORMATION_SCHEMA.TABLES t
                    LEFT JOIN sys.partitions p ON p.object_id = OBJECT_ID(t.TABLE_SCHEMA + '.' + t.TABLE_NAME)
                        AND p.index_id IN (0, 1)
                    WHERE t.TABLE_TYPE = 'BASE TABLE'
                        AND t.TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
                    ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME
                """
                cursor.execute(table_query)

                for row in cursor.fetchall():
                    table_schema = row.TABLE_SCHEMA
                    table_name = row.TABLE_NAME
                    row_count = row.row_count or 0

                    items.append(
                        DataPlaneItem(
                            name=f"{table_schema}.{table_name}",
                            item_type="table",
                            properties={
                                "schema": table_schema,
                                "table_name": table_name,
                                "row_count": row_count
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "server": server_name,
                                "database": db_name,
                                "row_count": row_count
                            }
                        )
                    )

                self.logger.debug(f"Found {len([i for i in items if i.item_type == 'table'])} tables")
            except pyodbc.Error as e:
                self.logger.warning(f"Failed to list tables: {e}")

            # Discover stored procedures
            try:
                proc_query = """
                    SELECT
                        ROUTINE_SCHEMA,
                        ROUTINE_NAME
                    FROM INFORMATION_SCHEMA.ROUTINES
                    WHERE ROUTINE_TYPE = 'PROCEDURE'
                        AND ROUTINE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
                    ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
                """
                cursor.execute(proc_query)

                for row in cursor.fetchall():
                    proc_schema = row.ROUTINE_SCHEMA
                    proc_name = row.ROUTINE_NAME

                    items.append(
                        DataPlaneItem(
                            name=f"{proc_schema}.{proc_name}",
                            item_type="stored_procedure",
                            properties={
                                "schema": proc_schema,
                                "name": proc_name
                            },
                            source_resource_id=resource["id"],
                            metadata={"server": server_name, "database": db_name}
                        )
                    )

                self.logger.debug(f"Found {len([i for i in items if i.item_type == 'stored_procedure'])} stored procedures")
            except pyodbc.Error as e:
                self.logger.warning(f"Failed to list stored procedures: {e}")

            # Discover functions
            try:
                func_query = """
                    SELECT
                        ROUTINE_SCHEMA,
                        ROUTINE_NAME
                    FROM INFORMATION_SCHEMA.ROUTINES
                    WHERE ROUTINE_TYPE = 'FUNCTION'
                        AND ROUTINE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
                    ORDER BY ROUTINE_SCHEMA, ROUTINE_NAME
                """
                cursor.execute(func_query)

                for row in cursor.fetchall():
                    func_schema = row.ROUTINE_SCHEMA
                    func_name = row.ROUTINE_NAME

                    items.append(
                        DataPlaneItem(
                            name=f"{func_schema}.{func_name}",
                            item_type="function",
                            properties={
                                "schema": func_schema,
                                "name": func_name
                            },
                            source_resource_id=resource["id"],
                            metadata={"server": server_name, "database": db_name}
                        )
                    )

                self.logger.debug(f"Found {len([i for i in items if i.item_type == 'function'])} functions")
            except pyodbc.Error as e:
                self.logger.warning(f"Failed to list functions: {e}")

            # Discover views
            try:
                view_query = """
                    SELECT
                        TABLE_SCHEMA,
                        TABLE_NAME
                    FROM INFORMATION_SCHEMA.VIEWS
                    WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
                    ORDER BY TABLE_SCHEMA, TABLE_NAME
                """
                cursor.execute(view_query)

                for row in cursor.fetchall():
                    view_schema = row.TABLE_SCHEMA
                    view_name = row.TABLE_NAME

                    items.append(
                        DataPlaneItem(
                            name=f"{view_schema}.{view_name}",
                            item_type="view",
                            properties={
                                "schema": view_schema,
                                "name": view_name
                            },
                            source_resource_id=resource["id"],
                            metadata={"server": server_name, "database": db_name}
                        )
                    )

                self.logger.debug(f"Found {len([i for i in items if i.item_type == 'view'])} views")
            except pyodbc.Error as e:
                self.logger.warning(f"Failed to list views: {e}")

            # Clean up
            cursor.close()
            connection.close()

        except ImportError as e:
            self.logger.error(
                f"Required dependencies not installed. Install with: "
                f"pip install pyodbc azure-identity. "
                f"Note: pyodbc requires ODBC Driver 18 for SQL Server. "
                f"Error: {e}"
            )
        except Exception as e:
            self.logger.error(f"Unexpected error discovering SQL Database items: {e}")

        self.logger.info(
            f"Discovered {len(items)} data plane items in SQL Database '{db_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate SQL Database data plane items.

        For databases, this generates:
        - Documentation about schema export/import
        - BCP command templates for data export
        - Azure Data Factory pipeline references
        - sqlcmd script templates

        Args:
            items: List of SQL Database data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code with data migration documentation

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="dbo.users", item_type="table", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "BCP" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by SqlDatabasePlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} SQL Database items"
        )

        if not items:
            return "# No SQL Database data plane items to replicate\n"

        code_lines = [
            "# SQL Database Data Plane Items",
            "# Generated by Azure Tenant Grapher - SqlDatabasePlugin",
            "#",
            "# DATA MIGRATION NOTE: This plugin provides documentation for data migration.",
            "# Actual data replication requires:",
            "#   - BCP (Bulk Copy Program): For data export/import",
            "#   - sqlcmd: For schema scripts",
            "#   - Azure Data Factory: For large-scale migrations",
            "#   - SQL Server Management Studio: For manual operations",
            "#   - Azure Database Migration Service: For complete database migrations",
            "",
        ]

        # Group items by type
        schemas = [item for item in items if item.item_type == "schema"]
        tables = [item for item in items if item.item_type == "table"]
        stored_procedures = [item for item in items if item.item_type == "stored_procedure"]
        functions = [item for item in items if item.item_type == "function"]
        views = [item for item in items if item.item_type == "view"]

        # Summary
        code_lines.extend([
            f"# Discovered Items:",
            f"#   - {len(schemas)} schema(s)",
            f"#   - {len(tables)} table(s)",
            f"#   - {len(stored_procedures)} stored procedure(s)",
            f"#   - {len(functions)} function(s)",
            f"#   - {len(views)} view(s)",
            "",
        ])

        # Schema export documentation
        if schemas:
            code_lines.extend([
                "# Schema Export Commands:",
                "# Export database schema using sqlcmd:",
                "#",
            ])

            for schema in schemas:
                schema_name = schema.name
                code_lines.append(
                    f"#   sqlcmd -S source-server.database.windows.net -d source-db "
                    f"-Q \"SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{schema_name}'\" "
                    f"-o schema_{self._sanitize_name(schema_name)}.txt"
                )

            code_lines.append("")

        # Table data export with BCP
        if tables:
            code_lines.extend([
                "# Data Export with BCP:",
                "# Export table data using BCP (Bulk Copy Program):",
                "#",
            ])

            for table in tables[:10]:  # Limit to first 10 tables in documentation
                table_name = table.name
                safe_name = self._sanitize_name(table_name.replace(".", "_"))
                row_count = table.properties.get("row_count", 0)

                code_lines.extend([
                    f"# Table: {table_name} ({row_count} rows)",
                    f"#   bcp {table_name} out {safe_name}.dat "
                    f"-S source-server.database.windows.net -d source-db -T -n",
                ])

            if len(tables) > 10:
                code_lines.append(f"# ... and {len(tables) - 10} more tables")

            code_lines.append("")

        # Data import with BCP
        if tables:
            code_lines.extend([
                "# Data Import with BCP:",
                "# Import table data to target database:",
                "#",
            ])

            for table in tables[:10]:
                table_name = table.name
                safe_name = self._sanitize_name(table_name.replace(".", "_"))

                code_lines.append(
                    f"#   bcp {table_name} in {safe_name}.dat "
                    f"-S target-server.database.windows.net -d target-db -T -n"
                )

            if len(tables) > 10:
                code_lines.append(f"# ... and {len(tables) - 10} more tables")

            code_lines.append("")

        # Azure Data Factory migration template
        code_lines.extend([
            "# Azure Data Factory Pipeline Template:",
            "# For large-scale migrations, use Azure Data Factory:",
            "#",
            "# 1. Create linked services for source and target SQL databases",
            "# 2. Create datasets for each table",
            "# 3. Create copy activity pipelines",
            "# 4. Execute and monitor pipelines",
            "#",
            "# Reference: https://docs.microsoft.com/azure/data-factory/connector-azure-sql-database",
            "",
        ])

        # Stored procedures, functions, views migration
        if stored_procedures or functions or views:
            code_lines.extend([
                "# Database Objects Migration:",
                "# Export stored procedures, functions, and views using SSMS or sqlcmd:",
                "#",
                "# Using SQL Server Management Studio (SSMS):",
                "#   1. Right-click database -> Tasks -> Generate Scripts",
                "#   2. Select specific objects (procedures, functions, views)",
                "#   3. Export to .sql file",
                "#   4. Execute on target database",
                "#",
            ])

            if stored_procedures:
                code_lines.append(f"# Found {len(stored_procedures)} stored procedure(s):")
                for proc in stored_procedures[:5]:
                    code_lines.append(f"#   - {proc.name}")
                if len(stored_procedures) > 5:
                    code_lines.append(f"#   ... and {len(stored_procedures) - 5} more")
                code_lines.append("#")

            if functions:
                code_lines.append(f"# Found {len(functions)} function(s):")
                for func in functions[:5]:
                    code_lines.append(f"#   - {func.name}")
                if len(functions) > 5:
                    code_lines.append(f"#   ... and {len(functions) - 5} more")
                code_lines.append("#")

            if views:
                code_lines.append(f"# Found {len(views)} view(s):")
                for view in views[:5]:
                    code_lines.append(f"#   - {view.name}")
                if len(views) > 5:
                    code_lines.append(f"#   ... and {len(views) - 5} more")
                code_lines.append("#")

        # Migration script template
        code_lines.extend([
            "",
            "# Complete Migration Script Template:",
            "# Save as: migrate_sql_data.sh",
            "#",
            "# #!/bin/bash",
            "# SOURCE_SERVER='source-server.database.windows.net'",
            "# TARGET_SERVER='target-server.database.windows.net'",
            "# SOURCE_DB='source-db'",
            "# TARGET_DB='target-db'",
            "#",
            "# # Export all tables",
        ])

        for table in tables[:5]:
            table_name = table.name
            safe_name = self._sanitize_name(table_name.replace(".", "_"))
            code_lines.append(
                f"# bcp {table_name} out {safe_name}.dat -S $SOURCE_SERVER -d $SOURCE_DB -T -n"
            )

        if len(tables) > 5:
            code_lines.append(f"# # ... export {len(tables) - 5} more tables")

        code_lines.extend([
            "#",
            "# # Import all tables",
        ])

        for table in tables[:5]:
            table_name = table.name
            safe_name = self._sanitize_name(table_name.replace(".", "_"))
            code_lines.append(
                f"# bcp {table_name} in {safe_name}.dat -S $TARGET_SERVER -d $TARGET_DB -T -n"
            )

        if len(tables) > 5:
            code_lines.append(f"# # ... import {len(tables) - 5} more tables")

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate SQL Database contents from source to target.

        This is a partial implementation that provides guidance on data migration
        tools and approaches. Full automated replication would require:
        - BCP for data export/import
        - sqlcmd for schema scripts
        - Proper authentication to both databases
        - Transaction handling for consistency

        Args:
            source_resource: Source SQL Database resource containing:
                - id: Azure resource ID
                - type: Microsoft.Sql/servers/databases
                - name: Database name
            target_resource: Target SQL Database resource with same structure

        Returns:
            ReplicationResult with operation statistics

        Raises:
            ValueError: If source or target resource is invalid

        Example:
            >>> result = plugin.replicate(source_db, target_db)
            >>> if result.success:
            ...     print(f"Replicated {result.items_replicated} items")
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")
        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating from SQL Database {source_name} to {target_name}"
        )

        # 1. Discover items from source
        try:
            source_items = self.discover(source_resource)
        except Exception as e:
            self.logger.error(f"Failed to discover items from source: {e}")
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"Failed to discover items from source: {e}"],
                warnings=[],
            )

        if not source_items:
            self.logger.info("No items to replicate")
            warnings = [
                "No items found in source SQL Database.",
                "This could be due to:",
                "  - Empty database",
                "  - Missing pyodbc dependency",
                "  - Connection/authentication issues",
                "If the database has data, use these tools for manual migration:",
                "  - Azure Data Factory: For automated, large-scale migrations",
                "  - BCP (Bulk Copy Program): For table data export/import",
                "  - sqlcmd: For schema and object scripts",
                "  - SQL Server Management Studio: For manual operations",
                "  - Azure Database Migration Service: For complete database migrations",
            ]
            return ReplicationResult(
                success=True,
                items_discovered=0,
                items_replicated=0,
                errors=[],
                warnings=warnings,
            )

        self.logger.info(f"Discovered {len(source_items)} items from source")

        # Return result with guidance
        # Full implementation would require BCP, sqlcmd, or Azure Data Factory integration
        warnings = [
            "SQL Database replication not fully implemented.",
            "Use one of the following tools for data migration:",
            "  - Azure Data Factory: For automated, large-scale migrations",
            "  - BCP (Bulk Copy Program): For table data export/import",
            "  - sqlcmd: For schema and object scripts",
            "  - SQL Server Management Studio: For manual operations",
            "  - Azure Database Migration Service: For complete database migrations",
            f"Discovered {len(source_items)} items that need migration.",
        ]

        return ReplicationResult(
            success=False,
            items_discovered=len(source_items),
            items_replicated=0,
            errors=[
                "Automated SQL Database replication not fully implemented.",
                "Manual migration required using BCP, sqlcmd, or Azure Data Factory."
            ],
            warnings=warnings,
        )

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names and file names.

        Args:
            name: Original name (may contain hyphens, dots, special chars)

        Returns:
            Sanitized name safe for Terraform identifiers and file names

        Example:
            >>> plugin = SqlDatabasePlugin()
            >>> plugin._sanitize_name("dbo.Users-Table")
            'sql_dbo_users_table'
        """
        # Replace special characters with underscores
        sanitized = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        sanitized = sanitized.replace("[", "").replace("]", "")
        sanitized = sanitized.replace("(", "").replace(")", "")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "sql_" + sanitized

        return sanitized.lower()
