"""
Data plane orchestrator for coordinating discovery across multiple resources.

This module provides orchestration capabilities for data plane discovery,
handling plugin lookup, discovery execution, error handling, and progress tracking
across multiple Azure resources.

Example:
    orchestrator = DataPlaneOrchestrator(skip_resource_types=["Microsoft.Sql/servers/databases"])
    result = await orchestrator.discover_all(resources, progress_callback=my_callback)
    print(f"Discovered {result.stats.total_items} items across {result.stats.resources_with_items} resources")
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from .plugins import DataPlaneItem, PluginRegistry

logger = logging.getLogger(__name__)


@dataclass
class DiscoveryError:
    """Represents an error encountered during data plane discovery."""

    resource_id: str
    resource_type: str
    error_type: str  # "permission", "not_found", "sdk_missing", "unexpected"
    message: str

    def __str__(self) -> str:
        """Human-readable error representation."""
        return f"[{self.error_type}] {self.resource_type} ({self.resource_id}): {self.message}"


@dataclass
class DiscoveryStats:
    """Statistics about data plane discovery operation."""

    resources_scanned: int = 0
    resources_with_items: int = 0
    total_items: int = 0
    items_by_type: Dict[str, int] = field(default_factory=dict)

    def add_items(self, items: List[DataPlaneItem]) -> None:
        """
        Add items to statistics.

        Args:
            items: List of discovered items to count
        """
        if items:
            self.resources_with_items += 1
            self.total_items += len(items)
            for item in items:
                item_type = item.item_type
                self.items_by_type[item_type] = self.items_by_type.get(item_type, 0) + 1

    def __str__(self) -> str:
        """Human-readable statistics representation."""
        lines = [
            f"Resources scanned: {self.resources_scanned}",
            f"Resources with items: {self.resources_with_items}",
            f"Total items: {self.total_items}",
        ]
        if self.items_by_type:
            lines.append("Items by type:")
            for item_type, count in sorted(self.items_by_type.items()):
                lines.append(f"  - {item_type}: {count}")
        return "\n".join(lines)


@dataclass
class DiscoveryResult:
    """Result of data plane discovery operation."""

    items_by_resource: Dict[str, List[DataPlaneItem]] = field(default_factory=dict)
    errors: List[DiscoveryError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    stats: DiscoveryStats = field(default_factory=DiscoveryStats)

    @property
    def total_items(self) -> int:
        """Total number of items discovered."""
        return sum(len(items) for items in self.items_by_resource.values())

    @property
    def total_errors(self) -> int:
        """Total number of errors encountered."""
        return len(self.errors)

    @property
    def has_errors(self) -> bool:
        """Whether any errors were encountered."""
        return len(self.errors) > 0

    def get_items_by_type(self, item_type: str) -> List[DataPlaneItem]:
        """
        Get all items of a specific type.

        Args:
            item_type: Type of items to retrieve (e.g., "secret", "blob")

        Returns:
            List of all items matching the specified type
        """
        items = []
        for resource_items in self.items_by_resource.values():
            items.extend(
                [item for item in resource_items if item.item_type == item_type]
            )
        return items

    def get_errors_by_type(self, error_type: str) -> List[DiscoveryError]:
        """
        Get all errors of a specific type.

        Args:
            error_type: Type of errors to retrieve (e.g., "permission", "sdk_missing")

        Returns:
            List of all errors matching the specified type
        """
        return [error for error in self.errors if error.error_type == error_type]


class DataPlaneOrchestrator:
    """
    Orchestrates data plane discovery across multiple resources.

    Handles plugin lookup, discovery execution, error handling,
    and progress tracking. Provides resilient discovery that continues
    even when individual resources fail.

    Example:
        orchestrator = DataPlaneOrchestrator(
            skip_resource_types=["Microsoft.Sql/servers/databases"]
        )
        result = await orchestrator.discover_all(resources, my_progress_callback)
        print(f"Found {result.stats.total_items} items")
    """

    def __init__(
        self,
        skip_resource_types: Optional[List[str]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """
        Initialize data plane orchestrator.

        Args:
            skip_resource_types: List of resource types to skip during discovery
            logger: Optional logger instance (creates new one if not provided)
        """
        self.skip_resource_types = set(skip_resource_types or [])
        self.logger = logger or logging.getLogger(__name__)
        self._plugin_registry = PluginRegistry

    def _should_skip_resource(self, resource: Dict[str, Any]) -> bool:
        """
        Check if resource should be skipped.

        Args:
            resource: Resource dictionary to check

        Returns:
            True if resource should be skipped, False otherwise
        """
        resource_type = resource.get("type", "")
        return resource_type in self.skip_resource_types

    def _log_progress(
        self,
        message: str,
        current: int,
        total: int,
        callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> None:
        """
        Log progress and invoke callback if provided.

        Args:
            message: Progress message
            current: Current progress value
            total: Total progress value
            callback: Optional progress callback function
        """
        self.logger.debug(f"{message} ({current}/{total})")
        if callback:
            try:
                callback(message, current, total)
            except Exception as e:
                self.logger.warning(f"Progress callback failed: {e}")

    def _create_error(
        self, resource: Dict[str, Any], error_type: str, message: str
    ) -> DiscoveryError:
        """
        Create a DiscoveryError from resource and error details.

        Args:
            resource: Resource dictionary
            error_type: Type of error (permission, not_found, sdk_missing, unexpected)
            message: Error message

        Returns:
            DiscoveryError instance
        """
        return DiscoveryError(
            resource_id=resource.get("id", "unknown"),
            resource_type=resource.get("type", "unknown"),
            error_type=error_type,
            message=message,
        )

    async def discover_all(
        self,
        resources: List[Dict[str, Any]],
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> DiscoveryResult:
        """
        Discover data plane items for all resources.

        Iterates through all resources, finds appropriate plugins, and executes
        discovery. Handles errors gracefully and continues processing remaining
        resources even when individual discoveries fail.

        Args:
            resources: List of resource dictionaries from Neo4j graph
            progress_callback: Optional callback for progress updates
                Signature: (message: str, current: int, total: int) -> None

        Returns:
            DiscoveryResult containing discovered items, errors, warnings, and stats

        Example:
            >>> def progress(msg, cur, tot):
            ...     print(f"{msg}: {cur}/{tot}")
            >>> result = await orchestrator.discover_all(resources, progress)
            >>> print(f"Found {result.stats.total_items} items")
        """
        result = DiscoveryResult()
        total_resources = len(resources)

        self.logger.info(
            f"Starting data plane discovery for {total_resources} resources"
        )
        self._log_progress(
            "Initializing discovery", 0, total_resources, progress_callback
        )

        for idx, resource in enumerate(resources, start=1):
            # Skip None resources
            if resource is None:
                self.logger.warning(f"Skipping None resource at index {idx}")
                result.stats.resources_scanned += 1
                result.warnings.append(f"Skipped None resource at index {idx}")
                continue

            resource_id = resource.get("id", "unknown")
            resource_type = resource.get("type", "unknown")
            resource_name = resource.get("name", "unknown")

            # Update progress
            self._log_progress(
                f"Processing {resource_name}",
                idx,
                total_resources,
                progress_callback,
            )

            # Increment scanned count
            result.stats.resources_scanned += 1

            # Check if resource should be skipped
            if self._should_skip_resource(resource):
                self.logger.debug(
                    f"Skipping resource {resource_name} (type: {resource_type})"
                )
                result.warnings.append(
                    f"Skipped {resource_type} resource: {resource_name}"
                )
                continue

            # Find plugin for resource
            try:
                plugin = self._plugin_registry.get_plugin_for_resource(resource)
            except Exception as e:
                self.logger.error(
                    f"Error getting plugin for {resource_name}: {e}", exc_info=True
                )
                result.errors.append(
                    self._create_error(
                        resource, "unexpected", f"Plugin lookup failed: {e}"
                    )
                )
                continue

            if not plugin:
                # No plugin found - this is expected for many resource types
                self.logger.info(
                    f"No data plane plugin available for {resource_type}: {resource_name}"
                )
                continue

            # Execute discovery
            try:
                self.logger.debug(
                    f"Discovering data plane items for {resource_name} using {plugin.plugin_name}"
                )
                items = plugin.discover(resource)

                if items:
                    result.items_by_resource[resource_id] = items
                    result.stats.add_items(items)
                    self.logger.info(
                        f"Discovered {len(items)} items for {resource_name}"
                    )
                else:
                    self.logger.debug(f"No items found for {resource_name}")

            except ImportError as e:
                # SDK not installed
                error_msg = f"Required SDK not installed: {e}"
                self.logger.warning(f"{resource_name}: {error_msg}")
                result.errors.append(
                    self._create_error(resource, "sdk_missing", error_msg)
                )
                result.warnings.append(
                    f"Skipping {resource_name} - missing SDK dependencies"
                )

            except Exception as e:
                # Try to determine error type from exception
                error_type = "unexpected"
                error_msg = str(e)

                # Check for HTTP response errors
                if hasattr(e, "status_code"):
                    status_code = getattr(e, "status_code", None)
                    if status_code == 403:
                        error_type = "permission"
                        error_msg = f"Permission denied: {error_msg}"
                        self.logger.warning(f"{resource_name}: {error_msg}")
                        result.warnings.append(f"Permission denied for {resource_name}")
                    elif status_code == 404:
                        error_type = "not_found"
                        error_msg = f"Resource not found: {error_msg}"
                        self.logger.warning(f"{resource_name}: {error_msg}")
                        result.warnings.append(f"Resource not found: {resource_name}")
                    else:
                        self.logger.error(
                            f"HTTP error {status_code} for {resource_name}: {error_msg}",
                            exc_info=True,
                        )
                else:
                    self.logger.error(
                        f"Unexpected error discovering {resource_name}: {error_msg}",
                        exc_info=True,
                    )

                result.errors.append(
                    self._create_error(resource, error_type, error_msg)
                )

        # Final progress update
        self._log_progress(
            "Discovery complete",
            total_resources,
            total_resources,
            progress_callback,
        )

        # Log summary
        self.logger.info(
            f"Data plane discovery complete: {result.stats.resources_scanned} resources scanned, "
            f"{result.stats.resources_with_items} with items, "
            f"{result.stats.total_items} total items, "
            f"{len(result.errors)} errors"
        )

        return result


# Public API
__all__ = [
    "DataPlaneOrchestrator",
    "DiscoveryError",
    "DiscoveryResult",
    "DiscoveryStats",
]
