"""
Constants for Architecture-Based Tenant Replication.

This module contains all configuration constants, magic numbers, and default values
used in the architecture-based replication system.
"""

from dataclasses import dataclass
from typing import Dict


# Configuration Coherence Constants
DEFAULT_COHERENCE_THRESHOLD = 0.5
"""Default minimum similarity score for resources to be in the same instance (0.0-1.0)"""

CONFIGURATION_SIMILARITY_WEIGHTS: Dict[str, float] = {
    "location": 0.5,
    "sku_tier": 0.3,
    "tags": 0.2,
}
"""Weights for different configuration attributes when computing similarity"""


# Spectral Distance and Selection Constants
DEFAULT_SPECTRAL_WEIGHT = 0.4
"""Default weight for spectral component in hybrid scoring (0.0-1.0)
- 0.0 = pure distribution adherence
- 0.4 = recommended balance (60% distribution, 40% spectral)
- 1.0 = pure spectral distance
"""

NODE_COVERAGE_WEIGHT_RANDOM_CHOICES = [0.0, 1.0]
"""Choices for random node coverage weight selection when not specified
- 0.0 = only spectral distance (original behavior)
- 1.0 = only node coverage (greedy node selection)
"""

SPECTRAL_PENALTY_HIGH = 1.0
"""High penalty value for spectral contribution when edges are missing"""

DISTRIBUTION_ADHERENCE_ZERO = 0.0
"""Zero distribution adherence value"""


# Sampling Constants
DEFAULT_MAX_CONFIG_SAMPLES = 100
"""Default maximum number of representative configurations to sample per pattern"""

DEFAULT_MAX_SAMPLES_SMALL = 10
"""Default maximum samples for small sample sets"""

MIN_CLUSTER_SIZE = 2
"""Minimum number of resources required to form a cluster"""

PROGRESS_LOG_FREQUENCY = 10
"""Log progress every N iterations (for iterations < 10, log all)"""


# Resource Type Constants
ORPHANED_PATTERN_NAME = "Orphaned Resources"
"""Name used for the synthetic pattern containing orphaned resources"""

ORPHANED_PATTERN_BUDGET_FRACTION = 0.25
"""Fraction of instance budget allocated to orphaned resources (25%)"""


@dataclass(frozen=True)
class ReplicationDefaults:
    """Default parameter values for replication plan generation."""
    
    include_orphaned_node_patterns: bool = True
    """Include instances containing orphaned node resource types"""
    
    use_architecture_distribution: bool = True
    """Use distribution-based proportional allocation"""
    
    use_configuration_coherence: bool = True
    """Cluster resources by configuration similarity during instance fetching"""
    
    use_spectral_guidance: bool = True
    """Use hybrid scoring (distribution + spectral) for selection"""
    
    spectral_weight: float = DEFAULT_SPECTRAL_WEIGHT
    """Weight for spectral component in hybrid score"""
    
    max_config_samples: int = DEFAULT_MAX_CONFIG_SAMPLES
    """Maximum number of representative configurations to sample per pattern"""
    
    sampling_strategy: str = "coverage"
    """Strategy for selecting configuration samples ('coverage' or 'diversity')"""
    
    coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD
    """Minimum similarity score for resources to be in same instance"""
    
    include_colocated_orphaned_resources: bool = True
    """Include orphaned resource types that co-locate in same ResourceGroup as pattern resources"""


# Export all constants
__all__ = [
    "DEFAULT_COHERENCE_THRESHOLD",
    "CONFIGURATION_SIMILARITY_WEIGHTS",
    "DEFAULT_SPECTRAL_WEIGHT",
    "NODE_COVERAGE_WEIGHT_RANDOM_CHOICES",
    "SPECTRAL_PENALTY_HIGH",
    "DISTRIBUTION_ADHERENCE_ZERO",
    "DEFAULT_MAX_CONFIG_SAMPLES",
    "DEFAULT_MAX_SAMPLES_SMALL",
    "MIN_CLUSTER_SIZE",
    "PROGRESS_LOG_FREQUENCY",
    "ORPHANED_PATTERN_NAME",
    "ORPHANED_PATTERN_BUDGET_FRACTION",
    "ReplicationDefaults",
]
