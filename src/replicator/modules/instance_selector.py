"""
Instance Selector Brick

Brick for selecting architectural pattern instances using various strategies:
- Proportional selection (with optional spectral guidance)
- Hybrid scoring (distribution + spectral)
- Greedy spectral selection

Philosophy:
- Single Responsibility: Instance selection strategies
- Self-contained: Clear public contracts with injected dependencies
- Regeneratable: Stateless operations
- Zero-BS: All functions work, no stubs
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any

from ...architecture_replication_constants import (
    DEFAULT_MAX_CONFIG_SAMPLES,
    DEFAULT_SPECTRAL_WEIGHT,
)

if TYPE_CHECKING:
    import networkx as nx

    from .graph_structure_analyzer import GraphStructureAnalyzer
    from .target_graph_builder import TargetGraphBuilder

logger = logging.getLogger(__name__)


class InstanceSelector:
    """
    Selects architectural pattern instances using various strategies.

    This brick provides multiple selection strategies that can be combined:
    - Proportional: Select from each pattern proportionally
    - Hybrid: Score instances by distribution adherence and spectral improvement
    - Greedy: Iteratively select instances minimizing spectral distance

    Dependencies (injected):
        - graph_analyzer: GraphStructureAnalyzer for spectral distance computation
        - graph_builder: TargetGraphBuilder for building candidate graphs

    Public Contract:
        - select_proportionally(pattern_targets, pattern_resources, ...) -> list
        - select_greedy(all_instances, target_count, ...) -> list
    """

    def __init__(
        self,
        graph_analyzer: GraphStructureAnalyzer,
        graph_builder: TargetGraphBuilder,
    ):
        """
        Initialize with injected dependencies.

        Args:
            graph_analyzer: GraphStructureAnalyzer brick for spectral distance
            graph_builder: TargetGraphBuilder brick for building pattern graphs
        """
        self.graph_analyzer = graph_analyzer
        self.graph_builder = graph_builder

    def select_proportionally(
        self,
        pattern_targets: dict[str, int],
        pattern_resources: dict[str, list[list[dict[str, Any]]]],
        use_spectral_guidance: bool = False,
        spectral_weight: float = DEFAULT_SPECTRAL_WEIGHT,
        max_config_samples: int = DEFAULT_MAX_CONFIG_SAMPLES,
        sampling_strategy: str = "coverage",
        source_pattern_graph: nx.DiGraph | None = None,
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        """
        Select instances proportionally from each pattern.

        Supports two selection modes:
        1. Spectral-guided: Uses hybrid score (distribution + spectral) for best structural match
        2. Random: Fast, no bias (default when spectral guidance disabled)

        Args:
            pattern_targets: Target count per pattern from proportional allocation
            pattern_resources: Available instances per pattern
            use_spectral_guidance: If True, use hybrid scoring with spectral distance
            spectral_weight: Weight for spectral component in hybrid score (0.0-1.0)
            max_config_samples: Maximum configurations to sample per pattern
            sampling_strategy: "coverage" (greedy set cover) or "diversity" (maximin)
            source_pattern_graph: Source pattern graph (required if use_spectral_guidance=True)

        Returns:
            List of (pattern_name, instance) tuples

        Examples:
            >>> selector = InstanceSelector(graph_analyzer, graph_builder)
            >>> targets = {"web_app": 3, "database": 2}
            >>> resources = {
            ...     "web_app": [instance1, instance2, instance3, instance4],
            ...     "database": [db1, db2, db3]
            ... }
            >>> selected = selector.select_proportionally(targets, resources)
            >>> len(selected)
            5  # 3 web_app + 2 database
        """
        if use_spectral_guidance and source_pattern_graph is None:
            raise ValueError(
                "source_pattern_graph is required when use_spectral_guidance=True"
            )

        selected_instances: list[tuple[str, list[dict[str, Any]]]] = []
        current_counts: dict[str, int] = dict.fromkeys(pattern_targets, 0)
        total_target = sum(pattern_targets.values())

        # Warm cache for all patterns to avoid repeated Neo4j queries during spectral scoring
        if use_spectral_guidance:
            logger.info("Warming relationship cache for all candidate instances...")
            all_candidates = [(name, resources) for name, resources in pattern_resources.items()]
            self.graph_builder.warm_cache(all_candidates)
            logger.info(f"Cache warmed with {len(self.graph_builder._relationship_cache)} resource IDs")

        for pattern_name, target_count in pattern_targets.items():
            if pattern_name not in pattern_resources:
                logger.warning(
                    f"Pattern {pattern_name} not found in pattern_resources, skipping"
                )
                continue

            available_instances = pattern_resources[pattern_name]

            if not available_instances:
                logger.warning(
                    f"No instances available for pattern {pattern_name}, skipping"
                )
                continue

            # Limit to available instances
            actual_count = min(target_count, len(available_instances))

            if use_spectral_guidance:
                # Hybrid spectral-guided selection
                logger.info(
                    f"  Selecting {actual_count}/{len(available_instances)} instances "
                    f"from {pattern_name} (spectral-guided, weight={spectral_weight:.2f})"
                )

                chosen_instances = self._select_with_hybrid_scoring(
                    available_instances,
                    actual_count,
                    pattern_name,
                    selected_instances,
                    current_counts,
                    total_target,
                    spectral_weight,
                    max_config_samples,
                    sampling_strategy,
                    source_pattern_graph,
                )

            else:
                # Random selection
                logger.info(
                    f"  Selecting {actual_count}/{len(available_instances)} instances "
                    f"from {pattern_name} (random)"
                )
                chosen_instances = random.sample(available_instances, actual_count)

            # Add to selected
            for instance in chosen_instances:
                selected_instances.append((pattern_name, instance))
                current_counts[pattern_name] += 1

        logger.info(
            f"Selected {len(selected_instances)} total instances across all patterns"
        )

        return selected_instances

    def select_greedy(
        self,
        all_instances: list[tuple[str, list[dict[str, Any]]]],
        target_instance_count: int,
        source_pattern_graph: nx.DiGraph,
        node_coverage_weight: float,
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        """
        Greedy spectral distance-based instance selection.

        Iteratively selects instances that minimize a weighted score combining
        spectral distance and node coverage.

        Args:
            all_instances: All available (pattern_name, instance) tuples
            target_instance_count: Number of instances to select
            source_pattern_graph: Source pattern graph to match
            node_coverage_weight: Weight for node coverage component (0.0-1.0)

        Returns:
            List of selected (pattern_name, instance) tuples

        Examples:
            >>> selector = InstanceSelector(graph_analyzer, graph_builder)
            >>> all_instances = [("web_app", instance1), ("database", instance2), ...]
            >>> selected = selector.select_greedy(all_instances, 5, source_graph, 0.5)
            >>> len(selected)
            5
        """
        # Get source node types for coverage tracking
        source_node_types = set(source_pattern_graph.nodes())

        selected_instances: list[tuple[str, list[dict[str, Any]]]] = []
        remaining_instances = list(all_instances)  # Make a copy

        # Greedy selection: iteratively pick the instance that best improves our score
        for i in range(min(target_instance_count, len(remaining_instances))):
            best_score = float("inf")
            best_idx = 0
            best_new_nodes = set()

            # Evaluate each remaining instance
            for idx, (pattern_name, instance) in enumerate(remaining_instances):
                # Build hypothetical target graph with this instance added
                hypothetical_selected = [*selected_instances, (pattern_name, instance)]
                hypothetical_target = self.graph_builder.build_from_instances(
                    hypothetical_selected
                )

                # Compute weighted score
                score = self.graph_analyzer.compute_weighted_score(
                    source_pattern_graph,
                    hypothetical_target,
                    source_node_types,
                    node_coverage_weight,
                )

                # Track which instance gives best score
                if score < best_score:
                    best_score = score
                    best_idx = idx
                    best_new_nodes = set(hypothetical_target.nodes()) - (
                        set(
                            self.graph_builder.build_from_instances(
                                selected_instances
                            ).nodes()
                        )
                        if selected_instances
                        else set()
                    )

            # Select the best instance
            pattern_name, instance = remaining_instances.pop(best_idx)
            selected_instances.append((pattern_name, instance))

            # Build current target pattern graph from selected instances
            target_pattern_graph = self.graph_builder.build_from_instances(
                selected_instances
            )

            # Calculate coverage metrics
            current_nodes = set(target_pattern_graph.nodes())
            node_coverage = len(current_nodes & source_node_types) / len(
                source_node_types
            )

            if (i + 1) % 10 == 0 or i < 10:
                distance = self.graph_analyzer.compute_spectral_distance(
                    source_pattern_graph, target_pattern_graph
                )
                logger.info(
                    f"  Selected {i + 1}/{target_instance_count} instances: "
                    f"spectral_distance={distance:.4f}, "
                    f"node_coverage={node_coverage:.2%}, "
                    f"score={best_score:.4f}, "
                    f"new_nodes={best_new_nodes}"
                )

        return selected_instances

    def _select_with_hybrid_scoring(
        self,
        available_instances: list[list[dict[str, Any]]],
        target_count: int,
        pattern_name: str,
        selected_so_far: list[tuple[str, list[dict[str, Any]]]],
        current_counts: dict[str, int],
        total_target: int,
        spectral_weight: float,
        max_config_samples: int,
        sampling_strategy: str,
        source_pattern_graph: nx.DiGraph,
    ) -> list[list[dict[str, Any]]]:
        """
        Select instances using hybrid scoring: distribution adherence + spectral improvement.

        Samples representative configurations, then scores each based on:
        - Distribution adherence: How well it maintains proportional balance
        - Spectral contribution: How much it improves structural similarity

        Args:
            available_instances: Pool of instances to select from
            target_count: Number of instances to select
            pattern_name: Name of the current pattern
            selected_so_far: Instances already selected from all patterns
            current_counts: Current count per pattern
            total_target: Total target instance count across all patterns
            spectral_weight: Weight for spectral component (0.0-1.0)
            max_config_samples: Maximum samples to consider per pattern
            sampling_strategy: "coverage" (greedy set cover) or "diversity" (maximin)
            source_pattern_graph: Source pattern graph to match

        Returns:
            List of selected instances
        """
        # Sample representative configurations using chosen strategy
        actual_max_samples = min(max_config_samples, len(available_instances))

        # Log sampling behavior for diagnostics
        if actual_max_samples < len(available_instances):
            logger.info(
                f"    Sampling limited: {actual_max_samples}/{len(available_instances)} instances "
                f"(max_config_samples={max_config_samples})"
            )
        else:
            logger.debug(
                f"    No sampling limit: evaluating all {len(available_instances)} instances "
                f"(max_config_samples={max_config_samples} >= available)"
            )

        if sampling_strategy == "coverage":
            sampled_instances, _instance_metadata = self._sample_for_coverage(
                available_instances, max_samples=actual_max_samples
            )
        else:  # "diversity" or default
            sampled_instances = self._sample_representative_configs(
                available_instances, max_samples=actual_max_samples
            )

        # Build current target graph once (for comparing edge additions)
        current_target = self.graph_builder.build_from_instances(selected_so_far)
        current_edges = set(current_target.edges())

        # Score each sampled instance using hybrid function
        scored_instances = []
        for _sampled_idx, instance in enumerate(sampled_instances):
            # Build hypothetical target graph with this instance added
            hypothetical_selected = [*selected_so_far, (pattern_name, instance)]
            hypothetical_target = self.graph_builder.build_from_instances(
                hypothetical_selected
            )

            # Component 2: Spectral contribution using SUBGRAPH approach
            # Identify NEW EDGES added by this instance
            hypothetical_edges = set(hypothetical_target.edges())
            new_edges = hypothetical_edges - current_edges

            if len(new_edges) > 0:
                # Extract nodes involved in new edges
                new_edge_nodes = set()
                for edge in new_edges:
                    # Edge could be (source, target) or (source, target, key) depending on graph type
                    if len(edge) == 3:
                        source, target, _ = edge
                    else:
                        source, target = edge
                    new_edge_nodes.add(source)
                    new_edge_nodes.add(target)

                # Build subgraph of nodes involved in new edges
                source_subgraph = source_pattern_graph.subgraph(new_edge_nodes)
                target_subgraph = hypothetical_target.subgraph(new_edge_nodes)

                # Compare local structure of newly connected nodes
                spectral_contribution = self.graph_analyzer.compute_spectral_distance(
                    source_subgraph, target_subgraph
                )
            else:
                # No new edges - instance doesn't add structural information
                spectral_contribution = 1.0  # High penalty

            # Use spectral contribution as the primary score (lower is better)
            hybrid_score = spectral_contribution

            # For logging compatibility, compute distribution adherence
            total_selected = sum(current_counts.values())
            if total_selected > 0:
                actual_ratio = (current_counts[pattern_name] + 1) / (total_selected + 1)
                target_ratio = (current_counts[pattern_name] + 1) / total_target
                distribution_adherence = abs(actual_ratio - target_ratio)
            else:
                distribution_adherence = 0.0

            scored_instances.append(
                (hybrid_score, distribution_adherence, spectral_contribution, instance)
            )

        # Log score statistics for debugging spectral_weight behavior
        if scored_instances:
            hybrid_scores = [s[0] for s in scored_instances]
            dist_scores = [s[1] for s in scored_instances]
            spec_scores = [s[2] for s in scored_instances]

            logger.debug(
                f"    Score statistics for {pattern_name} (n={len(scored_instances)}, spectral_weight={spectral_weight}):"
            )
            logger.debug(f"      Current edges: {len(current_edges)}")
            logger.debug(
                f"      Distribution: min={min(dist_scores):.4f}, max={max(dist_scores):.4f}, "
                f"range={max(dist_scores) - min(dist_scores):.4f}"
            )
            logger.debug(
                f"      Spectral:     min={min(spec_scores):.4f}, max={max(spec_scores):.4f}, "
                f"range={max(spec_scores) - min(spec_scores):.4f}"
            )
            logger.debug(
                f"      Hybrid:       min={min(hybrid_scores):.4f}, max={max(hybrid_scores):.4f}, "
                f"range={max(hybrid_scores) - min(hybrid_scores):.4f}"
            )

        # Sort by hybrid score (lower is better) and take top instances
        scored_instances.sort(key=lambda x: x[0])

        logger.debug(
            f"    After spectral rescoring: {len(scored_instances)} candidates, "
            f"selecting top {target_count}"
        )

        # Select best instances up to target_count
        # If we sampled < target_count, need to fill remaining slots
        chosen = []
        for _hybrid_score, _dist_score, _spec_score, instance in scored_instances[
            :target_count
        ]:
            chosen.append(instance)

        # If we need more instances (sampled < target), fill with remaining
        if len(chosen) < target_count:
            remaining = [inst for inst in available_instances if inst not in chosen]
            additional_needed = target_count - len(chosen)
            if remaining:
                chosen.extend(
                    random.sample(remaining, min(additional_needed, len(remaining)))
                )

        logger.debug(
            f"    Hybrid scoring: sampled {len(sampled_instances)} configs, "
            f"selected {len(chosen)} instances (dist_weight={1.0 - spectral_weight:.2f}, "
            f"spec_weight={spectral_weight:.2f})"
        )

        return chosen

    def _sample_representative_configs(
        self, instances: list[list[dict[str, Any]]], max_samples: int = 10
    ) -> list[list[dict[str, Any]]]:
        """
        Sample representative instances using maximin diversity.

        Ensures sampled instances are spread across configuration space
        (different resource types, counts) rather than clustered.

        Args:
            instances: Pool of instances to sample from
            max_samples: Maximum number of samples to return

        Returns:
            List of sampled instances (diverse configurations)
        """
        if len(instances) <= max_samples:
            return instances

        sampled = []
        remaining = list(instances)

        # Pick first instance randomly
        seed = random.choice(remaining)
        sampled.append(seed)
        remaining.remove(seed)

        # Iteratively pick most diverse instance (maximin strategy)
        while len(sampled) < max_samples and remaining:
            best_diversity = -1
            best_instance = None

            for candidate in remaining:
                # Compute minimum similarity to already sampled instances
                # Use simplified diversity metric: resource type overlap
                min_similarity = min(
                    self._instance_similarity(candidate, s) for s in sampled
                )

                # Pick instance most different from existing samples
                if min_similarity > best_diversity:
                    best_diversity = min_similarity
                    best_instance = candidate

            if best_instance:
                sampled.append(best_instance)
                remaining.remove(best_instance)

        return sampled

    def _sample_for_coverage(
        self,
        instances: list[list[dict[str, Any]]],
        max_samples: int = DEFAULT_MAX_CONFIG_SAMPLES,
    ) -> tuple[list[list[dict[str, Any]]], dict[int, dict[str, Any]]]:
        """
        Sample instances using greedy set cover to maximize unique resource types.

        Uses greedy algorithm to prioritize instances containing rare resource types,
        ensuring maximum node coverage in the pattern graph.

        Args:
            instances: Pool of instances to sample from
            max_samples: Maximum number of samples to return

        Returns:
            Tuple of (sampled_instances, instance_metadata) where:
            - sampled_instances: List of sampled instances
            - instance_metadata: Dict mapping instance index to metadata dict with:
                - 'types': Set of resource types in instance
        """
        logger.info(
            f"Coverage sampling: instances={len(instances)}, max_samples={max_samples}"
        )

        # Build type frequency map across all instances
        type_counts: dict[str, int] = {}
        instance_types: list[set[str]] = []

        for instance in instances:
            types_in_instance = set()
            for resource in instance:
                # Handle both dict and string (resource ID) formats
                if isinstance(resource, dict):
                    resource_type = resource.get("type", "unknown")
                elif isinstance(resource, str):
                    # Resource is just an ID string - skip for type counting
                    continue
                else:
                    resource_type = "unknown"
                types_in_instance.add(resource_type)
                type_counts[resource_type] = type_counts.get(resource_type, 0) + 1
            instance_types.append(types_in_instance)

        # Greedy set cover: prioritize instances with rare types
        sampled = []
        covered_types: set[str] = set()
        remaining_indices = list(range(len(instances)))

        for _ in range(min(max_samples, len(instances))):
            if not remaining_indices:
                break

            best_idx = None
            best_score = -1

            for idx in remaining_indices:
                # Calculate coverage score: prioritize rare uncovered types
                new_types = instance_types[idx] - covered_types
                if not new_types:
                    continue

                # Score based on rarity: sum of inverse frequencies
                score = sum(1.0 / type_counts[t] for t in new_types)

                if score > best_score:
                    best_score = score
                    best_idx = idx

            if best_idx is None:
                # No more new types to cover, sample randomly from remaining
                best_idx = random.choice(remaining_indices)

            sampled.append(instances[best_idx])
            covered_types.update(instance_types[best_idx])
            remaining_indices.remove(best_idx)

        # Build metadata dict
        metadata = {}
        for idx, instance in enumerate(sampled):
            metadata[idx] = {"types": instance_types[instances.index(instance)]}

        logger.info(
            f"Coverage sampling complete: {len(sampled)} instances "
            f"covering {len(covered_types)} unique resource types"
        )

        logger.debug(
            f"    Coverage sampling: selected {len(sampled)} instances covering "
            f"{len(covered_types)} unique resource types"
        )

        return sampled, metadata

    @staticmethod
    def _instance_similarity(
        instance1: list[dict[str, Any]], instance2: list[dict[str, Any]]
    ) -> float:
        """
        Compute similarity between two instances based on resource types.

        Uses Jaccard similarity: |intersection| / |union| of resource types.

        Args:
            instance1: First instance (list of resources)
            instance2: Second instance (list of resources)

        Returns:
            Similarity score (0.0 = completely different, 1.0 = identical types)
        """
        types1 = {r["type"] for r in instance1}
        types2 = {r["type"] for r in instance2}

        if not types1 and not types2:
            return 1.0

        intersection = len(types1 & types2)
        union = len(types1 | types2)

        return intersection / union if union > 0 else 0.0


__all__ = ["InstanceSelector"]
