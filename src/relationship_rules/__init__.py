from .creator_rule import CreatorRule
from .depends_on_rule import DependsOnRule
from .diagnostic_rule import DiagnosticRule
from .identity_rule import IdentityRule
from .monitoring_rule import MonitoringRule
from .network_rule_optimized import NetworkRuleOptimized
from .nic_relationship_rule import NICRelationshipRule
from .region_rule import RegionRule
from .secret_rule import SecretRule
from .subnet_extraction_rule import SubnetExtractionRule
from .tag_rule import TagRule


def create_relationship_rules():
    """
    Create all relationship rule instances with dual-graph support.

    FIX Issue #873: Disable auto-flush to prevent flushing before target nodes exist.
    Relationships are now buffered during processing and flushed at the end when all
    nodes are guaranteed to exist.

    Returns:
        List of relationship rule instances
    """
    return [
        SubnetExtractionRule(
            enable_dual_graph=True, enable_auto_flush=False
        ),  # Extract subnets from VNets first
        NetworkRuleOptimized(
            enable_dual_graph=True, enable_auto_flush=False
        ),  # 100-400x faster with batching
        NICRelationshipRule(
            enable_dual_graph=True, enable_auto_flush=False
        ),  # NIC → Subnet relationships (Issue #873)
        IdentityRule(enable_dual_graph=True, enable_auto_flush=False),
        TagRule(enable_dual_graph=True, enable_auto_flush=False),
        RegionRule(enable_dual_graph=True, enable_auto_flush=False),
        CreatorRule(enable_dual_graph=True, enable_auto_flush=False),
        MonitoringRule(enable_dual_graph=True, enable_auto_flush=False),
        DiagnosticRule(enable_dual_graph=True, enable_auto_flush=False),
        DependsOnRule(enable_dual_graph=True, enable_auto_flush=False),
        SecretRule(
            enable_dual_graph=True, enable_auto_flush=False
        ),  # KeyVault secrets (Issue #478)
    ]


# Default rule list with dual-graph enabled
ALL_RELATIONSHIP_RULES = create_relationship_rules()
