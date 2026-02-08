"""
Resource Type Resolver Brick

Pure utility brick for resolving Azure resource types to standardized names.
No dependencies, stateless operations.

Philosophy:
- Single Responsibility: Resource type resolution
- Self-contained: No external state
- Regeneratable: Pure function logic
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

from typing import Optional

from ...analysis.patterns.core.resource_type_handler import ResourceTypeHandler


class ResourceTypeResolver:
    """
    Resolves Azure resource types to standardized names.

    This brick provides a stateless interface for resource type resolution,
    wrapping the ResourceTypeHandler for use in the replicator.

    Public Contract:
        - resolve_type(labels, azure_type) -> str
    """

    @staticmethod
    def resolve_type(labels: list[str], azure_type: Optional[str]) -> str:
        """
        Resolve Azure resource type to standardized name.

        Args:
            labels: Node labels from Neo4j (e.g., ["Resource", "VirtualMachine"])
            azure_type: Azure resource type string (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            Standardized resource type name (e.g., "virtualMachines")

        Examples:
            >>> ResourceTypeResolver.resolve_type(["Resource"], "Microsoft.Compute/virtualMachines")
            'virtualMachines'
            >>> ResourceTypeResolver.resolve_type(["Resource", "VirtualMachine"], None)
            'VirtualMachine'
            >>> ResourceTypeResolver.resolve_type([], None)
            'Unknown'
        """
        return ResourceTypeHandler.get_resource_type_name(labels, azure_type)


__all__ = ["ResourceTypeResolver"]
