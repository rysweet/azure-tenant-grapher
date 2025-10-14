"""Plugin system for data-plane replication.

This module provides a plugin architecture for replicating data-plane
configurations from source resources to target resources.

Example:
    >>> from src.iac.plugins import get_registry
    >>> registry = get_registry()
    >>> registry.discover_plugins()
    >>> plugin = registry.get_plugin({"type": "Microsoft.Compute/virtualMachines"})
    >>> if plugin:
    ...     result = await plugin.replicate(source_resource, target_id)
"""

from .active_directory_plugin import ActiveDirectoryReplicationPlugin
from .android_dev_plugin import AndroidDevReplicationPlugin
from .apache_web_server_plugin import ApacheWebServerReplicationPlugin
from .base import ResourceReplicationPlugin
from .cloud_toolkit_plugin import CloudToolkitReplicationPlugin
from .exchange_server_plugin import ExchangeServerReplicationPlugin
from .file_server_plugin import FileServerReplicationPlugin
from .kali_linux_plugin import KaliLinuxReplicationPlugin
from .key_vault_secrets_plugin import KeyVaultSecretsReplicationPlugin
from .linux_client_plugin import LinuxClientReplicationPlugin
from .models import (
    DataPlaneAnalysis,
    DataPlaneElement,
    ExtractionResult,
    PluginMetadata,
    ReplicationResult,
    ReplicationStatus,
    ReplicationStep,
    ReplicationStepType,
    StepType,
)
from .rd_gateway_plugin import RDGatewayReplicationPlugin
from .registry import PluginRegistry, get_registry, register_plugin
from .sql_server_plugin import SQLServerReplicationPlugin
from .storage_data_plugin import StorageDataReplicationPlugin
from .ubuntu_plugin import UbuntuReplicationPlugin
from .vm_extensions_plugin import VMExtensionsReplicationPlugin
from .windows_server_plugin import WindowsServerReplicationPlugin

# Auto-register plugins
_registry = get_registry()
_registry.register(ActiveDirectoryReplicationPlugin)
_registry.register(AndroidDevReplicationPlugin)
_registry.register(ApacheWebServerReplicationPlugin)
_registry.register(CloudToolkitReplicationPlugin)
_registry.register(ExchangeServerReplicationPlugin)
_registry.register(FileServerReplicationPlugin)
_registry.register(KaliLinuxReplicationPlugin)
_registry.register(KeyVaultSecretsReplicationPlugin)
_registry.register(LinuxClientReplicationPlugin)
_registry.register(RDGatewayReplicationPlugin)
_registry.register(SQLServerReplicationPlugin)
_registry.register(StorageDataReplicationPlugin)
_registry.register(UbuntuReplicationPlugin)
_registry.register(VMExtensionsReplicationPlugin)
_registry.register(WindowsServerReplicationPlugin)

__all__ = [
    # Plugins
    "ActiveDirectoryReplicationPlugin",
    "AndroidDevReplicationPlugin",
    "ApacheWebServerReplicationPlugin",
    "CloudToolkitReplicationPlugin",
    # Models
    "DataPlaneAnalysis",
    "DataPlaneElement",
    "ExchangeServerReplicationPlugin",
    "ExtractionResult",
    "FileServerReplicationPlugin",
    "KaliLinuxReplicationPlugin",
    "KeyVaultSecretsReplicationPlugin",
    "LinuxClientReplicationPlugin",
    "PluginMetadata",
    # Registry
    "PluginRegistry",
    "RDGatewayReplicationPlugin",
    "ReplicationResult",
    "ReplicationStatus",
    "ReplicationStep",
    "ReplicationStepType",
    # Base classes
    "ResourceReplicationPlugin",
    "SQLServerReplicationPlugin",
    "StepType",
    "StorageDataReplicationPlugin",
    "UbuntuReplicationPlugin",
    "VMExtensionsReplicationPlugin",
    "WindowsServerReplicationPlugin",
    "get_registry",
    "register_plugin",
]
