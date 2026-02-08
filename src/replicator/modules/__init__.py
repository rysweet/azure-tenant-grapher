"""
Replicator brick modules.

This package contains independent, composable bricks for tenant replication.
Each brick is self-contained with clear public contracts.
"""

from .configuration_similarity import ConfigurationSimilarity
from .graph_structure_analyzer import GraphStructureAnalyzer
from .instance_selector import InstanceSelector
from .orphaned_resource_manager import OrphanedResourceManager
from .pattern_instance_finder import PatternInstanceFinder
from .resource_type_resolver import ResourceTypeResolver
from .target_graph_builder import TargetGraphBuilder

__all__ = [
    "ConfigurationSimilarity",
    "GraphStructureAnalyzer",
    "InstanceSelector",
    "OrphanedResourceManager",
    "PatternInstanceFinder",
    "ResourceTypeResolver",
    "TargetGraphBuilder",
]
