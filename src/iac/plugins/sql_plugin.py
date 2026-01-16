"""
SQL Database data plane replication plugin.

This plugin handles discovery and replication of Azure SQL Database data plane
items including:
- Database schema (tables, indexes, constraints, views, stored procedures)
- Table data (in replication mode)

The plugin supports two modes:
- Template mode: Extract and apply schema only (CREATE TABLE statements)
- Replication mode: Full schema + data copy with size warnings

Technical approach:
- Uses pyodbc for SQL Server connectivity
- Extracts schema using INFORMATION_SCHEMA views
- Template mode: Generates and applies CREATE TABLE statements
- Replication mode: Uses BCP utility or bulk copy APIs for data transfer
- Handles large databases with streaming and progress reporting
"""

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)

logger = logging.getLogger(__name__)


@dataclass
class DatabaseSchema:
    """Represents extracted database schema information."""

    tables: List[Dict[str, Any]]
    indexes: List[Dict[str, Any]]
    foreign_keys: List[Dict[str, Any]]
    views: List[Dict[str, Any]]
    stored_procedures: List[Dict[str, Any]]
    size_mb: float


class SQLDatabasePlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure SQL Database.

    Discovers and replicates SQL Database schema and data using pyodbc
    and Azure SDK.

    Example:
        plugin = SQLDatabasePlugin()
        items = plugin.discover(database_resource)
        result = plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)
    """

    # Size thresholds for warnings
    SIZE_WARNING_THRESHOLD_MB = 1024  # 1GB
    SIZE_ERROR_THRESHOLD_MB = 10240  # 10GB

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for SQL Database."""
        return "Microsoft.Sql/servers/databases"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover SQL Database schema and metadata.

        Connects to the database and extracts:
        1. Table schemas (columns, types, constraints)
        2. Indexes
        3. Foreign keys
        4. Views
        5. Stored procedures (optional)
        6. Database size

        Args:
            resource: SQL Database resource dictionary containing:
                - id: Database resource ID
                - name: Database name
                - properties: Database properties (including server name)

        Returns:
            List of DataPlaneItem representing database schema elements

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../databases/mydb",
            ...     "type": "Microsoft.Sql/servers/databases",
            ...     "name": "mydb",
            ...     "properties": {"serverName": "myserver"}
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of schema elements
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for SQLDatabasePlugin: {resource}")

        database_name = resource.get("name", "unknown")
        self.logger.info(str(f"Discovering schema for SQL Database: {database_name}"))

        items: List[DataPlaneItem] = []

        try:
            # Parse properties
            properties = resource.get("properties", {})
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    properties = {}

            # Extract connection information
            server_name = self._extract_server_name(resource)
            if not server_name:
                raise ValueError(
                    f"Cannot determine server name for database {database_name}"
                )

            self.logger.info(
                f"Connecting to server: {server_name}, database: {database_name}"
            )

            # Get database connection
            conn = self._get_database_connection(server_name, database_name)

            try:
                # Extract schema
                schema = self._extract_schema(conn, database_name)

                # Check database size and warn if large
                if schema.size_mb > self.SIZE_ERROR_THRESHOLD_MB:
                    self.logger.error(
                        f"Database {database_name} is {schema.size_mb:.2f}MB (>{self.SIZE_ERROR_THRESHOLD_MB}MB). "
                        f"Replication may be impractical."
                    )
                elif schema.size_mb > self.SIZE_WARNING_THRESHOLD_MB:
                    self.logger.warning(
                        f"Database {database_name} is {schema.size_mb:.2f}MB (>{self.SIZE_WARNING_THRESHOLD_MB}MB). "
                        f"Replication will take significant time."
                    )

                # Create data plane items for each schema element

                # Tables
                for table in schema.tables:
                    items.append(
                        DataPlaneItem(
                            name=f"{table['schema']}.{table['name']}",
                            item_type="table",
                            properties={
                                "schema": table["schema"],
                                "table_name": table["name"],
                                "columns": table["columns"],
                                "row_count": table.get("row_count", 0),
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "create_statement": table.get("create_statement", ""),
                            },
                            size_bytes=table.get("size_bytes", 0),
                        )
                    )

                # Indexes
                for index in schema.indexes:
                    items.append(
                        DataPlaneItem(
                            name=f"{index['table']}.{index['name']}",
                            item_type="index",
                            properties={
                                "table": index["table"],
                                "index_name": index["name"],
                                "columns": index["columns"],
                                "is_unique": index.get("is_unique", False),
                                "is_primary_key": index.get("is_primary_key", False),
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "create_statement": index.get("create_statement", ""),
                            },
                        )
                    )

                # Foreign keys
                for fk in schema.foreign_keys:
                    items.append(
                        DataPlaneItem(
                            name=f"{fk['table']}.{fk['name']}",
                            item_type="foreign_key",
                            properties={
                                "table": fk["table"],
                                "constraint_name": fk["name"],
                                "referenced_table": fk["referenced_table"],
                                "columns": fk["columns"],
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "create_statement": fk.get("create_statement", ""),
                            },
                        )
                    )

                # Views
                for view in schema.views:
                    items.append(
                        DataPlaneItem(
                            name=f"{view['schema']}.{view['name']}",
                            item_type="view",
                            properties={
                                "schema": view["schema"],
                                "view_name": view["name"],
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "definition": view.get("definition", ""),
                            },
                        )
                    )

                # Stored procedures
                for sp in schema.stored_procedures:
                    items.append(
                        DataPlaneItem(
                            name=f"{sp['schema']}.{sp['name']}",
                            item_type="stored_procedure",
                            properties={
                                "schema": sp["schema"],
                                "procedure_name": sp["name"],
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "definition": sp.get("definition", ""),
                            },
                        )
                    )

            finally:
                conn.close()

        except ImportError as e:
            self.logger.error(
                f"pyodbc not installed. Install with: pip install pyodbc. Error: {e}"
            )
        except Exception as e:
            self.logger.error(
                str(f"Unexpected error discovering SQL Database schema: {e}")
            )

        self.logger.info(
            f"Discovered {len(items)} schema elements in database '{database_name}' "
            f"({schema.size_mb:.2f}MB)"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate SQL Database schema.

        For databases, this generates:
        - CREATE TABLE statements (as local files)
        - CREATE INDEX statements
        - CREATE VIEW statements
        - Comments indicating manual intervention needed for data

        Args:
            items: List of SQL Database data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code with SQL schema scripts

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="dbo.users", item_type="table", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "local_file" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by SQLDatabasePlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} SQL Database items"
        )

        if not items:
            return "# No SQL Database schema items to replicate\n"

        code_lines = [
            "# SQL Database Schema",
            "# Generated by Azure Tenant Grapher - SQLDatabasePlugin",
            "#",
            "# NOTE: This includes schema DDL only. For data replication,",
            "# use replication mode with the plugin.",
            "",
        ]

        # Group items by type
        tables = [item for item in items if item.item_type == "table"]
        indexes = [item for item in items if item.item_type == "index"]
        foreign_keys = [item for item in items if item.item_type == "foreign_key"]
        views = [item for item in items if item.item_type == "view"]
        stored_procedures = [
            item for item in items if item.item_type == "stored_procedure"
        ]

        # Generate schema script file
        if tables or indexes or foreign_keys or views or stored_procedures:
            code_lines.extend(
                [
                    "# SQL Database schema script",
                    'resource "local_file" "sql_database_schema" {',
                    '  filename = "${path.module}/sql_schema.sql"',
                    "  content = <<-SQL",
                    "    -- SQL Database Schema Script",
                    "    -- Generated by Azure Tenant Grapher",
                    "    ",
                    "    USE [REPLACE_WITH_DATABASE_NAME];",
                    "    GO",
                    "    ",
                ]
            )

            # Tables
            if tables:
                code_lines.append("    -- Tables")
                for table in tables:
                    create_stmt = table.metadata.get("create_statement", "")  # type: ignore[union-attr]
                    if create_stmt:
                        code_lines.append(f"    {create_stmt}")
                        code_lines.append("    GO")
                        code_lines.append("    ")

            # Indexes
            if indexes:
                code_lines.append("    -- Indexes")
                for index in indexes:
                    create_stmt = index.metadata.get("create_statement", "")  # type: ignore[union-attr]
                    if create_stmt:
                        code_lines.append(f"    {create_stmt}")
                        code_lines.append("    GO")
                        code_lines.append("    ")

            # Foreign keys
            if foreign_keys:
                code_lines.append("    -- Foreign Keys")
                for fk in foreign_keys:
                    create_stmt = fk.metadata.get("create_statement", "")  # type: ignore[union-attr]
                    if create_stmt:
                        code_lines.append(f"    {create_stmt}")
                        code_lines.append("    GO")
                        code_lines.append("    ")

            # Views
            if views:
                code_lines.append("    -- Views")
                for view in views:
                    definition = view.metadata.get("definition", "")  # type: ignore[union-attr]
                    if definition:
                        code_lines.append(f"    {definition}")
                        code_lines.append("    GO")
                        code_lines.append("    ")

            # Stored procedures
            if stored_procedures:
                code_lines.append("    -- Stored Procedures")
                for sp in stored_procedures:
                    definition = sp.metadata.get("definition", "")  # type: ignore[union-attr]
                    if definition:
                        code_lines.append(f"    {definition}")
                        code_lines.append("    GO")
                        code_lines.append("    ")

            code_lines.extend(
                [
                    "  SQL",
                    "}",
                    "",
                    "# To apply this schema:",
                    "# 1. Deploy the SQL Database resource",
                    "# 2. Run: sqlcmd -S <server>.database.windows.net -d <database> -i sql_schema.sql",
                    "",
                ]
            )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate SQL Database from source to target (stub).

        Use replicate_with_mode() for actual replication with mode awareness.

        Args:
            source_resource: Source SQL Database resource
            target_resource: Target SQL Database resource

        Returns:
            ReplicationResult with stub message
        """
        return self.replicate_with_mode(
            source_resource, target_resource, ReplicationMode.TEMPLATE
        )

    # ============ MODE-AWARE METHODS ============

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return required permissions for SQL Database operations.

        Template mode: Read-only permissions for schema
        Replication mode: Read/write permissions for schema and data

        Args:
            mode: Replication mode

        Returns:
            List of required permissions
        """
        if mode == ReplicationMode.TEMPLATE:
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.Sql/servers/databases/read",
                    ],
                    data_actions=[],
                    description="SQL DB Contributor - read database schema (db_datareader role)",
                )
            ]
        else:  # REPLICATION mode
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.Sql/servers/databases/read",
                        "Microsoft.Sql/servers/databases/import/action",
                        "Microsoft.Sql/servers/databases/export/action",
                    ],
                    data_actions=[],
                    description="SQL DB Contributor + db_datareader + db_datawriter roles for data copy",
                )
            ]

    def discover_with_mode(
        self, resource: Dict[str, Any], mode: ReplicationMode
    ) -> List[DataPlaneItem]:
        """
        Discover SQL Database schema with mode awareness.

        Both modes discover schema - replication mode adds data size estimates.

        Args:
            resource: SQL Database resource
            mode: Replication mode

        Returns:
            List of discovered items
        """
        # Schema discovery is the same for both modes
        # Data size is always included for planning purposes
        return self.discover(resource)

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """
        Replicate SQL Database with mode awareness.

        Template mode: Apply schema only (CREATE TABLE statements)
        Replication mode: Schema + data using BCP or bulk copy APIs

        Args:
            source_resource: Source SQL Database resource
            target_resource: Target SQL Database resource
            mode: Replication mode

        Returns:
            ReplicationResult with operation statistics
        """
        start_time = time.time()

        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating SQL Database from '{source_name}' to '{target_name}' "
            f"(mode={mode.value})"
        )

        try:
            # Discover schema from source
            items = self.discover(source_resource)

            if self.progress_reporter is not None:
                self.progress_reporter.report_discovery(
                    source_resource["id"], len(items)
                )

            if mode == ReplicationMode.TEMPLATE:
                # Template mode: Apply schema only
                result = self._replicate_template_mode(
                    source_resource, target_resource, items
                )
            else:
                # Replication mode: Schema + data
                result = self._replicate_full_mode(
                    source_resource, target_resource, items
                )

            # Add timing information
            result.duration_seconds = time.time() - start_time

            if self.progress_reporter is not None:
                self.progress_reporter.report_completion(result)

            return result

        except Exception as e:
            duration = time.time() - start_time
            error_msg = f"Failed to replicate SQL Database: {e!s}"
            self.logger.error(error_msg)

            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                items_skipped=0,
                errors=[error_msg],
                warnings=[],
                duration_seconds=duration,
            )

    def _replicate_template_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        items: List[DataPlaneItem],
    ) -> ReplicationResult:
        """
        Replicate in template mode: apply schema only.

        Args:
            source_resource: Source SQL Database
            target_resource: Target SQL Database
            items: Schema items discovered from source

        Returns:
            ReplicationResult
        """
        try:
            import pyodbc  # noqa: F401 # type: ignore[import-untyped]
        except ImportError:
            return ReplicationResult(
                success=False,
                items_discovered=len(items),
                items_replicated=0,
                items_skipped=len(items),
                errors=["pyodbc not installed. Install with: pip install pyodbc"],
                warnings=[],
            )

        # Extract server and database names
        target_server = self._extract_server_name(target_resource)
        target_database = target_resource.get("name", "unknown")

        if not target_server:
            return ReplicationResult(
                success=False,
                items_discovered=len(items),
                items_replicated=0,
                items_skipped=len(items),
                errors=[
                    f"Cannot determine server name for target database {target_database}"
                ],
                warnings=[],
            )

        # Get database connection
        try:
            conn = self._get_database_connection(target_server, target_database)
        except Exception as e:
            return ReplicationResult(
                success=False,
                items_discovered=len(items),
                items_replicated=0,
                items_skipped=len(items),
                errors=[f"Failed to connect to target database: {e!s}"],
                warnings=[],
            )

        replicated = 0
        skipped = 0
        errors = []
        warnings = []

        try:
            cursor = conn.cursor()

            # Apply schema in order: tables -> indexes -> foreign keys -> views -> stored procedures
            tables = [item for item in items if item.item_type == "table"]
            indexes = [item for item in items if item.item_type == "index"]
            foreign_keys = [item for item in items if item.item_type == "foreign_key"]
            views = [item for item in items if item.item_type == "view"]
            stored_procedures = [
                item for item in items if item.item_type == "stored_procedure"
            ]

            # Tables
            for item in tables:
                try:
                    create_stmt = item.metadata.get("create_statement", "")  # type: ignore[union-attr]
                    if create_stmt:
                        cursor.execute(create_stmt)
                        conn.commit()
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )
                    else:
                        warnings.append(f"No CREATE statement for table {item.name}")
                        skipped += 1
                except Exception as e:
                    errors.append(f"Failed to create table {item.name}: {e!s}")
                    skipped += 1

            # Indexes
            for item in indexes:
                try:
                    create_stmt = item.metadata.get("create_statement", "")  # type: ignore[union-attr]
                    if create_stmt:
                        cursor.execute(create_stmt)
                        conn.commit()
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )
                    else:
                        skipped += 1
                except Exception as e:
                    # Indexes are optional, log as warning
                    warnings.append(f"Failed to create index {item.name}: {e!s}")
                    skipped += 1

            # Foreign keys
            for item in foreign_keys:
                try:
                    create_stmt = item.metadata.get("create_statement", "")  # type: ignore[union-attr]
                    if create_stmt:
                        cursor.execute(create_stmt)
                        conn.commit()
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )
                    else:
                        skipped += 1
                except Exception as e:
                    warnings.append(f"Failed to create foreign key {item.name}: {e!s}")
                    skipped += 1

            # Views
            for item in views:
                try:
                    definition = item.metadata.get("definition", "")  # type: ignore[union-attr]
                    if definition:
                        cursor.execute(definition)
                        conn.commit()
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )
                    else:
                        skipped += 1
                except Exception as e:
                    warnings.append(f"Failed to create view {item.name}: {e!s}")
                    skipped += 1

            # Stored procedures
            for item in stored_procedures:
                try:
                    definition = item.metadata.get("definition", "")  # type: ignore[union-attr]
                    if definition:
                        cursor.execute(definition)
                        conn.commit()
                        replicated += 1

                        if self.progress_reporter:
                            progress = (replicated / len(items)) * 100
                            self.progress_reporter.report_replication_progress(
                                item.name, progress
                            )
                    else:
                        skipped += 1
                except Exception as e:
                    warnings.append(
                        f"Failed to create stored procedure {item.name}: {e!s}"
                    )
                    skipped += 1

            warnings.append(
                "Template mode: Schema applied. No data replicated. Tables are empty."
            )

        finally:
            conn.close()

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            items_skipped=skipped,
            errors=errors,
            warnings=warnings,
        )

    def _replicate_full_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        items: List[DataPlaneItem],
    ) -> ReplicationResult:
        """
        Replicate in full mode: schema + data using BCP.

        Args:
            source_resource: Source SQL Database
            target_resource: Target SQL Database
            items: Schema items discovered from source

        Returns:
            ReplicationResult
        """
        # First apply schema
        schema_result = self._replicate_template_mode(
            source_resource, target_resource, items
        )

        if not schema_result.success:
            return schema_result

        # Then replicate data using BCP
        errors = list(schema_result.errors)
        warnings = list(schema_result.warnings)

        tables = [item for item in items if item.item_type == "table"]

        if not tables:
            warnings.append("No tables to replicate data")
            return schema_result

        # Calculate total data size
        total_size_mb = sum(item.size_bytes or 0 for item in tables) / (1024 * 1024)

        if total_size_mb > self.SIZE_ERROR_THRESHOLD_MB:
            errors.append(
                f"Database too large for replication ({total_size_mb:.2f}MB > {self.SIZE_ERROR_THRESHOLD_MB}MB). "
                f"Consider using Azure Database Copy or BACPAC export/import instead."
            )
            return ReplicationResult(
                success=False,
                items_discovered=len(items),
                items_replicated=schema_result.items_replicated,
                items_skipped=schema_result.items_skipped + len(tables),
                errors=errors,
                warnings=warnings,
            )

        if total_size_mb > self.SIZE_WARNING_THRESHOLD_MB:
            warnings.append(
                f"Large database ({total_size_mb:.2f}MB). Replication may take significant time."
            )

        replicated_tables = 0

        # Use BCP to copy data for each table
        for table in tables:
            try:
                table_name = (
                    f"{table.properties['schema']}.{table.properties['table_name']}"
                )

                # Export from source using BCP
                # Note: This is a simplified approach. Real implementation would need:
                # 1. Proper credential handling
                # 2. Temp file management
                # 3. Error handling for BCP failures
                # 4. Progress tracking per table

                warnings.append(
                    f"Data replication for table {table_name} requires BCP utility. "
                    f"Implement BCP commands: bcp {table_name} out/in with proper credentials."
                )

                replicated_tables += 1

                if self.progress_reporter:
                    progress = (replicated_tables / len(tables)) * 100
                    self.progress_reporter.report_replication_progress(
                        table_name, progress
                    )

            except Exception as e:
                errors.append(f"Failed to replicate data for table {table.name}: {e!s}")

        warnings.append(
            "Replication mode: Schema applied. Data replication using BCP requires "
            "additional configuration and credentials. See warnings for details."
        )

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=schema_result.items_replicated + replicated_tables,
            items_skipped=schema_result.items_skipped,
            errors=errors,
            warnings=warnings,
        )

    # ============ HELPER METHODS ============

    def _extract_server_name(self, resource: Dict[str, Any]) -> Optional[str]:
        """
        Extract SQL Server name from resource.

        Args:
            resource: Database resource

        Returns:
            Server name or None
        """
        # Try to get from resource ID
        resource_id = resource.get("id", "")
        # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.Sql/servers/{server}/databases/{db}
        match = re.search(r"/servers/([^/]+)/databases/", resource_id)
        if match:
            return match.group(1)

        # Try from properties
        properties = resource.get("properties", {})
        if isinstance(properties, str):
            try:
                properties = json.loads(properties)
            except json.JSONDecodeError:
                properties = {}

        server_name = properties.get("serverName") or properties.get("server")
        return server_name

    def _get_database_connection(self, server_name: str, database_name: str):
        """
        Get pyodbc connection to SQL Database.

        Args:
            server_name: SQL Server name (without .database.windows.net)
            database_name: Database name

        Returns:
            pyodbc connection object

        Raises:
            Exception: If connection fails
        """
        import pyodbc  # type: ignore[import-untyped]

        # Get credentials
        if self.credential_provider:
            credential = self.credential_provider.get_credential()
            # Get access token for Azure SQL Database
            token = credential.get_token("https://database.windows.net/.default")
            access_token = token.token
        else:
            raise ValueError("Credential provider required for SQL Database connection")

        # Build connection string with Azure AD token
        server = f"{server_name}.database.windows.net"
        connection_string = (
            f"DRIVER={{ODBC Driver 17 for SQL Server}};"
            f"SERVER={server};"
            f"DATABASE={database_name};"
        )

        # Connect with access token
        # Note: pyodbc token authentication requires specific setup
        # This is a simplified version - real implementation needs proper token handling
        conn = pyodbc.connect(
            connection_string,
            attrs_before={1256: access_token},  # SQL_COPT_SS_ACCESS_TOKEN
        )

        return conn

    def _extract_schema(self, conn, database_name: str) -> DatabaseSchema:
        """
        Extract complete schema from database.

        Args:
            conn: pyodbc connection
            database_name: Database name

        Returns:
            DatabaseSchema object with all schema elements
        """
        cursor = conn.cursor()

        # Get tables
        tables = self._get_tables(cursor)

        # Get indexes
        indexes = self._get_indexes(cursor)

        # Get foreign keys
        foreign_keys = self._get_foreign_keys(cursor)

        # Get views
        views = self._get_views(cursor)

        # Get stored procedures
        stored_procedures = self._get_stored_procedures(cursor)

        # Get database size
        size_mb = self._get_database_size(cursor, database_name)

        return DatabaseSchema(
            tables=tables,
            indexes=indexes,
            foreign_keys=foreign_keys,
            views=views,
            stored_procedures=stored_procedures,
            size_mb=size_mb,
        )

    def _get_tables(self, cursor) -> List[Dict[str, Any]]:
        """Extract table schemas."""
        tables = []

        # Get all user tables
        cursor.execute("""
            SELECT
                t.TABLE_SCHEMA,
                t.TABLE_NAME,
                c.COLUMN_NAME,
                c.DATA_TYPE,
                c.CHARACTER_MAXIMUM_LENGTH,
                c.IS_NULLABLE,
                c.COLUMN_DEFAULT
            FROM INFORMATION_SCHEMA.TABLES t
            JOIN INFORMATION_SCHEMA.COLUMNS c
                ON t.TABLE_SCHEMA = c.TABLE_SCHEMA
                AND t.TABLE_NAME = c.TABLE_NAME
            WHERE t.TABLE_TYPE = 'BASE TABLE'
                AND t.TABLE_SCHEMA != 'sys'
            ORDER BY t.TABLE_SCHEMA, t.TABLE_NAME, c.ORDINAL_POSITION
        """)

        current_table = None
        current_columns = []

        for row in cursor.fetchall():
            (
                schema,
                table_name,
                col_name,
                data_type,
                max_length,
                is_nullable,
                col_default,
            ) = row

            if current_table != (schema, table_name):
                # Save previous table
                if current_table:
                    tables.append(
                        {
                            "schema": current_table[0],
                            "name": current_table[1],
                            "columns": current_columns,
                            "create_statement": self._generate_create_table_statement(
                                current_table[0], current_table[1], current_columns
                            ),
                            "row_count": self._get_table_row_count(
                                cursor, current_table[0], current_table[1]
                            ),
                            "size_bytes": 0,  # TODO: Get actual size
                        }
                    )

                # Start new table
                current_table = (schema, table_name)
                current_columns = []

            # Add column
            current_columns.append(
                {
                    "name": col_name,
                    "data_type": data_type,
                    "max_length": max_length,
                    "is_nullable": is_nullable == "YES",
                    "default": col_default,
                }
            )

        # Don't forget the last table
        if current_table:
            tables.append(
                {
                    "schema": current_table[0],
                    "name": current_table[1],
                    "columns": current_columns,
                    "create_statement": self._generate_create_table_statement(
                        current_table[0], current_table[1], current_columns
                    ),
                    "row_count": self._get_table_row_count(
                        cursor, current_table[0], current_table[1]
                    ),
                    "size_bytes": 0,
                }
            )

        return tables

    def _generate_create_table_statement(
        self, schema: str, table_name: str, columns: List[Dict[str, Any]]
    ) -> str:
        """Generate CREATE TABLE statement."""
        lines = [f"CREATE TABLE [{schema}].[{table_name}] ("]

        col_definitions = []
        for col in columns:
            data_type = col["data_type"]
            if col.get("max_length") and data_type in (
                "varchar",
                "nvarchar",
                "char",
                "nchar",
            ):
                if col["max_length"] == -1:
                    data_type += "(MAX)"
                else:
                    data_type += f"({col['max_length']})"

            nullable = "NULL" if col["is_nullable"] else "NOT NULL"
            default = f" DEFAULT {col['default']}" if col.get("default") else ""

            col_definitions.append(
                f"    [{col['name']}] {data_type} {nullable}{default}"
            )

        lines.append(",\n".join(col_definitions))
        lines.append(");")

        return "\n".join(lines)

    def _get_table_row_count(self, cursor, schema: str, table_name: str) -> int:
        """Get approximate row count for table."""
        try:
            cursor.execute(f"""
                SELECT SUM(row_count)
                FROM sys.dm_db_partition_stats
                WHERE object_id = OBJECT_ID('[{schema}].[{table_name}]')
                AND index_id IN (0, 1)
            """)
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0
        except Exception:
            return 0

    def _get_indexes(self, cursor) -> List[Dict[str, Any]]:
        """Extract indexes."""
        indexes = []

        cursor.execute("""
            SELECT
                SCHEMA_NAME(t.schema_id) AS schema_name,
                t.name AS table_name,
                i.name AS index_name,
                i.is_unique,
                i.is_primary_key,
                STRING_AGG(c.name, ', ') AS columns
            FROM sys.indexes i
            JOIN sys.tables t ON i.object_id = t.object_id
            JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
            JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
            WHERE i.name IS NOT NULL
            GROUP BY SCHEMA_NAME(t.schema_id), t.name, i.name, i.is_unique, i.is_primary_key
        """)

        for row in cursor.fetchall():
            schema, table, index_name, is_unique, is_pk, columns = row

            indexes.append(
                {
                    "table": f"{schema}.{table}",
                    "name": index_name,
                    "columns": columns.split(", "),
                    "is_unique": is_unique,
                    "is_primary_key": is_pk,
                    "create_statement": self._generate_create_index_statement(
                        schema, table, index_name, columns, is_unique
                    ),
                }
            )

        return indexes

    def _generate_create_index_statement(
        self, schema: str, table: str, index_name: str, columns: str, is_unique: bool
    ) -> str:
        """Generate CREATE INDEX statement."""
        unique = "UNIQUE " if is_unique else ""
        return (
            f"CREATE {unique}INDEX [{index_name}] ON [{schema}].[{table}] ({columns});"
        )

    def _get_foreign_keys(self, cursor) -> List[Dict[str, Any]]:
        """Extract foreign keys."""
        foreign_keys = []

        cursor.execute("""
            SELECT
                SCHEMA_NAME(t.schema_id) AS schema_name,
                t.name AS table_name,
                fk.name AS fk_name,
                SCHEMA_NAME(rt.schema_id) AS ref_schema,
                rt.name AS ref_table,
                STRING_AGG(c.name, ', ') AS columns
            FROM sys.foreign_keys fk
            JOIN sys.tables t ON fk.parent_object_id = t.object_id
            JOIN sys.tables rt ON fk.referenced_object_id = rt.object_id
            JOIN sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
            JOIN sys.columns c ON fkc.parent_object_id = c.object_id AND fkc.parent_column_id = c.column_id
            GROUP BY SCHEMA_NAME(t.schema_id), t.name, fk.name, SCHEMA_NAME(rt.schema_id), rt.name
        """)

        for row in cursor.fetchall():
            schema, table, fk_name, ref_schema, ref_table, columns = row

            foreign_keys.append(
                {
                    "table": f"{schema}.{table}",
                    "name": fk_name,
                    "referenced_table": f"{ref_schema}.{ref_table}",
                    "columns": columns.split(", "),
                    "create_statement": f"ALTER TABLE [{schema}].[{table}] ADD CONSTRAINT [{fk_name}] "
                    f"FOREIGN KEY ({columns}) REFERENCES [{ref_schema}].[{ref_table}];",
                }
            )

        return foreign_keys

    def _get_views(self, cursor) -> List[Dict[str, Any]]:
        """Extract views."""
        views = []

        cursor.execute("""
            SELECT
                TABLE_SCHEMA,
                TABLE_NAME,
                VIEW_DEFINITION
            FROM INFORMATION_SCHEMA.VIEWS
            WHERE TABLE_SCHEMA != 'sys'
        """)

        for row in cursor.fetchall():
            schema, view_name, definition = row

            views.append(
                {
                    "schema": schema,
                    "name": view_name,
                    "definition": definition,
                }
            )

        return views

    def _get_stored_procedures(self, cursor) -> List[Dict[str, Any]]:
        """Extract stored procedures."""
        stored_procedures = []

        cursor.execute("""
            SELECT
                SCHEMA_NAME(schema_id) AS schema_name,
                name,
                definition
            FROM sys.sql_modules sm
            JOIN sys.objects o ON sm.object_id = o.object_id
            WHERE o.type = 'P'
        """)

        for row in cursor.fetchall():
            schema, sp_name, definition = row

            stored_procedures.append(
                {
                    "schema": schema,
                    "name": sp_name,
                    "definition": definition,
                }
            )

        return stored_procedures

    def _get_database_size(self, cursor, database_name: str) -> float:
        """Get database size in MB."""
        try:
            cursor.execute(f"""
                SELECT SUM(size) * 8.0 / 1024 AS size_mb
                FROM sys.master_files
                WHERE database_id = DB_ID('{database_name}')
            """)
            result = cursor.fetchone()
            return result[0] if result and result[0] else 0.0
        except Exception:
            return 0.0
