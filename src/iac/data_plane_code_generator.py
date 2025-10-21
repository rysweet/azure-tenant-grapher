"""
Data plane code generator for Azure Tenant Grapher.

Generates IaC code for discovered data plane items by delegating to
appropriate plugins.
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List

from .plugins import PluginRegistry
from .plugins.base_plugin import DataPlaneItem

logger = logging.getLogger(__name__)


class DataPlaneCodeGenerator:
    """
    Generates IaC code for data plane items.

    Groups items by resource type and delegates to appropriate plugins
    for code generation. Creates separate files per resource type.
    """

    def __init__(self, output_format: str = "terraform"):
        """
        Initialize generator for specified IaC format.

        Args:
            output_format: IaC format (terraform, bicep, arm)
        """
        self.output_format = output_format.lower()
        self.logger = logger

        # Validate output format
        valid_formats = ["terraform", "bicep", "arm"]
        if self.output_format not in valid_formats:
            raise ValueError(
                f"Invalid output format '{output_format}'. "
                f"Must be one of: {', '.join(valid_formats)}"
            )

    def _get_file_extension(self) -> str:
        """
        Get file extension for output format.

        Returns:
            File extension (e.g., ".tf", ".bicep", ".json")
        """
        extensions = {
            "terraform": ".tf",
            "bicep": ".bicep",
            "arm": ".json",
        }
        return extensions[self.output_format]

    def _sanitize_resource_type(self, resource_type: str) -> str:
        """
        Sanitize resource type for use in filename.

        Converts resource types like "Microsoft.KeyVault/vaults" to "keyvault".

        Args:
            resource_type: Azure resource type

        Returns:
            Sanitized filename component
        """
        # Extract the service name from resource type
        # E.g., "Microsoft.KeyVault/vaults" -> "keyvault"
        # E.g., "Microsoft.Storage/storageAccounts" -> "storage"
        # E.g., "Microsoft.Sql/servers/databases" -> "sql"
        # E.g., "Microsoft.Web/sites" -> handled specially below

        # Remove "Microsoft." prefix
        sanitized = resource_type.replace("Microsoft.", "")

        # Extract first component (before first slash)
        if "/" in sanitized:
            sanitized = sanitized.split("/")[0]

        # Convert to lowercase
        sanitized = sanitized.lower()

        # Remove special characters, keep only alphanumeric
        sanitized = re.sub(r"[^a-z0-9]", "", sanitized)

        return sanitized

    def _group_items_by_resource_type(
        self, items_by_resource: Dict[str, List[DataPlaneItem]], resources: List[Dict[str, Any]]
    ) -> Dict[str, List[DataPlaneItem]]:
        """
        Group data plane items by resource type.

        Args:
            items_by_resource: Dict mapping resource IDs to data plane items
            resources: List of resource dictionaries (for type lookup)

        Returns:
            Dict mapping resource types to all items for that type
        """
        # Create resource ID -> resource type mapping
        resource_type_map = {r.get("id"): r.get("type") for r in resources if r}

        # Group items by type
        items_by_type: Dict[str, List[DataPlaneItem]] = {}

        for resource_id, items in items_by_resource.items():
            resource_type = resource_type_map.get(resource_id)
            if not resource_type:
                self.logger.warning(
                    f"Could not determine type for resource {resource_id}, skipping"
                )
                continue

            if resource_type not in items_by_type:
                items_by_type[resource_type] = []

            items_by_type[resource_type].extend(items)

        return items_by_type

    def _get_output_filename(self, resource_type: str) -> str:
        """
        Generate output filename for resource type.

        Args:
            resource_type: Azure resource type

        Returns:
            Filename (e.g., "data_plane_keyvault.tf")
        """
        sanitized_type = self._sanitize_resource_type(resource_type)
        extension = self._get_file_extension()

        # Special case handling for Microsoft.Web/sites
        # (distinguish between App Service and Function App in the filename if needed)
        # For now, we'll just use "appservice" for all Microsoft.Web/sites
        if resource_type == "Microsoft.Web/sites":
            sanitized_type = "appservice"

        return f"data_plane_{sanitized_type}{extension}"

    def generate(
        self,
        items_by_resource: Dict[str, List[DataPlaneItem]],
        resources: List[Dict[str, Any]],
        output_dir: Path
    ) -> List[Path]:
        """
        Generate data plane IaC files.

        Creates separate files per resource type:
        - data_plane_keyvault.tf
        - data_plane_storage.tf
        - data_plane_sql.tf
        - data_plane_appservice.tf
        - data_plane_functionapp.tf

        Args:
            items_by_resource: Dict mapping resource IDs to data plane items
            resources: List of resource dictionaries (for metadata)
            output_dir: Output directory for generated files

        Returns:
            List of written file paths
        """
        if not items_by_resource:
            self.logger.info("No data plane items to generate code for")
            return []

        self.logger.info(
            f"Generating {self.output_format} code for data plane items in {output_dir}"
        )

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Group items by resource type
        items_by_type = self._group_items_by_resource_type(items_by_resource, resources)

        self.logger.info(
            f"Grouped items into {len(items_by_type)} resource types: "
            f"{', '.join(items_by_type.keys())}"
        )

        # Generate code for each resource type
        written_files: List[Path] = []

        for resource_type, items in items_by_type.items():
            try:
                self.logger.info(
                    f"Generating code for {resource_type} ({len(items)} items)"
                )

                # Get plugin for this resource type
                plugin = PluginRegistry.get_plugin(resource_type)

                if not plugin:
                    self.logger.warning(
                        f"No plugin available for resource type {resource_type}, skipping"
                    )
                    continue

                # Check if plugin supports output format
                if not plugin.supports_output_format(self.output_format):
                    self.logger.warning(
                        f"Plugin {plugin.plugin_name} does not support {self.output_format} format, skipping"
                    )
                    continue

                # Generate replication code
                code = plugin.generate_replication_code(items, self.output_format)

                if not code or not code.strip():
                    self.logger.warning(
                        f"Plugin {plugin.plugin_name} generated empty code, skipping"
                    )
                    continue

                # Determine output filename
                filename = self._get_output_filename(resource_type)
                output_path = output_dir / filename

                # Write to file
                with open(output_path, "w", encoding="utf-8") as f:
                    f.write(code)

                written_files.append(output_path)
                self.logger.info(f"✅ Wrote {output_path}")

            except Exception as e:
                self.logger.error(
                    f"Failed to generate code for {resource_type}: {e}",
                    exc_info=True
                )
                # Continue processing other resource types
                continue

        if written_files:
            self.logger.info(
                f"Successfully generated {len(written_files)} data plane files"
            )
        else:
            self.logger.warning("No data plane files were generated")

        return written_files


# Public API
__all__ = ["DataPlaneCodeGenerator"]
