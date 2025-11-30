"""IaC emitters package for different target formats.

This package provides emitter implementations for various Infrastructure-as-Code
formats (Terraform, ARM templates, Bicep).

Complete emitter registry implemented with format-specific implementations:
- TerraformEmitter (production-ready, 49 resource types)
- ArmEmitter (cross-tenant support, Bug #107 fix)
- BicepEmitter (cross-tenant support, Bug #107 fix)
"""

from typing import Dict, Type

from .base import IaCEmitter

# Global emitter registry
_EMITTER_REGISTRY: Dict[str, Type[IaCEmitter]] = {}


def register_emitter(format_name: str, emitter_class: Type[IaCEmitter]) -> None:
    """Register an emitter class for a specific format.

    Args:
        format_name: Name of the IaC format (e.g., 'terraform', 'arm', 'bicep')
        emitter_class: Emitter class implementing IaCEmitter interface
    """
    _EMITTER_REGISTRY[format_name.lower()] = emitter_class


def get_emitter_registry() -> Dict[str, Type[IaCEmitter]]:
    """Get the current emitter registry.

    Returns:
        Dictionary mapping format names to emitter classes
    """
    return _EMITTER_REGISTRY.copy()


def get_emitter(format_name: str) -> Type[IaCEmitter]:
    """Get emitter class for specified format.

    Args:
        format_name: Name of the IaC format

    Returns:
        Emitter class for the specified format

    Raises:
        KeyError: If format is not registered
    """
    format_key = format_name.lower()
    if format_key not in _EMITTER_REGISTRY:
        available_formats = list(_EMITTER_REGISTRY.keys())
        raise KeyError(
            f"No emitter registered for format '{format_name}'. "
            f"Available formats: {available_formats}"
        )

    return _EMITTER_REGISTRY[format_key]


# Import emitter implementations to auto-register them
from . import (  # noqa: E402  # type: ignore  # pyright: ignore[reportUnusedImport]
    arm_emitter,  # pyright: ignore[reportUnusedImport]
    bicep_emitter,  # pyright: ignore[reportUnusedImport]
    terraform_emitter,  # pyright: ignore[reportUnusedImport]
)

__all__ = [
    "IaCEmitter",
    "get_emitter",
    "get_emitter_registry",
    "register_emitter",
]
