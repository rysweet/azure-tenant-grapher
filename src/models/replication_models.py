"""
Data models for architecture-based tenant replication.

This module provides strongly-typed dataclasses to replace Dict[str, Any]
throughout the replication system, improving type safety and documentation.
"""

from dataclasses import dataclass, field
from typing import List, Set, Dict, Any, Optional
from enum import Enum


# =============================================================================
# CORE DOMAIN MODELS
# =============================================================================

@dataclass(frozen=True)
class ResourceIdentifier:
    """Immutable resource identifier (Azure resource ID)."""
    id: str
    type: str  # Simplified type (e.g., "virtualMachines")
    name: str

    def __post_init__(self):
        if not self.id:
            raise ValueError("Resource ID cannot be empty")


@dataclass
class PatternInstance:
    """Connected group of resources forming an architectural pattern instance."""
    pattern_name: str
    resources: List[ResourceIdentifier]
    resource_group_id: Optional[str] = None

    @property
    def resource_types(self) -> Set[str]:
        """Get unique resource types in this instance."""
        return {r.type for r in self.resources}

    @property
    def size(self) -> int:
        """Get number of resources in instance."""
        return len(self.resources)


@dataclass
class ArchitecturalPattern:
    """Detected architectural pattern with matched resources."""
    name: str
    matched_resources: Set[str]  # Resource types in pattern
    completeness: float  # 0.0-1.0
    source_instances: int

    def __post_init__(self):
        if not 0.0 <= self.completeness <= 1.0:
            raise ValueError(f"Completeness must be 0-1, got {self.completeness}")


@dataclass
class DetectedPatterns:
    """Collection of detected patterns with lookup methods."""
    patterns: Dict[str, ArchitecturalPattern]

    def get_pattern_types(self) -> Set[str]:
        """Get all resource types covered by patterns."""
        types = set()
        for pattern in self.patterns.values():
            types.update(pattern.matched_resources)
        return types

    def get_patterns_with_type(self, resource_type: str) -> List[str]:
        """Get pattern names containing a resource type."""
        return [
            name for name, pattern in self.patterns.items()
            if resource_type in pattern.matched_resources
        ]


@dataclass
class ResourceTypeCounts:
    """Count of resources by type in source tenant."""
    counts: Dict[str, int]

    @property
    def total_types(self) -> int:
        return len(self.counts)

    @property
    def total_resources(self) -> int:
        return sum(self.counts.values())

    def get_orphaned_types(self, pattern_types: Set[str]) -> Set[str]:
        """Compute resource types not covered by any pattern."""
        return set(self.counts.keys()) - pattern_types


# =============================================================================
# CONFIGURATION MODELS
# =============================================================================

@dataclass(frozen=True)
class ConfigurationFingerprint:
    """Immutable configuration signature for similarity comparison."""
    location: str
    sku: str
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class CoherenceThreshold:
    """Configuration coherence parameters."""
    threshold: float = 0.5

    def __post_init__(self):
        if not 0.0 <= self.threshold <= 1.0:
            raise ValueError(f"Threshold must be 0-1, got {self.threshold}")


# =============================================================================
# SELECTION MODELS
# =============================================================================

class SelectionMode(Enum):
    """Selection strategy modes."""
    PROPORTIONAL_RANDOM = "proportional_random"
    PROPORTIONAL_SPECTRAL = "proportional_spectral"
    GREEDY_SPECTRAL = "greedy_spectral"


@dataclass
class SelectionParameters:
    """Parameters controlling instance selection behavior."""
    target_instance_count: Optional[int] = None
    include_orphaned: bool = True
    use_architecture_distribution: bool = True
    use_configuration_coherence: bool = True
    use_spectral_guidance: bool = True
    spectral_weight: float = 0.4
    node_coverage_weight: Optional[float] = None
    max_config_samples: int = 100
    sampling_strategy: str = "coverage"

    def __post_init__(self):
        if self.spectral_weight < 0.0 or self.spectral_weight > 1.0:
            raise ValueError(f"spectral_weight must be 0-1, got {self.spectral_weight}")

        if self.node_coverage_weight is not None:
            if self.node_coverage_weight < 0.0 or self.node_coverage_weight > 1.0:
                raise ValueError(f"node_coverage_weight must be 0-1, got {self.node_coverage_weight}")


@dataclass
class ScoredInstance:
    """Instance with computed selection scores."""
    instance: PatternInstance
    hybrid_score: float
    distribution_adherence: float
    spectral_contribution: float

    @property
    def is_structural_contributor(self) -> bool:
        """Check if instance adds new structural edges."""
        return self.spectral_contribution < 1.0


@dataclass
class PatternTargets:
    """Target instance counts per pattern from proportional allocation."""
    targets: Dict[str, int]

    @property
    def total_target(self) -> int:
        return sum(self.targets.values())

    def get_target(self, pattern_name: str) -> int:
        """Get target count for pattern (0 if not present)."""
        return self.targets.get(pattern_name, 0)


# =============================================================================
# RESULT MODELS
# =============================================================================

@dataclass
class ReplicationPlan:
    """Complete replication plan with instances and metadata."""
    selected_instances: List[PatternInstance]
    spectral_history: List[float]
    distribution_metadata: Optional[Dict[str, Any]]

    def group_by_pattern(self) -> Dict[str, List[PatternInstance]]:
        """Group instances by pattern name."""
        grouped = {}
        for instance in self.selected_instances:
            if instance.pattern_name not in grouped:
                grouped[instance.pattern_name] = []
            grouped[instance.pattern_name].append(instance)
        return grouped

    @property
    def total_instances(self) -> int:
        return len(self.selected_instances)

    @property
    def final_spectral_distance(self) -> Optional[float]:
        """Get final spectral distance (if available)."""
        return self.spectral_history[-1] if self.spectral_history else None


@dataclass
class OrphanedAnalysis:
    """Analysis of orphaned nodes in source and target graphs."""
    source_orphaned: Set[str]
    target_orphaned: Set[str]
    missing_in_target: Set[str]
    suggested_patterns: List[Dict[str, Any]]  # TODO: Type this properly

    @property
    def source_orphaned_count(self) -> int:
        return len(self.source_orphaned)

    @property
    def target_orphaned_count(self) -> int:
        return len(self.target_orphaned)

    @property
    def missing_count(self) -> int:
        return len(self.missing_in_target)


@dataclass
class AnalysisSummary:
    """Summary of source tenant analysis."""
    total_relationships: int
    unique_patterns: int
    resource_types: int
    pattern_graph_edges: int
    detected_patterns: int
    total_pattern_resources: int
    configuration_coherence_enabled: bool
