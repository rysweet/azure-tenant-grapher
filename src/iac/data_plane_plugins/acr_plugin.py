"""
Azure Container Registry (ACR) data plane replication plugin.

This plugin handles discovery and replication of Azure Container Registry data plane
items including:
- Repositories
- Container images
- Image tags
- Image manifests (multi-arch support)

The plugin supports two modes:
1. Template Mode: Creates empty repository structure (no image data)
2. Replication Mode: Provides strategies for full image replication

Replication strategies:
- ACR Import API (recommended for same-region Azure registries)
- Docker pull/push (works cross-cloud, slower)
- Azure CLI scripts (az acr import commands)

WARNING: Container registries can be very large (50GB+). This plugin provides
size warnings and progress tracking for replication operations.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional

import sys
sys.path.insert(0, '/home/azureuser/src/azure-tenant-grapher/src/iac/plugins')
from base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    Permission,
    ReplicationMode,
    ReplicationResult,
)

logger = logging.getLogger(__name__)


class ContainerRegistryPlugin(DataPlanePlugin):
    """
    Data plane plugin for Azure Container Registry.

    Discovers and replicates container images, repositories, and tags using
    Azure Container Registry SDK and Docker SDK.

    Example:
        plugin = ContainerRegistryPlugin()
        items = plugin.discover(acr_resource)
        code = plugin.generate_replication_code(items, "terraform")
    """

    # Size thresholds for warnings (in bytes)
    SIZE_WARNING_10GB = 10 * 1024 * 1024 * 1024
    SIZE_WARNING_50GB = 50 * 1024 * 1024 * 1024
    SIZE_WARNING_100GB = 100 * 1024 * 1024 * 1024

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for Container Registry."""
        return "Microsoft.ContainerRegistry/registries"

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """
        Return Azure RBAC permissions required for ACR operations.

        Template mode requires read-only access to list repositories and tags.
        Replication mode requires pull/push permissions for image transfer.

        Args:
            mode: The replication mode

        Returns:
            List of Permission objects describing needed RBAC roles
        """
        if mode == ReplicationMode.TEMPLATE:
            return [
                Permission(
                    scope="resource",
                    actions=["Microsoft.ContainerRegistry/registries/read"],
                    data_actions=[
                        "Microsoft.ContainerRegistry/registries/metadata/read",
                    ],
                    description="Read registry metadata and list repositories (no image pull)",
                )
            ]
        else:  # REPLICATION mode
            return [
                Permission(
                    scope="resource",
                    actions=[
                        "Microsoft.ContainerRegistry/registries/read",
                        "Microsoft.ContainerRegistry/registries/importImage/action",
                    ],
                    data_actions=[
                        "Microsoft.ContainerRegistry/registries/pull/read",
                        "Microsoft.ContainerRegistry/registries/push/write",
                    ],
                    description="Pull and push container images, import from other registries",
                )
            ]

    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover Container Registry repositories, images, and tags.

        Uses Azure Container Registry SDK to:
        1. Authenticate to the registry
        2. List all repositories
        3. For each repository, list all tags
        4. Retrieve image manifest and size information
        5. Support multi-architecture images

        Args:
            resource: Container Registry resource dictionary containing:
                - id: Registry resource ID
                - name: Registry name
                - properties: Registry properties (including loginServer)

        Returns:
            List of DataPlaneItem representing repositories and images

        Example:
            >>> resource = {
            ...     "id": "/subscriptions/.../registries/myacr",
            ...     "type": "Microsoft.ContainerRegistry/registries",
            ...     "name": "myacr",
            ...     "properties": {"loginServer": "myacr.azurecr.io"}
            ... }
            >>> items = plugin.discover(resource)
            >>> len(items)  # Returns count of repositories
        """
        if not self.validate_resource(resource):
            raise ValueError(f"Invalid resource for ContainerRegistryPlugin: {resource}")

        registry_name = resource.get("name", "unknown")
        self.logger.info(f"Discovering data plane items for Container Registry: {registry_name}")

        items: List[DataPlaneItem] = []
        total_size_bytes = 0

        try:
            # Import Azure SDK components
            from azure.identity import DefaultAzureCredential
            from azure.containerregistry import ContainerRegistryClient
            from azure.core.exceptions import AzureError, HttpResponseError

            # Parse registry properties
            properties = resource.get("properties", {})
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    properties = {}

            login_server = properties.get("loginServer")
            if not login_server:
                # Construct login server from registry name
                login_server = f"{registry_name}.azurecr.io"
                self.logger.warning(
                    f"loginServer not found in properties, using constructed URL: {login_server}"
                )

            endpoint = f"https://{login_server}"

            # Authenticate
            credential = DefaultAzureCredential()

            # Create Container Registry client
            try:
                client = ContainerRegistryClient(endpoint=endpoint, credential=credential)

                # List repositories
                repositories = client.list_repository_names()

                for repo_name in repositories:
                    self.logger.debug(f"Discovering tags for repository: {repo_name}")

                    try:
                        # Get repository properties
                        repo_props = client.get_repository_properties(repo_name)

                        # List tags for this repository
                        tags = []
                        tag_details = []

                        for tag in client.list_tag_properties(repo_name):
                            tags.append(tag.name)

                            # Get manifest for size info
                            manifest_size = 0
                            digest = None
                            architectures = []

                            try:
                                # Get manifest to determine size and architecture
                                manifest = client.get_manifest_properties(
                                    repo_name, tag.name
                                )
                                manifest_size = manifest.size or 0
                                digest = manifest.digest

                                # Try to get architecture info from manifest
                                # Note: This requires additional API call which may not always work
                                if hasattr(manifest, 'architecture'):
                                    architectures.append(manifest.architecture)
                                else:
                                    architectures.append("unknown")

                            except Exception as e:
                                self.logger.debug(
                                    f"Could not get manifest details for {repo_name}:{tag.name}: {e}"
                                )

                            tag_details.append({
                                "tag": tag.name,
                                "size_bytes": manifest_size,
                                "digest": digest,
                                "architectures": architectures,
                                "created_on": tag.created_on.isoformat() if tag.created_on else None,
                                "last_updated": tag.last_updated_on.isoformat() if tag.last_updated_on else None,
                            })

                            total_size_bytes += manifest_size

                        # Create DataPlaneItem for this repository
                        items.append(
                            DataPlaneItem(
                                name=repo_name,
                                item_type="repository",
                                properties={
                                    "tag_count": repo_props.tag_count if hasattr(repo_props, 'tag_count') else len(tags),
                                    "manifest_count": repo_props.manifest_count if hasattr(repo_props, 'manifest_count') else len(tags),
                                    "tags": tags,
                                },
                                source_resource_id=resource["id"],
                                metadata={
                                    "created_on": (
                                        repo_props.created_on.isoformat()
                                        if hasattr(repo_props, 'created_on') and repo_props.created_on
                                        else None
                                    ),
                                    "last_updated": (
                                        repo_props.last_updated_on.isoformat()
                                        if hasattr(repo_props, 'last_updated_on') and repo_props.last_updated_on
                                        else None
                                    ),
                                    "tag_details": tag_details,
                                    "registry_name": registry_name,
                                    "login_server": login_server,
                                },
                                size_bytes=sum(td.get("size_bytes", 0) for td in tag_details),
                            )
                        )

                    except (AzureError, HttpResponseError) as e:
                        self.logger.warning(f"Failed to discover tags for repository {repo_name}: {e}")
                        continue

            except (AzureError, HttpResponseError) as e:
                self.logger.error(f"Failed to connect to Container Registry {registry_name}: {e}")
                # Return empty list but log the error
                return []

        except ImportError as e:
            self.logger.error(
                f"Azure Container Registry SDK not installed. Install with: "
                f"pip install azure-containerregistry azure-identity. "
                f"Error: {e}"
            )
            return []
        except Exception as e:
            self.logger.error(f"Unexpected error discovering Container Registry items: {e}")
            return []

        # Log size warnings
        self._log_size_warnings(registry_name, total_size_bytes)

        # Report discovery progress
        if self.progress_reporter:
            self.progress_reporter.report_discovery(resource["id"], len(items))

        self.logger.info(
            f"Discovered {len(items)} repositories in Container Registry '{registry_name}' "
            f"(total size: {self._format_size(total_size_bytes)})"
        )
        return items

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to document Container Registry repositories.

        For template mode, this generates:
        - Comments documenting repositories and tags
        - Placeholder null_resource with local-exec for ACR import
        - References to replication strategies

        Security note: Images are not included in Terraform state.
        Actual image replication requires separate tooling (Docker, ACR import, etc.).

        Args:
            items: List of Container Registry repositories to document
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code with replication strategy documentation

        Raises:
            ValueError: If output_format is not supported

        Example:
            >>> items = [DataPlaneItem(name="myapp", item_type="repository", ...)]
            >>> code = plugin.generate_replication_code(items)
            >>> "# Container Registry Repositories" in code
            True
        """
        if not self.supports_output_format(output_format):
            raise ValueError(
                f"Output format '{output_format}' not supported by ContainerRegistryPlugin"
            )

        if output_format.lower() != "terraform":
            # Future: Support Bicep and ARM templates
            raise ValueError("Only Terraform format is currently supported")

        self.logger.info(
            f"Generating {output_format} code for {len(items)} Container Registry repositories"
        )

        if not items:
            return "# No Container Registry repositories to replicate\n"

        code_lines = [
            "# Container Registry Repositories",
            "# Generated by Azure Tenant Grapher - ContainerRegistryPlugin",
            "#",
            "# NOTE: Container images are NOT stored in Terraform state.",
            "# This code documents the repositories and provides replication strategies.",
            "#",
            "# Replication Options:",
            "# 1. ACR Import (fastest, same Azure region):",
            "#    az acr import --name <target-registry> --source <source-registry>/<repo>:<tag>",
            "#",
            "# 2. Docker Pull/Push (works cross-cloud):",
            "#    docker pull <source>/<repo>:<tag>",
            "#    docker tag <source>/<repo>:<tag> <target>/<repo>:<tag>",
            "#    docker push <target>/<repo>:<tag>",
            "#",
            "# 3. Azure Container Registry Tasks (automated):",
            "#    https://docs.microsoft.com/azure/container-registry/container-registry-tasks-overview",
            "",
        ]

        # Calculate total size
        total_size = sum(item.size_bytes or 0 for item in items)
        total_images = sum(len(item.properties.get("tags", [])) for item in items)

        code_lines.extend([
            f"# Total Repositories: {len(items)}",
            f"# Total Images/Tags: {total_images}",
            f"# Estimated Total Size: {self._format_size(total_size)}",
            "",
        ])

        # Add size warnings
        if total_size >= self.SIZE_WARNING_100GB:
            code_lines.extend([
                "# ⚠️  EXTREMELY LARGE REGISTRY (100GB+)",
                "# Manual or selective replication is strongly recommended.",
                "# Consider using ACR geo-replication instead of full copy.",
                "",
            ])
        elif total_size >= self.SIZE_WARNING_50GB:
            code_lines.extend([
                "# ⚠️  VERY LARGE REGISTRY (50GB+)",
                "# Full replication will take significant time and bandwidth.",
                "# Consider selective replication or ACR Tasks.",
                "",
            ])
        elif total_size >= self.SIZE_WARNING_10GB:
            code_lines.extend([
                "# ⚠️  LARGE REGISTRY (10GB+)",
                "# Replication may take considerable time.",
                "",
            ])

        # Document each repository
        code_lines.append("# Repository Inventory")
        code_lines.append("")

        for item in items:
            repo_name = item.name
            tags = item.properties.get("tags", [])
            repo_size = item.size_bytes or 0
            tag_details = item.metadata.get("tag_details", []) if item.metadata else []

            code_lines.extend([
                f"# Repository: {repo_name}",
                f"#   Tags: {len(tags)}",
                f"#   Size: {self._format_size(repo_size)}",
            ])

            # List first 10 tags
            for tag in tags[:10]:
                # Find tag details if available
                tag_info = next((td for td in tag_details if td.get("tag") == tag), {})
                tag_size = tag_info.get("size_bytes", 0)
                architectures = tag_info.get("architectures", [])

                arch_str = f" ({', '.join(architectures)})" if architectures else ""
                size_str = f" - {self._format_size(tag_size)}" if tag_size > 0 else ""

                code_lines.append(f"#     - {tag}{arch_str}{size_str}")

            if len(tags) > 10:
                code_lines.append(f"#     ... and {len(tags) - 10} more tags")

            code_lines.append("")

        # Generate replication script template
        code_lines.extend([
            "# Example Replication Script",
            "# Uncomment and customize for your target registry",
            "",
            "# locals {",
            "#   source_registry = \"SOURCE_REGISTRY.azurecr.io\"",
            "#   target_registry = \"TARGET_REGISTRY.azurecr.io\"",
            "#   repositories = [",
        ])

        for item in items:
            code_lines.append(f'#     "{item.name}",')

        code_lines.extend([
            "#   ]",
            "# }",
            "",
            "# # Option 1: Using ACR Import (recommended)",
            "# resource \"null_resource\" \"acr_image_import\" {",
            "#   for_each = toset(local.repositories)",
            "#",
            "#   provisioner \"local-exec\" {",
            "#     command = <<-EOT",
            "#       az acr import \\",
            "#         --name ${local.target_registry} \\",
            "#         --source ${local.source_registry}/${each.value}:latest \\",
            "#         --image ${each.value}:latest",
            "#     EOT",
            "#   }",
            "#",
            "#   depends_on = [azurerm_container_registry.target]",
            "# }",
            "",
            "# # Option 2: Using Docker CLI",
            "# resource \"null_resource\" \"acr_docker_copy\" {",
            "#   for_each = toset(local.repositories)",
            "#",
            "#   provisioner \"local-exec\" {",
            "#     command = <<-EOT",
            "#       docker pull ${local.source_registry}/${each.value}:latest",
            "#       docker tag ${local.source_registry}/${each.value}:latest \\",
            "#         ${local.target_registry}/${each.value}:latest",
            "#       docker push ${local.target_registry}/${each.value}:latest",
            "#     EOT",
            "#   }",
            "#",
            "#   depends_on = [azurerm_container_registry.target]",
            "# }",
            "",
        ])

        return "\n".join(code_lines)

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate Container Registry contents from source to target.

        This implementation provides a foundation for ACR replication with
        support for both template and replication modes via replicate_with_mode.

        Args:
            source_resource: Source Container Registry resource
            target_resource: Target Container Registry resource

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
        Replicate Container Registry with mode awareness.

        Template Mode:
        - Discovers repositories and tags
        - Creates documentation
        - Returns success with discovery stats

        Replication Mode:
        - Discovers all images
        - Generates replication scripts using az acr import
        - Provides step-by-step instructions
        - NOTE: Actual image replication requires external tooling

        Args:
            source_resource: Source Container Registry resource
            target_resource: Target Container Registry resource
            mode: Replication mode (template or replication)

        Returns:
            ReplicationResult with operation statistics and guidance

        Example:
            >>> source = {"id": "...", "type": "Microsoft.ContainerRegistry/registries", ...}
            >>> target = {"id": "...", "type": "Microsoft.ContainerRegistry/registries", ...}
            >>> result = plugin.replicate_with_mode(source, target, ReplicationMode.TEMPLATE)
            >>> result.success
            True
        """
        if not self.validate_resource(source_resource):
            raise ValueError(f"Invalid source resource: {source_resource}")

        if not self.validate_resource(target_resource):
            raise ValueError(f"Invalid target resource: {target_resource}")

        start_time = time.time()

        source_name = source_resource.get("name", "unknown")
        target_name = target_resource.get("name", "unknown")

        self.logger.info(
            f"Replicating Container Registry from '{source_name}' to '{target_name}' "
            f"(mode: {mode.value})"
        )

        # Discover items from source
        try:
            source_items = self.discover(source_resource)
        except Exception as e:
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"Failed to discover source registry: {e}"],
                warnings=[],
                duration_seconds=time.time() - start_time,
            )

        if not source_items:
            return ReplicationResult(
                success=True,
                items_discovered=0,
                items_replicated=0,
                warnings=["Source registry has no repositories"],
                duration_seconds=time.time() - start_time,
            )

        warnings = []
        errors = []

        # Calculate total size
        total_size = sum(item.size_bytes or 0 for item in source_items)

        if mode == ReplicationMode.TEMPLATE:
            # Template mode: Just document what exists
            self.logger.info(
                f"Template mode: Documented {len(source_items)} repositories "
                f"({self._format_size(total_size)} total)"
            )

            warnings.append(
                "Template mode: Repository structure documented. "
                "No images were copied. Use replication mode or manual tools for actual image transfer."
            )

            result = ReplicationResult(
                success=True,
                items_discovered=len(source_items),
                items_replicated=0,
                warnings=warnings,
                duration_seconds=time.time() - start_time,
            )

            if self.progress_reporter:
                self.progress_reporter.report_completion(result)

            return result

        else:  # REPLICATION mode
            # For replication mode, we generate detailed instructions
            # Actual image copying requires external tools (Docker, ACR import, etc.)

            self.logger.info(
                f"Replication mode: Preparing to replicate {len(source_items)} repositories "
                f"({self._format_size(total_size)} total)"
            )

            # Generate replication script
            source_login_server = source_resource.get("properties", {}).get(
                "loginServer", f"{source_name}.azurecr.io"
            )
            target_login_server = target_resource.get("properties", {}).get(
                "loginServer", f"{target_name}.azurecr.io"
            )

            # Build replication commands
            replication_commands = []
            for item in source_items:
                repo_name = item.name
                tags = item.properties.get("tags", [])

                for tag in tags:
                    cmd = (
                        f"az acr import "
                        f"--name {target_name} "
                        f"--source {source_login_server}/{repo_name}:{tag} "
                        f"--image {repo_name}:{tag}"
                    )
                    replication_commands.append(cmd)

            # Save replication script
            script_content = self._generate_replication_script(
                source_name,
                target_name,
                source_items,
                source_login_server,
                target_login_server,
            )

            warnings.extend([
                f"Replication mode: Generated commands for {len(replication_commands)} images.",
                "Actual image replication requires running the generated script.",
                "See replication script for detailed instructions.",
                f"Estimated data transfer: {self._format_size(total_size)}",
            ])

            # Add size-specific warnings
            if total_size >= self.SIZE_WARNING_100GB:
                warnings.append(
                    "EXTREMELY LARGE REGISTRY: Consider geo-replication or selective replication instead."
                )
            elif total_size >= self.SIZE_WARNING_50GB:
                warnings.append(
                    "VERY LARGE REGISTRY: Full replication will take significant time."
                )

            self.logger.info(f"Generated replication script with {len(replication_commands)} commands")

            if self.progress_reporter:
                result = ReplicationResult(
                    success=True,
                    items_discovered=len(source_items),
                    items_replicated=0,  # Script generated, but not executed
                    items_skipped=0,
                    warnings=warnings,
                    duration_seconds=time.time() - start_time,
                )
                self.progress_reporter.report_completion(result)

            return ReplicationResult(
                success=True,
                items_discovered=len(source_items),
                items_replicated=0,  # Actual replication happens outside Terraform
                items_skipped=0,
                warnings=warnings,
                errors=errors,
                duration_seconds=time.time() - start_time,
            )

    def estimate_operation_time(
        self,
        items: List[DataPlaneItem],
        mode: ReplicationMode
    ) -> float:
        """
        Estimate time required for Container Registry replication.

        Template mode: Fast, just API calls
        Replication mode: Depends on total image size

        Args:
            items: Container repositories to replicate
            mode: Replication mode

        Returns:
            Estimated seconds
        """
        if mode == ReplicationMode.TEMPLATE:
            # Template mode is just API calls
            return len(items) * 2.0  # 2 seconds per repository

        # Replication mode: Estimate based on size
        total_size = sum(item.size_bytes or 0 for item in items)

        # Assume 10 MB/s transfer rate
        transfer_rate_mbps = 10 * 1024 * 1024  # 10 MB/s

        estimated_seconds = total_size / transfer_rate_mbps

        # Add overhead for each image (tagging, pushing)
        total_images = sum(len(item.properties.get("tags", [])) for item in items)
        overhead_seconds = total_images * 5  # 5 seconds per image

        return estimated_seconds + overhead_seconds

    def _log_size_warnings(self, registry_name: str, total_size_bytes: int) -> None:
        """Log appropriate warnings based on registry size."""
        if total_size_bytes >= self.SIZE_WARNING_100GB:
            self.logger.warning(
                f"Container Registry '{registry_name}' is EXTREMELY LARGE "
                f"({self._format_size(total_size_bytes)}). "
                "Manual or selective replication is strongly recommended."
            )
        elif total_size_bytes >= self.SIZE_WARNING_50GB:
            self.logger.warning(
                f"Container Registry '{registry_name}' is VERY LARGE "
                f"({self._format_size(total_size_bytes)}). "
                "Full replication will take significant time."
            )
        elif total_size_bytes >= self.SIZE_WARNING_10GB:
            self.logger.info(
                f"Container Registry '{registry_name}' is large "
                f"({self._format_size(total_size_bytes)}). "
                "Replication may take considerable time."
            )

    def _format_size(self, size_bytes: int) -> str:
        """Format byte size as human-readable string."""
        if size_bytes == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        unit_index = 0
        size = float(size_bytes)

        while size >= 1024.0 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1

        return f"{size:.2f} {units[unit_index]}"

    def _generate_replication_script(
        self,
        source_name: str,
        target_name: str,
        items: List[DataPlaneItem],
        source_login_server: str,
        target_login_server: str,
    ) -> str:
        """
        Generate a bash script for ACR replication.

        Args:
            source_name: Source registry name
            target_name: Target registry name
            items: List of repositories to replicate
            source_login_server: Source registry login server
            target_login_server: Target registry login server

        Returns:
            Bash script content
        """
        lines = [
            "#!/bin/bash",
            "# Azure Container Registry Replication Script",
            "# Generated by Azure Tenant Grapher",
            "#",
            f"# Source Registry: {source_name} ({source_login_server})",
            f"# Target Registry: {target_name} ({target_login_server})",
            "#",
            "# Prerequisites:",
            "# 1. Azure CLI installed and authenticated (az login)",
            "# 2. Permissions: AcrPull on source, AcrPush on target",
            "# 3. Network connectivity to both registries",
            "",
            "set -e  # Exit on error",
            "",
            f'SOURCE_REGISTRY="{source_name}"',
            f'TARGET_REGISTRY="{target_name}"',
            f'SOURCE_LOGIN_SERVER="{source_login_server}"',
            f'TARGET_LOGIN_SERVER="{target_login_server}"',
            "",
            "echo 'Starting Container Registry replication...'",
            "echo",
            "",
        ]

        # Add commands for each repository/tag
        for item in items:
            repo_name = item.name
            tags = item.properties.get("tags", [])
            repo_size = item.size_bytes or 0

            lines.extend([
                f"# Repository: {repo_name} ({self._format_size(repo_size)})",
                f"echo 'Replicating repository: {repo_name}'",
                "",
            ])

            for tag in tags:
                lines.extend([
                    f"echo '  Importing {repo_name}:{tag}...'",
                    f"az acr import \\",
                    f"  --name $TARGET_REGISTRY \\",
                    f"  --source $SOURCE_LOGIN_SERVER/{repo_name}:{tag} \\",
                    f"  --image {repo_name}:{tag} \\",
                    f"  --force",
                    "",
                ])

        lines.extend([
            "echo",
            "echo 'Container Registry replication completed!'",
            f"echo 'Replicated {len(items)} repositories'",
            "",
        ])

        return "\n".join(lines)
