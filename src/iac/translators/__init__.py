"""IaC translators for Azure Tenant Grapher."""

from .coordinator import (
    TranslationContext,
    TranslationCoordinator,
)
from .private_endpoint_translator import (
    PrivateEndpointTranslator,
    TranslationResult,
)
from .registry import (
    TranslatorRegistry,
    register_translator,
)

__all__ = [
    "PrivateEndpointTranslator",
    "TranslationContext",
    "TranslationCoordinator",
    "TranslationResult",
    "TranslatorRegistry",
    "register_translator",
]
