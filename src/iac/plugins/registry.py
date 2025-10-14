"""Plugin registry for discovering and managing replication plugins."""

import importlib
import inspect
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import ResourceReplicationPlugin


class PluginRegistry:
    """Registry for resource replication plugins.

    Manages plugin discovery, registration, and lookup.
    """

    def __init__(self):
        """Initialize empty plugin registry."""
        self._plugins: List[Type[ResourceReplicationPlugin]] = []
        self._resource_type_map: Dict[str, List[Type[ResourceReplicationPlugin]]] = {}

    def register(self, plugin_class: Type[ResourceReplicationPlugin]) -> None:
        """Register a plugin class.

        Args:
            plugin_class: Plugin class to register
        """
        if plugin_class not in self._plugins:
            self._plugins.append(plugin_class)

            # Build resource type mapping
            # Create instance to get metadata
            instance = plugin_class()
            for resource_type in instance.resource_types:
                if resource_type not in self._resource_type_map:
                    self._resource_type_map[resource_type] = []
                self._resource_type_map[resource_type].append(plugin_class)

    def get_plugin(self, resource: Dict[str, Any]) -> Optional[ResourceReplicationPlugin]:
        """Get appropriate plugin for a resource.

        Args:
            resource: Resource dictionary with 'type' key

        Returns:
            Plugin instance if found, None otherwise
        """
        resource_type = resource.get("type", "")

        # First try exact resource type match
        if resource_type in self._resource_type_map:
            for plugin_class in self._resource_type_map[resource_type]:
                instance = plugin_class()
                if instance.can_handle(resource):
                    return instance

        # Then try all plugins (some may have custom can_handle logic)
        for plugin_class in self._plugins:
            instance = plugin_class()
            if instance.can_handle(resource):
                return instance

        return None

    def get_all_plugins(self) -> List[Type[ResourceReplicationPlugin]]:
        """Get all registered plugins.

        Returns:
            List of plugin classes
        """
        return self._plugins.copy()

    def discover_plugins(self, plugins_dir: Optional[Path] = None) -> int:
        """Discover and register plugins from directory.

        Args:
            plugins_dir: Directory to scan for plugins. If None, uses current package.

        Returns:
            Number of plugins discovered
        """
        if plugins_dir is None:
            plugins_dir = Path(__file__).parent

        discovered = 0

        # Scan for Python files
        for plugin_file in plugins_dir.glob("*_plugin.py"):
            module_name = f"src.iac.plugins.{plugin_file.stem}"

            try:
                # Import module
                module = importlib.import_module(module_name)

                # Find plugin classes
                for _name, obj in inspect.getmembers(module, inspect.isclass):
                    # Check if it's a plugin subclass
                    if (
                        issubclass(obj, ResourceReplicationPlugin)
                        and obj is not ResourceReplicationPlugin
                        and not inspect.isabstract(obj)
                    ):
                        self.register(obj)
                        discovered += 1

            except Exception as e:
                # Log but don't fail - allows partial plugin loading
                print(f"Warning: Failed to load plugin from {plugin_file}: {e}")

        return discovered


# Global registry instance
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry.

    Returns:
        Global PluginRegistry instance
    """
    return _registry


def register_plugin(plugin_class: Type[ResourceReplicationPlugin]) -> None:
    """Register a plugin in the global registry.

    Args:
        plugin_class: Plugin class to register
    """
    _registry.register(plugin_class)
