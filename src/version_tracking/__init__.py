"""Version tracking for Azure Tenant Grapher graph database.

This module provides version detection, metadata management, and rebuild services
for the Neo4j graph database used by Azure Tenant Grapher.

Includes hash-based tracking to detect code changes even when version number
is not updated.

Public API:
    VersionDetector: Detects version mismatches between semaphore and metadata
    GraphMetadataService: CRUD operations for graph metadata
    RebuildService: Orchestrates graph rebuild operations
    HashTracker: Calculate and validate file hashes for construction files
    calculate_construction_hash: Calculate hash of all tracked files
    validate_hash: Validate stored hash against current files
"""

from .detector import VersionDetector
from .hash_tracker import (
    HashTracker,
    HashValidationResult,
    calculate_construction_hash,
    validate_hash,
)
from .metadata import GraphMetadataService
from .rebuild import RebuildService

__all__ = [
    "GraphMetadataService",
    "HashTracker",
    "HashValidationResult",
    "RebuildService",
    "VersionDetector",
    "calculate_construction_hash",
    "validate_hash",
]
