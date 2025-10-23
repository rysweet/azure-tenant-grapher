"""Resource transformers for IaC generation.

This package provides transformers that modify resources
before IaC generation to ensure valid deployment configurations.
"""

from .bastion_nsg_rules import BastionNSGRuleGenerator
from .location_mapper import GlobalLocationMapper
from .name_generator import UniqueNameGenerator

__all__ = [
    "BastionNSGRuleGenerator",
    "GlobalLocationMapper",
    "UniqueNameGenerator",
]
