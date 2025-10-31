"""
Translator registry for automatic translator discovery and orchestration.

This module provides a registry pattern for managing resource translators:
- Decorator-based registration (@register_translator)
- Singleton registry (one per process)
- Thread-safe operations
- Automatic discovery and instantiation

Usage:
    @register_translator
    class MyTranslator(BaseTranslator):
        ...

    # Later, in the emitter:
    translators = TranslatorRegistry.create_translators(context)
"""

import logging
import threading
from typing import Any, List, Optional, Set, Type

logger = logging.getLogger(__name__)


class TranslatorRegistry:
    """
    Registry for resource translators.

    Uses automatic discovery pattern: translators register themselves
    via @register_translator decorator. Zero coupling between registry
    and specific translator implementations.

    Thread-safe singleton pattern ensures only one registry per process.
    """

    _lock = threading.RLock()
    _translators: List[Type["BaseTranslator"]] = []
    _registration_complete = False

    @classmethod
    def register(cls, translator_class: Type["BaseTranslator"]) -> None:
        """
        Register a translator class.

        Thread-safe registration. Prevents duplicate registrations.

        Args:
            translator_class: Translator class to register (must inherit from BaseTranslator)

        Raises:
            TypeError: If translator_class is not a class or doesn't inherit from BaseTranslator
        """
        with cls._lock:
            # Validation
            if not isinstance(translator_class, type):
                raise TypeError(
                    f"Expected a class, got {type(translator_class).__name__}"
                )

            # Check for BaseTranslator inheritance (import check deferred to avoid circular imports)
            # We'll do a duck-type check for required methods instead
            required_methods = ["can_translate", "translate", "get_translation_results"]
            missing_methods = [
                method
                for method in required_methods
                if not hasattr(translator_class, method)
            ]

            if missing_methods:
                raise TypeError(
                    f"Translator class {translator_class.__name__} missing required methods: "
                    f"{', '.join(missing_methods)}"
                )

            # Check for duplicate registration
            if translator_class in cls._translators:
                logger.debug(
                    f"Translator {translator_class.__name__} already registered, skipping"
                )
                return

            cls._translators.append(translator_class)
            logger.info(f"Registered translator: {translator_class.__name__}")

    @classmethod
    def get_translator(cls, resource_type: str) -> Optional[Type["BaseTranslator"]]:
        """
        Get a translator class that can handle a specific resource type.

        Args:
            resource_type: Azure resource type (e.g., "Microsoft.Storage/storageAccounts")

        Returns:
            Translator class that can handle the resource type, or None if not found

        Note:
            This returns the first matching translator. If multiple translators
            can handle the same resource type, the first registered one wins.
        """
        with cls._lock:
            for translator_class in cls._translators:
                # Check if translator has supported_resource_types property
                if hasattr(translator_class, "supported_resource_types"):
                    supported_types = translator_class.supported_resource_types
                    if isinstance(supported_types, property):
                        # Skip properties that need instance
                        continue
                    if resource_type in supported_types:
                        return translator_class

            return None

    @classmethod
    def get_all_translators(cls) -> List[Type["BaseTranslator"]]:
        """
        Get all registered translator classes.

        Returns:
            List of all registered translator classes
        """
        with cls._lock:
            return cls._translators.copy()

    @classmethod
    def create_translator_instance(
        cls, resource_type: str, context: "TranslationContext"
    ) -> Optional["BaseTranslator"]:
        """
        Create a translator instance for a specific resource type.

        Args:
            resource_type: Azure resource type
            context: Translation context

        Returns:
            Translator instance, or None if no translator found
        """
        translator_class = cls.get_translator(resource_type)
        if not translator_class:
            return None

        try:
            return translator_class(context)
        except Exception as e:
            logger.error(
                f"Failed to instantiate translator {translator_class.__name__}: {e}"
            )
            return None

    @classmethod
    def create_translators(
        cls, context: "TranslationContext"
    ) -> List["BaseTranslator"]:
        """
        Create instances of all registered translators.

        Args:
            context: Translation context to pass to translators

        Returns:
            List of translator instances

        Note:
            Gracefully handles instantiation failures by logging errors
            and continuing with remaining translators.
        """
        translators = []

        with cls._lock:
            for translator_class in cls._translators:
                try:
                    translator = translator_class(context)
                    translators.append(translator)
                    logger.debug(
                        f"Instantiated translator: {translator_class.__name__}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to instantiate translator {translator_class.__name__}: {e}",
                        exc_info=True,
                    )

        if not translators:
            logger.warning("No translators were successfully instantiated")
        else:
            logger.info(
                f"Created {len(translators)} translator instances: "
                f"{[t.__class__.__name__ for t in translators]}"
            )

        return translators

    @classmethod
    def get_supported_resource_types(cls) -> Set[str]:
        """
        Get all resource types supported by registered translators.

        Returns:
            Set of Azure resource types that can be translated

        Note:
            Only includes translators with static supported_resource_types attribute.
            Translators using instance properties will not be included.
        """
        supported_types: Set[str] = set()

        with cls._lock:
            for translator_class in cls._translators:
                if hasattr(translator_class, "supported_resource_types"):
                    types = translator_class.supported_resource_types
                    if isinstance(types, (list, set, tuple)):
                        supported_types.update(types)

        return supported_types

    @classmethod
    def get_registered_translators(cls) -> List[str]:
        """
        Get names of all registered translators.

        Returns:
            List of translator class names
        """
        with cls._lock:
            return [t.__name__ for t in cls._translators]

    @classmethod
    def clear(cls) -> None:
        """
        Clear all registered translators.

        Warning:
            This should only be used in testing. In production, translators
            are registered once at module import time and remain registered
            for the lifetime of the process.
        """
        with cls._lock:
            cls._translators.clear()
            cls._registration_complete = False
            logger.debug("Cleared translator registry")

    @classmethod
    def count(cls) -> int:
        """
        Get count of registered translators.

        Returns:
            Number of registered translators
        """
        with cls._lock:
            return len(cls._translators)


def register_translator(
    translator_class: Type["BaseTranslator"],
) -> Type["BaseTranslator"]:
    """
    Decorator to register a translator class.

    Usage:
        @register_translator
        class MyTranslator(BaseTranslator):
            @property
            def supported_resource_types(self):
                return ["azurerm_storage_account"]

            def can_translate(self, resource):
                return resource.get("type") == "azurerm_storage_account"

            def translate(self, resource):
                # Translation logic here
                return resource

    Args:
        translator_class: Translator class to register

    Returns:
        The translator class (unmodified)

    Raises:
        TypeError: If translator_class is invalid
    """
    TranslatorRegistry.register(translator_class)
    return translator_class


# Type hints for forward references
# These will be properly resolved when base_translator.py imports this module
try:
    from .base_translator import BaseTranslator, TranslationContext
except ImportError:
    # Allow module to load even if base_translator doesn't exist yet
    # This enables proper sequencing during initial implementation
    BaseTranslator = Any  # type: ignore
    TranslationContext = Any  # type: ignore
