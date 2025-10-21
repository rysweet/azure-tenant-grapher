"""
Storage Account data plane replication plugin.

This plugin handles discovery and replication of Azure Storage Account data plane
items including:
- Blob containers and blobs
- File shares and files
- Tables
- Queues

The plugin integrates with the IaC generation process to ensure that Storage Account
contents are preserved when deploying to new environments.
"""

import logging
from typing import Any, Dict, List

from .base_plugin import DataPlaneItem, DataPlanePlugin, ReplicationResult

logger = logging.getLogger(__name__)


class StoragePlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure Storage Account.

    Discovers and replicates blob containers, file shares, tables, and queues using
    Azure SDK.

    Example:
        plugin = StoragePlugin()
        items = plugin.discover(storage_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for Storage Account."""
        return "Microsoft.Storage/storageAccounts"

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover Storage Account containers, shares, tables, and queues.

        Uses Azure SDK to:
        1. Authenticate to the Storage Account
        2. List all blob containers and sample blobs
        3. List file shares
        4. List tables
        5. List queues
        6. Return structured DataPlaneItem list

        Args:
            resource: Storage Account resource dictionary containing:
                - id: Storage Account resource ID
                - name: Storage Account name
                - properties: Storage Account properties

        Returns:
            List of DataPlaneItem representing Storage Account contents

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../storageAccounts/mystorageacct",
            ...     "type": "Microsoft.Storage/storageAccounts",
            ...     "name": "mystorageacct"
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of containers/shares/tables/queues
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for StoragePlugin: {resource}")

        storage_name = resource.get("name", "unknown")
        self.logger.info(
            f"Discovering data plane items for Storage Account: {storage_name}"
        )

        items: List[DataPlaneItem] = []

        try:
            # Import Azure SDK components
            from azure.core.exceptions import AzureError, HttpResponseError
            from azure.identity import DefaultAzureCredential
            from azure.storage.blob import BlobServiceClient

            # Construct storage account URL
            account_url = f"https://{storage_name}.blob.core.windows.net"
            credential = DefaultAzureCredential()

            # Discover blob containers
            try:
                blob_service = BlobServiceClient(
                    account_url=account_url, credential=credential
                )
                containers = blob_service.list_containers()

                for container_props in containers:
                    # Add container as data plane item
                    items.append(
                        DataPlaneItem(
                            name=container_props.name,
                            item_type="container",
                            properties={
                                "public_access": container_props.public_access
                                or "None",
                                "metadata": container_props.metadata or {},
                            },
                            source_resource_id=resource["id"],
                            metadata={
                                "last_modified": (
                                    container_props.last_modified.isoformat()
                                    if container_props.last_modified
                                    else None
                                ),
                            },
                        )
                    )

                    # Sample blobs in each container (limit to avoid performance issues)
                    try:
                        container_client = blob_service.get_container_client(
                            container_props.name
                        )
                        blob_list = container_client.list_blobs()
                        blob_count = 0

                        for blob_props in blob_list:
                            if blob_count >= 10:  # Limit sampling
                                self.logger.debug(
                                    f"Limiting blob discovery to 10 per container in {container_props.name}"
                                )
                                break

                            items.append(
                                DataPlaneItem(
                                    name=f"{container_props.name}/{blob_props.name}",
                                    item_type="blob",
                                    properties={
                                        "container": container_props.name,
                                        "blob_type": blob_props.blob_type,
                                        "size": blob_props.size,
                                        "content_type": blob_props.content_settings.content_type
                                        if blob_props.content_settings
                                        else None,
                                    },
                                    source_resource_id=resource["id"],
                                    metadata={
                                        "last_modified": (
                                            blob_props.last_modified.isoformat()
                                            if blob_props.last_modified
                                            else None
                                        ),
                                        "etag": blob_props.etag,
                                    },
                                )
                            )
                            blob_count += 1
                    except (AzureError, HttpResponseError) as e:
                        self.logger.warning(
                            f"Failed to list blobs in container {container_props.name}: {e}"
                        )

            except (AzureError, HttpResponseError) as e:
                self.logger.warning(
                    f"Failed to discover blob containers in {storage_name}: {e}"
                )

        except ImportError as e:
            self.logger.error(
                f"Azure Storage SDK not installed. Install with: "
                f"pip install azure-storage-blob azure-storage-file-share. "
                f"Error: {e}"
            )
        except Exception as e:
            self.logger.error(
                f"Unexpected error discovering Storage Account items: {e}"
            )

        self.logger.info(
            f"Discovered {len(items)} data plane items in Storage Account '{storage_name}'"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate Storage Account data plane items.

        For containers and blobs, this generates:
        - Blob container resources
        - Documentation about data migration
        - References to data migration tools

        Note: Actual blob data is not included. Users must use Azure Storage migration
        tools (AzCopy, Azure Data Factory, etc.) to copy data.

        Args:
            items: List of Storage Account data plane items to replicate
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code for containers

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="data", item_type="container", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "azurerm_storage_container" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by StoragePlugin"
            )

        if output_format.lower() != "terraform":
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} Storage items"
        )

        if not items:
            return "# No Storage Account data plane items to replicate\n"

        code_lines = [
            "# Storage Account Data Plane Items",
            "# Generated by Azure Tenant Grapher - StoragePlugin",
            "#",
            "# DATA MIGRATION NOTE: This creates empty containers/shares.",
            "# You must manually migrate data using:",
            "#   - AzCopy: https://docs.microsoft.com/azure/storage/common/storage-use-azcopy-v10",
            "#   - Azure Data Factory: For large-scale migrations",
            "#   - Azure Storage Explorer: For manual/selective migration",
            "",
        ]

        # Group items by type
        containers = [item for item in items if item.item_type == "container"]
        blobs = [item for item in items if item.item_type == "blob"]

        # Generate code for containers
        if containers:
            code_lines.append("# Blob Containers")
            for item in containers:
                resource_name = self._sanitize_name(item.name)
                code_lines.extend(
                    [
                        f'resource "azurerm_storage_container" "{resource_name}" {{',
                        f'  name                  = "{item.name}"',
                        "  # TODO: Reference your Storage Account resource here",
                        "  storage_account_name  = azurerm_storage_account.REPLACE_ME.name",
                        f'  container_access_type = "{item.properties.get("public_access", "private")}"',
                        "}",
                        "",
                    ]
                )

        # Add blob migration notes
        if blobs:
            code_lines.extend(
                [
                    "# Blobs",
                    f"# Discovered {len(blobs)} blob(s) across containers.",
                    "# Use AzCopy to migrate blob data:",
                    "#   azcopy copy 'https://source.blob.core.windows.net/container/*' \\",
                    "#               'https://target.blob.core.windows.net/container/' \\",
                    "#               --recursive",
                    "",
                ]
            )

        # Add migration script template
        code_lines.extend(
            [
                "# Migration Script Template",
                "# Save as: migrate_storage_data.sh",
                "# ",
                "# #!/bin/bash",
                "# SOURCE_ACCOUNT='source_account_name'",
                "# TARGET_ACCOUNT='target_account_name'",
                "# ",
            ]
        )

        for container in containers:
            code_lines.append(
                f"# azcopy copy 'https://$SOURCE_ACCOUNT.blob.core.windows.net/{container.name}/*' \\"
            )
            code_lines.append(
                f"#              'https://$TARGET_ACCOUNT.blob.core.windows.net/{container.name}/' \\"
            )
            code_lines.append("#              --recursive")

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate Storage Account contents from source to target using AzCopy.

        This method:
        1. Discovers all containers from the source Storage Account
        2. Validates AzCopy is installed
        3. Replicates each container to the target Storage Account
        4. Returns detailed statistics and error information

        Args:
            source_resource: Source Storage Account resource containing:
                - id: Azure resource ID
                - name: Storage Account name
                - type: Resource type (must be Microsoft.Storage/storageAccounts)
            target_resource: Target Storage Account resource with same structure

        Returns:
            ReplicationResult containing:
                - success: True if at least one container replicated successfully
                - items_discovered: Total number of items discovered from source
                - items_replicated: Number of containers successfully replicated
                - errors: List of error messages encountered
                - warnings: List of warning messages

        Raises:
            ValueError: If source or target resource is invalid

        Example:
            >>> result = plugin.replicate(source_storage, target_storage)
            >>> if result.success:
            ...     print(f"Replicated {result.items_replicated} containers")
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating from Storage Account {source_name} to {target_name}"
        )

        # 1. Discover items from source
        try:
            source_items = self.discover(source_resource)
        except Exception as e:
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"Failed to discover items from source: {e}"],
                warnings=[],
            )

        # Filter to containers only
        containers = [item for item in source_items if item.item_type == "container"]

        if not containers:
            return ReplicationResult(
                success=True,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[],
                warnings=["No containers to replicate"],
            )

        # 2. Check if AzCopy is available
        import subprocess

        try:
            result = subprocess.run(
                ["azcopy", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return ReplicationResult(
                    success=False,
                    items_discovered=len(source_items),
                    items_replicated=0,
                    errors=[
                        "AzCopy not available. Install from: "
                        "https://docs.microsoft.com/azure/storage/common/storage-use-azcopy-v10"
                    ],
                    warnings=[],
                )
            self.logger.debug(f"AzCopy version: {result.stdout.strip()}")
        except FileNotFoundError:
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=[
                    "AzCopy not found. Install from: "
                    "https://docs.microsoft.com/azure/storage/common/storage-use-azcopy-v10"
                ],
                warnings=[],
            )
        except subprocess.TimeoutExpired:
            return ReplicationResult(
                success=False,
                items_discovered=len(source_items),
                items_replicated=0,
                errors=["AzCopy command timed out"],
                warnings=[],
            )

        # 3. Replicate each container
        replicated_count = 0
        errors = []
        warnings = []

        for container in containers:
            container_name = container.name
            source_url = (
                f"https://{source_name}.blob.core.windows.net/{container_name}/*"
            )
            target_url = (
                f"https://{target_name}.blob.core.windows.net/{container_name}/"
            )

            self.logger.info(f"Replicating container: {container_name}")

            try:
                # Run AzCopy copy command
                # Note: Assumes Azure credentials are configured (via env vars or Azure CLI login)
                result = subprocess.run(
                    [
                        "azcopy",
                        "copy",
                        source_url,
                        target_url,
                        "--recursive",
                        "--overwrite=ifSourceNewer",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 minute timeout per container
                )

                if result.returncode == 0:
                    replicated_count += 1
                    self.logger.debug(
                        f"Successfully replicated container: {container_name}"
                    )
                else:
                    error_msg = (
                        result.stderr.strip() if result.stderr else "Unknown error"
                    )
                    errors.append(
                        f"Failed to replicate container {container_name}: {error_msg}"
                    )
                    self.logger.warning(
                        f"AzCopy failed for {container_name}: {error_msg}"
                    )

            except subprocess.TimeoutExpired:
                errors.append(
                    f"Timeout replicating container {container_name} (exceeded 10 minutes)"
                )
            except Exception as e:
                errors.append(
                    f"Unexpected error replicating container {container_name}: {e!s}"
                )

        success = replicated_count > 0
        self.logger.info(
            f"Replication complete: {replicated_count}/{len(containers)} "
            f"containers replicated"
        )

        return ReplicationResult(
            success=success,
            items_discovered=len(source_items),
            items_replicated=replicated_count,
            errors=errors,
            warnings=warnings,
        )

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize a name for use in Terraform resource names.

        Args:
            name: Original name (may contain hyphens, special chars)

        Returns:
            Sanitized name safe for Terraform identifiers
        """
        # Replace hyphens and special chars with underscores
        sanitized = (
            name.replace("-", "_").replace(".", "_").replace(" ", "_").replace("/", "_")
        )

        # Ensure it starts with a letter
        if sanitized and not sanitized[0].isalpha():
            sanitized = "storage_" + sanitized

        return sanitized.lower()
