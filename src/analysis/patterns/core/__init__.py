"""
Core Pattern Processing Module

Handles resource processing and graph building.

Public API:
    ResourceTypeHandler: Processes resource types and groupings
    GraphBuilder: Builds NetworkX graphs from Neo4j data

Issue #729: Removed unused RelationshipAggregator (Zero-BS compliance)
"""

from .graph_builder import GraphBuilder
from .resource_type_handler import ResourceTypeHandler

__all__ = [
    "GraphBuilder",
    "ResourceTypeHandler",
]
