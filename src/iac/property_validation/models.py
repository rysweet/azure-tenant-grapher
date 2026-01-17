"""Data models for property validation.

This module defines the core data structures used throughout the property
validation system.

Philosophy:
- Immutable dataclasses for data integrity
- Clear type hints for self-documentation
- Simple enums for classification
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Criticality(Enum):
    """Property criticality levels."""

    CRITICAL = "critical"  # Blocks deployment, no defaults
    HIGH = "high"  # Security/compliance properties
    MEDIUM = "medium"  # Operational properties
    LOW = "low"  # Optional features


@dataclass(frozen=True)
class PropertyDefinition:
    """Definition of a Terraform property from schema."""

    name: str
    required: bool
    has_default: bool
    property_type: str
    description: str = ""


@dataclass(frozen=True)
class PropertyGap:
    """A missing property identified in generated IaC."""

    property_name: str
    criticality: Criticality
    reason: str
    suggested_value: Optional[str] = None


@dataclass(frozen=True)
class CoverageMetrics:
    """Coverage analysis results."""

    total_properties: int
    covered_properties: int
    missing_properties: int
    coverage_percentage: float
    gaps: List[PropertyGap] = field(default_factory=list)
    critical_gaps: int = 0
    high_priority_gaps: int = 0
    medium_priority_gaps: int = 0
    low_priority_gaps: int = 0


@dataclass
class PropertyUsage:
    """Single instance of property usage in handler code.

    Attributes:
        property_name: Name of the property (e.g., "account_tier")
        usage_type: Type of usage - "read", "write", or "both"
        terraform_key: Terraform config key (e.g., "account_tier")
        azure_key: Azure property key (e.g., "accountTier")
        line_number: Line number where property is used
        code_snippet: Actual code snippet showing usage
    """

    property_name: str
    usage_type: str  # "read", "write", or "both"
    terraform_key: str
    azure_key: str
    line_number: int
    code_snippet: str


@dataclass
class HandlerPropertyUsage:
    """Complete analysis result for a handler file.

    Attributes:
        handler_file: Path to handler file analyzed
        handler_class: Name of handler class
        handled_types: Set of Azure resource types handled
        terraform_types: Set of Terraform resource types emitted
        properties: List of all property usages found
        terraform_writes: Set of Terraform config keys written
        azure_reads: Set of Azure property keys read
        bidirectional_mappings: Dict mapping Terraform key to Azure key
    """

    handler_file: str
    handler_class: str
    handled_types: set = field(default_factory=set)
    terraform_types: set = field(default_factory=set)
    properties: List[PropertyUsage] = field(default_factory=list)
    terraform_writes: set = field(default_factory=set)
    azure_reads: set = field(default_factory=set)
    bidirectional_mappings: Dict[str, str] = field(default_factory=dict)


__all__ = [
    "Criticality",
    "PropertyDefinition",
    "PropertyGap",
    "CoverageMetrics",
    "PropertyUsage",
    "HandlerPropertyUsage",
]
