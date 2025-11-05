import os

from .creator_rule import CreatorRule
from .depends_on_rule import DependsOnRule
from .diagnostic_rule import DiagnosticRule
from .identity_rule import IdentityRule
from .monitoring_rule import MonitoringRule
from .network_rule import NetworkRule
from .region_rule import RegionRule
from .subnet_extraction_rule import SubnetExtractionRule
from .tag_rule import TagRule

# Feature flag for dual-graph architecture (Issue #420)
ENABLE_DUAL_GRAPH = os.getenv("ENABLE_DUAL_GRAPH", "false").lower() == "true"


def create_relationship_rules(enable_dual_graph: bool = ENABLE_DUAL_GRAPH):
    """
    Create all relationship rule instances with dual-graph support.

    Args:
        enable_dual_graph: Enable dual-graph relationship duplication

    Returns:
        List of relationship rule instances
    """
    return [
        SubnetExtractionRule(
            enable_dual_graph=enable_dual_graph
        ),  # Extract subnets from VNets first
        NetworkRule(enable_dual_graph=enable_dual_graph),
        IdentityRule(enable_dual_graph=enable_dual_graph),
        TagRule(enable_dual_graph=enable_dual_graph),
        RegionRule(enable_dual_graph=enable_dual_graph),
        CreatorRule(enable_dual_graph=enable_dual_graph),
        MonitoringRule(enable_dual_graph=enable_dual_graph),
        DiagnosticRule(enable_dual_graph=enable_dual_graph),
        DependsOnRule(enable_dual_graph=enable_dual_graph),
    ]


# Default rule list for backward compatibility (uses environment variable)
ALL_RELATIONSHIP_RULES = create_relationship_rules()
