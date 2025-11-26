"""
Resource Processing Module

This module provides robust, resumable, and parallel processing of Azure resources
with improved error handling, progress tracking, and database operations.
It uses the dual-graph architecture where every resource is stored as both
an Original node and an Abstracted node.

Public Interface:
    ProcessingStats - Statistics dataclass for processing operations
    ResourceProcessor - Main orchestrator for resource processing
    NodeManager - Handles dual-graph node operations
    RelationshipEmitter - Creates Neo4j relationships
    BatchProcessor - Handles retry queue and worker scheduling
    LLMIntegration - Handles LLM description generation
    ResourceState - Manages resource state checking
    DatabaseOperations - Backward compatibility alias for NodeManager
    serialize_value - Safe value serialization for Neo4j
    validate_resource_data - Input validation
    extract_identity_fields - Identity field extraction
    create_resource_processor - Factory function
"""

# Core classes
from .batch_processor import BatchProcessor, BatchResult
from .llm_integration import LLMIntegration
from .node_manager import DatabaseOperations, NodeManager
from .processor import ResourceProcessor, create_resource_processor
from .relationship_emitter import RelationshipEmitter

# Utilities
from .serialization import serialize_value
from .state import ResourceState
from .stats import ProcessingStats
from .validation import (
    GLOBAL_RESOURCE_TYPES,
    extract_identity_fields,
    get_required_fields,
    validate_resource_data,
)

__all__ = [
    "GLOBAL_RESOURCE_TYPES",
    "BatchProcessor",
    "BatchResult",
    "DatabaseOperations",
    "LLMIntegration",
    "NodeManager",
    "ProcessingStats",
    "RelationshipEmitter",
    "ResourceProcessor",
    "ResourceState",
    "create_resource_processor",
    "extract_identity_fields",
    "get_required_fields",
    "serialize_value",
    "validate_resource_data",
]
