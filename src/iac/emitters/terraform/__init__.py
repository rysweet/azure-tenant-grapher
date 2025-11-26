"""Terraform emitter package for Azure resource IaC generation.

This package provides handler-based Terraform configuration generation
from Azure resources. The architecture follows a Strategy pattern where
individual handlers are responsible for specific Azure resource types.

Main Components:
- TerraformEmitter: Main orchestrator for emission process
- EmitterContext: Shared state passed to all handlers
- ResourceHandler: Abstract base class for handlers
- HandlerRegistry: Registry for handler lookup by Azure type

Usage:
    from src.iac.emitters.terraform import TerraformEmitter

    emitter = TerraformEmitter(
        target_subscription_id="xxx-xxx-xxx",
        target_tenant_id="yyy-yyy-yyy",
    )
    config = emitter.emit(resources)
    emitter.write(config, Path("/output"))
"""

from .context import EmitterContext
from .emitter import TerraformEmitter
from .handlers import HandlerRegistry, ensure_handlers_registered, handler

__all__ = [
    "EmitterContext",
    "HandlerRegistry",
    "TerraformEmitter",
    "ensure_handlers_registered",
    "handler",
]

# Version for tracking compatibility
__version__ = "2.0.0"  # Handler-based architecture
