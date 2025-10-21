"""
Data plane plugin registry and discovery system.

This module provides a centralized registry for discovering and accessing
data plane replication plugins. Plugins are automatically discovered and
registered based on their supported resource types.

Example:
    # Get plugin for a resource
    plugin = PluginRegistry.get_plugin_for_resource(resource)

    # Discover all data plane items
    items = plugin.discover(resource)

    # Generate replication code
    code = plugin.generate_replication_code(items)
"""

import logging
from typing import Dict, List, Optional, Type

from .base_plugin import DataPlaneItem, DataPlanePlugin, ReplicationResult

logger = logging.getLogger(__name__)


class PluginRegistry:
    """
    Registry for data plane replication plugins.

    The registry maintains a mapping of Azure resource types to their
    corresponding data plane plugins. It provides methods to discover,
    register, and retrieve plugins.

    Plugins are registered either automatically via discover_plugins()
    or manually via register_plugin().
    """

    _plugins: Dict[str, DataPlanePlugin] = {}
    _initialized: bool = False

    @classmethod
    def register_plugin(cls, plugin: DataPlanePlugin) -> None:
        """
        Register a data plane plugin.

        Args:
            plugin: Plugin instance to register

        Raises:
            ValueError: If plugin has no supported_resource_type
        """
        resource_type = plugin.supported_resource_type
        if not resource_type:
            raise ValueError(
                f"Plugin {plugin.plugin_name} has no supported_resource_type"
            )

        if resource_type in cls._plugins:
            logger.warning(
                f"Overwriting existing plugin for resource type '{resource_type}'"
            )

        cls._plugins[resource_type] = plugin
        logger.info(
            f"Registered plugin '{plugin.plugin_name}' for resource type '{resource_type}'"
        )

    @classmethod
    def get_plugin(cls, resource_type: str) -> Optional[DataPlanePlugin]:
        """
        Get plugin for a specific resource type.

        Args:
            resource_type: Azure resource type (e.g., "Microsoft.KeyVault/vaults")

        Returns:
            Plugin instance if registered, None otherwise
        """
        if not cls._initialized:
            cls.discover_plugins()

        return cls._plugins.get(resource_type)

    @classmethod
    def get_plugin_for_resource(
        cls, resource: Dict[str, any]
    ) -> Optional[DataPlanePlugin]:
        """
        Get plugin for a resource dictionary.

        Attempts to find the most specific plugin that validates the resource.
        For Microsoft.Web/sites, will prefer FunctionAppPlugin for Function Apps
        and AppServicePlugin for regular web apps.

        Args:
            resource: Resource dictionary containing 'type' field

        Returns:
            Plugin instance if available for resource type, None otherwise
        """
        if not resource:
            logger.warning("Resource is None or empty, cannot determine plugin")
            return None

        resource_type = resource.get("type", "")
        if not resource_type:
            logger.warning("Resource missing 'type' field, cannot determine plugin")
            return None

        # For Microsoft.Web/sites, we need to check if it's a Function App
        # FunctionAppPlugin and AppServicePlugin both support this type
        if resource_type == "Microsoft.Web/sites":
            if not cls._initialized:
                cls.discover_plugins()

            # Try FunctionAppPlugin first (for Function Apps)
            from .functionapp_plugin import FunctionAppPlugin

            function_app_plugin = FunctionAppPlugin()
            if function_app_plugin.validate_resource(resource):
                logger.debug(
                    f"Selected FunctionAppPlugin for resource {resource.get('name')}"
                )
                return function_app_plugin

            # Fall back to AppServicePlugin (for regular web apps)
            from .appservice_plugin import AppServicePlugin

            app_service_plugin = AppServicePlugin()
            if app_service_plugin.validate_resource(resource):
                logger.debug(
                    f"Selected AppServicePlugin for resource {resource.get('name')}"
                )
                return app_service_plugin

            return None

        return cls.get_plugin(resource_type)

    @classmethod
    def list_supported_types(cls) -> List[str]:
        """
        List all supported resource types.

        Returns:
            List of Azure resource types with registered plugins
        """
        if not cls._initialized:
            cls.discover_plugins()

        return list(cls._plugins.keys())

    @classmethod
    def has_plugin(cls, resource_type: str) -> bool:
        """
        Check if a plugin exists for a resource type.

        Args:
            resource_type: Azure resource type to check

        Returns:
            True if plugin is registered for this type
        """
        if not cls._initialized:
            cls.discover_plugins()

        return resource_type in cls._plugins

    @classmethod
    def discover_plugins(cls) -> None:
        """
        Discover and register all available plugins.

        This method dynamically imports and registers plugin classes.
        Currently supports:
        - KeyVaultPlugin: Microsoft.KeyVault/vaults
        - StoragePlugin: Microsoft.Storage/storageAccounts
        - SqlDatabasePlugin: Microsoft.Sql/servers/databases
        - AppServicePlugin: Microsoft.Web/sites

        Future plugins will be auto-discovered here.
        """
        if cls._initialized:
            logger.debug("Plugin registry already initialized")
            return

        logger.info("Discovering data plane plugins...")

        # Import and register available plugins
        try:
            from .keyvault_plugin import KeyVaultPlugin

            cls.register_plugin(KeyVaultPlugin())
            logger.debug("Registered KeyVaultPlugin")
        except ImportError as e:
            logger.warning(f"Could not import KeyVaultPlugin: {e}")

        try:
            from .storage_plugin import StoragePlugin

            cls.register_plugin(StoragePlugin())
            logger.debug("Registered StoragePlugin")
        except ImportError as e:
            logger.warning(f"Could not import StoragePlugin: {e}")

        try:
            from .sql_plugin import SqlDatabasePlugin

            cls.register_plugin(SqlDatabasePlugin())
            logger.debug("Registered SqlDatabasePlugin")
        except ImportError as e:
            logger.warning(f"Could not import SqlDatabasePlugin: {e}")

        try:
            from .appservice_plugin import AppServicePlugin

            cls.register_plugin(AppServicePlugin())
            logger.debug("Registered AppServicePlugin")
        except ImportError as e:
            logger.warning(f"Could not import AppServicePlugin: {e}")

        cls._initialized = True
        logger.info(
            f"Plugin discovery complete. Registered {len(cls._plugins)} plugins."
        )

    @classmethod
    def reset(cls) -> None:
        """
        Reset the plugin registry.

        This is primarily used for testing purposes to clear
        the registry state between test runs.
        """
        cls._plugins.clear()
        cls._initialized = False
        logger.debug("Plugin registry reset")


# Public API
__all__ = [
    "DataPlaneItem",
    "DataPlanePlugin",
    "PluginRegistry",
    "ReplicationResult",
]
