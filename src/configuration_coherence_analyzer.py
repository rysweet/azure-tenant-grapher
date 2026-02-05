"""
Configuration Coherence Analysis for Architecture-Based Replication.

This module handles configuration similarity computations and clustering
of resources based on their configuration attributes (location, SKU, tags).
"""

import json
import logging
from typing import Any, Dict, List, Set

from .architecture_replication_constants import (
    CONFIGURATION_SIMILARITY_WEIGHTS,
    DEFAULT_COHERENCE_THRESHOLD,
    MIN_CLUSTER_SIZE,
)
from .architecture_replication_models import ConfigurationCluster

logger = logging.getLogger(__name__)


class ConfigurationCoherenceAnalyzer:
    """
    Analyzes and clusters resources based on configuration coherence.
    
    Configuration coherence is based on:
    - Location match (same Azure region)
    - SKU tier similarity (e.g., Standard vs Premium)
    - Tag overlap
    """
    
    def __init__(self, analyzer=None):
        """
        Initialize the configuration coherence analyzer.
        
        Args:
            analyzer: ArchitecturalPatternAnalyzer instance for creating fingerprints
        """
        self.analyzer = analyzer
    
    def compute_similarity(
        self,
        fingerprint1: Dict[str, Any],
        fingerprint2: Dict[str, Any],
    ) -> float:
        """
        Compute similarity score between two configuration fingerprints.
        
        Args:
            fingerprint1: First configuration fingerprint
            fingerprint2: Second configuration fingerprint
            
        Returns:
            Similarity score (0.0 to 1.0, where 1.0 = identical)
        """
        score = 0.0
        weights = CONFIGURATION_SIMILARITY_WEIGHTS
        
        # Location match (exact)
        loc1 = fingerprint1.get("location", "")
        loc2 = fingerprint2.get("location", "")
        if loc1 and loc2 and loc1 == loc2:
            score += weights["location"]
        
        # SKU tier similarity (extract tier from SKU)
        sku1 = fingerprint1.get("sku", "")
        sku2 = fingerprint2.get("sku", "")
        
        tier1 = self._extract_tier(sku1)
        tier2 = self._extract_tier(sku2)
        if tier1 and tier2 and tier1 == tier2:
            score += weights["sku_tier"]
        
        # Tag overlap (Jaccard similarity)
        tags1_data = fingerprint1.get("tags", {})
        tags2_data = fingerprint2.get("tags", {})
        
        # Parse tags if they're JSON strings
        if isinstance(tags1_data, str):
            try:
                tags1_data = json.loads(tags1_data)
            except:
                tags1_data = {}
        if isinstance(tags2_data, str):
            try:
                tags2_data = json.loads(tags2_data)
            except:
                tags2_data = {}
        
        tags1 = set(tags1_data.keys() if isinstance(tags1_data, dict) else [])
        tags2 = set(tags2_data.keys() if isinstance(tags2_data, dict) else [])
        if tags1 or tags2:
            intersection = len(tags1 & tags2)
            union = len(tags1 | tags2)
            tag_similarity = intersection / union if union > 0 else 0
            score += weights["tags"] * tag_similarity
        
        return score
    
    @staticmethod
    def _extract_tier(sku: str) -> str:
        """
        Extract tier from SKU string.
        
        Args:
            sku: SKU string (e.g., "Standard_D2s_v3", "Premium_LRS")
            
        Returns:
            Tier string (e.g., "standard", "premium")
        """
        if not sku or sku == "UnknownSKU":
            return ""
        parts = sku.split("_")
        if parts:
            # Common patterns: "Standard_D2s_v3", "Premium_LRS"
            return parts[0].lower()
        return ""
    
    def cluster_by_coherence(
        self,
        resources: List[Dict[str, Any]],
        resource_fingerprints: Dict[str, Dict[str, Any]],
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
    ) -> List[List[Dict[str, Any]]]:
        """
        Cluster resources by configuration coherence using agglomerative clustering.
        
        Args:
            resources: List of resources to cluster
            resource_fingerprints: Map of resource ID to configuration fingerprint
            coherence_threshold: Minimum similarity for resources to be in same cluster
            
        Returns:
            List of clusters, where each cluster is a list of resources
        """
        if len(resources) < MIN_CLUSTER_SIZE:
            # Single resource, trivially coherent
            return [resources] if resources else []
        
        # Compute pairwise similarities
        similarity_matrix = {}
        for i, res1 in enumerate(resources):
            for j, res2 in enumerate(resources):
                if i < j:
                    fp1 = resource_fingerprints[res1["id"]]
                    fp2 = resource_fingerprints[res2["id"]]
                    sim = self.compute_similarity(fp1, fp2)
                    similarity_matrix[(i, j)] = sim
        
        # Start with each resource in its own cluster
        clusters = [[res] for res in resources]
        
        # Iteratively merge most similar clusters above threshold
        merged = True
        while merged and len(clusters) > 1:
            merged = False
            best_sim = coherence_threshold
            best_pair = None
            
            # Find best cluster pair to merge
            for i in range(len(clusters)):
                for j in range(i + 1, len(clusters)):
                    # Compute average similarity between clusters
                    similarities = []
                    for res1 in clusters[i]:
                        for res2 in clusters[j]:
                            idx1 = resources.index(res1)
                            idx2 = resources.index(res2)
                            key = (min(idx1, idx2), max(idx1, idx2))
                            if key in similarity_matrix:
                                similarities.append(similarity_matrix[key])
                    
                    if similarities:
                        avg_sim = sum(similarities) / len(similarities)
                        if avg_sim > best_sim:
                            best_sim = avg_sim
                            best_pair = (i, j)
            
            # Merge best pair if found
            if best_pair:
                i, j = best_pair
                merged_cluster = clusters[i] + clusters[j]
                # Remove old clusters (remove j first to preserve i index)
                clusters.pop(j)
                clusters.pop(i)
                clusters.append(merged_cluster)
                merged = True
        
        # Only return clusters with minimum size
        return [c for c in clusters if len(c) >= MIN_CLUSTER_SIZE]
    
    def find_configuration_coherent_instances(
        self,
        pattern_name: str,
        matched_types: Set[str],
        session,
        detected_patterns: Dict[str, Dict[str, Any]],
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        include_colocated_orphaned_resources: bool = True,
    ) -> List[List[Dict[str, Any]]]:
        """
        Find architectural instances with configuration coherence.
        
        Instead of grouping resources only by ResourceGroup, this method
        splits ResourceGroups into configuration-coherent clusters where
        resources have similar configurations (same location, similar tier, etc.).
        
        Args:
            pattern_name: Name of the architectural pattern
            matched_types: Set of resource types in this pattern
            session: Neo4j session
            detected_patterns: Dict of all detected patterns
            coherence_threshold: Minimum similarity score for resources in same instance
            include_colocated_orphaned_resources: Include orphaned resources from same RG
            
        Returns:
            List of configuration-coherent instances
        """
        if not self.analyzer:
            raise RuntimeError("Analyzer not set. Cannot fetch instances.")
        
        # Compute all pattern types across all detected patterns (for orphan detection)
        all_pattern_types = set()
        for pattern_info in detected_patterns.values():
            all_pattern_types.update(pattern_info["matched_resources"])
        
        # Query for resources
        if include_colocated_orphaned_resources:
            # Get ALL resources to identify orphans
            query = """
            MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
            RETURN rg.id as resource_group_id,
                   r.id as id,
                   r.type as type,
                   r.name as name,
                   r.location as location,
                   r.tags as tags,
                   r.properties as properties
            ORDER BY rg.id
            """
            result = session.run(query)
        else:
            # Original behavior: only get pattern type resources
            query = """
            MATCH (rg:ResourceGroup)-[:CONTAINS]->(r:Resource:Original)
            WHERE r.type IN $types
            RETURN rg.id as resource_group_id,
                   r.id as id,
                   r.type as type,
                   r.name as name,
                   r.location as location,
                   r.tags as tags,
                   r.properties as properties
            ORDER BY rg.id
            """
            
            # Convert simplified types to full Azure types
            full_types = []
            for simplified in matched_types:
                # Common namespace patterns
                for namespace in [
                    "Microsoft.Compute",
                    "Microsoft.Network",
                    "Microsoft.Storage",
                    "Microsoft.Web",
                    "Microsoft.Insights",
                    "Microsoft.Sql",
                    "Microsoft.KeyVault",
                    "Microsoft.ContainerRegistry",
                    "Microsoft.ContainerService",
                ]:
                    full_types.append(f"{namespace}/{simplified}")
            
            result = session.run(query, types=full_types)
        
        # Group by ResourceGroup first
        rg_to_pattern_resources = {}  # Only pattern types
        rg_to_all_resources = {}  # All resources (for orphan inclusion)
        resource_fingerprints = {}
        
        for record in result:
            simplified_type = self.analyzer._get_resource_type_name(
                ["Resource"], record["type"]
            )
            
            resource_id = record["id"]
            rg_id = record["resource_group_id"]
            
            # Parse properties if JSON string
            properties = record["properties"]
            if isinstance(properties, str):
                try:
                    properties = json.loads(properties)
                except json.JSONDecodeError:
                    properties = None
            
            # Create configuration fingerprint
            fingerprint = self.analyzer.create_configuration_fingerprint(
                resource_id,
                record["type"],
                record["location"],
                record["tags"],
                properties,
            )
            
            resource = {
                "id": resource_id,
                "type": simplified_type,
                "name": record["name"],
            }
            
            # Track all resources if including orphaned
            if include_colocated_orphaned_resources:
                if rg_id not in rg_to_all_resources:
                    rg_to_all_resources[rg_id] = []
                rg_to_all_resources[rg_id].append((simplified_type, resource))
            
            # Only include pattern-matching resources in clustering
            if simplified_type not in matched_types:
                continue
            
            # This resource matches the pattern - add to pattern tracking
            if rg_id not in rg_to_pattern_resources:
                rg_to_pattern_resources[rg_id] = []
            
            rg_to_pattern_resources[rg_id].append(resource)
            resource_fingerprints[resource_id] = fingerprint
        
        if not rg_to_pattern_resources:
            return []
        
        # Now split each ResourceGroup into configuration-coherent clusters
        all_instances = []
        
        for rg_id, resources in rg_to_pattern_resources.items():
            if len(resources) < MIN_CLUSTER_SIZE:
                # Single resource, trivially coherent
                all_instances.append(resources)
                continue
            
            # Cluster resources by configuration coherence
            clusters = self.cluster_by_coherence(
                resources, resource_fingerprints, coherence_threshold
            )
            
            # Add orphaned resources if enabled
            for cluster in clusters:
                if include_colocated_orphaned_resources and rg_id in rg_to_all_resources:
                    orphaned_count = 0
                    for resource_type, resource in rg_to_all_resources[rg_id]:
                        # Check if this resource type is NOT in any pattern (orphaned)
                        if resource_type not in all_pattern_types:
                            # Check if not already in cluster (avoid duplicates)
                            if not any(r["id"] == resource["id"] for r in cluster):
                                cluster.append(resource)
                                orphaned_count += 1
                    
                    if orphaned_count > 0:
                        logger.debug(
                            f"  Added {orphaned_count} co-located orphaned resources "
                            f"to cluster in RG {rg_id}"
                        )
                
                all_instances.append(cluster)
        
        logger.debug(
            f"  Found {len(all_instances)} configuration-coherent instances "
            f"(threshold: {coherence_threshold})"
        )
        
        return all_instances


__all__ = ["ConfigurationCoherenceAnalyzer"]
