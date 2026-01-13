"""
Database Translator for Cross-Tenant Translation

Translates Azure Database service cross-tenant references including:
- Resource IDs for SQL, PostgreSQL, MySQL, and Cosmos DB resources
- Server-to-database hierarchical relationships
- Connection strings (conservative approach - logs warnings but preserves)
- Endpoint URIs for database servers

Supported Database Types:
- Azure SQL: azurerm_mssql_server, azurerm_mssql_database
- PostgreSQL: azurerm_postgresql_server, azurerm_postgresql_database
- MySQL: azurerm_mysql_server, azurerm_mysql_database
- Cosmos DB: azurerm_cosmosdb_account

Design Philosophy:
    Conservative with sensitive data: Connection strings contain secrets,
    so we log warnings rather than attempting risky transformations.
    Only translate resource IDs and server names in URIs when safe to do so.

Example Translations:
    Resource ID:
        /subscriptions/SOURCE/resourceGroups/rg/providers/Microsoft.Sql/servers/sqlserver1
        -> /subscriptions/TARGET/resourceGroups/rg/providers/Microsoft.Sql/servers/sqlserver1

    SQL Connection String (conservative):
        Server=tcp:sqlserver1.database.windows.net,1433;Database=db1;User ID=admin;Password=xxx;
        -> (Preserved with warning if server not in IaC)

    Server Endpoint URI:
        sqlserver1.database.windows.net
        -> (Preserved with warning if server not in IaC)

Private Endpoint Connections:
    Private endpoint connections to database servers are handled by
    PrivateEndpointTranslator, not this translator.
"""

import logging
import re
from typing import Any, Dict, List, Tuple

from .base_translator import BaseTranslator
from .registry import register_translator

logger = logging.getLogger(__name__)

# Connection string patterns for different database types
# SQL Server connection string pattern
SQL_CONNECTION_STRING_PATTERN = re.compile(
    r"Server=tcp:([^,;]+)[,;].*?Database=([^;]+)",
    re.IGNORECASE,
)

# PostgreSQL connection string pattern
POSTGRESQL_CONNECTION_STRING_PATTERN = re.compile(
    r"host=([^\s;]+).*?dbname=([^\s;]+)",
    re.IGNORECASE,
)

# MySQL connection string pattern
MYSQL_CONNECTION_STRING_PATTERN = re.compile(
    r"Server=([^;]+);.*?Database=([^;]+)",
    re.IGNORECASE,
)

# Cosmos DB connection string pattern
COSMOSDB_CONNECTION_STRING_PATTERN = re.compile(
    r"AccountEndpoint=https://([^./]+)[^;]*;",
    re.IGNORECASE,
)

# Endpoint URI patterns
SQL_SERVER_ENDPOINT_PATTERN = re.compile(
    r"([a-z0-9\-]+)\.database\.windows\.net",
    re.IGNORECASE,
)

POSTGRESQL_SERVER_ENDPOINT_PATTERN = re.compile(
    r"([a-z0-9\-]+)\.postgres\.database\.azure\.com",
    re.IGNORECASE,
)

MYSQL_SERVER_ENDPOINT_PATTERN = re.compile(
    r"([a-z0-9\-]+)\.mysql\.database\.azure\.com",
    re.IGNORECASE,
)

COSMOSDB_ENDPOINT_PATTERN = re.compile(
    r"https://([a-z0-9\-]+)\.documents\.azure\.com",
    re.IGNORECASE,
)


@register_translator
class DatabaseTranslator(BaseTranslator):
    """
    Translates Azure Database service cross-tenant references.

    Handles translation of:
    - Database resource IDs (SQL, PostgreSQL, MySQL, Cosmos DB)
    - Server-to-database relationships
    - Connection strings (conservative: warns but preserves)
    - Endpoint URIs

    This translator focuses on database servers and databases themselves.
    Private endpoint connections are handled by PrivateEndpointTranslator.

    Design Philosophy:
    - Conservative: Connection strings contain secrets - we warn rather than transform
    - Safe: Only translate resource IDs and check for missing references
    - Informative: Provide detailed warnings for manual review
    - Traceable: Record all checks for reporting
    """

    @property
    def supported_resource_types(self) -> List[str]:
        """
        Get list of resource types this translator handles.

        Supports both Azure and Terraform resource type formats.

        Returns:
            List of database resource types
        """
        return [
            # Azure SQL
            "azurerm_mssql_server",
            "Microsoft.Sql/servers",
            "azurerm_mssql_database",
            "Microsoft.Sql/servers/databases",
            # PostgreSQL
            "azurerm_postgresql_server",
            "Microsoft.DBforPostgreSQL/servers",
            "Microsoft.DBforPostgreSQL/flexibleServers",
            "azurerm_postgresql_database",
            "Microsoft.DBforPostgreSQL/servers/databases",
            # MySQL
            "azurerm_mysql_server",
            "Microsoft.DBforMySQL/servers",
            "Microsoft.DBforMySQL/flexibleServers",
            "azurerm_mysql_database",
            "Microsoft.DBforMySQL/servers/databases",
            # Cosmos DB
            "azurerm_cosmosdb_account",
            "Microsoft.DocumentDB/databaseAccounts",
        ]

    def can_translate(self, resource: Dict[str, Any]) -> bool:
        """
        Determine if this resource needs database translation.

        A resource needs translation if:
        1. It's a supported database resource type
        2. It has properties that might contain cross-subscription references

        Args:
            resource: Resource dictionary from Neo4j graph

        Returns:
            True if translation is needed
        """
        resource_type = resource.get("type", "")

        # Check if this is a supported database type
        if resource_type not in self.supported_resource_types:
            return False

        # Check if there are properties that might need translation
        translatable_properties = [
            "id",
            "server_id",  # For databases that reference servers
            "connection_string",
            "primary_connection_string",
            "secondary_connection_string",
            "connection_strings",  # Cosmos DB
            "fqdn",  # Fully qualified domain name
            "fully_qualified_domain_name",
            "endpoint",
            "primary_key_connection_string",  # Cosmos DB
            "secondary_key_connection_string",  # Cosmos DB
            "primary_readonly_key_connection_string",  # Cosmos DB
            "secondary_readonly_key_connection_string",  # Cosmos DB
        ]

        # Check if any translatable property exists
        for prop in translatable_properties:
            if prop in resource:
                logger.debug(
                    f"Database resource {resource.get('name', 'unknown')} has "
                    f"translatable property: {prop}"
                )
                return True

        return False

    def translate(self, resource: Dict[str, Any]) -> Dict[str, Any]:
        """
        Translate database cross-tenant references.

        Args:
            resource: Database resource to translate

        Returns:
            Translated resource dictionary

        Note:
            This method creates a copy to avoid modifying the original resource.
        """
        # Create a copy to avoid modifying original
        translated = resource.copy()
        resource_name = resource.get("name", "unknown")
        resource_type = resource.get("type", "unknown")

        logger.info(
            str(f"Translating database resource: {resource_name} ({resource_type})")
        )

        # Translate resource ID
        if "id" in translated:
            original_id = translated["id"]
            translated_id, warnings = self._translate_resource_id(original_id, "id")
            translated["id"] = translated_id
            self._add_result(
                "id",
                original_id,
                translated_id,
                warnings,
                resource_type=self._get_azure_resource_type(resource_type),
                resource_name=resource_name,
            )

        # Translate server_id (for databases that reference servers)
        if "server_id" in translated:
            original_server_id = translated["server_id"]
            translated_server_id, warnings = self._translate_resource_id(
                original_server_id, "server_id"
            )
            translated["server_id"] = translated_server_id
            self._add_result(
                "server_id",
                original_server_id,
                translated_server_id,
                warnings,
                resource_type=self._get_azure_resource_type(resource_type),
                resource_name=resource_name,
            )

        # Translate connection strings (conservative approach)
        self._translate_connection_strings(translated, resource_name, resource_type)

        # Translate endpoint URIs
        self._translate_endpoints(translated, resource_name, resource_type)

        logger.info(
            str(f"Completed translation for database resource: {resource_name}")
        )
        return translated

    def _translate_connection_strings(
        self, translated: Dict[str, Any], resource_name: str, resource_type: str
    ) -> None:
        """
        Translate connection strings in database resource.

        Conservative approach: We check connection strings for server references
        and warn if servers are missing, but we preserve the original strings
        since they contain sensitive information.

        Args:
            translated: Resource dictionary to update
            resource_name: Name of the database resource
            resource_type: Type of the database resource
        """
        # Single connection string
        if "connection_string" in translated:
            original_str = translated["connection_string"]
            translated_str, warnings = self._check_connection_string(
                original_str, resource_name, resource_type
            )
            # Keep original (conservative approach)
            translated["connection_string"] = translated_str
            self._add_result(
                "connection_string",
                original_str,
                translated_str,
                warnings,
                resource_type=self._get_azure_resource_type(resource_type),
                resource_name=resource_name,
            )

        # Primary/secondary connection strings
        for conn_str_field in [
            "primary_connection_string",
            "secondary_connection_string",
        ]:
            if conn_str_field in translated:
                original_str = translated[conn_str_field]
                translated_str, warnings = self._check_connection_string(
                    original_str, resource_name, resource_type
                )
                translated[conn_str_field] = translated_str
                self._add_result(
                    conn_str_field,
                    original_str,
                    translated_str,
                    warnings,
                    resource_type=self._get_azure_resource_type(resource_type),
                    resource_name=resource_name,
                )

        # Cosmos DB specific connection strings
        cosmos_conn_fields = [
            "primary_key_connection_string",
            "secondary_key_connection_string",
            "primary_readonly_key_connection_string",
            "secondary_readonly_key_connection_string",
        ]

        for conn_str_field in cosmos_conn_fields:
            if conn_str_field in translated:
                original_str = translated[conn_str_field]
                translated_str, warnings = self._check_cosmosdb_connection_string(
                    original_str, resource_name
                )
                translated[conn_str_field] = translated_str
                self._add_result(
                    conn_str_field,
                    original_str,
                    translated_str,
                    warnings,
                    resource_type="Microsoft.DocumentDB/databaseAccounts",
                    resource_name=resource_name,
                )

    def _translate_endpoints(
        self, translated: Dict[str, Any], resource_name: str, resource_type: str
    ) -> None:
        """
        Translate endpoint URIs in database resource.

        Args:
            translated: Resource dictionary to update
            resource_name: Name of the database resource
            resource_type: Type of the database resource
        """
        endpoint_fields = [
            "fqdn",
            "fully_qualified_domain_name",
            "endpoint",
        ]

        for endpoint_field in endpoint_fields:
            if endpoint_field in translated:
                original_endpoint = translated[endpoint_field]
                translated_endpoint, warnings = self._check_endpoint_uri(
                    original_endpoint, resource_name, resource_type
                )
                translated[endpoint_field] = translated_endpoint
                self._add_result(
                    endpoint_field,
                    original_endpoint,
                    translated_endpoint,
                    warnings,
                    resource_type=self._get_azure_resource_type(resource_type),
                    resource_name=resource_name,
                )

    def _check_connection_string(
        self, conn_str: str, resource_name: str, resource_type: str
    ) -> Tuple[str, List[str]]:
        """
        Check connection string for cross-subscription references.

        Conservative approach: We validate that referenced servers exist
        but preserve the original connection string.

        Args:
            conn_str: Connection string to check
            resource_name: Name of the database resource
            resource_type: Type of the database resource

        Returns:
            Tuple of (connection_string, warnings)
        """
        warnings: List[str] = []

        if not conn_str or not isinstance(conn_str, str):
            warnings.append("Connection string is empty or invalid")
            return conn_str, warnings

        # Skip Terraform variables
        if "${" in conn_str or "var." in conn_str:
            return conn_str, warnings

        # Determine database type and check accordingly
        if "azurerm_mssql" in resource_type:
            return self._check_sql_connection_string(conn_str, resource_name)
        elif "azurerm_postgresql" in resource_type:
            return self._check_postgresql_connection_string(conn_str, resource_name)
        elif "azurerm_mysql" in resource_type:
            return self._check_mysql_connection_string(conn_str, resource_name)
        else:
            # Generic check
            warnings.append(
                "Connection string detected but database type not recognized. "
                "Manual review recommended."
            )
            return conn_str, warnings

    def _check_sql_connection_string(
        self, conn_str: str, resource_name: str
    ) -> Tuple[str, List[str]]:
        """
        Check SQL Server connection string.

        Args:
            conn_str: SQL connection string
            resource_name: Name of the database resource

        Returns:
            Tuple of (connection_string, warnings)
        """
        warnings: List[str] = []

        try:
            match = SQL_CONNECTION_STRING_PATTERN.search(conn_str)
            if match:
                server_fqdn = match.group(1)
                database_name = match.group(2)

                # Extract server name from FQDN
                server_name = server_fqdn.split(".")[0]

                logger.debug(
                    f"SQL connection string: server={server_name}, database={database_name}"
                )

                # Check if server exists in target
                target_exists = self._check_target_exists(
                    "Microsoft.Sql/servers", server_name
                )

                if not target_exists:
                    warnings.append(
                        f"SQL Server '{server_name}' referenced in connection string "
                        f"not found in generated IaC. Manual review required."
                    )
            else:
                warnings.append(
                    "Could not parse SQL connection string. Manual review recommended."
                )

        except Exception as e:
            warnings.append(f"Error checking SQL connection string: {e!s}")
            logger.error(
                f"Error parsing SQL connection string for {resource_name}: {e}"
            )

        return conn_str, warnings

    def _check_postgresql_connection_string(
        self, conn_str: str, resource_name: str
    ) -> Tuple[str, List[str]]:
        """
        Check PostgreSQL connection string.

        Args:
            conn_str: PostgreSQL connection string
            resource_name: Name of the database resource

        Returns:
            Tuple of (connection_string, warnings)
        """
        warnings: List[str] = []

        try:
            match = POSTGRESQL_CONNECTION_STRING_PATTERN.search(conn_str)
            if match:
                server_fqdn = match.group(1)
                database_name = match.group(2)

                # Extract server name from FQDN
                server_name = server_fqdn.split(".")[0]

                logger.debug(
                    f"PostgreSQL connection string: server={server_name}, database={database_name}"
                )

                # Check if server exists in target
                target_exists = self._check_target_exists(
                    "Microsoft.DBforPostgreSQL/servers", server_name
                )

                if not target_exists:
                    warnings.append(
                        f"PostgreSQL Server '{server_name}' referenced in connection string "
                        f"not found in generated IaC. Manual review required."
                    )
            else:
                warnings.append(
                    "Could not parse PostgreSQL connection string. Manual review recommended."
                )

        except Exception as e:
            warnings.append(f"Error checking PostgreSQL connection string: {e!s}")
            logger.error(
                f"Error parsing PostgreSQL connection string for {resource_name}: {e}"
            )

        return conn_str, warnings

    def _check_mysql_connection_string(
        self, conn_str: str, resource_name: str
    ) -> Tuple[str, List[str]]:
        """
        Check MySQL connection string.

        Args:
            conn_str: MySQL connection string
            resource_name: Name of the database resource

        Returns:
            Tuple of (connection_string, warnings)
        """
        warnings: List[str] = []

        try:
            match = MYSQL_CONNECTION_STRING_PATTERN.search(conn_str)
            if match:
                server_fqdn = match.group(1)
                database_name = match.group(2)

                # Extract server name from FQDN
                server_name = server_fqdn.split(".")[0]

                logger.debug(
                    f"MySQL connection string: server={server_name}, database={database_name}"
                )

                # Check if server exists in target
                target_exists = self._check_target_exists(
                    "Microsoft.DBforMySQL/servers", server_name
                )

                if not target_exists:
                    warnings.append(
                        f"MySQL Server '{server_name}' referenced in connection string "
                        f"not found in generated IaC. Manual review required."
                    )
            else:
                warnings.append(
                    "Could not parse MySQL connection string. Manual review recommended."
                )

        except Exception as e:
            warnings.append(f"Error checking MySQL connection string: {e!s}")
            logger.error(
                f"Error parsing MySQL connection string for {resource_name}: {e}"
            )

        return conn_str, warnings

    def _check_cosmosdb_connection_string(
        self, conn_str: str, resource_name: str
    ) -> Tuple[str, List[str]]:
        """
        Check Cosmos DB connection string.

        Args:
            conn_str: Cosmos DB connection string
            resource_name: Name of the Cosmos DB account

        Returns:
            Tuple of (connection_string, warnings)
        """
        warnings: List[str] = []

        if not conn_str or not isinstance(conn_str, str):
            warnings.append("Cosmos DB connection string is empty or invalid")
            return conn_str, warnings

        # Skip Terraform variables
        if "${" in conn_str or "var." in conn_str:
            return conn_str, warnings

        try:
            match = COSMOSDB_CONNECTION_STRING_PATTERN.search(conn_str)
            if match:
                account_name = match.group(1)

                logger.debug(
                    str(f"Cosmos DB connection string: account={account_name}")
                )

                # Check if account exists in target
                target_exists = self._check_target_exists(
                    "Microsoft.DocumentDB/databaseAccounts", account_name
                )

                if not target_exists:
                    warnings.append(
                        f"Cosmos DB account '{account_name}' referenced in connection string "
                        f"not found in generated IaC. Manual review required."
                    )
            else:
                warnings.append(
                    "Could not parse Cosmos DB connection string. Manual review recommended."
                )

        except Exception as e:
            warnings.append(f"Error checking Cosmos DB connection string: {e!s}")
            logger.error(
                f"Error parsing Cosmos DB connection string for {resource_name}: {e}"
            )

        return conn_str, warnings

    def _check_endpoint_uri(
        self, uri: str, resource_name: str, resource_type: str
    ) -> Tuple[str, List[str]]:
        """
        Check endpoint URI for cross-subscription references.

        Args:
            uri: Endpoint URI to check
            resource_name: Name of the database resource
            resource_type: Type of the database resource

        Returns:
            Tuple of (uri, warnings)
        """
        warnings: List[str] = []

        if not uri or not isinstance(uri, str):
            warnings.append("Endpoint URI is empty or invalid")
            return uri, warnings

        # Skip Terraform variables
        if "${" in uri or "var." in uri:
            return uri, warnings

        # Try to match against known endpoint patterns
        patterns = [
            ("SQL Server", SQL_SERVER_ENDPOINT_PATTERN, "Microsoft.Sql/servers"),
            (
                "PostgreSQL",
                POSTGRESQL_SERVER_ENDPOINT_PATTERN,
                "Microsoft.DBforPostgreSQL/servers",
            ),
            ("MySQL", MYSQL_SERVER_ENDPOINT_PATTERN, "Microsoft.DBforMySQL/servers"),
            (
                "Cosmos DB",
                COSMOSDB_ENDPOINT_PATTERN,
                "Microsoft.DocumentDB/databaseAccounts",
            ),
        ]

        for service_name, pattern, azure_type in patterns:
            match = pattern.search(uri)
            if match:
                server_name = match.group(1)

                logger.debug(
                    f"Found {service_name} endpoint: server={server_name}, "
                    f"resource_name={resource_name}"
                )

                # Check if target exists
                target_exists = self._check_target_exists(azure_type, server_name)

                if not target_exists:
                    warnings.append(
                        f"{service_name} '{server_name}' referenced in endpoint URI "
                        f"not found in generated IaC. Manual review may be required."
                    )

                return uri, warnings

        # If no pattern matched, it might be a custom format
        warnings.append(
            f"Endpoint URI has unrecognized format: {uri}. Manual review may be required."
        )

        return uri, warnings

    def _get_azure_resource_type(self, terraform_type: str) -> str:
        """
        Convert Terraform resource type to Azure resource type.

        Args:
            terraform_type: Terraform resource type

        Returns:
            Azure resource type string
        """
        type_map = {
            "azurerm_mssql_server": "Microsoft.Sql/servers",
            "azurerm_mssql_database": "Microsoft.Sql/servers/databases",
            "azurerm_postgresql_server": "Microsoft.DBforPostgreSQL/servers",
            "azurerm_postgresql_database": "Microsoft.DBforPostgreSQL/servers/databases",
            "azurerm_mysql_server": "Microsoft.DBforMySQL/servers",
            "azurerm_mysql_database": "Microsoft.DBforMySQL/servers/databases",
            "azurerm_cosmosdb_account": "Microsoft.DocumentDB/databaseAccounts",
        }

        return type_map.get(terraform_type, terraform_type)
