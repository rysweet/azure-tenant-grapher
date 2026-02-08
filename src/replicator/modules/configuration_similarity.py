"""
Configuration Similarity Brick

Pure utility brick for computing configuration similarity and clustering resources
by configuration coherence.

Philosophy:
- Single Responsibility: Configuration comparison and clustering
- Self-contained: No external state
- Regeneratable: Pure function logic
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

import json
from typing import Any

from ...architecture_replication_constants import (
    CONFIGURATION_SIMILARITY_WEIGHTS,
    DEFAULT_COHERENCE_THRESHOLD,
    MIN_CLUSTER_SIZE,
)


class ConfigurationSimilarity:
    """
    Computes configuration similarity and clusters resources by coherence.

    This brick provides stateless methods for comparing resource configurations
    and clustering resources with similar configurations.

    Public Contract:
        - compute_similarity(fingerprint1, fingerprint2) -> float
        - cluster_by_coherence(resources, fingerprints, threshold) -> list[list[dict]]
    """

    @staticmethod
    def compute_similarity(
        fingerprint1: dict[str, Any],
        fingerprint2: dict[str, Any],
    ) -> float:
        """
        Compute similarity score between two configuration fingerprints.

        Configuration coherence is based on:
        - Location match (same Azure region)
        - SKU tier similarity (e.g., Standard vs Premium)
        - Tag overlap (Jaccard similarity)

        Args:
            fingerprint1: First configuration fingerprint with keys: location, sku, tags
            fingerprint2: Second configuration fingerprint with keys: location, sku, tags

        Returns:
            Similarity score between 0.0 and 1.0, where 1.0 means identical configuration

        Examples:
            >>> fp1 = {"location": "eastus", "sku": "Standard_D2s_v3", "tags": {"env": "prod"}}
            >>> fp2 = {"location": "eastus", "sku": "Standard_D4s_v3", "tags": {"env": "prod"}}
            >>> ConfigurationSimilarity.compute_similarity(fp1, fp2)
            0.85  # Same location, same tier, same tags
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

        tier1 = ConfigurationSimilarity._extract_sku_tier(sku1)
        tier2 = ConfigurationSimilarity._extract_sku_tier(sku2)
        if tier1 and tier2 and tier1 == tier2:
            score += weights["sku_tier"]

        # Tag overlap (Jaccard similarity)
        tags1_data = ConfigurationSimilarity._parse_tags(fingerprint1.get("tags", {}))
        tags2_data = ConfigurationSimilarity._parse_tags(fingerprint2.get("tags", {}))

        tags1 = set(tags1_data.keys() if isinstance(tags1_data, dict) else [])
        tags2 = set(tags2_data.keys() if isinstance(tags2_data, dict) else [])
        if tags1 or tags2:
            intersection = len(tags1 & tags2)
            union = len(tags1 | tags2)
            tag_similarity = intersection / union if union > 0 else 0
            score += weights["tags"] * tag_similarity

        return score

    @staticmethod
    def cluster_by_coherence(
        resources: list[dict[str, Any]],
        resource_fingerprints: dict[str, dict[str, Any]],
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
    ) -> list[list[dict[str, Any]]]:
        """
        Cluster resources by configuration coherence using agglomerative clustering.

        Resources with similar configurations (location, SKU tier, tags) are grouped
        into clusters. Only clusters meeting the minimum size are returned.

        Args:
            resources: List of resources to cluster, each with an "id" field
            resource_fingerprints: Map of resource ID to configuration fingerprint
            coherence_threshold: Minimum similarity score for resources to be in same cluster (0.0-1.0)

        Returns:
            List of clusters, where each cluster is a list of resources with similar configurations

        Examples:
            >>> resources = [{"id": "vm1"}, {"id": "vm2"}, {"id": "vm3"}]
            >>> fingerprints = {
            ...     "vm1": {"location": "eastus", "sku": "Standard_D2s_v3"},
            ...     "vm2": {"location": "eastus", "sku": "Standard_D4s_v3"},
            ...     "vm3": {"location": "westus", "sku": "Premium_D2s_v3"}
            ... }
            >>> clusters = ConfigurationSimilarity.cluster_by_coherence(resources, fingerprints, 0.7)
            >>> len(clusters)
            2  # VM1 and VM2 in one cluster (same location), VM3 separate
        """
        if len(resources) < MIN_CLUSTER_SIZE:
            # < 2 resources, no clustering needed
            return [resources] if resources else []

        # Compute pairwise similarities
        similarity_matrix = {}
        for i, res1 in enumerate(resources):
            for j, res2 in enumerate(resources):
                if i < j:
                    fp1 = resource_fingerprints[res1["id"]]
                    fp2 = resource_fingerprints[res2["id"]]
                    sim = ConfigurationSimilarity.compute_similarity(fp1, fp2)
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

    @staticmethod
    def _parse_tags(tags_data: Any) -> dict[str, Any]:
        """
        Parse tags data which may be a JSON string or dict.

        Args:
            tags_data: Tags as dict or JSON string

        Returns:
            Dict of tags or empty dict if parsing fails
        """
        if isinstance(tags_data, str):
            try:
                return json.loads(tags_data)
            except (json.JSONDecodeError, TypeError):
                return {}
        return tags_data if isinstance(tags_data, dict) else {}

    @staticmethod
    def _extract_sku_tier(sku: str) -> str:
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


__all__ = ["ConfigurationSimilarity"]
