"""
Configuration constants for architecture-based replication.

This module centralizes all tunable parameters, thresholds, and weights
used throughout the replication system.
"""

from dataclasses import dataclass


# =============================================================================
# CONFIGURATION SIMILARITY WEIGHTS
# =============================================================================

@dataclass(frozen=True)
class ConfigurationSimilarityWeights:
    """Weights for configuration similarity scoring.

    These determine relative importance of location, SKU tier, and tags
    when computing configuration coherence between resources.

    Sum should equal 1.0 for normalized scoring.
    """
    location: float = 0.5   # Location match is most important
    sku_tier: float = 0.3   # SKU tier similarity (Standard/Premium/Basic)
    tags: float = 0.2       # Tag overlap (least important)

    def __post_init__(self):
        total = self.location + self.sku_tier + self.tags
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")


# Default weights (line 402 in original file)
DEFAULT_CONFIG_SIMILARITY_WEIGHTS = ConfigurationSimilarityWeights()


# =============================================================================
# COHERENCE THRESHOLDS
# =============================================================================

# Minimum similarity score for resources to be considered configuration-coherent
# Resources with similarity >= this threshold will be clustered together
# Lower values = more permissive clustering (larger instances)
# Higher values = stricter clustering (smaller, more homogeneous instances)
DEFAULT_COHERENCE_THRESHOLD = 0.5  # Line 460 in original file


# =============================================================================
# SELECTION STRATEGY PARAMETERS
# =============================================================================

# Default spectral weight in hybrid scoring (line 692 in original file)
# Determines balance between distribution adherence and spectral optimization
# 0.0 = pure distribution adherence (ignore structure)
# 0.4 = RECOMMENDED (60% distribution, 40% spectral)
# 1.0 = pure spectral distance (ignore distribution)
DEFAULT_SPECTRAL_WEIGHT = 0.4

# Maximum configuration samples per pattern for spectral guidance (line 693 in original file)
# Limits number of instances evaluated per pattern to control performance
# Only affects patterns with MORE instances than this value
# Lower values = faster but less thorough
# Higher values = slower but more thorough exploration
MAX_CONFIG_SAMPLES = 100

# Target instance count scaling factors
DEFAULT_TARGET_SCALE_FACTOR = 0.1  # 10% of source (line 1599 in original file)


# =============================================================================
# ORPHANED RESOURCE ALLOCATION
# =============================================================================

# Budget for orphaned resources as fraction of total target instances
# Ensures orphaned types (not in patterns) still get representation
# Lower values = less budget for edge-case types
# Higher values = more coverage of rare types
ORPHANED_RESOURCE_BUDGET = 0.25  # 25% of total target (line 856 in original file)

# Maximum standalone orphaned instances as fraction of RG-based instances
# Limits number of singleton orphaned resources to prevent noise
# Standalone resources have no ResourceGroup parent
STANDALONE_ORPHANED_CAP = 0.5  # 50% of RG instances (line 1147 in original file)

# Maximum instances per standalone orphaned type
# Prevents over-representation of common standalone types
MAX_INSTANCES_PER_STANDALONE_TYPE = 2  # Line 1190 in original file


# =============================================================================
# SAMPLING STRATEGIES
# =============================================================================

class SamplingStrategy:
    """Configuration sampling strategy identifiers."""
    COVERAGE = "coverage"      # Greedy set cover (maximize unique types)
    DIVERSITY = "diversity"    # Maximin diversity (maximize config variation)


DEFAULT_SAMPLING_STRATEGY = SamplingStrategy.COVERAGE


# =============================================================================
# LOGGING INTERVALS
# =============================================================================

# Log progress every N instances during greedy selection
# Lower values = more verbose logging
# Higher values = less verbose but faster
GREEDY_SELECTION_LOG_INTERVAL = 10  # Line 2306 in original file


# =============================================================================
# CLUSTERING PARAMETERS
# =============================================================================

# Minimum number of resources required for an instance to be valid
# Instances with fewer resources are filtered out
MINIMUM_INSTANCE_SIZE = 2  # Used throughout the codebase


# =============================================================================
# DERIVED CONSTANTS
# =============================================================================

def get_distribution_weight(spectral_weight: float) -> float:
    """Compute distribution weight from spectral weight.

    Distribution and spectral weights are complementary (sum to 1.0).

    Args:
        spectral_weight: Weight for spectral component (0.0-1.0)

    Returns:
        Distribution weight (1.0 - spectral_weight)
    """
    return 1.0 - spectral_weight


# =============================================================================
# VALIDATION HELPERS
# =============================================================================

def validate_weight(weight: float, name: str) -> None:
    """Validate that a weight is in valid range [0.0, 1.0].

    Args:
        weight: Weight value to validate
        name: Name of the weight (for error messages)

    Raises:
        ValueError: If weight is outside valid range
    """
    if not 0.0 <= weight <= 1.0:
        raise ValueError(f"{name} must be in range [0.0, 1.0], got {weight}")


def validate_threshold(threshold: float, name: str) -> None:
    """Validate that a threshold is in valid range [0.0, 1.0].

    Args:
        threshold: Threshold value to validate
        name: Name of the threshold (for error messages)

    Raises:
        ValueError: If threshold is outside valid range
    """
    if not 0.0 <= threshold <= 1.0:
        raise ValueError(f"{name} must be in range [0.0, 1.0], got {threshold}")


# =============================================================================
# TUNEABLE PARAMETER REGISTRY
# =============================================================================

@dataclass(frozen=True)
class ReplicationParameters:
    """Complete parameter set for replication tuning.

    Use this to override defaults for experimentation or optimization.
    All parameters have sensible defaults based on empirical testing.
    """
    # Configuration similarity
    config_similarity_weights: ConfigurationSimilarityWeights = DEFAULT_CONFIG_SIMILARITY_WEIGHTS
    coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD

    # Selection strategy
    spectral_weight: float = DEFAULT_SPECTRAL_WEIGHT
    max_config_samples: int = MAX_CONFIG_SAMPLES
    sampling_strategy: str = DEFAULT_SAMPLING_STRATEGY

    # Orphaned resources
    orphaned_budget: float = ORPHANED_RESOURCE_BUDGET
    standalone_cap: float = STANDALONE_ORPHANED_CAP
    max_standalone_per_type: int = MAX_INSTANCES_PER_STANDALONE_TYPE

    # Target scaling
    target_scale_factor: float = DEFAULT_TARGET_SCALE_FACTOR

    def __post_init__(self):
        """Validate all parameters."""
        validate_weight(self.spectral_weight, "spectral_weight")
        validate_threshold(self.coherence_threshold, "coherence_threshold")
        validate_weight(self.orphaned_budget, "orphaned_budget")
        validate_weight(self.standalone_cap, "standalone_cap")

        if self.max_config_samples < 1:
            raise ValueError(f"max_config_samples must be >= 1, got {self.max_config_samples}")


# Default parameter set
DEFAULT_REPLICATION_PARAMETERS = ReplicationParameters()
