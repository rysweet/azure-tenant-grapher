"""
CosmosDB data plane replication plugin.

This plugin handles discovery and replication of Azure Cosmos DB data plane
items including:
- Databases (SQL API)
- Containers with partition keys and throughput settings
- Documents (in replication mode only)
- Stored procedures, triggers, and UDFs

The plugin supports two modes:
- Template: Replicate database and container structure without documents
- Replication: Full data copy including all documents with RU throttling
"""

import json
import logging
import time
from typing import Any, Dict, List

from ..plugins.base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)

logger = logging.getLogger(__name__)


class CosmosDBPlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure Cosmos DB (SQL API).

    Discovers and replicates Cosmos DB databases, containers, and documents
    using Azure SDK.

    Example:
        plugin = CosmosDBPlugin()
        items = plugin.discover(cosmosdb_resource)
        result = plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)
    """

    # RU throttling configuration
    DEFAULT_RU_LIMIT = 1000  # Maximum RUs to consume per second
    THROTTLE_RETRY_SECONDS = 5  # Retry delay when rate limited

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for Cosmos DB accounts."""
        # Support both variations found in Azure
        return "Microsoft.DocumentDB/databaseAccounts"

    def can_handle(self, resource: Dict[str, Any]) -> bool:
        """
        Check if this plugin can handle the given resource.

        Supports both:
        - Microsoft.DocumentDB/databaseAccounts
        - Microsoft.DocumentDb/databaseAccounts (case variation)

        Args:
            resource: Resource dictionary to check

        Returns:
            True if this plugin can handle the resource type
        """
        if not resource:
            return False

        resource_type = resource.get("type", "")
        return resource_type.lower() in [
            "microsoft.documentdb/databaseaccounts",
            "microsoft.documentdb/databaseaccounts",
        ]

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover Cosmos DB databases and containers.

        Uses Azure SDK to:
        1. Authenticate to Cosmos DB
        2. List all databases
        3. List all containers in each database
        4. Extract partition keys and throughput settings

        Args:
            resource: Cosmos DB account resource dictionary containing:
                - id: Cosmos DB account resource ID
                - name: Account name
                - properties: Account properties including documentEndpoint

        Returns:
            List of DataPlaneItem representing databases and containers

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../databaseAccounts/my-cosmos",
            ...     "type": "Microsoft.DocumentDB/databaseAccounts",
            ...     "name": "my-cosmos",
            ...     "properties": {"documentEndpoint": "https://my-cosmos.documents.azure.com:443/"}
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of databases + containers
        """
        if not self.can_handle(resource):
            raise ValueError(f"Invalid resource for CosmosDBPlugin: {resource}")

        account_name = resource.get("name", "unknown")
        self.logger.info(f"Discovering data plane items for Cosmos DB: {account_name}")

        items: List[DataPlaneItem] = []

        try:
            # Import Azure Cosmos SDK
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential

            # Get endpoint from resource properties
            properties = resource.get("properties", {})
            endpoint = properties.get("documentEndpoint")

            if not endpoint:
                self.logger.error(
                    f"No documentEndpoint found in resource properties: {properties}"
                )
                return items

            # Get credential from provider or use default
            if self.credential_provider:
                credential = self.credential_provider.get_credential()
            else:
                credential = DefaultAzureCredential()

            # Create Cosmos client
            # Note: Cosmos SDK expects a dict credential for certain operations
            # We'll use the resource key if available, otherwise use managed identity
            client = self._create_cosmos_client(endpoint, credential, resource)

            # Discover databases
            try:
                databases = list(client.list_databases())

                for db in databases:
                    db_id = db.get("id", "unknown")
                    self.logger.debug(f"Discovered database: {db_id}")

                    # Add database item
                    items.append(
                        DataPlaneItem(
                            name=db_id,
                            item_type="database",
                            properties={
                                "id": db_id,
                                "_rid": db.get("_rid"),
                                "_ts": db.get("_ts"),
                            },
                            source_resource_id=resource["id"],
                            metadata={"endpoint": endpoint},
                        )
                    )

                    # Discover containers in this database
                    try:
                        database = client.get_database_client(db_id)
                        containers = list(database.list_containers())

                        for container in containers:
                            container_id = container.get("id", "unknown")
                            partition_key_path = container.get("partitionKey", {}).get(
                                "paths", [""]
                            )[0]

                            self.logger.debug(
                                f"Discovered container: {db_id}/{container_id}"
                            )

                            # Get throughput if available
                            throughput = None
                            try:
                                container_client = database.get_container_client(
                                    container_id
                                )
                                offer = container_client.read_offer()
                                throughput = offer.get("content", {}).get(
                                    "offerThroughput"
                                )
                            except Exception as e:
                                self.logger.debug(
                                    f"Could not read throughput for {container_id}: {e}"
                                )

                            # Estimate document count (sampling)
                            doc_count = 0
                            try:
                                # Query for count (expensive on large containers)
                                query = "SELECT VALUE COUNT(1) FROM c"
                                result = list(
                                    container_client.query_items(
                                        query=query,
                                        enable_cross_partition_query=True,
                                        max_item_count=1,
                                    )
                                )
                                if result:
                                    doc_count = result[0]
                            except Exception as e:
                                self.logger.debug(
                                    f"Could not count documents in {container_id}: {e}"
                                )

                            items.append(
                                DataPlaneItem(
                                    name=container_id,
                                    item_type="container",
                                    properties={
                                        "id": container_id,
                                        "database_id": db_id,
                                        "partitionKey": partition_key_path,
                                        "throughput": throughput,
                                        "document_count": doc_count,
                                        "_rid": container.get("_rid"),
                                    },
                                    source_resource_id=resource["id"],
                                    metadata={
                                        "endpoint": endpoint,
                                        "indexingPolicy": container.get(
                                            "indexingPolicy"
                                        ),
                                        "conflictResolutionPolicy": container.get(
                                            "conflictResolutionPolicy"
                                        ),
                                    },
                                )
                            )

                    except (AzureError, HttpResponseError) as e:
                        self.logger.warning(
                            f"Failed to discover containers in database {db_id}: {e}"
                        )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover databases for {account_name}: {e}"
                )

            # Report discovery progress
            if self.progress_reporter:
                self.progress_reporter.report_discovery(resource["id"], len(items))

        except ImportError as e:
            self.logger.error(
                f"Azure Cosmos SDK not installed. Install with: "
                f"pip install azure-cosmos. Error: {e}"
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error discovering Cosmos DB items: {e}", exc_info=True
            )

        self.logger.info(
            f"Discovered {len(items)} data plane items for Cosmos DB '{account_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate Cosmos DB structure.

        For Cosmos DB, this generates:
        - azurerm_cosmosdb_sql_database resources
        - azurerm_cosmosdb_sql_container resources with partition keys
        - Comments about throughput and indexing policies

        Args:
            items: List of Cosmos DB data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code for Cosmos DB structure

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="mydb", item_type="database", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "azurerm_cosmosdb_sql_database" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by CosmosDBPlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} Cosmos DB items"
        )

        if not items:
            return "# No Cosmos DB data plane items to replicate\n"

        code_lines = [
            "# Cosmos DB Data Plane Items",
            "# Generated by Azure Tenant Grapher - CosmosDBPlugin",
            "#",
            "# NOTE: This creates database and container structure only.",
            "# Document data is not included in template mode.",
            "# Use replication mode to copy documents.",
            "",
        ]

        # Group items by type
        databases = [item for item in items if item.item_type == "database"]
        containers = [item for item in items if item.item_type == "container"]

        # Generate code for databases
        if databases:
            code_lines.append("# Cosmos DB Databases")
            for item in databases:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_cosmosdb_sql_database" "{resource_name}" {{',
                        f'  name                = "{item.name}"',
                        "  # TODO: Reference your Cosmos DB account here",
                        "  account_name        = azurerm_cosmosdb_account.REPLACE_ME.name",
                        "  resource_group_name = azurerm_resource_group.REPLACE_ME.name",
                        "",
                        "  # Throughput configuration",
                        "  # Set to null for serverless, or specify RU/s",
                        "  # throughput = 400",
                        "",
                        "}",
                        "",
                    ]
                )

        # Generate code for containers
        if containers:
            code_lines.append("# Cosmos DB Containers")
            for item in containers:
                resource_name = self._sanitize_name(
                    f"{item.properties['database_id']}_{item.name}"
                )
                db_resource_name = self._sanitize_name(item.properties["database_id"])

                partition_key = item.properties.get("partitionKey", "/id")
                throughput = item.properties.get("throughput")

                code_lines.extend(
                    [
                        f'resource "azurerm_cosmosdb_sql_container" "{resource_name}" {{',
                        f'  name                = "{item.name}"',
                        "  resource_group_name = azurerm_resource_group.REPLACE_ME.name",
                        "  account_name        = azurerm_cosmosdb_account.REPLACE_ME.name",
                        f"  database_name       = azurerm_cosmosdb_sql_database.{db_resource_name}.name",
                        "",
                        f'  partition_key_path  = "{partition_key}"',
                        "",
                    ]
                )

                # Add throughput if specified
                if throughput:
                    code_lines.append(f"  throughput          = {throughput}")
                    code_lines.append("")

                # Add indexing policy comment
                indexing_policy = item.metadata.get("indexingPolicy")
                if indexing_policy:
                    code_lines.extend(
                        [
                            "  # Indexing policy",
                            "  # TODO: Configure indexing based on your requirements",
                            "  # Original policy (commented):",
                            f"  # {json.dumps(indexing_policy, indent=2).replace(chr(10), chr(10) + '  # ')}",
                            "",
                        ]
                    )

                # Document count info
                doc_count = item.properties.get("document_count", 0)
                if doc_count > 0:
                    code_lines.extend(
                        [
                            f"  # Original container had {doc_count} documents",
                            "  # Use replication mode to copy document data",
                            "",
                        ]
                    )

                code_lines.append("}")
                code_lines.append("")

        # Add helpful comments
        code_lines.extend(
            [
                "# IMPORTANT NOTES:",
                "# 1. Replace REPLACE_ME with actual resource references",
                "# 2. Adjust throughput settings based on your needs",
                "# 3. Configure indexing policies for optimal performance",
                "# 4. Document data requires replication mode",
                "# 5. Test with sample data before full migration",
                "",
            ]
        )

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate Cosmos DB structure from source to target (legacy method).

        This delegates to replicate_with_mode() using TEMPLATE mode by default.

        Args:
            source_resource: Source Cosmos DB account resource
            target_resource: Target Cosmos DB account resource

        Returns:
            ReplicationResult with operation statistics
        """
        return self.replicate_with_mode(
            source_resource, target_resource, ReplicationMode.TEMPLATE
        )

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """
        Replicate Cosmos DB data plane with mode awareness.

        Template mode: Create databases and containers without documents
        Replication mode: Full data copy including all documents with RU throttling

        Args:
            source_resource: Source Cosmos DB account resource
            target_resource: Target Cosmos DB account resource
            mode: Replication mode

        Returns:
            ReplicationResult with operation statistics

        Example:
            >>> source = {"id": "...", "type": "Microsoft.DocumentDB/databaseAccounts", ...}
            >>> target = {"id": "...", "type": "Microsoft.DocumentDB/databaseAccounts", ...}
            >>> result = plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)
            >>> result.success
            True
        """
        if not self.can_handle(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.can_handle(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating Cosmos DB from {source_name} to {target_name} "
            f"(mode={mode.value})"
        )

        errors = []
        warnings = []
        items_replicated = 0
        start_time = time.time()
        source_items = []  # Initialize here to avoid UnboundLocalError

        try:
            # Import Azure Cosmos SDK
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.cosmos import PartitionKey
            from azure.identity import DefaultAzureCredential

            # Get endpoints
            source_endpoint = source_resource.get("properties", {}).get(
                "documentEndpoint"
            )
            target_endpoint = target_resource.get("properties", {}).get(
                "documentEndpoint"
            )

            if not source_endpoint or not target_endpoint:
                errors.append("Missing documentEndpoint in resource properties")
                return ReplicationResult(
                    success=False,
                    items_discovered=0,
                    items_replicated=0,
                    errors=errors,
                    warnings=warnings,
                    duration_seconds=time.time() - start_time,
                )

            # Get credential
            if self.credential_provider:
                credential = self.credential_provider.get_credential()
            else:
                credential = DefaultAzureCredential()

            # Create clients
            source_client = self._create_cosmos_client(
                source_endpoint, credential, source_resource
            )
            target_client = self._create_cosmos_client(
                target_endpoint, credential, target_resource
            )

            # Discover items from source
            source_items = self.discover(source_resource)

            if not source_items:
                warnings.append("No data plane items found in source Cosmos DB")
                return ReplicationResult(
                    success=True,
                    items_discovered=0,
                    items_replicated=0,
                    errors=errors,
                    warnings=warnings,
                    duration_seconds=time.time() - start_time,
                )

            # Group items by type
            databases = [item for item in source_items if item.item_type == "database"]
            containers = [
                item for item in source_items if item.item_type == "container"
            ]

            # Replicate databases
            for db_item in databases:
                try:
                    db_id = db_item.name

                    if mode == ReplicationMode.TEMPLATE:
                        # Template mode: Just log
                        self.logger.info(f"[TEMPLATE] Would create database: {db_id}")
                        items_replicated += 1
                    else:
                        # Replication mode: Create database
                        self.logger.info(f"Creating database: {db_id}")
                        target_client.create_database_if_not_exists(id=db_id)
                        items_replicated += 1

                except (AzureError, HttpResponseError) as e:
                    error_msg = f"Failed to replicate database {db_item.name}: {e}"
                    self.logger.error(error_msg)
                    errors.append(error_msg)

            # Replicate containers
            for container_item in containers:
                try:
                    db_id = container_item.properties["database_id"]
                    container_id = container_item.name
                    partition_key_path = container_item.properties.get(
                        "partitionKey", "/id"
                    )

                    if mode == ReplicationMode.TEMPLATE:
                        # Template mode: Just log
                        self.logger.info(
                            f"[TEMPLATE] Would create container: {db_id}/{container_id}"
                        )
                        items_replicated += 1
                    else:
                        # Replication mode: Create container
                        self.logger.info(f"Creating container: {db_id}/{container_id}")

                        target_database = target_client.get_database_client(db_id)

                        # Create container with partition key
                        target_database.create_container_if_not_exists(
                            id=container_id,
                            partition_key=PartitionKey(path=partition_key_path),
                        )
                        items_replicated += 1

                        # Replicate documents if in replication mode
                        doc_count = container_item.properties.get("document_count", 0)
                        if doc_count > 0:
                            self.logger.info(
                                f"Replicating {doc_count} documents in {container_id}..."
                            )

                            replicated_docs = self._replicate_documents(
                                source_client.get_database_client(db_id),
                                target_database,
                                container_id,
                            )

                            items_replicated += replicated_docs
                            self.logger.info(f"Replicated {replicated_docs} documents")

                except (AzureError, HttpResponseError) as e:
                    error_msg = (
                        f"Failed to replicate container {container_item.name}: {e}"
                    )
                    self.logger.error(error_msg)
                    errors.append(error_msg)

                # Report progress
                if self.progress_reporter:
                    progress = (
                        (len(databases) + containers.index(container_item) + 1)
                        / len(source_items)
                        * 100
                    )
                    self.progress_reporter.report_replication_progress(
                        container_item.name, progress
                    )

        except ImportError as e:
            errors.append(f"Azure Cosmos SDK not available: {e}")
        except Exception as e:
            self.logger.error(
                f"Unexpected error during replication: {e}", exc_info=True
            )
            errors.append(f"Unexpected error: {e!s}")

        # Build result
        success = len(errors) == 0
        duration = time.time() - start_time

        result = ReplicationResult(
            success=success,
            items_discovered=len(source_items),
            items_replicated=items_replicated,
            items_skipped=len(source_items) - items_replicated,
            errors=errors,
            warnings=warnings,
            duration_seconds=duration,
        )

        # Report completion
        if self.progress_reporter:
            self.progress_reporter.report_completion(result)

        return result

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return Azure RBAC permissions required for Cosmos DB plugin.

        Args:
            mode: The replication mode (affects required permissions)

        Returns:
            List of Permission objects describing needed RBAC roles

        Example:
            >>> plugin = CosmosDBPlugin()
            >>> perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
            >>> len(perms) > 0
            True
        """
        if mode == ReplicationMode.TEMPLATE:
            return [
                Permission(
                    scope="resource",
                    actions=["Microsoft.DocumentDB/databaseAccounts/read"],
                    data_actions=[
                        "Microsoft.DocumentDB/databaseAccounts/readMetadata",
                    ],
                    description="Read Cosmos DB account metadata (template mode)",
                )
            ]
        else:
            # Replication mode
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.DocumentDB/databaseAccounts/read",
                        "Microsoft.DocumentDB/databaseAccounts/readwrite",
                    ],
                    data_actions=[
                        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read",
                        "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/create",
                    ],
                    description="Read and write Cosmos DB data (replication mode)",
                )
            ]

    def estimate_operation_time(
        self, items: List[DataPlaneItem], mode: ReplicationMode
    ) -> float:
        """
        Estimate time required for Cosmos DB replication operation.

        Args:
            items: Items to replicate
            mode: Replication mode

        Returns:
            Estimated seconds

        Example:
            >>> items = [DataPlaneItem(...) for _ in range(3)]
            >>> time_est = plugin.estimate_operation_time(items, ReplicationMode.TEMPLATE)
            >>> time_est >= 0
            True
        """
        if mode == ReplicationMode.TEMPLATE:
            # Template mode is fast (just create structure)
            databases = [item for item in items if item.item_type == "database"]
            containers = [item for item in items if item.item_type == "container"]
            return len(databases) * 2.0 + len(containers) * 5.0

        # Replication mode: depends on document count
        total_docs = 0
        for item in items:
            if item.item_type == "container":
                doc_count = item.properties.get("document_count", 0)
                total_docs += doc_count

        # Estimate: ~1000 documents per second (with RU throttling)
        # Plus overhead for structure creation
        databases = [item for item in items if item.item_type == "database"]
        containers = [item for item in items if item.item_type == "container"]
        structure_time = len(databases) * 2.0 + len(containers) * 5.0
        document_time = total_docs / 1000.0

        return structure_time + document_time

    def _create_cosmos_client(
        self, endpoint: str, credential: Any, resource: Dict[str, Any]
    ) -> Any:
        """
        Create Cosmos DB client with appropriate authentication.

        Args:
            endpoint: Cosmos DB endpoint URL
            credential: Azure credential object
            resource: Resource dictionary (may contain keys)

        Returns:
            CosmosClient instance
        """
        from azure.cosmos import CosmosClient

        # Try to use credential provider for connection string
        if self.credential_provider:
            connection_string = self.credential_provider.get_connection_string(
                resource.get("id", "")
            )
            if connection_string:
                self.logger.debug("Using connection string for Cosmos DB")
                return CosmosClient.from_connection_string(connection_string)

        # Otherwise use managed identity / credential
        self.logger.debug("Using credential-based auth for Cosmos DB")
        return CosmosClient(endpoint, credential=credential)

    def _replicate_documents(
        self, source_database: Any, target_database: Any, container_id: str
    ) -> int:
        """
        Replicate documents from source to target container with RU throttling.

        Args:
            source_database: Source database client
            target_database: Target database client
            container_id: Container ID to replicate

        Returns:
            Number of documents replicated
        """
        replicated_count = 0

        try:
            source_container = source_database.get_container_client(container_id)
            target_container = target_database.get_container_client(container_id)

            # Query all documents
            query = "SELECT * FROM c"
            items = source_container.query_items(
                query=query, enable_cross_partition_query=True
            )

            # Track RU consumption for throttling
            ru_consumed = 0
            last_throttle_check = time.time()

            for item in items:
                try:
                    # Create document in target
                    target_container.create_item(body=item)
                    replicated_count += 1

                    # Estimate RU consumption (rough estimate: 5 RU per document)
                    ru_consumed += 5

                    # Check if we need to throttle
                    elapsed = time.time() - last_throttle_check
                    if elapsed >= 1.0:
                        # Reset RU counter every second
                        if ru_consumed > self.DEFAULT_RU_LIMIT:
                            sleep_time = 1.0 - elapsed + self.THROTTLE_RETRY_SECONDS
                            if sleep_time > 0:
                                self.logger.debug(
                                    f"RU throttling: sleeping {sleep_time:.2f}s"
                                )
                                time.sleep(sleep_time)

                        ru_consumed = 0
                        last_throttle_check = time.time()

                except Exception as e:
                    self.logger.warning(f"Failed to replicate document (skipping): {e}")

        except Exception as e:
            self.logger.error(f"Error replicating documents: {e}", exc_info=True)

        return replicated_count

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names.

        Args:
            name: Original name (may contain hyphens, special chars)

        Returns:
            Sanitized name safe for Terraform identifiers

        Example:
            >>> plugin._sanitize_name("my-database-v1.0")
            'my_database_v1_0'
        """
        # Replace hyphens and special chars with underscores
        sanitized = name.replace("-", "_").replace(".", "_").replace(" ", "_")
        sanitized = sanitized.replace("/", "_")

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "cosmos_" + sanitized

        return sanitized.lower()
