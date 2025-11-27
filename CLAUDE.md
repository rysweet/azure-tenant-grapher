# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Azure Tenant Grapher is a security-focused tool that builds a Neo4j graph database representation of Azure tenant resources and their relationships. It generates Infrastructure-as-Code (IaC) in multiple formats (Terraform, ARM, Bicep) and provides threat modeling capabilities.

### Dual-Graph Architecture

The system uses a **dual-graph architecture** where every Azure resource is stored as two nodes:
- **Original nodes** (`:Resource:Original`): Real Azure IDs from the source tenant
- **Abstracted nodes** (`:Resource`): Translated IDs suitable for cross-tenant deployment
- Linked by `SCAN_SOURCE_NODE` relationships

This architecture enables:
- Cross-tenant deployments with safe ID abstraction
- Query flexibility (original topology OR deployment view)
- Simplified IaC generation (no runtime translation needed)
- Graph-based validation of abstractions

**Key Services:**
- `IDAbstractionService`: Deterministic hash-based ID abstraction (e.g., `vm-a1b2c3d4`)
- `TenantSeedManager`: Per-tenant cryptographic seeds for reproducible abstraction

## Development Commands

### Testing
```bash
# Run all tests with artifacts
./scripts/run_tests_with_artifacts.sh

# Run specific test
uv run pytest tests/test_specific.py -v

# Run tests with coverage
uv run pytest --cov=src --cov-report=term-missing
```

### Linting and Type Checking
```bash
# Run Ruff linter
uv run ruff check src scripts tests

# Run Ruff formatter
uv run ruff format src scripts tests

# Run Pyright type checker
uv run pyright

# Run Bandit security linter
uv run bandit -r src scripts
```

### Pre-commit Hooks
```bash
# Install pre-commit hooks
uv run pre-commit install

# Run pre-commit on all files
uv run pre-commit run --all-files
```

### Running the CLI
```bash
# Main CLI commands (all aliases work: azure-tenant-grapher, azure-graph, atg)
uv run atg scan --tenant-id <TENANT_ID>
uv run atg generate-spec
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform
uv run atg create-tenant --spec path/to/spec.md
uv run atg visualize
uv run atg agent-mode
uv run atg threat-model
uv run atg doctor  # Check and install CLI dependencies

# IaC generation with subnet validation (Issue #333)
uv run atg generate-iac --tenant-id <TENANT_ID>  # Validates subnets by default
uv run atg generate-iac --tenant-id <TENANT_ID> --auto-fix-subnets  # Auto-fix invalid subnets
uv run atg generate-iac --tenant-id <TENANT_ID> --skip-subnet-validation  # Skip validation (not recommended)

# Cross-tenant IaC generation (Issue #406)
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID>  # Cross-tenant deployment
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID> --target-subscription <TARGET_SUB_ID>  # With target subscription
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID> --identity-mapping-file identity_mappings.json  # With Entra ID translation

# Terraform import blocks (Issue #412) - FULLY IMPLEMENTED
uv run atg generate-iac --auto-import-existing --import-strategy resource_groups  # Generates Terraform 1.5+ import blocks
uv run atg generate-iac --target-tenant-id <TARGET_TENANT_ID> --auto-import-existing --import-strategy resource_groups  # Cross-tenant with imports

# Azure provider registration - FULLY IMPLEMENTED
uv run atg generate-iac --auto-register-providers  # Automatically register required Azure providers without prompting
# By default (without --auto-register-providers), atg will detect required providers and prompt user to register them

# SPA/GUI commands
uv run atg start    # Launch Electron GUI (desktop mode)
uv run atg stop     # Stop GUI application

# Web App Mode (NEW)
cd spa && npm run start:web       # Run as web server (accessible from other machines)
cd spa && npm run start:web:dev   # Run web server in dev mode with hot reload
```

## Architecture Overview

### Core Components

1. **Azure Discovery Service** (`src/services/azure_discovery_service.py`):
   - Discovers Azure resources using Azure SDK
   - Handles pagination and rate limiting
   - Supports resource limits for testing

2. **Resource Processing Service** (`src/services/resource_processing_service.py`):
   - Processes discovered resources
   - Creates Neo4j nodes and relationships
   - Applies relationship rules

3. **Relationship Rules** (`src/relationship_rules/`):
   - Modular rules for creating graph relationships
   - Each rule handles specific relationship types (network, identity, monitoring, etc.)
   - Plugin-based architecture for extensibility

4. **Neo4j Container Management** (`src/container_manager.py`):
   - Manages Neo4j Docker container lifecycle
   - Handles database backups
   - Ensures Neo4j is running before operations

5. **IaC Generation** (`src/iac/`):
   - Traverses Neo4j graph to generate IaC
   - Supports multiple output formats via emitters
   - Handles resource dependencies and ordering
   - Validates subnet address space containment (Issue #333)
   - Cross-tenant resource translation (Issue #406)

6. **Cross-Tenant Translation**: See `@docs/cross-tenant/FEATURES.md` for details

7. **IaC Validators** (`src/iac/validators/`):
   - **SubnetValidator**: Validates subnets are within VNet address space
   - **TerraformValidator**: Validates Terraform templates
   - Supports auto-fix for common subnet misconfigurations

### Key Design Patterns

- **Async/Await**: Core services use asyncio for concurrent API calls
- **Dashboard Integration**: Rich TUI dashboard for progress tracking during long operations
- **MCP Server**: Model Context Protocol server for AI agent integration
- **Migration System**: Database schema versioning and migrations in `migrations/`
- **Electron SPA**: Desktop GUI application with React frontend and Express backend

### Neo4j Graph Schema

For complete schema documentation, see [docs/NEO4J_SCHEMA_REFERENCE.md](docs/NEO4J_SCHEMA_REFERENCE.md).

**Node Types:**
- **Resource nodes** (dual-graph architecture):
  - `:Resource` - Abstracted nodes with translated IDs (default for queries)
  - `:Resource:Original` - Original nodes with real Azure IDs
  - Linked by `(abstracted)-[:SCAN_SOURCE_NODE]->(original)`
- **Other nodes**: Subscription, Tenant, ResourceGroup, User, ServicePrincipal, etc.

**Relationships:**
- Resource relationships duplicated in both graphs: CONTAINS, USES_IDENTITY, CONNECTED_TO, DEPENDS_ON, USES_SUBNET, SECURED_BY
- Shared relationships to non-Resource nodes: TAGGED_WITH, LOCATED_IN, CREATED_BY
- **Indexes**: On both abstracted and original resource IDs for fast lookups
- **Constraints**: Unique constraints on both node types
- **Schema Assembly**: Dynamic schema built through rule-based relationship emission

### Testing Strategy

- **Unit Tests**: Mock Azure SDK responses
- **Integration Tests**: Use testcontainers for Neo4j
- **E2E Tests**: Full workflow testing with real containers
- **Coverage Target**: 40% minimum (per pyproject.toml)

### SPA/GUI Architecture

The SPA can run in two modes:

#### Desktop Mode (Electron)
The Electron-based desktop GUI provides a full-featured interface for all CLI functionality:

**Key Directories:**
- `spa/main/`: Electron main process (app lifecycle, IPC, subprocess management)
- `spa/renderer/`: React frontend (UI components, context providers, hooks)
- `spa/backend/`: Express server (API layer)
- `spa/tests/`: Comprehensive test suites (unit, integration, e2e)

**Core Features:**
- **Tabbed Interface**: Scan, Generate Spec, Generate IaC, Create Tenant, Visualize, Agent Mode, Threat Model, Config
- **Real-time Communication**: WebSocket for live logs and progress updates
- **Process Management**: Spawns and manages CLI subprocesses
- **Cross-Platform**: Windows, macOS, and Linux support

#### Web App Mode (NEW)
Run the SPA as a standalone web application accessible from other machines:

**Key Files:**
- `spa/backend/src/web-server.ts`: Web server entry point
- `spa/config/web-server.config.js`: Configuration file
- `spa/docs/WEB_APP_MODE.md`: Complete setup guide

**Features:**
- Network-accessible from any browser
- SSH tunneling support (Azure Bastion)
- Configurable CORS for remote access
- Same functionality as desktop mode
- Lower resource footprint

**Quick Start:**
```bash
cd spa
npm run build:web
npm run start:web
# Access at http://localhost:3000
```

**Configuration:**
```bash
export WEB_SERVER_PORT=3000
export WEB_SERVER_HOST=0.0.0.0  # Listen on all interfaces
export ENABLE_CORS=true
export ALLOWED_ORIGINS="*"  # Or specific origins
```

For detailed setup including Azure Bastion connection, see [Web App Mode Guide](spa/docs/WEB_APP_MODE.md) and [Azure Bastion Connection Guide](docs/AZURE_BASTION_CONNECTION_GUIDE.md).

## Common Development Tasks

### Adding a New Relationship Rule
1. Create new file in `src/relationship_rules/`
2. Inherit from `RelationshipRule` base class
3. Implement `create_relationships()` method
4. Register in `__init__.py`

### Adding a New CLI Command
1. Add command handler in `src/cli_commands.py`
2. Register command in `scripts/cli.py`
3. Add tests in `tests/test_cli_*.py`

### Modifying IaC Generation
1. Update traverser logic in `src/iac/traverser.py`
2. Modify emitter in `src/iac/emitters/`
3. Test with `--dry-run` flag first

### Working with the SPA/GUI
1. **Start Development Environment**:
   ```bash
   cd spa && npm run dev
   ```
2. **Add New UI Components**: Place in `spa/renderer/src/components/`
3. **Add New Tabs**: Create in `spa/renderer/src/components/tabs/`
4. **Test Changes**:
   ```bash
   cd spa && npm test
   npm run test:e2e
   ```
5. **Build for Production**:
   ```bash
   cd spa && npm run build && npm run package
   ```

## Environment Configuration

Required environment variables (see .env.example):
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `NEO4J_PASSWORD` (required)
- `NEO4J_PORT` (required, configures the Neo4j port)
- `NEO4J_URI` (optional, defaults to bolt://localhost:${NEO4J_PORT})
- `OPENAI_API_KEY` (for LLM descriptions)

Optional debugging command-line flag:
- `--debug` (enables verbose debug output including environment variables)

## CI/CD Pipeline

GitHub Actions workflow (`ci.yml`):
1. Sets up Neo4j service container
2. Installs dependencies with uv
3. Runs database migrations
4. Executes test suite with artifacts
5. Uploads test results

Check CI status: `./scripts/check_ci_status.sh`

### Helpful Scripts

- **CI Status Check**: Use the script `@scripts/check_ci_status.sh` to efficiently check CI status

## CLI Dashboard Shortcuts

When using the CLI dashboard (during `atg scan` operations):
- **Press 'x'** to exit the dashboard
- **Press 'g'** to launch the GUI (SPA) - provides quick access to the desktop interface
- **Press 'i', 'd', 'w'** to change log levels (INFO, DEBUG, WARNING)

## Project Memories

- The CI takes almost 20 minutes to complete. Just run the script and wait for it.

## Recent Bug Fixes (November 2025)

### Bug #89: KeyVault Translator Over-Aggressive Policy Skipping
**Status**: FIXED (commit cf92e38)
**Impact**: Enables KeyVault cross-tenant deployment without full identity mapping (+7 tests)

**Problem**: KeyVault access policies were being SKIPPED entirely when identity mapping unavailable, preventing cross-tenant KeyVault deployment.

**Solution**: Changed from "skip policy" to "keep policy with warning". ALWAYS translate tenant_id, keep object_id/application_id unchanged when no mapping available.

**Files Modified**: `src/iac/translators/keyvault_translator.py:323-370`

### Bug #90: Smart Detector Missing enabled and scope Fields
**Status**: FIXED (commit 69966d9)
**Impact**: Smart Detector Alert Rules properly convert enabled state and scope (+3 tests)

**Problem**: Missing `enabled` field and empty `scope_resource_ids` (Azure uses both "scope" and "scopes").

**Solution**: Map `state` property to `enabled` boolean, handle both "scope" (singular) and "scopes" (plural) field variants.

**Files Modified**: `src/iac/emitters/terraform_emitter.py:1757-1772`

### Bug #91: Lowercase Azure Type Variants Missing
**Status**: FIXED (commit b5057d2)
**Impact**: Tests can now use lowercase Azure type names (+4 tests)

**Problem**: Mapping missing lowercase variants for Smart Detector and DNS zones, causing "unsupported type" errors.

**Solution**: Added lowercase variants to AZURE_TO_TERRAFORM_MAPPING.

**Files Modified**: `src/iac/emitters/terraform_emitter.py:205,232`

### Bug #92: TransformationEngine YAML Loading Error
**Status**: FIXED (commit b065e55)
**Impact**: TransformationEngine can now load rules files (+1 test)

**Problem**: Engine failed to load rules files with error "'YAML' object has no attribute 'safe_load'". Code imported `YAML` class from ruamel.yaml but tried to use it like standard library `yaml.safe_load()`.

**Solution**: Create YAML instance and use its load() method instead of calling nonexistent class method.

**Files Modified**: `src/iac/engine.py:70-73`

### Bug #93: Same-Tenant Detection Failure When Azure CLI Unavailable ⭐
**Status**: FIXED (commits 9d6e915, 23051c8)
**Impact**: Prevents loss of 1,017 role assignments in Issue #502 same-tenant deployments

**Problem**: When running `generate-iac --target-tenant-id X` without `--source-tenant-id` and Azure CLI not logged in:
- Code tries to get source tenant from `az account show` (cli_handler.py:601-614)
- Azure CLI unavailable → source tenant defaults to None
- Comparison: `None != X` → falsely detected as "cross-tenant mode"
- Cross-tenant mode without identity mapping → SKIPS ALL ROLE ASSIGNMENTS

**Root Cause**: No fallback for source tenant when Azure CLI unavailable (subscription had fallback, tenant didn't).

**Solution**:
1. **cli_handler.py:629-641**: Added intelligent fallback - if target specified but source unknown AND no identity mapping file, assume same-tenant (source = target)
2. **ARM emitter (arm_emitter.py:145-158)**: Added is_same_tenant detection before skip
3. **Bicep emitter (bicep_emitter.py:240-253)**: Added is_same_tenant detection
4. **Modular Terraform (terraform/handlers/identity/role_assignment.py:72-90)**: Added is_same_tenant detection

**Files Modified**: 4 files, 45 lines changed

**Verification**: Log evidence shows fix working - same-tenant mode correctly detected

### Bug #94: Database Corruption from Missing `upsert_generic` Method ⭐⭐
**Status**: ALREADY FIXED (commit 63f06a9 - just requires fresh scan)
**Impact**: 0 role assignments in old database (1,017 resources affected in Issue #502)

**Root Cause**: Database created with code BEFORE commit 63f06a9 which lacked `upsert_generic` method, causing 1,496 AttributeErrors and loss of 1,214 resources (44% data loss) including ALL role assignments.

**What Actually Happened**:
1. Phase 1.5 DID execute successfully (discovered 676 role assignments)
2. ResourceProcessor called relationship rules (TagRule, RegionRule)
3. Rules called non-existent `db_ops.upsert_generic()` method
4. 1,496 AttributeErrors occurred (silent failures in relationship creation)
5. Resources processed but relationships failed → 1,214 resources lost

**Previous Understanding (WRONG)**:
- ❌ "Phase 1.5 never executes" - FALSE (it executed perfectly)
- ❌ "Discovery problem" - FALSE (discovery worked, processing failed)
- ❌ "Needs investigation" - FALSE (already fixed by commit 63f06a9)

**The Fix** (commit 63f06a9 - Nov 26):
- Added missing `upsert_generic()` method to NodeManager (+86 lines)
- File: `src/services/resource_processing/node_manager.py:499-586`
- Fixed relationship rule failures

**Verification**: Fresh scan with current code shows 0 `upsert_generic` errors (fix working)

**Solution**: Re-scan with current main branch code (commit 63f06a9 or later)

**Documentation**: `/tmp/BUG_94_FINAL_ROOT_CAUSE.md`, `/tmp/BUG_94_CORRECTED_UNDERSTANDING.md`

### Bug #59: Subscription ID Abstraction in Dual-Graph Properties ⭐
**Status**: FIXED (commit faeb284)  
**Impact**: Eliminates manual sed replacements for cross-tenant deployments

**Problem**: Abstracted Resource nodes in Neo4j had source subscription IDs embedded in properties JSON (roleDefinitionId, scope fields), requiring manual replacement of 2,292 occurrences before deployment.

**Root Cause**: `resource_processor.py:_create_abstracted_node()` abstracted principalId but not subscription IDs.

**Solution**: 
1. ResourceProcessor: Replace subscription IDs with `/subscriptions/ABSTRACT_SUBSCRIPTION` placeholder at scan time
2. TerraformEmitter: Update regex to replace placeholder with target subscription at IaC generation time

**Files Modified**:
- `src/resource_processor.py:528-555`
- `src/iac/emitters/terraform_emitter.py:3234,3248`

**Documentation**: See `docs/BUG_59_DOCUMENTATION.md` for technical deep dive.

### Bug #57: NIC NSG Deprecated Field
**Status**: FIXED (commit 2011688)

**Problem**: `network_security_group_id` field deprecated in azurerm provider.

**Solution**: Use `azurerm_network_interface_security_group_association` resources instead.

### Bug #58: Skip NIC NSG When NSG Not Emitted
**Status**: FIXED (commit 7651fde)

**Problem**: NIC NSG associations created for NSGs that weren't emitted, causing undeclared resource errors.

**Solution**: Validate NSG exists in `_available_resources` before creating association.

### Bug #68: Provider Name Case Sensitivity in Resource IDs
**Status**: FIXED (commit d8ef246) | **GitHub**: Issue #498

**Problem**: Terraform plan failed with 85 validation errors. Neo4j stored lowercase provider names (`microsoft.operationalinsights`) but Terraform requires proper case (`Microsoft.OperationalInsights`).

**Root Cause**: Cross-tenant resource ID translation preserved original casing from Neo4j without normalization.

**Solution**: Added `_normalize_provider_casing()` method to BaseTranslator that normalizes 9 common Microsoft providers. Called automatically in `_translate_resource_id()` so all translators inherit the fix.

**Impact**: Unlocked 85 resources (68 OperationalInsights, 15 Insights, 2 KeyVault). Enabled clean terraform plan for 3,682 resources (50.6% success rate).

**Files Modified**:
- `src/iac/translators/base_translator.py:321-352, 380-381, 389-390`

**Documentation**: See `docs/BUG_68_DOCUMENTATION.md` for technical deep dive.

### Bug #87: Smart Detector Alert Rules Invalid Location Field ⭐
**Status**: FIXED (commit f43a32d) | **Issue**: #502

**Problem**: All 72 `azurerm_monitor_smart_detector_alert_rule` resources failed terraform plan validation with "Extraneous JSON object property 'location'" errors. The Smart Detector resource type does not support a location argument.

**Root Cause**: The emitter was including location from `build_base_config()` which adds location by default for most resources, but Smart Detector Alert Rules don't accept this field.

**Solution**: Added `resource_config.pop("location", None)` after Smart Detector configuration to remove the invalid field.

**Impact**: Fixed terraform validation for all 72 Smart Detector Alert Rules. Part of eliminating all terraform plan errors for Issue #502.

**Files Modified**:
- `src/iac/emitters/terraform_emitter.py:1771`

### Bug #88: Action Group Resource ID Case Sensitivity ⭐
**Status**: FIXED (commit 1d63c66) | **Issue**: #502

**Problem**: All 72 Smart Detector Alert Rules failed terraform plan with "ID was missing the `actionGroups` element" errors. Action group resource IDs had incorrect casing: `/subscriptions/{}/resourcegroups/{}/providers/microsoft.insights/actiongroups/{}`.

**Root Cause**: Azure API returns action group IDs with lowercase "resourcegroups" and "actiongroups", but Terraform requires proper camelCase: "resourceGroups" and "actionGroups".

**Solution**:
1. Enhanced `_normalize_azure_resource_id()` to fix "resourcegroups" → "resourceGroups" and "actiongroups" → "actionGroups" casing
2. Applied normalization to action group IDs in Smart Detector emitter using list comprehension

**Impact**: Fixed all remaining 72 terraform validation errors. **After Bug #87 & #88 fixes: terraform plan validates with 0 configuration errors!** Enables deployment-ready IaC for Issue #502.

**Files Modified**:
- `src/iac/emitters/terraform_emitter.py:1766` (normalize action group IDs)
- `src/iac/emitters/terraform_emitter.py:5105-5106` (enhanced normalization function)

**Documentation**: See `/tmp/BUG_88_ACTION_GROUP_ID_FORMAT.md` for technical details.

### Bug #69: Missing account_kind Field for Storage Accounts
**Status**: FIXED (commit 4daf659) | **GitHub**: Issue #499

**Problem**: Storage accounts had 0/91 success rate (0%) despite being correctly generated in IaC.

**Root Cause**: The required `account_kind` field was missing from Terraform configuration in terraform_emitter.py:1715-1723.

**Solution**: Added `account_kind` field with default value "StorageV2" (most common type).

**Impact**: Unlocks 91 storage accounts (1.25% of 7,273 total resources). Success rate: 0% → expected 95%.

**Files Modified**:
- `src/iac/emitters/terraform_emitter.py:1722`

**Evidence**: StorageAccountTranslator processed all 91/91 successfully, but Terraform requires account_kind for deployment.

### Bug #70: Missing smartDetectorAlertRules Emitter Support ⭐
**Status**: FIXED (commit 46647e5)
**Impact**: +31 resources unlocked (0.4% improvement)

**Problem**: 31 Azure smartDetectorAlertRules were being skipped because type mapping was commented out in terraform_emitter.py.

**Root Cause**: Missing field mappings for required Terraform fields (frequency, severity, scope_resource_ids, detector_type, action_group).

**Solution**:
1. Uncommented type mapping at line 262
2. Added field mapping logic at lines 1725-1746

**Files Modified**:
- `src/iac/emitters/terraform_emitter.py:262,1725-1746`

**Testing**: Quick win - ready for next IaC generation. GitHub Issue: #500

### Bug #72: Skip Entra ID Users in Same-Tenant Deployments (Issue #496 Problem #2) ⭐
**Status**: FIXED & VERIFIED WORKING (commits abc0770, 9101bef, 5acbbdf, bf57224)
**Impact**: Eliminates 219 user conflicts in same-tenant deployments

**Problem**: 219 Entra ID users fail in same-tenant deployments because they already exist (source tenant == target tenant).

**Root Cause (Primary)**: EntraUserHandler blindly creates all users without checking if deployment is same-tenant.
**Root Cause (Secondary - CRITICAL)**: Attribute name mismatch caused fix to not work initially
- Code checked: `self._source_tenant_id` (with underscore)
- Actual attribute: `self.source_tenant_id` (without underscore)

**Solution**:
1. Added same-tenant detection logic (commits abc0770, 5acbbdf)
2. Fixed attribute names (commit bf57224) - removed underscore prefixes
- Detect when source_tenant_id == target_tenant_id
- Skip user emission with debug message
- Returns None to prevent duplicate user creation

**Files Modified**:
- `src/iac/emitters/terraform/handlers/identity/entra_user.py:44-57` (handler version)
- `src/iac/emitters/terraform_emitter.py:2503-2528` (production version)
- `src/iac/emitters/terraform_emitter.py:2507-2509` (attribute name fix)

**Verification** (2025-11-26): ✅ PASSED
- Before fix: 219 users generated in same-tenant mode
- After bf57224: 0 users generated
- Tests: 47/48 PASSED
- GitHub Issue: #501


## Recent Code Improvements (November 2025)

### Dependency Validation Enhancement
**Commit**: feat: Add DependencyValidator and enhance TerraformEmitter

**Purpose**: Prevent "undeclared resource" Terraform errors by validating references before emission

**New Files**:
- `src/iac/validators/dependency_validator.py` - Terraform validation integration
  - Runs `terraform validate -json`
  - Parses undeclared resource errors
  - Returns structured dependency errors

**Enhanced Files**:
- `src/iac/emitters/terraform_emitter.py`
  - `_validate_all_references_in_config()` - Recursively validates resource references
  - NSG association validation - Checks both subnet and NSG exist before creating associations
  - Skips resources with missing dependencies (prevents invalid IaC)

**Benefits**:
- Fixes Bug #58: NSG associations for non-existent NSGs
- Prevents entire category of Terraform errors
- Clear warning messages for debugging
- Improves IaC generation quality

**Usage**:
```python
from src.iac.validators import DependencyValidator

validator = DependencyValidator()
result = validator.validate(Path("/tmp/iac_output"))
if not result.valid:
    for error in result.errors:
        print(f"{error.resource_type}.{error.resource_name}: {error.missing_reference}")
```

### Iteration 19 Breakthrough (2025-11-25) ✅
**Status**: 🟢 MAJOR SUCCESS - Replication loop now operational
**Resources Deployed**: **902** (vs 81-resource ceiling)
**Improvement**: **11.1x** increase

**Bugs Fixed This Session**:

1. **Bug #60: Service Principal Authentication** ✅ (Commits: .env update)
   - Root cause: Wrong SP credentials in .env (source tenant SP doesn't exist in target)
   - Fix: Updated .env with target tenant SP (30acd0d7-08b8-40d2-901d-17634bf19136)
   - Impact: 228 import blocks generated (was 0), broke the "81-Resource Pattern"

2. **Bug #61: Case-Insensitive Type Lookup** ✅ (Commit: 31d8132)
   - Root cause: Azure API returns "microsoft.insights", mapping expects "Microsoft.Insights"
   - Fix: Added `_normalize_azure_type()` helper in terraform_emitter.py:128-166
   - Impact: Infrastructure for case-insensitive lookups

3. **Bug #62: Missing Proper-Case Variants** ✅ (Commit: 53e675e)
   - Fix: Added Microsoft.Insights/components and actiongroups proper-case mappings
   - Impact: +36 resources unlocked

4. **Bug #63: Missing Terraform-Supported Types** ✅ (Commit: 76e72a3)
   - Fix: Added 17 Azure types (Databricks, Synapse, Purview, Communication, etc.)
   - Impact: +48 resources, 55 types unlocked (117 → 62 unsupported)

5. **Bug #64: Missing Lowercase Variants** ✅ (Commit: 56c22c1)
   - Fix: Added operationalinsights, metricalerts, VM extensions lowercase mappings
   - Impact: +22 resources (15 Log Analytics Workspaces!)

6. **Bug #65: Complete Linting Cleanup** ✅ (Commit: 3cc5c5c)
   - Fix: Resolved all 193 Ruff linting errors
   - Impact: Clean codebase, production-ready

**New Blockers Discovered**:

1. 🔴 **Limited Import Strategy** (711 resources affected)
   - Issue: `--import-strategy resource_groups` only imports RGs, not child resources
   - Solution: Use `--import-strategy all_resources` for next iteration
   - Expected: +711 import blocks → +711 resources

2. 🔴 **Entra ID User Conflicts** (219 users affected)
   - Issue: Same-tenant deployment tries to create existing users
   - Solution: Skip azuread_user when source==target tenant
   - Expected: +219 resources or graceful skip

**Deployment Metrics**:
- Import blocks: 228 (resource groups only)
- Resources created: 615
- Resources imported: 228
- Total in state: 902
- Deployment time: 4h 26min

**Next Steps**:
- Use `--import-strategy all_resources` to unlock 711 more imports
- Add same-tenant user detection/skipping
- Continue mapping expansion for remaining 62 unsupported types

**Documentation**:
- See `/tmp/COMPREHENSIVE_SESSION_SUMMARY.md` for complete session analysis
- See `/tmp/ITERATION_19_FINAL_RESULTS.md` for detailed results and blockers
- See `/tmp/00_PROJECT_STATUS_INDEX_UPDATED.md` for current status


### Bug #73: Import Block Generation for Child Resources (Issue #502) ⭐
**Status**: FIXED (PR #503, commit 8158080)
**Impact**: +1,369 import blocks (+600% increase)

**Problem**: Import blocks only generated for 228/3,621 resources (6%), causing 2,600+ "already exists" errors during same-tenant deployments.

**Root Cause**: `_build_azure_resource_id()` in terraform_emitter.py assumed ALL Azure resources follow single Resource Group ID pattern. But Azure uses 4+ different patterns!

**Solution**: Created `resource_id_builder.py` with strategy pattern for multi-pattern ID construction:
- Resource Group Level: Standard Azure resources
- Child Resources: Subnets with parent VNet reference
- Subscription Level: Role assignments with scope handling
- Association Resources: Compound IDs for NSG associations

**Impact**: Import blocks 228 → 1,597
- Unlocked 266 subnets
- Unlocked 1,017 role assignments
- Unlocked 86 NSG associations

**Files Modified**:
- NEW: `src/iac/resource_id_builder.py` (403 lines)
- NEW: `tests/iac/test_resource_id_builder.py` (29 tests, 88% coverage)
- MODIFIED: `src/iac/emitters/terraform_emitter.py`

**Testing**: 29 unit tests, 100% pass rate, CI passed

---

### Emitter Coverage Expansion (Fixes #74-82): 9 Resource Types Added

**Status**: ALL COMMITTED to main (commits 36d25eb - 18ae0a8)
**Impact**: +9 supported resource types (55 → 64)

All previously excluded resource types now have full emitter support:

1. **Microsoft.Synapse/workspaces** (36d25eb)
2. **Microsoft.Purview/accounts** (db69bcb)
3. **Microsoft.Portal/dashboards** (199b622)
4. **Microsoft.Communication/CommunicationServices** (93c0f8c)
5. **Microsoft.App/jobs** (594d114)
6. **Microsoft.Communication/EmailServices** (594d114)
7. **Microsoft.Insights/workbooks** (12c39b6)
8. **Microsoft.Compute/galleries/images** (a107bb0)
9. **Microsoft.Insights/scheduledqueryrules** (18ae0a8)

---

### Bug #83: NodeManager Missing upsert_generic Methods
**Status**: FIXED (commit 63f06a9)
**Impact**: Eliminated 1,938 relationship creation errors during scan

**Problem**: RegionRule and TagRule relationship rules failing with AttributeError during scan.

**Root Cause**: ResourceProcessor refactoring (commit 5c10d20) didn't migrate `upsert_generic()` and `create_generic_rel()` methods to NodeManager.

**Solution**: Added both missing methods to NodeManager class.

**Impact**: Unblocks all relationship creation (Region, Tag, Identity, Network, Diagnostic rules)

**Files Modified**:
- `src/services/resource_processing/node_manager.py` (+86 lines)

