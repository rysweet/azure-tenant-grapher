"""IaC translators for Azure Tenant Grapher."""

from .private_endpoint_translator import (
    PrivateEndpointTranslator,
    TranslationResult,
)

__all__ = [
    "PrivateEndpointTranslator",
    "TranslationResult",
]
