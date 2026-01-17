"""
Core Pattern Processing Module

Handles resource processing, relationship aggregation, and graph building.

Public API:
    ResourceTypeHandler: Processes resource types and groupings
    RelationshipAggregator: Aggregates relationships between resources
    GraphBuilder: Builds NetworkX graphs from Neo4j data
"""

from .graph_builder import GraphBuilder
from .relationship_aggregator import RelationshipAggregator
from .resource_type_handler import ResourceTypeHandler

__all__ = [
    "GraphBuilder",
    "RelationshipAggregator",
    "ResourceTypeHandler",
]
