from .creator_rule import CreatorRule
from .depends_on_rule import DependsOnRule
from .diagnostic_rule import DiagnosticRule
from .identity_rule import IdentityRule
from .monitoring_rule import MonitoringRule
from .network_rule_optimized import NetworkRuleOptimized
from .region_rule import RegionRule
from .secret_rule import SecretRule
from .subnet_extraction_rule import SubnetExtractionRule
from .tag_rule import TagRule


def create_relationship_rules():
    """
    Create all relationship rule instances with dual-graph support.

    Returns:
        List of relationship rule instances
    """
    return [
        SubnetExtractionRule(
            enable_dual_graph=True
        ),  # Extract subnets from VNets first
        NetworkRuleOptimized(enable_dual_graph=True),  # 100-400x faster with batching
        IdentityRule(enable_dual_graph=True),
        TagRule(enable_dual_graph=True),
        RegionRule(enable_dual_graph=True),
        CreatorRule(enable_dual_graph=True),
        MonitoringRule(enable_dual_graph=True),
        DiagnosticRule(enable_dual_graph=True),
        DependsOnRule(enable_dual_graph=True),
        SecretRule(enable_dual_graph=True),  # KeyVault secrets (Issue #478)
    ]


# Default rule list with dual-graph enabled
ALL_RELATIONSHIP_RULES = create_relationship_rules()
