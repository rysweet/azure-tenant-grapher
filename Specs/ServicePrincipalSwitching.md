# Specification: Automatic Service Principal Switching

## Purpose

Enable azure-tenant-grapher to automatically switch between source and target tenant credentials based on operation context, supporting cross-tenant discovery and deployment workflows.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      CLI Commands                            │
│  (scan, generate-iac, deploy-iac with tenant context)       │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              DualTenantConfig                                │
│  - source_tenant (discovery, Reader)                         │
│  - target_tenant (deployment, Contributor)                   │
│  - operation_mode (single/dual)                              │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          TenantCredentialProvider                            │
│  get_credential(operation: OperationType) -> Credential      │
│  - Selects appropriate tenant based on operation             │
│  - Logs context switches                                     │
│  - Caches credentials per tenant                             │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        ▼                         ▼
┌──────────────────┐    ┌──────────────────┐
│ Discovery        │    │ Deployment       │
│ (Source Tenant)  │    │ (Target Tenant)  │
│ Reader role      │    │ Contributor role │
└──────────────────┘    └──────────────────┘
```

## Module 1: Dual Tenant Configuration

### Module: `src/dual_tenant_config.py`

#### Purpose
Extend configuration to support dual-tenant credentials with clear role separation.

#### Contract

**Inputs:**
- Environment variables: `AZURE_SOURCE_TENANT_*`, `AZURE_TARGET_TENANT_*`
- Backward compatible: single tenant via `AZURE_TENANT_ID`

**Outputs:**
- `DualTenantConfig` dataclass containing source and target credentials

**Side Effects:**
- None (pure configuration)

#### Data Model

```python
@dataclass
class TenantCredentials:
    """Credentials for a single tenant."""
    tenant_id: str
    client_id: str
    client_secret: str
    subscription_id: Optional[str] = None
    role: str = "Reader"  # Expected role: Reader or Contributor

@dataclass
class DualTenantConfig:
    """Configuration for dual-tenant operations."""
    source_tenant: Optional[TenantCredentials] = None  # For discovery
    target_tenant: Optional[TenantCredentials] = None  # For deployment
    operation_mode: Literal["single", "dual"] = "single"
    auto_switch: bool = True

    def is_dual_tenant_mode(self) -> bool:
        return self.operation_mode == "dual" and self.source_tenant and self.target_tenant
```

#### Environment Variables

```bash
# Source tenant (discovery - Reader role)
AZURE_SOURCE_TENANT_ID=<tenant-id>
AZURE_SOURCE_TENANT_CLIENT_ID=<client-id>
AZURE_SOURCE_TENANT_CLIENT_SECRET=<secret>
AZURE_SOURCE_TENANT_SUBSCRIPTION_ID=<subscription-id>

# Target tenant (deployment - Contributor role)
AZURE_TARGET_TENANT_ID=<tenant-id>
AZURE_TARGET_TENANT_CLIENT_ID=<client-id>
AZURE_TARGET_TENANT_CLIENT_SECRET=<secret>
AZURE_TARGET_TENANT_SUBSCRIPTION_ID=<subscription-id>

# Control
AZTG_DUAL_TENANT_MODE=true  # Enable dual-tenant mode
AZTG_AUTO_SWITCH=true       # Auto-switch credentials (default: true)
```

#### Backward Compatibility

- If only `AZURE_TENANT_ID` is set, use single-tenant mode
- If both source and target are set, enable dual-tenant mode
- Existing configs continue to work unchanged

#### Implementation Notes

- Add factory function: `create_dual_tenant_config_from_env()`
- Integrate with existing `AzureTenantGrapherConfig` as optional field
- Validation ensures credentials are present when dual mode enabled

---

## Module 2: Credential Provider

### Module: `src/credential_provider.py`

#### Purpose
Centralized credential selection based on operation context with transparent switching.

#### Contract

**Inputs:**
- `DualTenantConfig`
- `OperationType` enum (DISCOVERY, DEPLOYMENT, VALIDATION)

**Outputs:**
- Azure credential object for the appropriate tenant
- Logs credential switches at INFO level

**Side Effects:**
- Credential caching per tenant (identity-safe)
- Logging of tenant context switches

#### Core API

```python
class OperationType(Enum):
    """Types of operations requiring credentials."""
    DISCOVERY = "discovery"      # Read operations (source tenant)
    DEPLOYMENT = "deployment"    # Write operations (target tenant)
    VALIDATION = "validation"    # Depends on validation context

class TenantCredentialProvider:
    """Provides credentials based on operation context."""

    def __init__(self, config: DualTenantConfig):
        self.config = config
        self._credential_cache: Dict[str, Any] = {}
        self._current_tenant_id: Optional[str] = None

    def get_credential(self, operation: OperationType) -> tuple[Any, str]:
        """
        Get credential for operation type.

        Returns:
            Tuple of (credential, tenant_id)

        Raises:
            ValueError: If required credentials not configured
        """

    def get_tenant_id(self, operation: OperationType) -> str:
        """Get tenant ID for operation type."""

    def get_subscription_id(self, operation: OperationType) -> Optional[str]:
        """Get subscription ID for operation type."""
```

#### Selection Logic

```python
def _select_tenant_credentials(self, operation: OperationType) -> TenantCredentials:
    """Select credentials based on operation and mode."""

    # Single-tenant mode: use same credentials for everything
    if not self.config.is_dual_tenant_mode():
        return self._get_single_tenant_credentials()

    # Dual-tenant mode: switch based on operation
    if operation == OperationType.DISCOVERY:
        return self.config.source_tenant
    elif operation == OperationType.DEPLOYMENT:
        return self.config.target_tenant
    elif operation == OperationType.VALIDATION:
        # Validation uses source tenant (read-only)
        return self.config.source_tenant
    else:
        raise ValueError(f"Unknown operation type: {operation}")
```

#### Logging

All credential switches logged:
```
INFO: Switching to source tenant (ATEVET17) for DISCOVERY operation [Reader role]
INFO: Switching to target tenant (ATEVET12) for DEPLOYMENT operation [Contributor role]
```

#### Dependencies
- `azure.identity` for credential creation
- `azure.identity.ClientSecretCredential` for service principal auth

---

## Module 3: Discovery Service Integration

### Module: `src/services/azure_discovery_service.py` (Modified)

#### Purpose
Update discovery service to use credential provider instead of fixed credential.

#### Changes Required

1. **Constructor Enhancement**
```python
def __init__(
    self,
    config: AzureTenantGrapherConfig,
    credential: Optional[Any] = None,
    credential_provider: Optional[TenantCredentialProvider] = None,
    # ... existing parameters
):
    self.config = config
    self.credential_provider = credential_provider

    # Backward compatibility: use provided credential if no provider
    if credential_provider:
        self.credential, self.tenant_id = credential_provider.get_credential(
            OperationType.DISCOVERY
        )
    else:
        self.credential = credential or DefaultAzureCredential()
        self.tenant_id = config.tenant_id
```

2. **Operation Boundaries**
- All read operations use `OperationType.DISCOVERY`
- Credential retrieved at operation start
- No changes needed to internal logic

#### Test Requirements
- Mock credential provider returns test credentials
- Verify discovery uses source tenant in dual mode
- Verify backward compatibility with single tenant

---

## Module 4: Deployment Orchestrator Integration

### Module: `src/deployment/orchestrator.py` (Modified)

#### Purpose
Enable deployment to use target tenant credentials via credential provider.

#### Changes Required

1. **Function Signature Enhancement**
```python
def deploy_iac(
    iac_dir: Path,
    target_tenant_id: str,
    resource_group: str,
    location: str = "eastus",
    subscription_id: Optional[str] = None,
    iac_format: Optional[IaCFormat] = None,
    dry_run: bool = False,
    dashboard: Optional["DeploymentDashboard"] = None,
    credential_provider: Optional[TenantCredentialProvider] = None,  # NEW
) -> dict:
```

2. **Authentication Logic Replacement**

Replace subprocess-based `az login` with SDK credential:

```python
# OLD (lines 512-554)
current_tenant_result = subprocess.run(
    ["az", "account", "show", "--query", "tenantId", "-o", "tsv"],
    ...
)

# NEW
if credential_provider:
    # Get target tenant credentials from provider
    credential, tenant_id = credential_provider.get_credential(
        OperationType.DEPLOYMENT
    )
    subscription_id = credential_provider.get_subscription_id(
        OperationType.DEPLOYMENT
    ) or subscription_id

    # Set environment for Azure CLI commands
    # (terraform, bicep, arm all use az cli under the hood)
    _set_azure_cli_context(credential, tenant_id, subscription_id)
else:
    # Fallback to existing subprocess login
    ...
```

3. **Helper Function**
```python
def _set_azure_cli_context(
    credential: Any,
    tenant_id: str,
    subscription_id: Optional[str]
) -> None:
    """
    Configure Azure CLI to use specific credential context.

    Uses `az login --service-principal` with credential details.
    """
```

#### Test Requirements
- Mock credential provider for deployment operations
- Verify deployment uses target tenant in dual mode
- Verify subprocess fallback still works
- Test dry-run mode with credential provider

---

## Module 5: CLI Integration

### Module: `src/cli_commands.py` (Modified)

#### Purpose
Wire credential provider through CLI command handlers.

#### Changes Required

1. **Configuration Loading**
```python
async def build_command_handler(
    ctx: click.Context,
    tenant_id: str,
    # ... existing params
) -> str | None:

    # Load dual-tenant config
    dual_config = create_dual_tenant_config_from_env()

    # Create credential provider if dual mode
    credential_provider = None
    if dual_config.is_dual_tenant_mode():
        credential_provider = TenantCredentialProvider(dual_config)
        logger.info(
            f"Operating in dual-tenant mode: "
            f"source={dual_config.source_tenant.tenant_id}, "
            f"target={dual_config.target_tenant.tenant_id}"
        )

    # Pass to services
    grapher = AzureTenantGrapher(
        config,
        credential_provider=credential_provider
    )
```

2. **New CLI Option (Optional)**
```python
@click.option(
    '--source-tenant-id',
    help='Source tenant for discovery (overrides env)',
    required=False
)
@click.option(
    '--target-tenant-id',
    help='Target tenant for deployment (overrides env)',
    required=False
)
```

#### Implementation Notes
- Keep existing single-tenant flow unchanged
- Add dual-tenant support as opt-in via environment variables
- Log mode clearly at startup

---

## Module 6: AzureTenantGrapher Integration

### Module: `src/azure_tenant_grapher.py` (Modified)

#### Purpose
Thread credential provider through main orchestrator class.

#### Changes Required

1. **Constructor**
```python
def __init__(
    self,
    config: AzureTenantGrapherConfig,
    credential_provider: Optional[TenantCredentialProvider] = None
):
    self.config = config
    self.credential_provider = credential_provider

    # Pass to discovery service
    self.discovery_service = AzureDiscoveryService(
        config=config,
        credential_provider=credential_provider
    )
```

2. **Deployment Method**
```python
async def deploy_generated_iac(
    self,
    iac_dir: Path,
    resource_group: str,
    # ... existing params
):
    # Pass credential provider to deployment
    result = deploy_iac(
        iac_dir=iac_dir,
        target_tenant_id=self._get_target_tenant_id(),
        resource_group=resource_group,
        credential_provider=self.credential_provider,
        # ... other params
    )
```

---

## Testing Strategy

### Unit Tests

1. **Dual Tenant Config** (`tests/test_dual_tenant_config.py`)
   - Load from environment variables
   - Validate single vs dual mode detection
   - Backward compatibility with existing configs

2. **Credential Provider** (`tests/test_credential_provider.py`)
   - Credential selection based on operation type
   - Caching behavior
   - Logging output verification
   - Error handling for missing credentials

3. **Service Integration** (`tests/test_credential_integration.py`)
   - Discovery service uses source tenant
   - Deployment uses target tenant
   - Backward compatibility with direct credential injection

### Integration Tests

1. **Full Workflow** (`tests/integration/test_dual_tenant_workflow.py`)
   - Scan with source tenant
   - Generate IaC
   - Deploy to target tenant
   - Verify credential switches logged

### Manual Testing

1. Configure two service principals (Reader source, Contributor target)
2. Run full workflow: scan → generate-iac → deploy
3. Verify operations hit correct tenants via Azure portal activity logs

---

## Migration Path

### Phase 1: Additive Changes (No Breaking Changes)
- Add dual tenant config module
- Add credential provider module
- Keep existing single-tenant flow unchanged

### Phase 2: Integration
- Add credential provider to discovery service (optional parameter)
- Add credential provider to deployment orchestrator (optional parameter)
- Thread through CLI with backward compatibility

### Phase 3: Documentation
- Update README with dual-tenant setup instructions
- Add example .env configuration
- Document permission requirements (Reader vs Contributor)

### Phase 4: Validation
- Test backward compatibility with existing single-tenant setups
- Test new dual-tenant workflows
- Verify logging clarity

---

## Configuration Example

### Dual-Tenant Setup (.env)

```bash
# Source Tenant (ATEVET17) - Discovery/Scanning (Reader role)
AZURE_SOURCE_TENANT_ID=<atevet17-tenant-id>
AZURE_SOURCE_TENANT_CLIENT_ID=<reader-sp-client-id>
AZURE_SOURCE_TENANT_CLIENT_SECRET=<reader-sp-secret>
AZURE_SOURCE_TENANT_SUBSCRIPTION_ID=<atevet17-subscription-id>

# Target Tenant (ATEVET12) - Deployment (Contributor role)
AZURE_TARGET_TENANT_ID=<atevet12-tenant-id>
AZURE_TARGET_TENANT_CLIENT_ID=<contributor-sp-client-id>
AZURE_TARGET_TENANT_CLIENT_SECRET=<contributor-sp-secret>
AZURE_TARGET_TENANT_SUBSCRIPTION_ID=<atevet12-subscription-id>

# Control
AZTG_DUAL_TENANT_MODE=true
AZTG_AUTO_SWITCH=true

# Other standard config
NEO4J_PASSWORD=<password>
NEO4J_PORT=7687
```

### Single-Tenant Setup (Backward Compatible)

```bash
# Standard single-tenant config (no changes)
AZURE_TENANT_ID=<tenant-id>
AZURE_CLIENT_ID=<client-id>
AZURE_CLIENT_SECRET=<secret>
AZURE_SUBSCRIPTION_ID=<subscription-id>

NEO4J_PASSWORD=<password>
NEO4J_PORT=7687
```

---

## Security Considerations

1. **Credential Isolation**
   - Source and target credentials never mixed
   - Clear separation via OperationType enum
   - Logging indicates which credential in use

2. **Least Privilege**
   - Source tenant: Reader role only
   - Target tenant: Contributor role for deployment
   - No unnecessary permission escalation

3. **Audit Trail**
   - All credential switches logged
   - Operation context clearly documented
   - Can correlate logs with Azure activity logs

4. **Secret Management**
   - Credentials stored in environment variables
   - Never logged or exposed
   - Support for Azure Key Vault in future enhancement

---

## Key Design Decisions

1. **Why Credential Provider Pattern?**
   - Single responsibility: credential selection logic isolated
   - Testable: easy to mock for unit tests
   - Minimal invasiveness: existing code mostly unchanged

2. **Why Operation-Based Switching?**
   - Clear contract: operation type determines tenant
   - Explicit: no implicit switching based on call stack
   - Auditable: easy to verify correct credential used

3. **Why Backward Compatible?**
   - Existing users unaffected
   - Gradual migration possible
   - Reduces deployment risk

4. **Why Environment Variables?**
   - Standard Azure authentication pattern
   - Tool-agnostic (works with CLI, Python, Terraform)
   - Easy to configure in CI/CD

---

## Future Enhancements

1. **Multi-Operation Transactions**
   - Track operation context across async calls
   - Ensure credential consistency within transaction

2. **Credential Refresh**
   - Automatic token refresh before expiration
   - Health checks for credential validity

3. **Azure Key Vault Integration**
   - Fetch credentials from Key Vault
   - Reduce reliance on environment variables

4. **Managed Identity Support**
   - Use managed identity when available
   - Fallback to service principal

5. **Credential Validation**
   - Verify permissions at startup
   - Warn if roles don't match expectations (Reader/Contributor)

---

## Success Criteria

1. **Functional**
   - Discovery operations use source tenant
   - Deployment operations use target tenant
   - Single-tenant workflows unchanged

2. **Observable**
   - Clear logging of credential switches
   - Operation context visible in logs
   - Errors indicate which tenant failed

3. **Testable**
   - All components have unit tests
   - Integration tests cover full workflow
   - Mock credentials work in tests

4. **Maintainable**
   - Clear module boundaries
   - Each module regeneratable from spec
   - Minimal coupling between components

---

## Implementation Order

1. `src/dual_tenant_config.py` - Configuration foundation
2. `src/credential_provider.py` - Core credential logic
3. Modify `src/services/azure_discovery_service.py` - Discovery integration
4. Modify `src/deployment/orchestrator.py` - Deployment integration
5. Modify `src/azure_tenant_grapher.py` - Main orchestrator
6. Modify `src/cli_commands.py` - CLI wiring
7. Tests for all modules
8. Documentation and examples

---

## Questions for Builder

1. Should CLI accept `--source-tenant-id` and `--target-tenant-id` flags, or only environment variables?
2. Should we add `atg validate-credentials` command to verify dual-tenant setup?
3. Should credential validation be automatic at startup or on-demand?
4. Should we support mixing managed identity (source) with service principal (target)?

---

This specification provides complete blueprints for implementing automatic service principal switching while maintaining the project's philosophy of simplicity, modularity, and backward compatibility.
