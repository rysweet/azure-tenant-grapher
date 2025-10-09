"""Graph comparison engine for deployment validation.

This module provides functionality to compare two Neo4j graphs (source and target)
and generate detailed comparison results including resource counts, type distributions,
and similarity scores.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Set

logger = logging.getLogger(__name__)


@dataclass
class ComparisonResult:
    """Result of graph comparison between source and target deployments.

    Attributes:
        source_resource_count: Total number of resources in source graph
        target_resource_count: Total number of resources in target graph
        resource_type_counts: Dictionary mapping resource types to count dictionaries
        missing_resources: List of resource descriptions missing in target
        extra_resources: List of resource descriptions extra in target
        similarity_score: Percentage similarity between graphs (0-100)
    """

    source_resource_count: int
    target_resource_count: int
    resource_type_counts: Dict[str, Dict[str, int]]
    missing_resources: List[str]
    extra_resources: List[str]
    similarity_score: float


def compare_graphs(
    source_resources: List[Dict[str, Any]], target_resources: List[Dict[str, Any]]
) -> ComparisonResult:
    """Compare two resource graphs and return detailed comparison results.

    This function performs a count-based comparison of resources by type,
    identifying missing and extra resources, and calculating an overall
    similarity score.

    Args:
        source_resources: List of resource dictionaries from source graph
        target_resources: List of resource dictionaries from target graph

    Returns:
        ComparisonResult containing detailed comparison metrics

    Example:
        >>> source = [{"id": "vm1", "type": "Microsoft.Compute/virtualMachines"}]
        >>> target = [{"id": "vm1", "type": "Microsoft.Compute/virtualMachines"}]
        >>> result = compare_graphs(source, target)
        >>> assert result.similarity_score == 100.0
    """
    logger.info(
        f"Comparing graphs: {len(source_resources)} source, {len(target_resources)} target"
    )

    # Build resource type counts for source
    source_types: Dict[str, int] = {}
    for resource in source_resources:
        rtype = resource.get("type", "unknown")
        source_types[rtype] = source_types.get(rtype, 0) + 1

    # Build resource type counts for target
    target_types: Dict[str, int] = {}
    for resource in target_resources:
        rtype = resource.get("type", "unknown")
        target_types[rtype] = target_types.get(rtype, 0) + 1

    # Combine all types for comprehensive comparison
    all_types = set(source_types.keys()) | set(target_types.keys())
    type_counts: Dict[str, Dict[str, int]] = {}

    for rtype in all_types:
        type_counts[rtype] = {
            "source": source_types.get(rtype, 0),
            "target": target_types.get(rtype, 0),
        }

    # Identify missing and extra resources by type
    missing: List[str] = []
    extra: List[str] = []

    for rtype, counts in type_counts.items():
        diff = counts["source"] - counts["target"]
        if diff > 0:
            missing.append(f"{rtype} ({diff} missing)")
        elif diff < 0:
            extra.append(f"{rtype} ({abs(diff)} extra)")

    # Calculate similarity score based on resource counts
    source_count = len(source_resources)
    target_count = len(target_resources)

    if source_count == 0 and target_count == 0:
        similarity = 100.0
    elif source_count == 0 or target_count == 0:
        similarity = 0.0
    else:
        # Simple count-based similarity
        similarity = (min(source_count, target_count) / max(source_count, target_count)) * 100

    logger.info(f"Comparison complete: {similarity:.1f}% similarity")

    return ComparisonResult(
        source_resource_count=source_count,
        target_resource_count=target_count,
        resource_type_counts=type_counts,
        missing_resources=missing,
        extra_resources=extra,
        similarity_score=similarity,
    )


def compare_filtered_graphs(
    source_resources: List[Dict[str, Any]],
    target_resources: List[Dict[str, Any]],
    source_filter: str | None = None,
    target_filter: str | None = None,
) -> ComparisonResult:
    """Compare graphs with optional filtering applied.

    This function applies filters to both source and target resources before
    performing the comparison. Filters are in the format "key=value".

    Args:
        source_resources: List of resource dictionaries from source graph
        target_resources: List of resource dictionaries from target graph
        source_filter: Optional filter string for source (e.g., "resourceGroup=RG1")
        target_filter: Optional filter string for target (e.g., "resourceGroup=RG2")

    Returns:
        ComparisonResult containing detailed comparison metrics

    Example:
        >>> source = [{"id": "vm1", "type": "VM", "resourceGroup": "RG1"}]
        >>> target = [{"id": "vm2", "type": "VM", "resourceGroup": "RG2"}]
        >>> result = compare_filtered_graphs(source, target, "resourceGroup=RG1", "resourceGroup=RG2")
    """

    def apply_filter(resources: List[Dict[str, Any]], filter_str: str | None) -> List[Dict[str, Any]]:
        """Apply filter string to resources."""
        if not filter_str:
            return resources

        try:
            key, value = filter_str.split("=", 1)
            filtered = [r for r in resources if r.get(key) == value]
            logger.info(f"Filter '{filter_str}' matched {len(filtered)}/{len(resources)} resources")
            return filtered
        except ValueError:
            logger.warning(f"Invalid filter format: {filter_str}. Expected key=value")
            return resources

    # Apply filters
    filtered_source = apply_filter(source_resources, source_filter)
    filtered_target = apply_filter(target_resources, target_filter)

    # Perform comparison on filtered resources
    return compare_graphs(filtered_source, filtered_target)
