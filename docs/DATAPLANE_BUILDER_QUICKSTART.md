# Data Plane Plugin Implementation - Builder Quick Start

**For:** Builder Agents
**Purpose:** Get started implementing data plane plugins
**Time to First Working Plugin:** 2-3 days

---

## Overview

You're implementing data plane replication for Azure Tenant Grapher to increase fidelity from 30.8% to 95%+. This guide gets you started quickly.

---

## Before You Begin

### Required Reading

1. **MUST READ:** `/home/azureuser/src/azure-tenant-grapher/docs/DATAPLANE_PLUGIN_ARCHITECTURE.md`
   - Complete technical specification (100+ pages)
   - Read sections relevant to your assigned task

2. **SHOULD READ:** `/home/azureuser/src/azure-tenant-grapher/docs/DATAPLANE_ANALYSIS_SUMMARY.md`
   - 15-minute overview of the architecture

3. **REFERENCE:** Existing plugins
   - `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/keyvault_plugin.py` (90% complete)
   - `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/storage_plugin.py` (85% complete)

### Your Environment

- **Working Directory:** `/home/azureuser/src/azure-tenant-grapher`
- **Python Version:** 3.12
- **Package Manager:** `uv`
- **Test Command:** `uv run pytest tests/iac/plugins/ -v`

---

## Task Assignment Matrix

Pick your task based on priority and your expertise:

| Task | Priority | Complexity | Duration | Prerequisites |
|------|----------|-----------|----------|---------------|
| **Foundation: Base Classes** | 1 | Medium | 2 days | None |
| **Foundation: Credential Manager** | 1 | Low | 1 day | None |
| **Foundation: Plugin Registry** | 1 | Medium | 1 day | Base Classes |
| **Plugin: KeyVault Completion** | 2 | Low | 1 day | Foundation |
| **Plugin: Virtual Machine** | 2 | Medium | 3 days | Foundation |
| **Plugin: Storage Completion** | 2 | Low | 2 days | Foundation |
| **Plugin: Container Registry** | 3 | Medium | 3 days | Foundation |
| **Plugin: CosmosDB** | 3 | High | 4 days | Foundation |
| **Plugin: SQL Database** | 3 | High | 4 days | Foundation |
| **Plugin: App Service** | 4 | Medium | 3 days | Foundation |
| **Plugin: API Management** | 4 | High | 4 days | Foundation |
| **Orchestrator** | 2 | High | 3 days | Foundation + 1 plugin |
| **Deploy Integration** | 5 | Medium | 2 days | Orchestrator |

---

## Quick Start: Foundation Tasks

### Task 1: Enhance Base Plugin Class

**File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/base_plugin.py`

**Goal:** Add mode support and new protocols

**Steps:**

1. **Add new imports and enums:**
```python
from enum import Enum
from typing import Protocol

class ReplicationMode(Enum):
    """Data plane replication modes."""
    TEMPLATE = "template"
    REPLICATION = "replication"
```

2. **Add Permission data class:**
```python
@dataclass
class Permission:
    """Azure RBAC permission requirement."""
    scope: str
    actions: List[str]
    not_actions: List[str] = field(default_factory=list)
    data_actions: List[str] = field(default_factory=list)
    description: str = ""
```

3. **Add protocols:**
```python
class ProgressReporter(Protocol):
    """Protocol for progress reporting."""
    def report_discovery(self, resource_id: str, item_count: int) -> None: ...
    def report_replication_progress(self, item_name: str, progress_pct: float) -> None: ...
    def report_completion(self, result: ReplicationResult) -> None: ...

class CredentialProvider(Protocol):
    """Protocol for credential provision."""
    def get_credential(self) -> Any: ...
    def get_connection_string(self, resource_id: str) -> Optional[str]: ...
```

4. **Enhance DataPlaneItem:**
```python
@dataclass
class DataPlaneItem:
    name: str
    item_type: str
    properties: Dict[str, Any]
    source_resource_id: str
    metadata: Optional[Dict[str, Any]] = None
    size_bytes: Optional[int] = None  # NEW
```

5. **Enhance ReplicationResult:**
```python
@dataclass
class ReplicationResult:
    success: bool
    items_discovered: int
    items_replicated: int
    items_skipped: int = 0  # NEW
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0  # NEW
```

6. **Add new abstract methods to DataPlanePlugin:**
```python
@abstractmethod
def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
    """Return Azure RBAC permissions required."""
    pass

@abstractmethod
def discover_with_mode(
    self, resource: Dict[str, Any], mode: ReplicationMode
) -> List[DataPlaneItem]:
    """Discover with mode awareness."""
    pass

@abstractmethod
def replicate_with_mode(
    self,
    source_resource: Dict[str, Any],
    target_resource: Dict[str, Any],
    mode: ReplicationMode,
) -> ReplicationResult:
    """Replicate with mode awareness."""
    pass
```

7. **Add new concrete methods:**
```python
def verify_permissions(
    self, resource_id: str, mode: ReplicationMode
) -> tuple[bool, List[str]]:
    """Verify current credential has required permissions."""
    # Stub for now, implement after PermissionVerifier exists
    return (True, [])

def estimate_operation_time(
    self, items: List[DataPlaneItem], mode: ReplicationMode
) -> float:
    """Estimate time required."""
    if mode == ReplicationMode.TEMPLATE:
        return 0.0
    return len(items) * 0.1  # 100ms per item default

def supports_mode(self, mode: ReplicationMode) -> bool:
    """Check if plugin supports mode."""
    return True  # Default: support both
```

8. **Update __init__ to accept providers:**
```python
def __init__(
    self,
    credential_provider: Optional[CredentialProvider] = None,
    progress_reporter: Optional[ProgressReporter] = None,
) -> None:
    """Initialize with optional providers."""
    self.credential_provider = credential_provider
    self.progress_reporter = progress_reporter
    self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
```

**Test:**
```bash
cd /home/azureuser/src/azure-tenant-grapher
uv run pytest tests/iac/plugins/test_base_plugin.py -v
```

**Completion Criteria:**
- All new enums, classes, and methods added
- Existing tests still pass
- New tests for Permission class and protocols

---

### Task 2: Build Credential Manager

**File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/credential_manager.py` (NEW)

**Goal:** Implement credential resolution with priority chain

**Steps:**

1. **Create the file:**
```bash
cd /home/azureuser/src/azure-tenant-grapher/src/iac/plugins
touch credential_manager.py
```

2. **Implement CredentialConfig:**
```python
@dataclass
class CredentialConfig:
    """Configuration for credential resolution."""
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    tenant_id: Optional[str] = None
    allow_interactive: bool = False
    use_environment: bool = True
    connection_strings: dict[str, str] = None
```

3. **Implement CredentialManager:**
```python
class CredentialManager:
    """Manages Azure credential resolution."""

    def __init__(self, config: Optional[CredentialConfig] = None):
        self.config = config or CredentialConfig()
        self._credential_cache: Optional[Any] = None

    def get_credential(self) -> Any:
        """Get Azure credential using priority chain."""
        if self._credential_cache:
            return self._credential_cache

        # Priority 1: Explicit credentials
        if self._has_explicit_credentials():
            self._credential_cache = ClientSecretCredential(...)
            return self._credential_cache

        # Priority 2: Environment variables
        if self.config.use_environment and self._has_env_credentials():
            self._credential_cache = ClientSecretCredential(...)
            return self._credential_cache

        # Priority 3: DefaultAzureCredential
        self._credential_cache = DefaultAzureCredential()
        return self._credential_cache
```

**Full implementation in:** Architecture spec, Section "Credential Management System"

**Test:**
```bash
uv run pytest tests/iac/plugins/test_credential_manager.py -v
```

**Completion Criteria:**
- All 4 priority levels implemented
- Environment variable reading works
- Credential caching works
- Tests cover all code paths

---

### Task 3: Enhance Plugin Registry

**File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/registry.py` (NEW, replaces manual discovery in `__init__.py`)

**Goal:** Auto-discover plugins by scanning directory

**Steps:**

1. **Create the file:**
```bash
cd /home/azureuser/src/azure-tenant-grapher/src/iac/plugins
touch registry.py
```

2. **Implement PluginMetadata:**
```python
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
```

3. **Implement DataPlanePluginRegistry:**
```python
class DataPlanePluginRegistry:
    """Registry with auto-discovery."""

    _instance = None
    _plugins: Dict[str, PluginMetadata] = {}
    _initialized = False

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def discover_plugins(self) -> None:
        """Auto-discover plugins by scanning directory."""
        plugins_dir = Path(__file__).parent

        plugin_files = [
            f for f in plugins_dir.glob("*_plugin.py")
            if f.name not in ("base_plugin.py", "registry.py")
        ]

        for plugin_file in plugin_files:
            # Import module dynamically
            module_name = f"src.iac.plugins.{plugin_file.stem}"
            module = importlib.import_module(module_name)

            # Find DataPlanePlugin subclasses
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, DataPlanePlugin) and not inspect.isabstract(obj):
                    self._register_plugin_class(obj, str(plugin_file))
```

**Full implementation in:** Architecture spec, Section "Plugin Registry Enhancement"

**Test:**
```bash
uv run pytest tests/iac/plugins/test_plugin_registry.py -v
```

**Completion Criteria:**
- Auto-discovery scans directory correctly
- KeyVault and Storage plugins are found
- Registry is singleton
- Tests verify all methods

---

## Quick Start: Plugin Tasks

### Task: Complete KeyVault Plugin

**File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/keyvault_plugin.py`

**Status:** 90% complete, needs mode support

**Steps:**

1. **Add `get_required_permissions()` method:**
```python
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
                    # ... more actions
                ],
                description="Read and write secrets, keys, certificates"
            )
        ]
```

2. **Add `discover_with_mode()` method:**
```python
def discover_with_mode(
    self, resource: Dict[str, Any], mode: ReplicationMode
) -> List[DataPlaneItem]:
    """Discover with mode awareness."""
    # Current discover() already does metadata-only
    return self.discover(resource)
```

3. **Implement `replicate_with_mode()` method (replace stub):**
```python
def replicate_with_mode(
    self,
    source_resource: Dict[str, Any],
    target_resource: Dict[str, Any],
    mode: ReplicationMode,
) -> ReplicationResult:
    """Complete implementation."""
    items = self.discover(source_resource)

    if mode == ReplicationMode.TEMPLATE:
        # Create secrets with placeholder values
        target_vault_uri = self._get_vault_uri(target_resource)
        credential = self.credential_provider.get_credential()
        secret_client = SecretClient(vault_url=target_vault_uri, credential=credential)

        for item in items:
            if item.item_type == "secret":
                secret_client.set_secret(item.name, "PLACEHOLDER_VALUE")

        return ReplicationResult(
            success=True,
            items_discovered=len(items),
            items_replicated=len(items),
            warnings=["Template mode: secrets have placeholder values"]
        )
    else:  # REPLICATION
        # Full replication: fetch and copy actual values
        source_vault_uri = self._get_vault_uri(source_resource)
        target_vault_uri = self._get_vault_uri(target_resource)
        credential = self.credential_provider.get_credential()

        source_client = SecretClient(vault_url=source_vault_uri, credential=credential)
        target_client = SecretClient(vault_url=target_vault_uri, credential=credential)

        replicated = 0
        errors = []

        for item in items:
            try:
                if item.item_type == "secret":
                    # Get actual value from source
                    secret = source_client.get_secret(item.name)
                    # Set in target
                    target_client.set_secret(item.name, secret.value)
                    replicated += 1

                    # Report progress
                    if self.progress_reporter:
                        self.progress_reporter.report_replication_progress(
                            item.name, (replicated / len(items)) * 100
                        )
            except Exception as e:
                errors.append(f"Failed to replicate {item.name}: {e}")

        return ReplicationResult(
            success=len(errors) == 0,
            items_discovered=len(items),
            items_replicated=replicated,
            errors=errors,
        )
```

**Test:**
```bash
uv run pytest tests/iac/plugins/test_keyvault_plugin.py -v
```

**Completion Criteria:**
- All abstract methods implemented
- Both modes work correctly
- Integration test passes with real Key Vault
- Error handling robust

---

### Task: Implement New Plugin (Template)

**Example:** Virtual Machine Plugin

**File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/vm_plugin.py` (NEW)

**Steps:**

1. **Create skeleton:**
```python
"""Virtual Machine data plane replication plugin."""

import logging
from typing import Any, Dict, List

from .base_plugin import (
    DataPlaneItem,
    DataPlanePlugin,
    ReplicationMode,
    ReplicationResult,
    Permission,
)

logger = logging.getLogger(__name__)


class VirtualMachinePlugin(DataPlanePlugin):
    """Data plane plugin for Azure Virtual Machines."""

    @property
    def supported_resource_type(self) -> str:
        """Azure resource type for VMs."""
        return "Microsoft.Compute/virtualMachines"

    def get_required_permissions(self, mode: ReplicationMode) -> List[Permission]:
        """Return required permissions."""
        # Implement based on spec
        pass

    def discover_with_mode(
        self, resource: Dict[str, Any], mode: ReplicationMode
    ) -> List[DataPlaneItem]:
        """Discover VM extensions and data disks."""
        # Implement based on spec
        pass

    def replicate_with_mode(
        self,
        source_resource: Dict[str, Any],
        target_resource: Dict[str, Any],
        mode: ReplicationMode,
    ) -> ReplicationResult:
        """Replicate VM data plane."""
        # Implement based on spec
        pass

    # Legacy methods (delegate to mode-aware versions)
    def discover(self, resource: Dict[str, Any]) -> List[DataPlaneItem]:
        return self.discover_with_mode(resource, ReplicationMode.TEMPLATE)

    def generate_replication_code(
        self, items: List[DataPlaneItem], output_format: str = "terraform"
    ) -> str:
        # Generate Terraform code for extensions
        pass

    def replicate(
        self, source_resource: Dict[str, Any], target_resource: Dict[str, Any]
    ) -> ReplicationResult:
        return self.replicate_with_mode(
            source_resource, target_resource, ReplicationMode.TEMPLATE
        )
```

2. **Fill in implementation:** See architecture spec, section "Plugin: VirtualMachine"

3. **Write tests:**
```bash
touch tests/iac/plugins/test_vm_plugin.py
```

4. **Test:**
```bash
uv run pytest tests/iac/plugins/test_vm_plugin.py -v
```

**Completion Criteria:**
- All abstract methods implemented
- Unit tests pass (mocked Azure SDK)
- Integration test passes (real VM)
- Documented in docstrings

---

## Common Patterns

### Pattern 1: Azure SDK Authentication

```python
# In any plugin's discover_with_mode or replicate_with_mode:

from azure.identity import DefaultAzureCredential
from azure.mgmt.keyvault import KeyVaultManagementClient

# Get credential from provider
credential = self.credential_provider.get_credential() if self.credential_provider else DefaultAzureCredential()

# Use with Azure SDK client
client = KeyVaultManagementClient(credential=credential, subscription_id="...")
```

### Pattern 2: Progress Reporting

```python
# During discovery:
if self.progress_reporter:
    self.progress_reporter.report_discovery(resource_id, len(items))

# During replication:
if self.progress_reporter:
    progress_pct = (replicated / total) * 100
    self.progress_reporter.report_replication_progress(item_name, progress_pct)

# At completion:
if self.progress_reporter:
    self.progress_reporter.report_completion(result)
```

### Pattern 3: Error Handling

```python
from azure.core.exceptions import AzureError, HttpResponseError

errors = []
warnings = []

try:
    # Azure SDK operation
    items = client.list_secrets()
except HttpResponseError as e:
    if e.status_code == 404:
        errors.append(f"Resource not found: {resource_id}")
    elif e.status_code == 403:
        errors.append(f"Permission denied: {e.message}")
    else:
        errors.append(f"Azure error: {e}")
except AzureError as e:
    errors.append(f"Azure SDK error: {e}")
except Exception as e:
    errors.append(f"Unexpected error: {e}")

return ReplicationResult(
    success=len(errors) == 0,
    errors=errors,
    warnings=warnings,
)
```

---

## Testing Checklist

### Unit Tests (Mocked)

- [ ] Discovery returns correct DataPlaneItems
- [ ] Replication handles both modes
- [ ] Permission requirements correct for both modes
- [ ] Error handling works (404, 403, 500, etc.)
- [ ] Progress reporting called correctly
- [ ] Credential provider used correctly

### Integration Tests (Real Azure)

- [ ] Discovery works with real resource
- [ ] Replication works (template mode)
- [ ] Replication works (full mode)
- [ ] Permission denied handled gracefully
- [ ] Large datasets handled (pagination)

### E2E Tests

- [ ] Deploy + data plane replication end-to-end
- [ ] Target tenant matches source after replication
- [ ] Dashboard shows correct progress

---

## Debugging Tips

### Issue: Plugin Not Discovered

**Symptom:** Registry doesn't find your plugin

**Check:**
1. File named `*_plugin.py` (e.g., `vm_plugin.py`)
2. Class inherits from `DataPlanePlugin`
3. Class is not abstract (implements all abstract methods)
4. File in `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/` directory

**Debug:**
```python
from src.iac.plugins.registry import registry
print(registry.list_supported_types())  # Should include your type
```

### Issue: Permission Denied

**Symptom:** Azure SDK returns 403 Forbidden

**Check:**
1. Service principal has correct role assignments
2. Data plane permissions granted (not just control plane)
3. Key Vault access policies configured (for Key Vault)

**Fix:**
```bash
# Grant Key Vault data plane access
az role assignment create \
  --assignee $SP_ID \
  --role "Key Vault Secrets Officer" \
  --scope $KEYVAULT_ID
```

### Issue: Credential Not Found

**Symptom:** `CredentialError` or authentication failures

**Check:**
1. Environment variables set: `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`, `AZURE_TENANT_ID`
2. Azure CLI logged in: `az account show`
3. Credential provider passed to plugin constructor

**Fix:**
```bash
# Set environment variables
export AZURE_CLIENT_ID=xxx
export AZURE_CLIENT_SECRET=xxx
export AZURE_TENANT_ID=xxx

# Or login with Azure CLI
az login --tenant xxx
```

---

## Code Review Checklist

Before submitting your implementation:

### Code Quality
- [ ] All abstract methods implemented
- [ ] Docstrings on all public methods
- [ ] Type hints on all parameters and returns
- [ ] No hardcoded values (use config/env vars)
- [ ] Error messages are actionable

### Testing
- [ ] Unit tests pass: `uv run pytest tests/iac/plugins/test_*_plugin.py`
- [ ] Integration tests pass (if applicable)
- [ ] Test coverage >75%: `uv run pytest --cov=src/iac/plugins`

### Documentation
- [ ] Plugin documented in module docstring
- [ ] Mode behavior explained in docstrings
- [ ] Permission requirements documented
- [ ] Example usage in docstring

### Integration
- [ ] Plugin auto-discovered by registry
- [ ] Works with credential provider
- [ ] Reports progress correctly
- [ ] Handles errors gracefully

---

## Getting Help

### Documentation
1. **Full spec:** `/home/azureuser/src/azure-tenant-grapher/docs/DATAPLANE_PLUGIN_ARCHITECTURE.md`
2. **Summary:** `/home/azureuser/src/azure-tenant-grapher/docs/DATAPLANE_ANALYSIS_SUMMARY.md`
3. **Project guide:** `/home/azureuser/src/azure-tenant-grapher/CLAUDE.md`

### Code Examples
1. **KeyVault plugin:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/keyvault_plugin.py`
2. **Storage plugin:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/storage_plugin.py`
3. **Existing tests:** `/home/azureuser/src/azure-tenant-grapher/tests/iac/plugins/`

### Azure SDK Documentation
1. **Azure Identity:** https://learn.microsoft.com/python/api/azure-identity
2. **Key Vault:** https://learn.microsoft.com/python/api/azure-keyvault-secrets
3. **Storage:** https://learn.microsoft.com/python/api/azure-storage-blob
4. **Compute:** https://learn.microsoft.com/python/api/azure-mgmt-compute

---

## Success Criteria

Your implementation is complete when:

1. **All tests pass:** Unit + Integration + E2E
2. **Coverage >75%:** Code coverage meets target
3. **Registry finds plugin:** Auto-discovery works
4. **Both modes work:** Template and Replication modes tested
5. **Permissions documented:** All required RBAC permissions listed
6. **Error handling robust:** Graceful handling of all failure modes
7. **Progress reporting:** Dashboard integration working
8. **Documentation complete:** Docstrings and examples provided

---

## Next Steps After Your Task

Once you complete your assigned task:

1. **Update this document:** Add any lessons learned or debugging tips
2. **Create PR:** Submit for review
3. **Help next builder:** Answer questions in shared docs
4. **Pick next task:** Move to next priority plugin or orchestrator

---

**Good luck, and happy building!**
