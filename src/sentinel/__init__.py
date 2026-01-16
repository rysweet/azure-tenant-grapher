"""Sentinel integration module for Azure Tenant Grapher.

This module provides both single-tenant and multi-tenant Azure Sentinel integration
capabilities following the brick philosophy - self-contained, regeneratable modules.

Philosophy:
- Modular design (bricks & studs)
- Clear public contracts via __all__
- No breaking changes across versions
- Working code only (no stubs, no TODOs)

Public API:
- multi_tenant: Multi-tenant MSSP operations (Lighthouse, aggregation)
- (single_tenant functionality would be here if integrated)
"""

__all__ = ["multi_tenant"]
