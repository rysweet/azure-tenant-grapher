"""IaC translators for Azure Tenant Grapher."""

from .appservice_translator import (
    AppServiceTranslator,
)
from .base_translator import (
    BaseTranslator,
    TranslationContext,
    TranslationResult,
)
from .coordinator import (
    TranslationCoordinator,
)
from .database_translator import (
    DatabaseTranslator,
)
from .entraid_translator import (
    EntraIdTranslator,
)
from .keyvault_translator import (
    KeyVaultTranslator,
)
from .managed_identity_translator import (
    ManagedIdentityTranslator,
)
from .private_endpoint_translator import (
    PrivateEndpointTranslator,
)
from .registry import (
    TranslatorRegistry,
    register_translator,
)
from .storage_account_translator import (
    StorageAccountTranslator,
)

__all__ = [
    "AppServiceTranslator",
    "BaseTranslator",
    "DatabaseTranslator",
    "EntraIdTranslator",
    "KeyVaultTranslator",
    "ManagedIdentityTranslator",
    "PrivateEndpointTranslator",
    "StorageAccountTranslator",
    "TranslationContext",
    "TranslationCoordinator",
    "TranslationResult",
    "TranslatorRegistry",
    "register_translator",
]
