"""Resource filters for IaC generation.

This package provides filters that remove or modify resources
before IaC generation to prevent deployment errors.
"""

from .cross_tenant_filter import CrossTenantResourceFilter
from .existing_resource_filter import ExistingResourceFilter

__all__ = [
    "CrossTenantResourceFilter",
    "ExistingResourceFilter",
]
