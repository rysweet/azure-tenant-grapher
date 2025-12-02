"""Handler registry for resource type dispatch.

This module provides the HandlerRegistry class that manages registration
and lookup of resource handlers based on Azure resource types.
"""

import logging
from typing import Dict, List, Optional, Type

from ..base_handler import ResourceHandler

logger = logging.getLogger(__name__)


class HandlerRegistry:
    """Registry for resource handlers with type-based dispatch.

    The registry maintains a list of handler classes and provides
    efficient lookup by Azure resource type.

    Usage:
        @handler
        class MyHandler(ResourceHandler):
            HANDLED_TYPES = {"Microsoft.Storage/storageAccounts"}
            ...

        # Later:
        handler = HandlerRegistry.get_handler("Microsoft.Storage/storageAccounts")
        if handler:
            result = handler.emit(resource, context)
    """

    _handlers: List[Type[ResourceHandler]] = []
    _type_cache: Dict[str, Type[ResourceHandler]] = {}

    @classmethod
    def register(cls, handler_class: Type[ResourceHandler]) -> Type[ResourceHandler]:
        """Register a handler class.

        Use as decorator:
            @HandlerRegistry.register
            class MyHandler(ResourceHandler):
                ...

        Args:
            handler_class: Handler class to register

        Returns:
            The handler class (unchanged)
        """
        # Avoid duplicate registration
        if handler_class not in cls._handlers:
            cls._handlers.append(handler_class)

            # Pre-populate cache for fast lookup
            for azure_type in handler_class.HANDLED_TYPES:
                cls._type_cache[azure_type.lower()] = handler_class
                logger.debug(
                    f"Registered handler {handler_class.__name__} for {azure_type}"
                )

        return handler_class

    @classmethod
    def get_handler(cls, azure_type: str) -> Optional[ResourceHandler]:
        """Get handler instance for Azure type.

        Args:
            azure_type: Azure resource type (e.g., "Microsoft.Compute/virtualMachines")

        Returns:
            Handler instance or None if no handler registered
        """
        azure_type_lower = azure_type.lower()

        # Fast path: cached lookup
        if azure_type_lower in cls._type_cache:
            return cls._type_cache[azure_type_lower]()

        # Slow path: iterate handlers (for flexible matching)
        for handler_class in cls._handlers:
            if handler_class.can_handle(azure_type):
                # Cache for next time
                cls._type_cache[azure_type_lower] = handler_class
                return handler_class()

        return None

    @classmethod
    def get_all_supported_types(cls) -> List[str]:
        """Get all Azure types supported by registered handlers.

        Returns:
            Sorted list of supported Azure resource types
        """
        types = set()
        for handler_class in cls._handlers:
            types.update(handler_class.HANDLED_TYPES)
        return sorted(types)

    @classmethod
    def get_all_handlers(cls) -> List[Type[ResourceHandler]]:
        """Get all registered handler classes.

        Returns:
            List of handler classes (copy)
        """
        return cls._handlers.copy()

    @classmethod
    def clear(cls) -> None:
        """Clear all registered handlers.

        Primarily for testing.
        """
        cls._handlers = []
        cls._type_cache = {}


def handler(cls: Type[ResourceHandler]) -> Type[ResourceHandler]:
    """Decorator to register a handler class.

    Usage:
        @handler
        class StorageAccountHandler(ResourceHandler):
            HANDLED_TYPES = {"Microsoft.Storage/storageAccounts"}
            ...
    """
    return HandlerRegistry.register(cls)


# Import all handler modules to trigger registration
# This must be at the bottom after the registry is defined
def _register_all_handlers() -> None:
    """Import all handler modules to trigger registration."""
    # Storage handlers
    # Automation handlers
    from .automation import automation_account, runbook

    # Compute handlers
    from .compute import (
        disks,
        ssh_public_key,
        virtual_machine,
        vm_extensions,
    )

    # Container handlers
    from .container import (
        aks,
        container_app,
        container_group,
        container_registry,
    )

    # Database handlers
    from .database import cosmosdb, postgresql, sql_database, sql_server

    # DevTest handlers
    from .devtest import devtest_lab, devtest_schedule, devtest_vm

    # Identity handlers
    from .identity import (
        entra_group,
        entra_user,
        managed_identity,
        role_assignment,
        service_principal,
    )

    # KeyVault handlers
    from .keyvault import vault

    # Misc handlers
    from .misc import (
        app_config,
        data_factory,
        databricks,
        dns_zone,
        eventhub,
        recovery_vault,
        redis,
        resource_group,
        search_service,
        servicebus,
        waf_policy,
    )

    # ML handlers
    from .ml import cognitive_services, ml_workspace

    # Monitoring handlers
    from .monitoring import (
        action_group,
        app_insights,
        dcr,
        log_analytics,
        metric_alert,
    )

    # Network handlers
    from .network import (
        application_gateway,
        bastion,
        load_balancer,
        nat_gateway,
        nic,
        nsg,
        nsg_associations,
        public_ip,
        route_table,
        subnet,
        vnet,
    )
    from .storage import storage_account

    # Web handlers
    from .web import app_service, service_plan, static_web_app

    logger.info(
        f"Registered {len(HandlerRegistry._handlers)} handlers "
        f"covering {len(HandlerRegistry.get_all_supported_types())} Azure types"
    )


# Delay registration until first use to allow handler files to be created
_handlers_registered = False


def ensure_handlers_registered() -> None:
    """Ensure all handlers are registered.

    Called lazily on first handler lookup.
    """
    global _handlers_registered
    if not _handlers_registered:
        try:
            _register_all_handlers()
        except ImportError as e:
            # During development, some handlers may not exist yet
            logger.warning(f"Some handlers not available: {e}")
        _handlers_registered = True
