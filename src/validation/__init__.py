"""Validation module for deployment comparison and reporting.

This module provides functionality to compare source and target deployments
by analyzing their Neo4j graph representations and generating detailed reports.

Public API:
    - compare_graphs: Compare two resource lists
    - compare_filtered_graphs: Compare with optional filtering
    - generate_markdown_report: Create markdown validation report
    - generate_json_report: Create JSON validation report
    - ComparisonResult: Dataclass containing comparison results
    - AddressSpaceValidator: Validate VNet address space overlaps (Issue #334)
    - AddressSpaceConflict: Dataclass for conflict information
    - ValidationResult: Dataclass for validation results
    - validate_address_spaces: Convenience function for validation
    - NameConflictValidator: Validate Azure resource name conflicts (GAP-015)
    - NameConflict: Dataclass for name conflict information
    - NameValidationResult: Dataclass for name validation results
    - ResourceFidelityCalculator: Resource-level fidelity validation (Issue #894)
    - ResourceFidelityMetrics: Resource fidelity metrics dataclass
    - ResourceClassification: Resource-level classification dataclass
    - ResourceStatus: Resource status enum
    - RedactionLevel: Security redaction levels enum
    - PropertyComparison: Property-level comparison dataclass
    - FidelityResult: Complete fidelity validation result
"""

from .address_space_validator import (
    AddressSpaceConflict,
    AddressSpaceValidator,
    ValidationResult,
    validate_address_spaces,
)
from .comparator import ComparisonResult, compare_filtered_graphs, compare_graphs
from .name_conflict_validator import (
    NameConflict,
    NameConflictValidator,
    NameValidationResult,
)
from .report import generate_json_report, generate_markdown_report
from .resource_fidelity_calculator import (
    FidelityResult,
    PropertyComparison,
    RedactionLevel,
    ResourceClassification,
    ResourceFidelityCalculator,
    ResourceFidelityMetrics,
    ResourceStatus,
)

__all__ = [
    "AddressSpaceConflict",
    "AddressSpaceValidator",
    "ComparisonResult",
    "FidelityResult",
    "NameConflict",
    "NameConflictValidator",
    "NameValidationResult",
    "PropertyComparison",
    "RedactionLevel",
    "ResourceClassification",
    "ResourceFidelityCalculator",
    "ResourceFidelityMetrics",
    "ResourceStatus",
    "ValidationResult",
    "compare_filtered_graphs",
    "compare_graphs",
    "generate_json_report",
    "generate_markdown_report",
    "validate_address_spaces",
]
