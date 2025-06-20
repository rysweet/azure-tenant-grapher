from .creator_rule import CreatorRule
from .depends_on_rule import DependsOnRule
from .identity_rule import IdentityRule
from .monitoring_rule import MonitoringRule
from .network_rule import NetworkRule
from .region_rule import RegionRule
from .tag_rule import TagRule

ALL_RELATIONSHIP_RULES = [
    NetworkRule(),
    IdentityRule(),
    TagRule(),
    RegionRule(),
    CreatorRule(),
    MonitoringRule(),
    DependsOnRule(),
]
