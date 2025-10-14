"""
Base plugin infrastructure for data plane replication.

This module provides the abstract base class for implementing data plane
replication plugins. Data plane plugins handle the discovery and replication
of resource-specific data that isn't part of the control plane (e.g., Key Vault
secrets, Storage blobs, SQL data).

Each plugin is responsible for:
1. Discovering data plane items for a specific Azure resource type
2. Generating code to replicate those items (e.g., local_file resources)
3. Executing replication from source to target resources
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DataPlaneItem:
    """Represents a single data plane item to be replicated."""

    name: str
    item_type: str  # e.g., "secret", "blob", "file_share"
    properties: Dict[str, Any]
    source_resource_id: str
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ReplicationResult:
    """Result of a data plane replication operation."""

    success: bool
    items_discovered: int
    items_replicated: int
    errors: List[str]
    warnings: List[str]


class DataPlanePlugin(ABC):
    """
    Abstract base class for data plane replication plugins.

    Plugins extend IaC generation by discovering and replicating data plane
    resources that are not part of the Azure Resource Manager control plane.

    Example:
        class KeyVaultPlugin(DataPlanePlugin):
            @property
            def supported_resource_type(self) -> str:
                return "Microsoft.KeyVault/vaults"

            def discover(self, resource: Dict[str, Any]) -> List[Dict[str, Any]]:
                # Discover secrets in the Key Vault
                ...
    """

    def __init__(self) -> None:
        """Initialize the data plane plugin."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """
        Discover data plane items for a resource.

        This method should connect to the Azure resource and enumerate
        all data plane items that need to be replicated.

        Args:
            resource: Resource dictionary from Neo4j graph containing:
                - id: Azure resource ID
                - type: Azure resource type
                - properties: Resource properties
                - name: Resource name

        Returns:
            List of DataPlaneItem objects representing discovered items

        Raises:
            NotImplementedError: If not implemented by subclass
            ValueError: If resource is invalid or missing required properties
            Exception: For Azure SDK errors during discovery
        """
        pass

    @abstractmethod
    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """
        Generate IaC code to replicate data plane items.

        This method should generate code that will create local files or
        other resources to preserve the data plane items during IaC deployment.

        Args:
            items: List of data plane items to generate code for
            output_format: IaC format ("terraform", "bicep", "arm")

        Returns:
            String containing IaC code to replicate the items

        Raises:
            NotImplementedError: If not implemented by subclass
            ValueError: If output_format is unsupported
        """
        pass

    @abstractmethod
    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """
        Replicate data from source to target resource.

        This method performs the actual data replication operation,
        copying data plane items from the source resource to the target.

        Args:
            source_resource: Source resource dictionary with:
                - id: Azure resource ID
                - type: Azure resource type
                - properties: Resource properties
            target_resource: Target resource dictionary with same structure

        Returns:
            ReplicationResult with operation status and statistics

        Raises:
            NotImplementedError: If not implemented by subclass
            ValueError: If resources are invalid or incompatible
            Exception: For Azure SDK errors during replication
        """
        pass

    @property
    @abstractmethod
    def supported_resource_type(self) -> str:
        """
        Azure resource type this plugin supports.

        Returns:
            Azure resource type string (e.g., "Microsoft.KeyVault/vaults")

        Raises:
            NotImplementedError: If not implemented by subclass
        """
        pass

    @property
    def plugin_name(self) -> str:
        """
        Human-readable plugin name.

        Returns:
            Plugin name derived from class name
        """
        return self.__class__.__name__

    def validate_resource(self, resource: Dict[str, Any]) -> bool:
        """
        Validate that a resource is compatible with this plugin.

        Args:
            resource: Resource dictionary to validate

        Returns:
            True if resource is valid and supported by this plugin
        """
        if not resource:
            self.logger.warning("Resource is None or empty")
            return False

        resource_type = resource.get("type", "")
        if resource_type != self.supported_resource_type:
            self.logger.warning(
                f"Resource type '{resource_type}' does not match "
                f"supported type '{self.supported_resource_type}'"
            )
            return False

        if not resource.get("id"):
            self.logger.warning("Resource missing required 'id' field")
            return False

        return True

    def supports_output_format(self, output_format: str) -> bool:
        """
        Check if plugin supports a specific IaC output format.

        Args:
            output_format: IaC format to check ("terraform", "bicep", "arm")

        Returns:
            True if format is supported (default: only Terraform)
        """
        # Default implementation supports Terraform
        return output_format.lower() == "terraform"
