from .creator_rule import CreatorRule
from .depends_on_rule import DependsOnRule
from .diagnostic_rule import DiagnosticRule
from .identity_rule import IdentityRule
from .monitoring_rule import MonitoringRule
from .network_rule import NetworkRule
from .region_rule import RegionRule
from .subnet_extraction_rule import SubnetExtractionRule
from .tag_rule import TagRule

ALL_RELATIONSHIP_RULES = [
    SubnetExtractionRule(),  # Extract subnets from VNets first
    NetworkRule(),
    IdentityRule(),
    TagRule(),
    RegionRule(),
    CreatorRule(),
    MonitoringRule(),
    DiagnosticRule(),
    DependsOnRule(),
]
