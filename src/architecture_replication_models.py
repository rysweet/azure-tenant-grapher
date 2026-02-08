"""
Data models for Architecture-Based Tenant Replication.

This module contains dataclasses and structured types used throughout
the architecture-based replication system.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class ResourceFingerprint:
    """
    Configuration fingerprint for a resource.
    
    Used to determine configuration similarity between resources.
    """
    
    location: str = ""
    sku_tier: str = ""
    tags: Dict[str, str] = field(default_factory=dict)
    
    @classmethod
    def from_resource(cls, resource: Dict[str, Any]) -> "ResourceFingerprint":
        """
        Extract fingerprint from a resource dictionary.
        
        Args:
            resource: Resource dictionary with properties
            
        Returns:
            ResourceFingerprint instance
        """
        properties = resource.get("properties", {})
        
        # Extract location
        location = resource.get("location", "")
        
        # Extract SKU tier
        sku = properties.get("sku", {})
        sku_tier = ""
        if isinstance(sku, dict):
            sku_tier = sku.get("tier", sku.get("name", ""))
        
        # Extract tags
        tags = resource.get("tags", {})
        if not isinstance(tags, dict):
            tags = {}
        
        return cls(location=location, sku_tier=sku_tier, tags=tags)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for compatibility."""
        return {
            "location": self.location,
            "sku_tier": self.sku_tier,
            "tags": self.tags,
        }


@dataclass
class ConfigurationCluster:
    """
    A cluster of resources with similar configurations.
    
    Resources in the same cluster share similar location, SKU, and tags.
    """
    
    resources: List[Dict[str, Any]] = field(default_factory=list)
    centroid_fingerprint: Optional[ResourceFingerprint] = None
    average_similarity: float = 0.0
    
    def add_resource(self, resource: Dict[str, Any]) -> None:
        """Add a resource to this cluster."""
        self.resources.append(resource)
    
    def size(self) -> int:
        """Return the number of resources in this cluster."""
        return len(self.resources)


@dataclass
class PatternInstance:
    """
    A single instance of an architectural pattern.
    
    An instance is a connected set of resources that implement the pattern.
    """
    
    pattern_name: str
    resources: List[Dict[str, Any]] = field(default_factory=list)
    resource_types: Set[str] = field(default_factory=set)
    configuration_fingerprint: Optional[ResourceFingerprint] = None
    
    def add_resource(self, resource: Dict[str, Any]) -> None:
        """Add a resource to this instance."""
        self.resources.append(resource)
        resource_type = resource.get("type", "")
        if resource_type:
            self.resource_types.add(resource_type)
    
    def size(self) -> int:
        """Return the number of resources in this instance."""
        return len(self.resources)
    
    def to_resource_list(self) -> List[Dict[str, Any]]:
        """Convert to simple resource list for compatibility."""
        return self.resources


@dataclass
class DistributionScore:
    """
    Distribution analysis metadata for a pattern.
    
    Contains information about how well a pattern fits the source
    tenant's architectural distribution.
    """
    
    pattern_name: str
    distribution_score: float
    source_instances: int
    rank: int
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format."""
        return {
            "pattern_name": self.pattern_name,
            "distribution_score": self.distribution_score,
            "source_instances": self.source_instances,
            "rank": self.rank,
        }


@dataclass
class InstanceScore:
    """
    Scoring information for a candidate instance during selection.
    
    Used in hybrid scoring algorithms that combine multiple factors.
    """
    
    instance_index: int
    spectral_contribution: float
    distribution_adherence: float
    combined_score: float
    resources: List[Dict[str, Any]] = field(default_factory=list)
    
    def __lt__(self, other: "InstanceScore") -> bool:
        """Support sorting by combined score (lower is better)."""
        return self.combined_score < other.combined_score


@dataclass
class ReplicationPlan:
    """
    Complete replication plan with selected instances and metadata.
    
    Contains the final selection of instances to replicate, along with
    spectral distance history and distribution metadata.
    """
    
    selected_instances: List[tuple] = field(default_factory=list)
    """List of (pattern_name, [instances]) tuples"""
    
    spectral_distances: List[float] = field(default_factory=list)
    """History of spectral distances during selection"""
    
    distribution_metadata: Optional[Dict[str, Any]] = None
    """Architecture distribution analysis metadata"""
    
    target_instance_count: Optional[int] = None
    """Target number of instances requested"""
    
    actual_instance_count: int = 0
    """Actual number of instances selected"""
    
    def to_tuple(self) -> tuple:
        """Convert to legacy tuple format for compatibility."""
        return (
            self.selected_instances,
            self.spectral_distances,
            self.distribution_metadata,
        )


@dataclass
class OrphanedResourceInfo:
    """
    Information about orphaned resources (resources not in any pattern).
    
    Tracks orphaned resources found during analysis.
    """
    
    resource_type: str
    instances: List[Dict[str, Any]] = field(default_factory=list)
    count: int = 0
    
    def add_instance(self, resource: Dict[str, Any]) -> None:
        """Add an orphaned resource instance."""
        self.instances.append(resource)
        self.count = len(self.instances)


# Export all models
__all__ = [
    "ResourceFingerprint",
    "ConfigurationCluster",
    "PatternInstance",
    "DistributionScore",
    "InstanceScore",
    "ReplicationPlan",
    "OrphanedResourceInfo",
]
