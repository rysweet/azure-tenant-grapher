# Data Plane Plugin Architecture Specification

**Version:** 1.0
**Date:** 2025-10-17
**Status:** Design Phase
**Goal:** Achieve 95%+ fidelity in Azure tenant replication by implementing data plane replication

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Current State Analysis](#current-state-analysis)
4. [Enhanced Base Class Specification](#enhanced-base-class-specification)
5. [Plugin Registry Enhancement](#plugin-registry-enhancement)
6. [Credential Management System](#credential-management-system)
7. [Mode Selection Framework](#mode-selection-framework)
8. [Integration with ATG Deploy](#integration-with-atg-deploy)
9. [Individual Plugin Specifications](#individual-plugin-specifications)
10. [Permission Management](#permission-management)
11. [Error Handling & Resilience](#error-handling--resilience)
12. [Testing Strategy](#testing-strategy)
13. [Implementation Roadmap](#implementation-roadmap)

---

## Executive Summary

### Problem Statement
ATG currently achieves 30.8% fidelity (516/1674 resources) because it only replicates control plane (Azure Resource Manager) resources. Data plane elements like Key Vault secrets, storage blobs, VM extensions, and database contents are not replicated, leading to incomplete tenant reconstruction.

### Solution Overview
Implement a comprehensive data plane plugin system that:
- Discovers data plane items for each resource type
- Supports two modes: **Template Mode** (structure only) and **Replication Mode** (full data copy)
- Integrates seamlessly with existing `atg deploy` command via `--dataplane` flag
- Manages credentials and permissions automatically
- Provides progress tracking through existing dashboard infrastructure

### Expected Outcome
- Fidelity increase from 30.8% to 95%+
- Support for 9 critical resource types with data plane elements
- Extensible architecture for future resource types
- Production-ready error handling and recovery

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ATG Deploy Command                            │
│                     (deploy.py + orchestrator.py)                    │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              │ --dataplane flag
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Data Plane Orchestrator                            │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Mode Selection: [template | replication]                    │   │
│  │  Resource Filtering                                           │   │
│  │  Credential Resolution                                        │   │
│  │  Progress Tracking (Dashboard Integration)                   │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              │ Routes to appropriate plugin
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Plugin Registry                               │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Auto-discovery: Scans data_plane_plugins/ directory       │     │
│  │  Resource Type → Plugin Mapping                             │     │
│  │  Plugin Lifecycle Management                                │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              │ Returns plugin instance
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Individual Plugins                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │  KeyVault    │  │   Storage    │  │  VirtualMachine │           │
│  │   Plugin     │  │   Plugin     │  │    Plugin       │  ...       │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                       │
│  Each plugin implements:                                             │
│   • can_handle(resource) → bool                                      │
│   • discover(resource, mode) → List[DataPlaneItem]                   │
│   • generate_iac(items) → str                                        │
│   • replicate(source, target, mode) → ReplicationResult              │
│   • get_required_permissions() → List[Permission]                    │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              │ Uses credentials
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   Credential Provider System                         │
│  ┌────────────────────────────────────────────────────────────┐     │
│  │  Priority Chain:                                            │     │
│  │    1. Explicit credentials (--sp-* flags)                   │     │
│  │    2. Environment variables (AZURE_CLIENT_ID, etc.)         │     │
│  │    3. DefaultAzureCredential (Managed Identity, CLI, etc.)  │     │
│  │    4. Interactive prompt (last resort)                      │     │
│  └────────────────────────────────────────────────────────────┘     │
└─────────────┬───────────────────────────────────────────────────────┘
              │
              │ Authenticates with
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        Azure Services                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │
│  │ Key Vault│  │  Storage │  │    VM    │  │ SQL/Cosmos│  ...       │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │
└─────────────────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Single Responsibility**: Each plugin handles exactly one Azure resource type
2. **Fail-Safe Defaults**: Template mode is default (no data copying without explicit consent)
3. **Credential Isolation**: Plugins receive credentials but don't manage them
4. **Progress Transparency**: All operations report progress to unified dashboard
5. **Regeneratable**: All code can be regenerated from specifications alone

---

## Current State Analysis

### Existing Components (Strong Foundation)

#### 1. Base Plugin Infrastructure (`src/iac/plugins/base_plugin.py`)
**Status:** ✅ Well-designed, needs minor enhancements

**Current Capabilities:**
- Abstract base class `DataPlanePlugin`
- Data classes: `DataPlaneItem`, `ReplicationResult`
- Three abstract methods: `discover()`, `generate_replication_code()`, `replicate()`
- Resource validation via `validate_resource()`
- Output format support checking

**Gap Analysis:**
- ❌ No mode selection (template vs replication)
- ❌ No credential management interface
- ❌ No permission verification
- ❌ No progress reporting integration
- ❌ No error recovery mechanisms

#### 2. Plugin Registry (`src/iac/plugins/__init__.py`)
**Status:** ⚠️ Basic implementation, needs enhancement

**Current Capabilities:**
- Manual plugin registration via `register_plugin()`
- Plugin lookup by resource type
- Discovery method that manually imports known plugins

**Gap Analysis:**
- ❌ No automatic discovery from directory
- ❌ No plugin dependency resolution
- ❌ No plugin versioning or compatibility checking
- ❌ Manual import list (not scalable)

#### 3. Existing Plugins
**KeyVault Plugin** (`src/iac/plugins/keyvault_plugin.py`): ✅ 90% complete
- Discovers secrets, keys, certificates
- Generates Terraform code with placeholders
- Stub replication implementation

**Storage Plugin** (`src/iac/plugins/storage_plugin.py`): ✅ 85% complete
- Discovers containers and blobs (sampled)
- Generates container Terraform code
- Includes AzCopy migration scripts

#### 4. Empty Data Plane Plugin Base (`src/iac/data_plane_plugins/`)
**Status:** ⚠️ Placeholder directory with minimal base class

**Current State:**
- Very basic base class with two methods: `can_handle()`, `replicate()`
- Empty `__init__.py`

**Recommendation:**
- **Consolidate into single plugin system** under `src/iac/plugins/`
- Remove duplicate base classes
- Use existing well-designed `base_plugin.py` as foundation

### Neo4j Graph Schema Analysis

From `fidelity_comparison.cypher`, the graph contains:

**Nodes:**
- `Resource` (primary node type with `tenant_id`, `type`, `name`, `properties`)
- Properties stored as JSON strings in some cases

**Relationships:**
- `CONTAINS` (resource hierarchy)
- `CONNECTED_TO` (network connections)
- `DEPENDS_ON` (dependencies)

**Query Patterns for Plugins:**
```cypher
// Find all resources of a specific type needing data plane replication
MATCH (r:Resource)
WHERE r.type = 'Microsoft.KeyVault/vaults'
  AND r.tenant_id = $tenant_id
RETURN r
```

### Integration Points

#### Deploy Command (`src/commands/deploy.py`)
- Current flags: `--iac-dir`, `--target-tenant-id`, `--resource-group`, `--dry-run`
- **Needs:** `--dataplane`, `--dataplane-mode`, `--sp-*` flags

#### Orchestrator (`src/deployment/orchestrator.py`)
- Handles Terraform/Bicep/ARM deployment
- Has dashboard integration (`DeploymentDashboard`)
- **Needs:** Data plane phase injection point

---

## Enhanced Base Class Specification

### Module: `src/iac/plugins/base_plugin.py`

**Purpose:** Provide comprehensive base class for all data plane plugins with mode support, credential management, and progress reporting.

**Enhancements Required:**

```python
# File: src/iac/plugins/base_plugin.py (ENHANCED)

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol


class ReplicationMode(Enum):
    """Data plane replication modes."""
    TEMPLATE = "template"      # Structure only, no data
    REPLICATION = "replication"  # Full data copy


@dataclass
class Permission:
    """Azure RBAC permission requirement."""
    scope: str                # "resource" | "resource_group" | "subscription"
    actions: List[str]        # E.g., ["Microsoft.KeyVault/vaults/secrets/getSecret"]
    not_actions: List[str] = field(default_factory=list)
    data_actions: List[str] = field(default_factory=list)
    description: str = ""


@dataclass
class DataPlaneItem:
    """Represents a single data plane item to be replicated."""
    name: str
    item_type: str
    properties: Dict[str, Any]
    source_resource_id: str
    metadata: Optional[Dict[str, Any]] = None
    size_bytes: Optional[int] = None  # NEW: For progress tracking


@dataclass
class ReplicationResult:
    """Result of a data plane replication operation."""
    success: bool
    items_discovered: int
    items_replicated: int
    items_skipped: int = 0    # NEW: Track skipped items
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0  # NEW: Timing information


class ProgressReporter(Protocol):
    """Protocol for progress reporting (duck typing)."""
    def report_discovery(self, resource_id: str, item_count: int) -> None: ...
    def report_replication_progress(self, item_name: str, progress_pct: float) -> None: ...
    def report_completion(self, result: ReplicationResult) -> None: ...


class CredentialProvider(Protocol):
    """Protocol for credential provision (duck typing)."""
    def get_credential(self) -> Any: ...
    def get_connection_string(self, resource_id: str) -> Optional[str]: ...


class DataPlanePlugin(ABC):
    """Enhanced base class for data plane replication plugins."""

    def __init__(
        self,
        credential_provider: Optional[CredentialProvider] = None,
        progress_reporter: Optional[ProgressReporter] = None,
    ) -> None:
        """Initialize plugin with optional credential and progress reporting."""
        self.credential_provider = credential_provider
        self.progress_reporter = progress_reporter
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    # ============ EXISTING ABSTRACT METHODS (unchanged) ============

    @abstractmethod
    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        """Discover data plane items for a resource."""
        pass

    @abstractmethod
    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        """Generate IaC code to replicate data plane items."""
        pass

    @abstractmethod
    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        """Replicate data from source to target resource."""
        pass

    @property
    @abstractmethod
    def supported_resource_type(self) -> str:
        """Azure resource type this plugin supports."""
        pass

    # ============ NEW ABSTRACT METHODS ============

    @abstractmethod
    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """Return Azure RBAC permissions required for this plugin.

        Args:
            mode: The replication mode (affects required permissions)

        Returns:
            List of Permission objects describing needed RBAC roles
        """
        pass

    @abstractmethod
    def discover_with_mode(
        self,
        resource: Dict[str, Any],
        mode: ReplicationMode
    ) -> List[DataPlaneItem]:
        """Discover data plane items with mode awareness.

        Template mode: Discover metadata only (names, types, counts)
        Replication mode: Discover full details including values

        Args:
            resource: Resource dictionary from Neo4j
            mode: Replication mode

        Returns:
            List of discovered items (detail level varies by mode)
        """
        pass

    @abstractmethod
    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """Replicate with mode awareness.

        Template mode: Create empty structures (e.g., empty Key Vault)
        Replication mode: Copy actual data

        Args:
            source_resource: Source resource
            target_resource: Target resource
            mode: Replication mode

        Returns:
            ReplicationResult with statistics
        """
        pass

    # ============ NEW CONCRETE METHODS ============

    def verify_permissions(
        self,
        resource_id: str,
        mode: ReplicationMode
    ) -> tuple[bool, List[str]]:
        """Verify the current credential has required permissions.

        Args:
            resource_id: Azure resource ID to check
            mode: Replication mode (affects required permissions)

        Returns:
            (success: bool, missing_permissions: List[str])
        """
        # Implementation uses Azure RBAC API to check permissions
        # Returns True if all permissions granted, False + list of missing perms
        pass

    def estimate_operation_time(
        self,
        items: List[DataPlaneItem],
        mode: ReplicationMode
    ) -> float:
        """Estimate time required for replication operation.

        Args:
            items: Items to replicate
            mode: Replication mode

        Returns:
            Estimated seconds (0 for template mode)
        """
        if mode == ReplicationMode.TEMPLATE:
            return 0.0

        # Default: 100ms per item (override in subclasses)
        return len(items) * 0.1

    def supports_mode(self, mode: ReplicationMode) -> bool:
        """Check if plugin supports a specific mode.

        Default implementation supports both modes.
        Override if plugin has limitations.
        """
        return True
```

**Contract:**
- **Inputs:** Resource dict from Neo4j, mode enum, optional credential/progress
- **Outputs:** DataPlaneItems, ReplicationResult, Permission lists
- **Side Effects:** Azure API calls, progress reporting
- **Dependencies:** azure-identity, azure SDK packages (per plugin)

---

## Plugin Registry Enhancement

### Module: `src/iac/plugins/registry.py`

**Purpose:** Automatic discovery and lifecycle management of data plane plugins.

**New Design:**

```python
# File: src/iac/plugins/registry.py (NEW - replaces manual discovery in __init__.py)

import importlib
import inspect
import logging
from pathlib import Path
from typing import Dict, List, Optional, Type

from .base_plugin import DataPlanePlugin, ReplicationMode

logger = logging.getLogger(__name__)


class PluginMetadata:
    """Metadata about a registered plugin."""
    def __init__(
        self,
        plugin_class: Type[DataPlanePlugin],
        resource_type: str,
        module_path: str,
        supported_modes: List[ReplicationMode],
    ):
        self.plugin_class = plugin_class
        self.resource_type = resource_type
        self.module_path = module_path
        self.supported_modes = supported_modes


class DataPlanePluginRegistry:
    """
    Enhanced registry with automatic plugin discovery.

    Plugins are discovered by scanning src/iac/plugins/ directory
    for classes that inherit from DataPlanePlugin.
    """

    _instance = None
    _plugins: Dict[str, PluginMetadata] = {}
    _initialized = False

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize registry (idempotent)."""
        if not self._initialized:
            self.discover_plugins()
            self._initialized = True

    def discover_plugins(self) -> None:
        """Automatically discover all plugins in plugins directory."""
        plugins_dir = Path(__file__).parent
        logger.info(f"Discovering plugins in {plugins_dir}")

        # Find all Python files except __init__ and base_plugin
        plugin_files = [
            f for f in plugins_dir.glob("*_plugin.py")
            if f.name not in ("base_plugin.py", "registry.py")
        ]

        for plugin_file in plugin_files:
            try:
                # Import module dynamically
                module_name = f"src.iac.plugins.{plugin_file.stem}"
                module = importlib.import_module(module_name)

                # Find DataPlanePlugin subclasses
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (
                        issubclass(obj, DataPlanePlugin)
                        and obj is not DataPlanePlugin
                        and not inspect.isabstract(obj)
                    ):
                        self._register_plugin_class(obj, str(plugin_file))

            except Exception as e:
                logger.warning(f"Failed to load plugin from {plugin_file}: {e}")

        logger.info(f"Discovered {len(self._plugins)} plugins")

    def _register_plugin_class(
        self,
        plugin_class: Type[DataPlanePlugin],
        module_path: str
    ) -> None:
        """Register a plugin class."""
        try:
            # Instantiate to get resource type
            instance = plugin_class()
            resource_type = instance.supported_resource_type

            # Check supported modes
            supported_modes = [
                mode for mode in ReplicationMode
                if instance.supports_mode(mode)
            ]

            metadata = PluginMetadata(
                plugin_class=plugin_class,
                resource_type=resource_type,
                module_path=module_path,
                supported_modes=supported_modes,
            )

            self._plugins[resource_type] = metadata
            logger.info(
                f"Registered {plugin_class.__name__} for {resource_type} "
                f"(modes: {[m.value for m in supported_modes]})"
            )

        except Exception as e:
            logger.error(f"Failed to register {plugin_class.__name__}: {e}")

    def get_plugin(
        self,
        resource_type: str,
        credential_provider=None,
        progress_reporter=None,
    ) -> Optional[DataPlanePlugin]:
        """Get plugin instance for resource type."""
        metadata = self._plugins.get(resource_type)
        if not metadata:
            return None

        # Instantiate with providers
        return metadata.plugin_class(
            credential_provider=credential_provider,
            progress_reporter=progress_reporter,
        )

    def get_plugin_for_resource(
        self,
        resource: Dict[str, Any],
        credential_provider=None,
        progress_reporter=None,
    ) -> Optional[DataPlanePlugin]:
        """Get plugin for a resource dict."""
        resource_type = resource.get("type", "")
        return self.get_plugin(resource_type, credential_provider, progress_reporter)

    def list_supported_types(self) -> List[str]:
        """List all resource types with data plane plugins."""
        return list(self._plugins.keys())

    def get_required_permissions_for_resource(
        self,
        resource_type: str,
        mode: ReplicationMode
    ) -> List[Permission]:
        """Get permissions required for a resource type in specific mode."""
        plugin = self.get_plugin(resource_type)
        if not plugin:
            return []
        return plugin.get_required_permissions(mode)


# Singleton instance
registry = DataPlanePluginRegistry()
```

**Contract:**
- **Inputs:** None (self-discovering)
- **Outputs:** Plugin instances, metadata
- **Side Effects:** Module imports, singleton state
- **Dependencies:** importlib, inspect

---

## Credential Management System

### Module: `src/iac/plugins/credential_manager.py`

**Purpose:** Unified credential resolution with priority chain and secure handling.

**Design:**

```python
# File: src/iac/plugins/credential_manager.py (NEW)

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from azure.identity import (
    ClientSecretCredential,
    DefaultAzureCredential,
    InteractiveBrowserCredential,
)

logger = logging.getLogger(__name__)


@dataclass
class CredentialConfig:
    """Configuration for credential resolution."""
    # Explicit credentials (highest priority)
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None

    # Flags
    allow_interactive: bool = False  # Prompt user if needed
    use_environment: bool = True     # Read from env vars

    # Resource-specific connection strings
    connection_strings: dict[str, str] = None


class CredentialManager:
    """
    Manages Azure credential resolution with priority chain.

    Priority:
    1. Explicit credentials (service principal)
    2. Environment variables (AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID)
    3. DefaultAzureCredential (Managed Identity, Azure CLI, etc.)
    4. Interactive browser login (if allowed)
    """

    def __init__(self, config: Optional[CredentialConfig] = None):
        """Initialize with optional configuration."""
        self.config = config or CredentialConfig()
        self._credential_cache: Optional[Any] = None
        self.logger = logging.getLogger(__name__)

    def get_credential(self) -> Any:
        """Get Azure credential using priority chain."""
        if self._credential_cache:
            return self._credential_cache

        # Priority 1: Explicit credentials
        if self._has_explicit_credentials():
            self.logger.info("Using explicit service principal credentials")
            self._credential_cache = ClientSecretCredential(
                tenant_id=self.config.tenant_id,
                client_id=self.config.client_id,
                client_secret=self.config.client_secret,
            )
            return self._credential_cache

        # Priority 2: Environment variables
        if self.config.use_environment and self._has_env_credentials():
            self.logger.info("Using credentials from environment variables")
            self._credential_cache = ClientSecretCredential(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET"),
            )
            return self._credential_cache

        # Priority 3: DefaultAzureCredential
        self.logger.info("Using DefaultAzureCredential (Managed Identity, CLI, etc.)")
        try:
            self._credential_cache = DefaultAzureCredential()
            # Test the credential
            self._credential_cache.get_token("https://management.azure.com/.default")
            return self._credential_cache
        except Exception as e:
            self.logger.warning(f"DefaultAzureCredential failed: {e}")

        # Priority 4: Interactive (if allowed)
        if self.config.allow_interactive:
            self.logger.info("Prompting for interactive browser login")
            self._credential_cache = InteractiveBrowserCredential()
            return self._credential_cache

        # Failed
        raise ValueError(
            "Could not resolve Azure credentials. Please set AZURE_CLIENT_ID, "
            "AZURE_CLIENT_SECRET, AZURE_TENANT_ID environment variables or use "
            "--sp-* command-line flags."
        )

    def get_connection_string(self, resource_id: str) -> Optional[str]:
        """Get resource-specific connection string if available."""
        if not self.config.connection_strings:
            return None
        return self.config.connection_strings.get(resource_id)

    def _has_explicit_credentials(self) -> bool:
        """Check if explicit credentials are configured."""
        return bool(
            self.config.client_id
            and self.config.client_secret
            and self.config.tenant_id
        )

    def _has_env_credentials(self) -> bool:
        """Check if environment variables are set."""
        return bool(
            os.getenv("AZURE_CLIENT_ID")
            and os.getenv("AZURE_CLIENT_SECRET")
            and os.getenv("AZURE_TENANT_ID")
        )
```

**Contract:**
- **Inputs:** CredentialConfig (optional)
- **Outputs:** Azure credential object
- **Side Effects:** Environment variable reads, credential caching, interactive prompts
- **Dependencies:** azure-identity

---

## Mode Selection Framework

### Module: `src/iac/plugins/mode_selector.py`

**Purpose:** Handle mode selection logic and user interaction for dataplane operations.

**Design:**

```python
# File: src/iac/plugins/mode_selector.py (NEW)

import logging
from dataclasses import dataclass
from typing import Dict, List

from .base_plugin import ReplicationMode

logger = logging.getLogger(__name__)


@dataclass
class ModeSelectionResult:
    """Result of mode selection."""
    mode: ReplicationMode
    user_confirmed: bool
    resource_filter: List[str]  # Resource types to process


class ModeSelector:
    """
    Handles replication mode selection and validation.

    Ensures user understands implications of each mode:
    - Template: Fast, no data, safe
    - Replication: Slow, full data copy, requires permissions
    """

    def __init__(self, interactive: bool = True):
        """Initialize selector.

        Args:
            interactive: Allow user prompts (False for CI/CD)
        """
        self.interactive = interactive

    def select_mode(
        self,
        cli_mode: Optional[str] = None,
        resources: List[Dict[str, Any]] = None,
    ) -> ModeSelectionResult:
        """Select replication mode.

        Args:
            cli_mode: Mode from CLI flag (overrides prompts)
            resources: Resources to process (for estimation)

        Returns:
            ModeSelectionResult with selected mode and confirmation
        """
        # If CLI mode specified, use it
        if cli_mode:
            mode = ReplicationMode(cli_mode.lower())
            logger.info(f"Using CLI-specified mode: {mode.value}")
            return ModeSelectionResult(
                mode=mode,
                user_confirmed=True,
                resource_filter=self._extract_resource_types(resources),
            )

        # Interactive mode selection
        if self.interactive:
            return self._interactive_selection(resources)

        # Default to template mode (safe)
        logger.info("Non-interactive mode, defaulting to 'template'")
        return ModeSelectionResult(
            mode=ReplicationMode.TEMPLATE,
            user_confirmed=False,
            resource_filter=self._extract_resource_types(resources),
        )

    def _interactive_selection(
        self,
        resources: List[Dict[str, Any]]
    ) -> ModeSelectionResult:
        """Interactive mode selection with user confirmation."""
        import click  # Use click for prompts

        # Show summary
        resource_counts = self._count_resources_by_type(resources)
        click.echo("\n📊 Data Plane Resources Detected:")
        for resource_type, count in resource_counts.items():
            click.echo(f"  • {resource_type}: {count} instances")

        # Explain modes
        click.echo("\n🔧 Replication Modes:")
        click.echo("  1. TEMPLATE (Recommended for testing)")
        click.echo("     • Creates empty structures (e.g., empty Key Vault with secret names)")
        click.echo("     • Fast, minimal permissions required")
        click.echo("     • No actual data copied")
        click.echo()
        click.echo("  2. REPLICATION (Production use)")
        click.echo("     • Copies actual data (secrets, blobs, database contents)")
        click.echo("     • Slow, requires extensive permissions")
        click.echo("     • ⚠️  May incur data transfer costs")
        click.echo()

        # Prompt
        mode_choice = click.prompt(
            "Select mode",
            type=click.Choice(["template", "replication"], case_sensitive=False),
            default="template",
        )

        mode = ReplicationMode(mode_choice.lower())

        # Confirmation for replication mode
        if mode == ReplicationMode.REPLICATION:
            confirmed = click.confirm(
                "\n⚠️  REPLICATION mode will copy actual data. "
                "This requires extensive permissions and may take a long time. Continue?"
            )
            if not confirmed:
                click.echo("Falling back to TEMPLATE mode")
                mode = ReplicationMode.TEMPLATE

        return ModeSelectionResult(
            mode=mode,
            user_confirmed=True,
            resource_filter=list(resource_counts.keys()),
        )

    def _count_resources_by_type(
        self,
        resources: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Count resources by type."""
        counts = {}
        for resource in resources or []:
            resource_type = resource.get("type", "unknown")
            counts[resource_type] = counts.get(resource_type, 0) + 1
        return counts

    def _extract_resource_types(
        self,
        resources: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract unique resource types."""
        return list(set(r.get("type") for r in resources or [] if r.get("type")))
```

**Contract:**
- **Inputs:** CLI mode override, resource list
- **Outputs:** ModeSelectionResult
- **Side Effects:** User prompts (if interactive)
- **Dependencies:** click

---

## Integration with ATG Deploy

### Enhanced Deploy Command

**File:** `src/commands/deploy.py` (MODIFICATIONS)

**New Command-Line Flags:**

```python
@click.option(
    "--dataplane",
    is_flag=True,
    default=False,
    help="Enable data plane replication after control plane deployment",
)
@click.option(
    "--dataplane-mode",
    type=click.Choice(["template", "replication"], case_sensitive=False),
    default=None,
    help="Data plane replication mode (template=structure only, replication=full data)",
)
@click.option(
    "--sp-client-id",
    envvar="AZURE_DATAPLANE_CLIENT_ID",
    help="Service principal client ID for data plane operations",
)
@click.option(
    "--sp-client-secret",
    envvar="AZURE_DATAPLANE_CLIENT_SECRET",
    help="Service principal client secret",
)
@click.option(
    "--sp-tenant-id",
    envvar="AZURE_DATAPLANE_TENANT_ID",
    help="Service principal tenant ID",
)
@click.option(
    "--dataplane-interactive",
    is_flag=True,
    default=False,
    help="Allow interactive prompts for data plane operations",
)
def deploy_command(
    iac_dir: str,
    target_tenant_id: str,
    resource_group: str,
    location: str,
    subscription_id: str | None,
    iac_format: str | None,
    dry_run: bool,
    dataplane: bool,  # NEW
    dataplane_mode: str | None,  # NEW
    sp_client_id: str | None,  # NEW
    sp_client_secret: str | None,  # NEW
    sp_tenant_id: str | None,  # NEW
    dataplane_interactive: bool,  # NEW
):
    """Deploy generated IaC to target tenant."""

    # ... existing control plane deployment ...

    # NEW: Data plane phase
    if dataplane:
        click.echo("\n🔌 Starting data plane replication...")

        from ..iac.plugins.orchestrator import DataPlaneOrchestrator
        from ..iac.plugins.credential_manager import CredentialConfig, CredentialManager

        # Setup credentials
        cred_config = CredentialConfig(
            client_id=sp_client_id,
            client_secret=sp_client_secret,
            tenant_id=sp_tenant_id,
            allow_interactive=dataplane_interactive,
        )
        cred_manager = CredentialManager(cred_config)

        # Setup orchestrator
        orchestrator = DataPlaneOrchestrator(
            credential_manager=cred_manager,
            dashboard=dashboard,  # Reuse existing dashboard
        )

        # Execute data plane replication
        dataplane_result = orchestrator.replicate(
            iac_dir=Path(iac_dir),
            target_tenant_id=target_tenant_id,
            resource_group=resource_group,
            mode=dataplane_mode,
            dry_run=dry_run,
        )

        # Report results
        if dataplane_result.success:
            click.echo(f"✅ Data plane replication completed: {dataplane_result.summary}")
        else:
            click.echo(f"❌ Data plane replication failed: {dataplane_result.errors}", err=True)
```

### Data Plane Orchestrator

**File:** `src/iac/plugins/orchestrator.py` (NEW)

**Purpose:** Coordinate data plane replication across multiple plugins.

```python
# File: src/iac/plugins/orchestrator.py (NEW)

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from ..deployment.deployment_dashboard import DeploymentDashboard
from .base_plugin import ReplicationMode, ReplicationResult
from .credential_manager import CredentialManager
from .mode_selector import ModeSelector
from .registry import registry

logger = logging.getLogger(__name__)


@dataclass
class DataPlaneResult:
    """Result of data plane orchestration."""
    success: bool
    resources_processed: int
    plugins_executed: int
    results: List[ReplicationResult]
    errors: List[str]
    warnings: List[str]
    summary: str


class DataPlaneOrchestrator:
    """
    Orchestrates data plane replication across multiple plugins.

    Responsibilities:
    - Load deployed resources from Neo4j or Terraform state
    - Match resources to plugins
    - Execute replication in dependency order
    - Aggregate results and errors
    - Update dashboard with progress
    """

    def __init__(
        self,
        credential_manager: CredentialManager,
        dashboard: Optional[DeploymentDashboard] = None,
    ):
        """Initialize orchestrator."""
        self.credential_manager = credential_manager
        self.dashboard = dashboard
        self.mode_selector = ModeSelector(interactive=True)

    def replicate(
        self,
        iac_dir: Path,
        target_tenant_id: str,
        resource_group: str,
        mode: Optional[str] = None,
        dry_run: bool = False,
    ) -> DataPlaneResult:
        """Execute data plane replication."""

        # 1. Load resources from deployment
        resources = self._load_deployed_resources(iac_dir, target_tenant_id)
        logger.info(f"Found {len(resources)} deployed resources")

        # 2. Filter resources needing data plane plugins
        dataplane_resources = self._filter_dataplane_resources(resources)
        logger.info(f"Identified {len(dataplane_resources)} resources with data plane")

        if not dataplane_resources:
            return DataPlaneResult(
                success=True,
                resources_processed=0,
                plugins_executed=0,
                results=[],
                errors=[],
                warnings=["No resources require data plane replication"],
                summary="No data plane work needed",
            )

        # 3. Select mode
        mode_result = self.mode_selector.select_mode(
            cli_mode=mode,
            resources=dataplane_resources,
        )

        if self.dashboard:
            self.dashboard.update_phase("dataplane")
            self.dashboard.log_info(
                f"Data plane mode: {mode_result.mode.value} "
                f"({len(dataplane_resources)} resources)"
            )

        # 4. Execute replication per plugin
        results = []
        errors = []
        warnings = []

        for resource in dataplane_resources:
            try:
                result = self._replicate_resource(
                    resource=resource,
                    mode=mode_result.mode,
                    dry_run=dry_run,
                )
                results.append(result)

                if not result.success:
                    errors.extend(result.errors)
                warnings.extend(result.warnings)

            except Exception as e:
                error_msg = f"Failed to replicate {resource.get('name')}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)

        # 5. Aggregate results
        success = len(errors) == 0
        plugins_executed = len(set(r.get("type") for r in dataplane_resources))

        summary = self._generate_summary(results, mode_result.mode)

        return DataPlaneResult(
            success=success,
            resources_processed=len(dataplane_resources),
            plugins_executed=plugins_executed,
            results=results,
            errors=errors,
            warnings=warnings,
            summary=summary,
        )

    def _load_deployed_resources(
        self,
        iac_dir: Path,
        target_tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Load resources from Neo4j or Terraform state."""
        # Option 1: Query Neo4j for deployed resources
        # Option 2: Parse terraform.tfstate
        # For now, stub with Neo4j approach

        from ...db.async_neo4j_session import AsyncNeo4jSession

        session = AsyncNeo4jSession()
        # Query resources by tenant_id
        query = """
        MATCH (r:Resource)
        WHERE r.tenant_id = $tenant_id
        RETURN r
        """
        # Execute query and return results
        # (Actual implementation would use async properly)
        return []  # Stub

    def _filter_dataplane_resources(
        self,
        resources: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter resources that have data plane plugins."""
        supported_types = registry.list_supported_types()
        return [
            r for r in resources
            if r.get("type") in supported_types
        ]

    def _replicate_resource(
        self,
        resource: Dict[str, Any],
        mode: ReplicationMode,
        dry_run: bool,
    ) -> ReplicationResult:
        """Replicate a single resource."""
        resource_name = resource.get("name", "unknown")
        resource_type = resource.get("type", "unknown")

        logger.info(f"Replicating {resource_type}/{resource_name} (mode={mode.value})")

        # Get plugin
        plugin = registry.get_plugin_for_resource(
            resource,
            credential_provider=self.credential_manager,
            progress_reporter=self._create_progress_reporter(resource_name),
        )

        if not plugin:
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"No plugin for {resource_type}"],
                warnings=[],
            )

        # Check permissions
        success, missing = plugin.verify_permissions(resource["id"], mode)
        if not success:
            return ReplicationResult(
                success=False,
                items_discovered=0,
                items_replicated=0,
                errors=[f"Missing permissions: {', '.join(missing)}"],
                warnings=[],
            )

        # Execute replication
        if dry_run:
            # Just discover
            items = plugin.discover_with_mode(resource, mode)
            return ReplicationResult(
                success=True,
                items_discovered=len(items),
                items_replicated=0,
                warnings=["Dry-run mode: no data replicated"],
            )
        else:
            # Full replication
            # Note: This assumes target resource already exists from control plane deployment
            return plugin.replicate_with_mode(resource, resource, mode)

    def _create_progress_reporter(self, resource_name: str):
        """Create progress reporter for dashboard integration."""
        if not self.dashboard:
            return None

        # Return protocol-compatible object
        class DashboardProgressReporter:
            def __init__(self, dashboard, resource_name):
                self.dashboard = dashboard
                self.resource_name = resource_name

            def report_discovery(self, resource_id, item_count):
                self.dashboard.log_info(
                    f"Discovered {item_count} items in {self.resource_name}"
                )

            def report_replication_progress(self, item_name, progress_pct):
                self.dashboard.log_info(
                    f"Replicating {item_name}: {progress_pct:.0f}%"
                )

            def report_completion(self, result):
                if result.success:
                    self.dashboard.log_info(
                        f"✅ {self.resource_name}: {result.items_replicated} items replicated"
                    )
                else:
                    self.dashboard.add_error(
                        f"❌ {self.resource_name}: {', '.join(result.errors)}"
                    )

        return DashboardProgressReporter(self.dashboard, resource_name)

    def _generate_summary(
        self,
        results: List[ReplicationResult],
        mode: ReplicationMode
    ) -> str:
        """Generate human-readable summary."""
        total_discovered = sum(r.items_discovered for r in results)
        total_replicated = sum(r.items_replicated for r in results)
        total_errors = sum(len(r.errors) for r in results)

        if mode == ReplicationMode.TEMPLATE:
            return f"{total_discovered} structures created (template mode)"
        else:
            return f"{total_replicated}/{total_discovered} items replicated, {total_errors} errors"
```

**Contract:**
- **Inputs:** IaC directory, tenant ID, mode
- **Outputs:** DataPlaneResult with aggregated statistics
- **Side Effects:** Azure API calls via plugins, dashboard updates, Neo4j queries
- **Dependencies:** registry, credential_manager, dashboard

---

## Individual Plugin Specifications

### Priority Implementation Order

Based on resource counts and complexity:

| Priority | Resource Type | Count | Complexity | Estimated Effort |
|----------|---------------|-------|------------|------------------|
| 1 | Virtual Machines | 105 | Medium | 2 weeks |
| 2 | KeyVault | 70 | Low | 1 week |
| 3 | Storage Accounts | 61 | Medium | 1.5 weeks |
| 4 | Container Registry | 16 | Medium | 1 week |
| 5 | CosmosDB | 10 | High | 2 weeks |
| 6 | SQL Databases | 7 | High | 2 weeks |
| 7 | App Service | 7 | Medium | 1 week |
| 8 | API Management | TBD | High | 2 weeks |
| 9 | Functions | TBD | Low | 1 week |

### Plugin Specification Template

Each plugin follows this specification format:

---

### Plugin: VirtualMachine

**Module:** `src/iac/data_plane_plugins/vm_plugin.py`

**Purpose:** Replicate VM extensions, custom script data, and data disk contents

**Supported Resource Type:** `Microsoft.Compute/virtualMachines`

**Data Plane Items:**
1. **VM Extensions** (e.g., CustomScriptExtension, AADLogin)
   - Extension settings (JSON)
   - Protected settings (encrypted)
   - Script files (if applicable)

2. **Custom Script Data**
   - PowerShell/Bash scripts executed during VM provisioning
   - Script output logs

3. **Data Disks**
   - Disk snapshots (optional, large)
   - Disk metadata (size, SKU, caching)

**Modes:**
- **Template Mode**: Create empty data disks with correct sizes, list extensions by name
- **Replication Mode**: Copy extension configurations, optionally snapshot data disks

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Compute/virtualMachines/read",
            "Microsoft.Compute/virtualMachines/extensions/read",
        ],
        description="Read VM and extension metadata"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Compute/virtualMachines/read",
            "Microsoft.Compute/virtualMachines/extensions/read",
            "Microsoft.Compute/virtualMachines/extensions/write",
            "Microsoft.Compute/disks/read",
            "Microsoft.Compute/snapshots/write",  # For disk copying
        ],
        description="Read/write VM extensions and create disk snapshots"
    )
]
```

**Implementation Notes:**
- Use Azure Compute SDK: `azure-mgmt-compute`
- Extensions may contain secrets (handle carefully in template mode)
- Disk snapshots are very large (confirm with user before replication)
- Script content may be in protected settings (requires special decryption)

**Test Requirements:**
- Unit: Mock VM with extensions, verify discovery
- Integration: Real VM in test tenant, verify extension replication
- E2E: Deploy VM, replicate extensions, verify in target

**Dependencies:**
- `azure-mgmt-compute`
- `azure-identity`

**Estimated Effort:** 2 weeks (10 days)

---

### Plugin: KeyVault

**Status:** 90% implemented (`src/iac/plugins/keyvault_plugin.py`)

**Remaining Work:**
1. Add mode support to existing methods
2. Implement permission verification
3. Complete `replicate()` stub (currently returns failure)
4. Add progress reporting integration

**Required Changes:**

```python
# In KeyVaultPlugin class

def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
    """Return required permissions."""
    if mode == ReplicationMode.TEMPLATE:
        return [
            Permission(
                scope="resource",
                actions=["Microsoft.KeyVault/vaults/read"],
                data_actions=[
                    "Microsoft.KeyVault/vaults/secrets/getMetadata/action",
                    "Microsoft.KeyVault/vaults/keys/read",
                    "Microsoft.KeyVault/vaults/certificates/read",
                ],
                description="List secrets, keys, certificates (no values)"
            )
        ]
    else:  # REPLICATION
        return [
            Permission(
                scope="resource",
                actions=["Microsoft.KeyVault/vaults/read"],
                data_actions=[
                    "Microsoft.KeyVault/vaults/secrets/getSecret/action",
                    "Microsoft.KeyVault/vaults/secrets/setSecret/action",
                    "Microsoft.KeyVault/vaults/keys/read",
                    "Microsoft.KeyVault/vaults/keys/create/action",
                    "Microsoft.KeyVault/vaults/certificates/read",
                    "Microsoft.KeyVault/vaults/certificates/create/action",
                ],
                description="Read and write secrets, keys, certificates"
            )
        ]

def discover_with_mode(
    self, resource: Dict[str, Any], mode: ReplicationMode
) -> List[DataPlaneItem]:
    """Discover with mode awareness."""
    # Current discover() method already does metadata-only
    # Just return as-is for both modes (values fetched later in replicate)
    return self.discover(resource)

def replicate_with_mode(
    self,
    source_resource: Dict[str, Any],
    target_resource: Dict[str, Any],
    mode: ReplicationMode,
) -> ReplicationResult:
    """Complete implementation."""
    if mode == ReplicationMode.TEMPLATE:
        # Just verify target Key Vault exists, create empty secrets
        items = self.discover(source_resource)
        # Create secrets with placeholder values
        # ... implementation ...
        return ReplicationResult(
            success=True,
            items_discovered=len(items),
            items_replicated=len(items),
            warnings=["Template mode: secrets have placeholder values"]
        )
    else:
        # Full replication: fetch actual secret values and copy
        # ... implementation using SecretClient.get_secret() ...
        pass
```

**Estimated Effort:** 3 days (complete remaining work)

---

### Plugin: StorageAccount

**Status:** 85% implemented (`src/iac/plugins/storage_plugin.py`)

**Remaining Work:**
1. Add mode support
2. Implement permission verification
3. Complete `replicate()` with AzCopy integration
4. Add file shares, tables, queues support (currently only blob containers)

**Data Plane Items:**
- Blob containers + blobs
- File shares + files
- Tables + table data
- Queues + messages

**Modes:**
- **Template**: Create empty containers/shares/tables/queues
- **Replication**: Use AzCopy to copy all blob/file data

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=["Microsoft.Storage/storageAccounts/read"],
        data_actions=[
            "Microsoft.Storage/storageAccounts/blobServices/containers/read",
            "Microsoft.Storage/storageAccounts/fileServices/fileshares/read",
        ],
        description="List containers and shares"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Storage/storageAccounts/read",
            "Microsoft.Storage/storageAccounts/listKeys/action",  # For AzCopy
        ],
        data_actions=[
            "Microsoft.Storage/storageAccounts/blobServices/containers/read",
            "Microsoft.Storage/storageAccounts/blobServices/containers/write",
            "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read",
            "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write",
        ],
        description="Read/write blob data"
    )
]
```

**Implementation Notes:**
- Use AzCopy CLI for efficient bulk copying: `azcopy copy <source> <target> --recursive`
- Large data transfers may take hours (show progress)
- Consider parallel transfers for multiple containers

**Estimated Effort:** 1.5 weeks (complete remaining work + testing)

---

### Plugin: CosmosDB

**Module:** `src/iac/data_plane_plugins/cosmosdb_plugin.py` (NEW)

**Supported Resource Type:** `Microsoft.DocumentDB/databaseAccounts`

**Data Plane Items:**
1. Databases
2. Containers (collections)
3. Documents (optional in replication mode)
4. Stored procedures, triggers, UDFs

**Modes:**
- **Template**: Create empty databases and containers with correct schema
- **Replication**: Copy documents (can be very large, confirm with user)

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=["Microsoft.DocumentDB/databaseAccounts/read"],
        data_actions=[
            "Microsoft.DocumentDB/databaseAccounts/readMetadata",
        ],
        description="Read Cosmos DB metadata"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=["Microsoft.DocumentDB/databaseAccounts/readwrite"],
        data_actions=[
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/read",
            "Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers/items/create",
        ],
        description="Read/write documents"
    )
]
```

**Implementation Notes:**
- Use `azure-cosmos` SDK
- Partition key must match between source and target
- Large document counts require pagination
- Consider using Data Migration Tool for bulk operations

**Estimated Effort:** 2 weeks

---

### Plugin: SQLDatabase

**Module:** `src/iac/data_plane_plugins/sql_plugin.py` (NEW)

**Supported Resource Type:** `Microsoft.Sql/servers/databases`

**Data Plane Items:**
1. Database schema (tables, views, procedures)
2. Table data (optional)

**Modes:**
- **Template**: Create empty database with correct schema (using BACPAC or schema script)
- **Replication**: Full database copy (using Azure Database Copy or BACPAC export/import)

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Sql/servers/databases/read",
            "Microsoft.Sql/servers/databases/schemas/read",
        ],
        description="Read database schema"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Sql/servers/databases/read",
            "Microsoft.Sql/servers/databases/import/action",
            "Microsoft.Sql/servers/databases/export/action",
        ],
        description="Export/import database"
    )
]
```

**Implementation Notes:**
- Use SQL Server Management Objects (SMO) or Azure CLI
- BACPAC export for portable schema + data
- Azure Database Copy is faster but requires same region
- Large databases may take hours

**Estimated Effort:** 2 weeks

---

### Plugin: AppService

**Module:** `src/iac/data_plane_plugins/appservice_plugin.py` (NEW)

**Supported Resource Type:** `Microsoft.Web/sites`

**Data Plane Items:**
1. App settings (environment variables)
2. Connection strings
3. Deployment slots
4. SSL certificates
5. Application code (optional)

**Modes:**
- **Template**: Create app with settings/connection strings (no code)
- **Replication**: Deploy actual application code from source

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Web/sites/read",
            "Microsoft.Web/sites/config/read",
        ],
        description="Read app settings"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.Web/sites/read",
            "Microsoft.Web/sites/config/read",
            "Microsoft.Web/sites/config/write",
            "Microsoft.Web/sites/sourcecontrols/write",  # For deployment
        ],
        description="Read/write app configuration and deploy code"
    )
]
```

**Implementation Notes:**
- Use `azure-mgmt-web` SDK
- App settings may contain secrets (handle carefully)
- Code deployment can use Kudu API or ZIP deploy
- Connection strings are encrypted in Azure

**Estimated Effort:** 1 week

---

### Plugin: ContainerRegistry

**Module:** `src/iac/data_plane_plugins/acr_plugin.py` (NEW)

**Supported Resource Type:** `Microsoft.ContainerRegistry/registries`

**Data Plane Items:**
1. Repositories (image names)
2. Container images (layers)
3. Image tags

**Modes:**
- **Template**: Create empty registry with repository list
- **Replication**: Copy all images using `docker pull/push` or ACR import

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=["Microsoft.ContainerRegistry/registries/read"],
        data_actions=["Microsoft.ContainerRegistry/registries/metadata/read"],
        description="List repositories"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=["Microsoft.ContainerRegistry/registries/importImage/action"],
        data_actions=[
            "Microsoft.ContainerRegistry/registries/pull/read",
            "Microsoft.ContainerRegistry/registries/push/write",
        ],
        description="Pull and push container images"
    )
]
```

**Implementation Notes:**
- Use `azure-mgmt-containerregistry` for control plane
- Use Docker SDK or ACR CLI for image copying
- ACR import is faster than pull/push (same Azure region)
- Large images may take time

**Estimated Effort:** 1 week

---

### Plugin: APIManagement

**Module:** `src/iac/data_plane_plugins/apim_plugin.py` (NEW)

**Supported Resource Type:** `Microsoft.ApiManagement/service`

**Data Plane Items:**
1. API definitions (OpenAPI specs)
2. Policies (XML)
3. Products
4. Subscriptions
5. Backends

**Modes:**
- **Template**: Create empty API structure
- **Replication**: Copy all API definitions and policies

**Required Permissions:**

Template Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.ApiManagement/service/read",
            "Microsoft.ApiManagement/service/apis/read",
        ],
        description="Read API definitions"
    )
]
```

Replication Mode:
```python
[
    Permission(
        scope="resource",
        actions=[
            "Microsoft.ApiManagement/service/read",
            "Microsoft.ApiManagement/service/apis/read",
            "Microsoft.ApiManagement/service/apis/write",
            "Microsoft.ApiManagement/service/policies/write",
        ],
        description="Read/write APIs and policies"
    )
]
```

**Implementation Notes:**
- Use `azure-mgmt-apimanagement` SDK
- Export/import using ARM templates or SDK
- Policies are XML (validate format)

**Estimated Effort:** 2 weeks

---

### Plugin: FunctionApp

**Module:** `src/iac/data_plane_plugins/function_plugin.py` (NEW)

**Supported Resource Type:** `Microsoft.Web/sites` (with kind=functionapp)

**Data Plane Items:**
1. Function code
2. Function settings (host.json, local.settings.json)
3. Bindings

**Modes:**
- **Template**: Create empty function app with correct settings
- **Replication**: Deploy actual function code

**Required Permissions:**
Similar to AppService plugin

**Implementation Notes:**
- Function Apps are a special type of App Service
- Can reuse much logic from AppService plugin
- Use Azure Functions Core Tools CLI for deployment

**Estimated Effort:** 1 week

---

## Permission Management

### Module: `src/iac/plugins/permission_verifier.py`

**Purpose:** Verify Azure RBAC permissions before attempting operations.

```python
# File: src/iac/plugins/permission_verifier.py (NEW)

import logging
from typing import List, Tuple

from azure.identity import DefaultAzureCredential
from azure.mgmt.authorization import AuthorizationManagementClient

from .base_plugin import Permission

logger = logging.getLogger(__name__)


class PermissionVerifier:
    """
    Verifies Azure RBAC permissions using Azure Authorization API.
    """

    def __init__(self, credential=None, subscription_id: str = None):
        """Initialize verifier."""
        self.credential = credential or DefaultAzureCredential()
        self.subscription_id = subscription_id
        self._client = None

    @property
    def client(self):
        """Lazy-load authorization client."""
        if not self._client:
            self._client = AuthorizationManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id,
            )
        return self._client

    def verify_permissions(
        self,
        resource_id: str,
        required: List[Permission],
    ) -> Tuple[bool, List[str]]:
        """Verify current principal has required permissions.

        Args:
            resource_id: Azure resource ID
            required: List of required permissions

        Returns:
            (has_all_permissions: bool, missing_permissions: List[str])
        """
        missing = []

        for perm in required:
            # Check actions
            for action in perm.actions:
                if not self._has_action(resource_id, action):
                    missing.append(action)

            # Check data actions
            for data_action in perm.data_actions:
                if not self._has_data_action(resource_id, data_action):
                    missing.append(data_action)

        return (len(missing) == 0, missing)

    def _has_action(self, resource_id: str, action: str) -> bool:
        """Check if principal has a specific action."""
        try:
            # Use permissions.list_for_resource() API
            # This requires parsing resource_id to extract components
            resource_group, provider, resource_type, resource_name = \
                self._parse_resource_id(resource_id)

            permissions = self.client.permissions.list_for_resource(
                resource_group_name=resource_group,
                resource_provider_namespace=provider,
                parent_resource_path="",
                resource_type=resource_type,
                resource_name=resource_name,
            )

            # Check if action is in any permission set
            for perm in permissions:
                if action in perm.actions:
                    # Check not_actions don't exclude it
                    if action not in perm.not_actions:
                        return True

            return False

        except Exception as e:
            logger.warning(f"Failed to check permission {action}: {e}")
            return False  # Fail safe

    def _has_data_action(self, resource_id: str, data_action: str) -> bool:
        """Check if principal has a specific data action."""
        # Similar to _has_action but checks data_actions
        # ... implementation ...
        pass

    def _parse_resource_id(self, resource_id: str) -> tuple:
        """Parse Azure resource ID into components.

        Example:
            /subscriptions/{sub}/resourceGroups/{rg}/providers/{provider}/{type}/{name}

        Returns:
            (resource_group, provider, resource_type, resource_name)
        """
        parts = resource_id.split("/")
        # Extract components from parts list
        # ... implementation ...
        pass

    def generate_role_assignment_script(
        self,
        resource_id: str,
        required: List[Permission],
    ) -> str:
        """Generate Azure CLI script to grant required permissions.

        Useful for providing users with commands to fix permission issues.

        Returns:
            Bash script with az role assignment commands
        """
        script_lines = [
            "#!/bin/bash",
            "# Script to grant required permissions",
            f"# Resource: {resource_id}",
            "",
        ]

        for perm in required:
            # Map actions to built-in roles (e.g., "Contributor", "Key Vault Secrets Officer")
            role = self._suggest_role(perm)
            script_lines.append(
                f"az role assignment create --assignee <YOUR_PRINCIPAL_ID> "
                f"--role '{role}' --scope '{resource_id}'"
            )

        return "\n".join(script_lines)

    def _suggest_role(self, permission: Permission) -> str:
        """Suggest Azure built-in role for permission set."""
        # Map common action patterns to roles
        action_to_role = {
            "Microsoft.KeyVault/vaults/secrets/getSecret/action": "Key Vault Secrets User",
            "Microsoft.KeyVault/vaults/secrets/setSecret/action": "Key Vault Secrets Officer",
            "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/read": "Storage Blob Data Reader",
            "Microsoft.Storage/storageAccounts/blobServices/containers/blobs/write": "Storage Blob Data Contributor",
        }

        for action in permission.data_actions:
            if action in action_to_role:
                return action_to_role[action]

        # Default
        return "Contributor"
```

**Contract:**
- **Inputs:** Resource ID, list of required permissions
- **Outputs:** Bool (has permissions), list of missing permissions
- **Side Effects:** Azure Authorization API calls
- **Dependencies:** `azure-mgmt-authorization`

---

## Error Handling & Resilience

### Principles

1. **Partial Success**: One plugin failure doesn't stop others
2. **Detailed Logging**: Every error captured with context
3. **User Guidance**: Suggest fixes for common errors
4. **Retry Logic**: Transient failures get automatic retry
5. **Cleanup**: Failed operations don't leave partial state

### Error Categories

```python
# File: src/iac/plugins/errors.py (NEW)

class DataPlaneError(Exception):
    """Base exception for data plane operations."""
    pass


class PermissionDeniedError(DataPlaneError):
    """Insufficient Azure RBAC permissions."""
    def __init__(self, missing_permissions: List[str]):
        self.missing_permissions = missing_permissions
        super().__init__(f"Missing permissions: {', '.join(missing_permissions)}")


class ResourceNotFoundError(DataPlaneError):
    """Resource doesn't exist in Azure."""
    pass


class PluginNotFoundError(DataPlaneError):
    """No plugin available for resource type."""
    pass


class ReplicationFailedError(DataPlaneError):
    """Replication operation failed."""
    def __init__(self, resource_id: str, reason: str):
        self.resource_id = resource_id
        self.reason = reason
        super().__init__(f"Replication failed for {resource_id}: {reason}")


class CredentialError(DataPlaneError):
    """Failed to obtain Azure credentials."""
    pass
```

### Retry Decorator

```python
# File: src/iac/plugins/retry.py (NEW)

import functools
import logging
import time
from typing import Callable, Type

from azure.core.exceptions import AzureError, HttpResponseError

logger = logging.getLogger(__name__)


def retry_on_transient_error(
    max_attempts: int = 3,
    delay_seconds: float = 2.0,
    backoff_multiplier: float = 2.0,
    exceptions: tuple = (HttpResponseError,),
):
    """Decorator to retry operations on transient Azure errors.

    Args:
        max_attempts: Maximum retry attempts
        delay_seconds: Initial delay between retries
        backoff_multiplier: Multiply delay by this each retry
        exceptions: Tuple of exception types to catch
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 1
            delay = delay_seconds

            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        logger.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {e}"
                        )
                        raise

                    # Check if error is truly transient (status code 429, 503, etc.)
                    if hasattr(e, 'status_code') and e.status_code in (429, 503, 504):
                        logger.warning(
                            f"{func.__name__} attempt {attempt} failed (transient): {e}. "
                            f"Retrying in {delay}s..."
                        )
                        time.sleep(delay)
                        delay *= backoff_multiplier
                        attempt += 1
                    else:
                        # Not transient, fail immediately
                        raise

        return wrapper
    return decorator


# Usage example:
# @retry_on_transient_error(max_attempts=3, delay_seconds=1.0)
# def discover_items(self, resource):
#     # Azure SDK call that may fail transiently
#     pass
```

---

## Testing Strategy

### Test Levels

#### 1. Unit Tests

**Scope:** Individual plugin methods in isolation

**Approach:** Mock Azure SDK responses

**Example Test:**
```python
# File: tests/iac/plugins/test_keyvault_plugin_unit.py

import pytest
from unittest.mock import Mock, patch
from src.iac.plugins.keyvault_plugin import KeyVaultPlugin
from src.iac.plugins.base_plugin import ReplicationMode


def test_discover_with_mode_template():
    """Test discovery in template mode returns metadata only."""
    plugin = KeyVaultPlugin()

    resource = {
        "id": "/subscriptions/xxx/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv1",
        "type": "Microsoft.KeyVault/vaults",
        "name": "kv1",
        "properties": {"vaultUri": "https://kv1.vault.azure.net/"}
    }

    # Mock Azure SDK
    with patch('azure.keyvault.secrets.SecretClient') as mock_client:
        mock_props = Mock()
        mock_props.name = "db-password"
        mock_props.enabled = True
        mock_props.content_type = None
        mock_props.tags = {}

        mock_client.return_value.list_properties_of_secrets.return_value = [mock_props]

        items = plugin.discover_with_mode(resource, ReplicationMode.TEMPLATE)

        assert len(items) == 1
        assert items[0].name == "db-password"
        assert items[0].item_type == "secret"
        # Verify no secret values were fetched (no get_secret call)
        mock_client.return_value.get_secret.assert_not_called()


def test_get_required_permissions():
    """Test permission requirements differ by mode."""
    plugin = KeyVaultPlugin()

    template_perms = plugin.get_required_permissions(ReplicationMode.TEMPLATE)
    replication_perms = plugin.get_required_permissions(ReplicationMode.REPLICATION)

    # Template should have fewer permissions
    assert len(template_perms) < len(replication_perms)

    # Replication should include setSecret
    replication_actions = replication_perms[0].data_actions
    assert any("setSecret" in action for action in replication_actions)
```

#### 2. Integration Tests

**Scope:** Plugin interacting with real Azure resources

**Approach:** Use test Azure subscription with known resources

**Setup:**
- Create test resources in dedicated resource group
- Use service principal with full permissions
- Clean up after tests

**Example Test:**
```python
# File: tests/iac/plugins/test_keyvault_plugin_integration.py

import pytest
from azure.identity import DefaultAzureCredential
from src.iac.plugins.keyvault_plugin import KeyVaultPlugin
from src.iac.plugins.credential_manager import CredentialManager, CredentialConfig


@pytest.mark.integration
@pytest.mark.azure
def test_discover_real_keyvault(test_keyvault_resource):
    """Test discovery against real Azure Key Vault.

    Requires:
        - AZURE_TEST_SUBSCRIPTION_ID env var
        - Test Key Vault with known secrets
    """
    credential = DefaultAzureCredential()
    cred_manager = CredentialManager(CredentialConfig())

    plugin = KeyVaultPlugin(credential_provider=cred_manager)

    items = plugin.discover(test_keyvault_resource)

    # Verify expected secrets found
    assert len(items) > 0
    secret_names = [item.name for item in items if item.item_type == "secret"]
    assert "test-secret-1" in secret_names


@pytest.fixture
def test_keyvault_resource():
    """Fixture providing test Key Vault resource dict."""
    return {
        "id": "/subscriptions/.../resourceGroups/test-rg/providers/Microsoft.KeyVault/vaults/test-kv",
        "type": "Microsoft.KeyVault/vaults",
        "name": "test-kv",
        "properties": {"vaultUri": "https://test-kv.vault.azure.net/"}
    }
```

#### 3. E2E Tests

**Scope:** Full data plane replication workflow

**Approach:**
1. Deploy control plane resources
2. Execute data plane replication
3. Verify target resources match source

**Example Test:**
```python
# File: tests/e2e/test_full_dataplane_replication.py

import pytest
from pathlib import Path
from src.iac.plugins.orchestrator import DataPlaneOrchestrator
from src.iac.plugins.credential_manager import CredentialManager, CredentialConfig


@pytest.mark.e2e
@pytest.mark.slow
def test_full_keyvault_replication(source_tenant, target_tenant, test_iac_dir):
    """E2E test: replicate Key Vault from source to target tenant.

    Steps:
        1. Deploy IaC to target (control plane)
        2. Execute data plane replication
        3. Verify secrets exist in target Key Vault
    """
    # Setup
    cred_manager = CredentialManager(CredentialConfig(
        tenant_id=target_tenant,
        allow_interactive=False,
    ))

    orchestrator = DataPlaneOrchestrator(credential_manager=cred_manager)

    # Execute replication
    result = orchestrator.replicate(
        iac_dir=Path(test_iac_dir),
        target_tenant_id=target_tenant,
        resource_group="test-rg",
        mode="replication",
        dry_run=False,
    )

    # Verify
    assert result.success
    assert result.resources_processed > 0
    assert len(result.errors) == 0

    # Query target Key Vault to verify secrets
    # ... verification logic ...
```

#### 4. Performance Tests

**Scope:** Large-scale operations (100+ resources)

**Metrics:**
- Discovery time per resource type
- Replication throughput (items/second)
- Memory usage
- API call count

**Example Test:**
```python
# File: tests/performance/test_plugin_performance.py

import pytest
import time
from src.iac.plugins.keyvault_plugin import KeyVaultPlugin


@pytest.mark.performance
def test_discovery_performance_100_secrets(large_keyvault_resource):
    """Test discovery performance with 100 secrets."""
    plugin = KeyVaultPlugin()

    start = time.time()
    items = plugin.discover(large_keyvault_resource)
    duration = time.time() - start

    assert len(items) == 100
    assert duration < 10.0  # Should complete in under 10 seconds

    # Log metrics
    print(f"Discovery: {len(items)} items in {duration:.2f}s ({len(items)/duration:.1f} items/sec)")
```

### Test Coverage Goals

| Component | Target Coverage |
|-----------|----------------|
| Base Plugin | 90% |
| Registry | 85% |
| Credential Manager | 80% |
| Each Plugin | 75% |
| Orchestrator | 80% |
| Overall | 80% |

### CI/CD Integration

**GitHub Actions Workflow:**
```yaml
# .github/workflows/dataplane_tests.yml

name: Data Plane Plugin Tests

on: [push, pull_request]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          uv sync
      - name: Run unit tests
        run: |
          uv run pytest tests/iac/plugins/ -m "not integration" --cov=src/iac/plugins

  integration-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    env:
      AZURE_CLIENT_ID: ${{ secrets.AZURE_TEST_CLIENT_ID }}
      AZURE_CLIENT_SECRET: ${{ secrets.AZURE_TEST_CLIENT_SECRET }}
      AZURE_TENANT_ID: ${{ secrets.AZURE_TEST_TENANT_ID }}
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install dependencies
        run: |
          uv sync
      - name: Run integration tests
        run: |
          uv run pytest tests/iac/plugins/ -m integration
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)

**Goal:** Core infrastructure and first plugin

**Tasks:**
1. ✅ **Day 1-2:** Enhance base plugin class
   - Add mode support
   - Add permission interface
   - Add progress reporting protocol

2. ✅ **Day 3-4:** Build credential manager
   - Implement priority chain
   - Add connection string support
   - Write unit tests

3. ✅ **Day 5-6:** Enhance plugin registry
   - Implement auto-discovery
   - Add plugin metadata
   - Write tests

4. ✅ **Day 7-8:** Complete KeyVault plugin
   - Add mode support
   - Implement full replication
   - Integration tests

5. ✅ **Day 9-10:** Build orchestrator skeleton
   - Resource loading from Neo4j
   - Plugin routing logic
   - Dashboard integration

**Deliverables:**
- Enhanced base classes
- Working KeyVault plugin (100% complete)
- Orchestrator skeleton
- 80%+ test coverage

### Phase 2: High-Priority Plugins (Week 3-6)

**Goal:** VM, Storage, and Container Registry plugins

**Week 3: Virtual Machine Plugin**
- Days 1-3: Implementation
- Days 4-5: Testing and documentation

**Week 4: Storage Account Plugin**
- Days 1-3: Complete remaining work (file shares, tables, queues)
- Days 2-3: AzCopy integration
- Days 4-5: Testing

**Week 5: Container Registry Plugin**
- Days 1-3: Implementation
- Days 4-5: Testing

**Week 6: Integration and Testing**
- Days 1-2: E2E tests for all plugins
- Days 3-4: Performance testing
- Day 5: Bug fixes

**Deliverables:**
- 4 working plugins (KeyVault, VM, Storage, ACR)
- Complete test suites
- Performance benchmarks

### Phase 3: Database and API Plugins (Week 7-10)

**Goal:** CosmosDB, SQL, App Service, API Management

**Week 7-8: Database Plugins**
- CosmosDB implementation and testing
- SQL Database implementation and testing

**Week 9:** App Service Plugin
- Implementation
- Testing
- Function App variant

**Week 10:** API Management Plugin
- Implementation
- Testing

**Deliverables:**
- 8 total plugins complete
- Database replication capabilities
- API/App Service replication

### Phase 4: Integration and Polish (Week 11-12)

**Goal:** Production-ready system

**Tasks:**
1. Deploy command integration
2. Permission verification system
3. Comprehensive documentation
4. User guides and examples
5. Performance optimization
6. Error handling improvements
7. Dashboard UI refinements

**Deliverables:**
- Fully integrated `atg deploy --dataplane` command
- User documentation
- Video walkthrough
- Performance benchmarks
- Production deployment guide

---

## Appendix A: Command-Line Usage Examples

### Example 1: Template Mode (Default)

```bash
# Deploy control plane, then create empty data structures
atg deploy \
  --iac-dir ./output/terraform \
  --target-tenant-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group replicated-rg \
  --dataplane

# Result:
# - Empty Key Vaults with secret names (no values)
# - Empty storage containers (no blobs)
# - Empty databases with schema (no data)
```

### Example 2: Full Replication Mode

```bash
# Deploy control plane, then replicate all data
atg deploy \
  --iac-dir ./output/terraform \
  --target-tenant-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-mode replication \
  --sp-client-id $AZURE_CLIENT_ID \
  --sp-client-secret $AZURE_CLIENT_SECRET \
  --sp-tenant-id $AZURE_TENANT_ID

# Result:
# - Full Key Vault replication (actual secret values)
# - All storage blobs copied
# - All database data copied
```

### Example 3: Dry-Run (Plan Only)

```bash
# See what would be replicated without executing
atg deploy \
  --iac-dir ./output/terraform \
  --target-tenant-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-mode replication \
  --dry-run

# Result:
# - Lists all resources that would be replicated
# - Shows estimated time and data transfer size
# - No actual changes made
```

### Example 4: Interactive Mode

```bash
# Allow user prompts for mode selection and confirmation
atg deploy \
  --iac-dir ./output/terraform \
  --target-tenant-id xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx \
  --resource-group replicated-rg \
  --dataplane \
  --dataplane-interactive

# Prompts:
# - Select mode (template/replication)
# - Confirm data copy operations
# - Select which resource types to process
```

---

## Appendix B: Permission Requirements Summary

| Resource Type | Template Mode Permissions | Replication Mode Permissions |
|---------------|--------------------------|------------------------------|
| Key Vault | `secrets/getMetadata`, `keys/read`, `certificates/read` | `secrets/getSecret`, `secrets/setSecret`, `keys/create`, `certificates/create` |
| Storage Account | `containers/read` | `containers/read`, `blobs/read`, `blobs/write`, `listKeys` |
| Virtual Machine | `virtualMachines/read`, `extensions/read` | `extensions/write`, `disks/read`, `snapshots/write` |
| Cosmos DB | `readMetadata` | `items/read`, `items/create` |
| SQL Database | `databases/read`, `schemas/read` | `databases/import`, `databases/export` |
| App Service | `sites/read`, `config/read` | `config/write`, `sourcecontrols/write` |
| Container Registry | `registries/metadata/read` | `registries/pull`, `registries/push`, `importImage` |
| API Management | `apis/read` | `apis/write`, `policies/write` |

**Recommended Built-in Roles:**
- **Template Mode:** Reader + specific data reader roles
- **Replication Mode:** Contributor + specific data contributor roles

**Grant Commands:**
```bash
# Key Vault (Replication Mode)
az role assignment create \
  --assignee $SP_ID \
  --role "Key Vault Secrets Officer" \
  --scope $KEYVAULT_ID

# Storage Account (Replication Mode)
az role assignment create \
  --assignee $SP_ID \
  --role "Storage Blob Data Contributor" \
  --scope $STORAGE_ID

# Virtual Machine (Replication Mode)
az role assignment create \
  --assignee $SP_ID \
  --role "Virtual Machine Contributor" \
  --scope $VM_ID
```

---

## Appendix C: Neo4j Query Integration

### Query: Get Resources Needing Data Plane Replication

```cypher
// Find all resources in target tenant that have data plane plugins
MATCH (r:Resource)
WHERE r.tenant_id = $target_tenant_id
  AND r.type IN [
    'Microsoft.KeyVault/vaults',
    'Microsoft.Storage/storageAccounts',
    'Microsoft.Compute/virtualMachines',
    'Microsoft.DocumentDB/databaseAccounts',
    'Microsoft.Sql/servers/databases',
    'Microsoft.Web/sites',
    'Microsoft.ContainerRegistry/registries',
    'Microsoft.ApiManagement/service'
  ]
RETURN r.id AS resource_id,
       r.type AS resource_type,
       r.name AS resource_name,
       r.properties AS properties
ORDER BY r.type, r.name
```

### Query: Find Source Resource for Target

```cypher
// Match target resource to source resource by name and type
MATCH (source:Resource {name: $resource_name, type: $resource_type})
WHERE source.tenant_id = $source_tenant_id
MATCH (target:Resource {name: $resource_name, type: $resource_type})
WHERE target.tenant_id = $target_tenant_id
RETURN source, target
```

---

## Summary

This specification provides a complete architectural blueprint for implementing data plane replication in Azure Tenant Grapher. The design follows the project's core principles:

1. **Occam's Razor**: Simple, modular plugins with single responsibility
2. **Trust in Emergence**: Complex replication emerges from simple plugin contracts
3. **Regeneratable**: All code can be rebuilt from these specifications
4. **Self-Contained**: Each plugin is independent and testable

**Key Success Metrics:**
- Fidelity increase from 30.8% to 95%+
- All 9 critical resource types supported
- Comprehensive permission management
- Production-ready error handling
- Complete test coverage (80%+)

**Next Steps for Builder Agents:**
1. Begin with Phase 1 (Foundation) - enhance base classes
2. Implement credential manager and registry
3. Complete KeyVault plugin (90% done)
4. Build orchestrator and deploy integration
5. Progress through remaining plugins in priority order

All specifications are ready for parallel implementation by multiple builder agents.
