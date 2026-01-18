"""
Pattern detection for architectural analysis.

This module detects common Azure architectural patterns in resource graphs.
Extracted from architectural_pattern_analyzer.py god object (Issue #714).

Philosophy:
- Single Responsibility: Pattern detection only
- Brick & Studs: Public API via PatternDetector class
- Ruthless Simplicity: Pattern matching with NetworkX
- Zero-BS: All detection logic works, no stubs
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import networkx as nx

logger = logging.getLogger(__name__)

# Define architectural patterns with their characteristic resources
ARCHITECTURAL_PATTERNS = {
    "Web Application": {
        "resources": ["sites", "serverFarms", "storageAccounts", "components"],
        "description": "App Service web application with storage and monitoring",
    },
    "Virtual Machine Workload": {
        "resources": [
            "virtualMachines",
            "disks",
            "networkInterfaces",
            "virtualNetworks",
            "networkSecurityGroups",
        ],
        "description": "IaaS VM with networking and storage",
    },
    "Container Platform": {
        "resources": [
            "managedClusters",
            "containerRegistries",
            "virtualNetworks",
            "loadBalancers",
        ],
        "description": "AKS or container-based platform",
    },
    "Data Platform": {
        "resources": [
            "servers",
            "databases",
            "storageAccounts",
            "privateEndpoints",
        ],
        "description": "Database with secure connectivity and storage",
    },
    "Serverless Application": {
        "resources": ["sites", "storageAccounts", "components", "vaults"],
        "description": "Function App with storage, monitoring, and secrets",
    },
    "Data Analytics": {
        "resources": ["clusters", "workspaces", "storageAccounts", "namespaces"],
        "description": "Analytics platform with data ingestion and storage",
    },
    "Secure Workload": {
        "resources": [
            "vaults",
            "privateEndpoints",
            "privateDnsZones",
            "networkInterfaces",
        ],
        "description": "Resources with private networking and Key Vault",
    },
    "Managed Identity Pattern": {
        "resources": [
            "userAssignedIdentities",
            "sites",
            "managedClusters",
            "virtualMachines",
        ],
        "description": "Resources using managed identities for authentication",
    },
    "Monitoring & Observability": {
        "resources": [
            "components",
            "workspaces",
            "dataCollectionRules",
            "smartDetectorAlertRules",
        ],
        "description": "Application Insights and Log Analytics monitoring",
    },
    "Network Security": {
        "resources": [
            "networkSecurityGroups",
            "virtualNetworks",
            "subnets",
            "bastionHosts",
        ],
        "description": "Network isolation and secure access",
    },
}


class PatternDetector:
    """
    Detects architectural patterns in resource graphs.

    Analyzes NetworkX graphs to identify common Azure architectural patterns
    based on resource types and their connections.
    """

    def detect_patterns(
        self, graph: nx.MultiDiGraph[str], resource_type_counts: Dict[str, int]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Detect architectural patterns in the graph.

        Args:
            graph: NetworkX graph of resources
            resource_type_counts: Resource type frequency counts

        Returns:
            Dictionary of detected patterns with match information
        """
        pattern_matches = {}
        existing_resources = set(graph.nodes())

        for pattern_name, pattern_info in ARCHITECTURAL_PATTERNS.items():
            pattern_resources = set(pattern_info["resources"])
            matched_resources = pattern_resources.intersection(existing_resources)

            if len(matched_resources) >= 2:
                connection_count = 0
                pattern_edges = []

                for source in matched_resources:
                    for target in matched_resources:
                        if source != target and graph.has_edge(source, target):
                            edges = graph.get_edge_data(source, target)
                            if edges:
                                for _key, data in edges.items():
                                    connection_count += data.get("frequency", 1)
                                    pattern_edges.append(
                                        (source, data["relationship"], target)
                                    )

                pattern_matches[pattern_name] = {
                    "matched_resources": list(matched_resources),
                    "missing_resources": list(pattern_resources - matched_resources),
                    "connection_count": connection_count,
                    "pattern_edges": pattern_edges[:5],  # Top 5 edges
                    "completeness": len(matched_resources)
                    / len(pattern_resources)
                    * 100,
                }

        logger.info(str(f"Detected {len(pattern_matches)} architectural patterns"))
        return pattern_matches


__all__ = ["PatternDetector", "ARCHITECTURAL_PATTERNS"]
