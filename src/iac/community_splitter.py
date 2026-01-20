"""Community-based Terraform file splitting.

Philosophy:
- Single responsibility: Split Terraform config by graph community
- Self-contained: No dependencies on emitter internals
- Regeneratable: Can be rebuilt from this spec

Public API:
    CommunitySplitter: Main splitting logic
    CommunityManifest: Metadata structure

Issue #473: Community-based Terraform splitting for parallel deployment
"""

import json
import logging
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CommunityManifest:
    """Metadata for community-split Terraform files."""

    total_communities: int
    total_resources: int
    communities: List[Dict[str, Any]]
    generated_at: str
    split_strategy: str = "graph_connectivity"


class CommunitySplitter:
    """Split Terraform configuration by graph communities.

    Uses CommunityDetector to identify connected components and generates
    separate Terraform files per community for parallel deployment.
    """

    def __init__(self, community_detector):
        """Initialize with community detector.

        Args:
            community_detector: CommunityDetector instance
        """
        self.detector = community_detector

    def split_terraform(
        self, terraform_config: Dict[str, Any], out_dir: Path
    ) -> Tuple[List[Path], CommunityManifest]:
        """Split Terraform config into per-community files.

        Args:
            terraform_config: Full Terraform configuration
            out_dir: Output directory

        Returns:
            (list_of_file_paths, manifest)

        Raises:
            ValueError: If cross-community references detected
        """
        # 1. Detect communities
        communities = self.detector.detect_communities()
        logger.info(f"Detected {len(communities)} communities")

        # 2. Build resource-to-community mapping
        resource_map = self._build_resource_map(communities)

        # 3. Split resources by community
        community_configs = self._split_by_community(terraform_config, resource_map)

        # 4. Validate no cross-community references
        self._validate_references(community_configs, resource_map)

        # 5. Write files
        files = self._write_community_files(community_configs, out_dir)

        # 6. Generate manifest
        manifest = self._generate_manifest(communities, community_configs, files)
        manifest_path = out_dir / "community_manifest.json"
        manifest_path.write_text(json.dumps(asdict(manifest), indent=2))
        files.append(manifest_path)

        return files, manifest

    def _build_resource_map(self, communities: List[Set[str]]) -> Dict[str, int]:
        """Build mapping from resource ID to community ID.

        Args:
            communities: List of sets of resource IDs

        Returns:
            Dict mapping resource_id -> community_id
        """
        resource_map = {}
        for comm_id, community in enumerate(communities):
            for resource_id in community:
                resource_map[resource_id] = comm_id
        return resource_map

    def _split_by_community(
        self, terraform_config: Dict[str, Any], resource_map: Dict[str, int]
    ) -> Dict[int, Dict[str, Any]]:
        """Partition resources into per-community configs.

        Args:
            terraform_config: Full Terraform config
            resource_map: Resource ID to community ID mapping

        Returns:
            Dict mapping community_id -> terraform_config
        """
        community_configs: Dict[int, Dict[str, Any]] = defaultdict(
            lambda: {"provider": {"azurerm": [{"features": {}}]}, "resource": {}}
        )

        # Split resources by community
        for resource_type, resources in terraform_config.get("resource", {}).items():
            for resource_name, resource_body in resources.items():
                # Try multiple strategies to match resource to community
                # 1. Exact ID match from resource body
                resource_id = resource_body.get("id")
                comm_id = resource_map.get(resource_id) if resource_id else None

                # 2. Try resource_type.resource_name format (Terraform reference format)
                if comm_id is None:
                    tf_ref = f"{resource_type}.{resource_name}"
                    comm_id = resource_map.get(tf_ref)

                # 3. Try just the resource name
                if comm_id is None:
                    comm_id = resource_map.get(resource_name)

                if comm_id is None:
                    # Resource not in any community - skip
                    logger.warning(
                        f"Resource {resource_type}.{resource_name} not in any community "
                        f"(tried: {resource_id}, {resource_type}.{resource_name}, {resource_name})"
                    )
                    continue

                # Add to community config
                if resource_type not in community_configs[comm_id]["resource"]:
                    community_configs[comm_id]["resource"][resource_type] = {}

                community_configs[comm_id]["resource"][resource_type][resource_name] = (
                    resource_body
                )

        return dict(community_configs)

    def _validate_references(
        self,
        community_configs: Dict[int, Dict[str, Any]],
        resource_map: Dict[str, int],
    ) -> None:
        """Validate no cross-community resource references.

        Args:
            community_configs: Per-community Terraform configs
            resource_map: Resource ID to community ID mapping

        Raises:
            ValueError: If cross-community references detected
        """
        violations = []

        for comm_id, config in community_configs.items():
            for resource_type, resources in config.get("resource", {}).items():
                for resource_name, resource_body in resources.items():
                    # Extract all Terraform references (format: ${azurerm_*.*.id})
                    refs = self._extract_references(resource_body)

                    for ref in refs:
                        # Parse reference: "azurerm_virtual_network.vnet1.id" -> ("azurerm_virtual_network", "vnet1")
                        parts = ref.split(".")
                        if len(parts) >= 2:
                            ref_type, ref_name = parts[0], parts[1]
                            ref_resource_key = f"{ref_type}.{ref_name}"

                            # Check if referenced resource is in a different community
                            ref_comm_id = resource_map.get(ref_resource_key)
                            if ref_comm_id is not None and ref_comm_id != comm_id:
                                violations.append(
                                    f"{resource_type}.{resource_name} (community {comm_id}) "
                                    f"references {ref_resource_key} (community {ref_comm_id})"
                                )

        if violations:
            raise ValueError(
                f"Found {len(violations)} cross-community reference(s). "
                f"Communities must be independent deployment units. "
                f"Violations: {', '.join(violations)}"
            )

    def _extract_references(self, resource_body: Dict[str, Any]) -> List[str]:
        """Extract Terraform references from resource body.

        Args:
            resource_body: Terraform resource configuration

        Returns:
            List of reference strings
        """
        refs = []
        body_str = json.dumps(resource_body)

        # Pattern: ${azurerm_*.*.id} or similar (case-insensitive for Azure resource types)
        pattern = r"\$\{([a-zA-Z_]+\.[a-zA-Z0-9_]+\.[a-zA-Z_]+)\}"
        matches = re.findall(pattern, body_str)
        refs.extend(matches)

        return refs

    def _write_community_files(
        self, community_configs: Dict[int, Dict[str, Any]], out_dir: Path
    ) -> List[Path]:
        """Write per-community Terraform files.

        Args:
            community_configs: Per-community configs
            out_dir: Output directory

        Returns:
            List of created file paths
        """
        out_dir.mkdir(parents=True, exist_ok=True)
        files = []

        # Sort by community ID for deterministic output
        for comm_id in sorted(community_configs.keys()):
            config = community_configs[comm_id]

            # Count resources
            resource_count = sum(
                len(resources) for resources in config.get("resource", {}).values()
            )

            # Find dominant resource type
            type_counts = {
                rtype: len(resources)
                for rtype, resources in config.get("resource", {}).items()
            }
            dominant_type = (
                max(type_counts, key=lambda k: type_counts[k]).split("_")[-1]
                if type_counts
                else "resources"
            )

            # Generate filename
            filename = f"community_{comm_id}_{resource_count}_{dominant_type}.tf.json"
            filepath = out_dir / filename

            # Write file
            filepath.write_text(json.dumps(config, indent=2))
            files.append(filepath)

            logger.info(
                f"Created {filename}: {resource_count} resources, "
                f"dominant type: {dominant_type}"
            )

        return files

    def _generate_manifest(
        self,
        communities: List[Set[str]],
        community_configs: Dict[int, Dict[str, Any]],
        files: List[Path],
    ) -> CommunityManifest:
        """Generate community manifest with metadata.

        Args:
            communities: List of resource ID sets
            community_configs: Per-community Terraform configs
            files: List of created files

        Returns:
            CommunityManifest with complete metadata
        """
        total_resources = sum(
            sum(len(resources) for resources in config.get("resource", {}).values())
            for config in community_configs.values()
        )

        community_metadata = []
        for comm_id, filepath in enumerate(files):
            if filepath.name == "community_manifest.json":
                continue

            config = community_configs.get(comm_id, {})
            resource_types = {}
            for rtype, resources in config.get("resource", {}).items():
                resource_types[rtype] = len(resources)

            dominant_type = (
                max(resource_types, key=lambda k: resource_types[k])
                if resource_types
                else "unknown"
            )

            community_metadata.append(
                {
                    "id": comm_id,
                    "file": filepath.name,
                    "size": len(communities[comm_id])
                    if comm_id < len(communities)
                    else 0,
                    "resource_types": resource_types,
                    "dominant_type": dominant_type,
                }
            )

        return CommunityManifest(
            total_communities=len(communities),
            total_resources=total_resources,
            communities=community_metadata,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


__all__ = ["CommunityManifest", "CommunitySplitter"]
