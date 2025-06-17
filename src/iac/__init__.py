"""Infrastructure-as-Code generation package for Azure Tenant Grapher.

This package provides scaffolding for converting Neo4j graph data into
Infrastructure-as-Code templates (Terraform, ARM, Bicep).

TODO: Implement complete IaC generation pipeline.
"""

from .cli_handler import generate_iac_command_handler
from .emitters import IaCEmitter, get_emitter_registry
from .engine import TransformationEngine, TransformationRule
from .traverser import GraphTraverser, TenantGraph

__all__ = [
    "GraphTraverser",
    "IaCEmitter",
    "TenantGraph",
    "TransformationEngine",
    "TransformationRule",
    "generate_iac_command_handler",
    "get_emitter_registry",
]
