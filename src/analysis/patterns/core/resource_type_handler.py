"""
Resource Type Handler Module

Processes resource types and handles resource type name extraction.
Extracted from architectural_pattern_analyzer.py god object (Issue #714).

Philosophy:
- Single Responsibility: Resource type name standardization
- Self-contained: Pure function logic, no external dependencies
- Regeneratable: Can be rebuilt from specification
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

from typing import List, Optional


class ResourceTypeHandler:
    """
    Handles resource type name extraction and standardization.

    Converts Azure resource labels and types into standardized names
    for pattern analysis.
    """

    @staticmethod
    def get_resource_type_name(labels: List[str], azure_type: Optional[str]) -> str:
        """
        Determine standardized resource type name from labels and Azure type.

        Args:
            labels: Node labels from Neo4j
            azure_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            Standardized resource type name

        Examples:
            >>> handler = ResourceTypeHandler()
            >>> handler.get_resource_type_name(["Resource"], "Microsoft.Compute/virtualMachines")
            'virtualMachines'
            >>> handler.get_resource_type_name(["Resource", "VirtualMachine"], None)
            'VirtualMachine'
        """
        if not labels:
            return "Unknown"

        # Check if it's a Resource node with Azure type
        if "Resource" in labels and azure_type:
            # Extract resource type from Azure resource type
            # e.g., "Microsoft.Compute/virtualMachines" -> "virtualMachines"
            parts = azure_type.split("/")
            if len(parts) >= 2:
                return parts[-1]  # Last part is the resource type
            return parts[0]

        # For non-Resource nodes, use the most specific label
        # Filter out generic labels like 'Original'
        filtered_labels = [
            label for label in labels if label not in ["Original", "Resource"]
        ]
        if filtered_labels:
            return filtered_labels[0]

        return labels[0] if labels else "Unknown"


__all__ = ["ResourceTypeHandler"]
