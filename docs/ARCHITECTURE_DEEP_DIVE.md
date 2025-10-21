# Azure Tenant Grapher - Comprehensive Architecture Deep Dive

**Generated:** 2025-10-20
**Codebase Analysis:** 113 Python files, 871 lines in relationship rules, comprehensive IaC pipeline

---

## Executive Summary

Azure Tenant Grapher is a sophisticated security-focused tool that:
1. **Discovers** Azure tenant resources via Azure Management APIs
2. **Models** them in a Neo4j graph database with rich relationships
3. **Generates** Infrastructure-as-Code (Terraform/ARM/Bicep) for tenant replication
4. **Validates** generated IaC for deployment fidelity
5. **Threat models** the infrastructure using DFD analysis
6. **Provides** interactive interfaces (CLI, SPA/Electron, MCP agent mode)

**Key Insight:** The architecture is service-oriented with clear separation between discovery, processing, storage, IaC generation, and deployment orchestration.

---

## 1. Core Architecture Map

### 1.1 Entry Points

#### Primary CLI Entry Point
- **File:** `/home/azureuser/src/azure-tenant-grapher/scripts/cli.py` (1430 lines)
- **Key Functions:**
  - Lines 237-261: `cli()` - Main Click group with logging/debug setup
  - Lines 341-393: `build()` / `scan()` - Tenant scanning command (alias support)
  - Lines 754-840: `generate_iac()` - IaC generation with validation options
  - Lines 1193-1250: `create_tenant_command()` - Tenant creation from spec
  - Lines 969-981: `agent_mode()` - AutoGen MCP agent interface
  - Lines 910-915: `threat_model()` - Threat modeling workflow
  - Lines 1122-1198: `fidelity()` - Replication fidelity calculation
  - Lines 1024-1071: `monitor()` - Neo4j database monitoring

#### Command Handlers
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/cli_commands.py` (2370 lines)
- **Key Handlers:**
  - Lines 64-245: `build_command_handler()` - Orchestrates scan workflow
  - Lines 247-390: `_run_no_dashboard_mode()` - Line-by-line logging mode
  - Lines 392-617: `_run_dashboard_mode()` - Rich TUI dashboard mode
  - Lines 619-721: `visualize_command_handler()` - Graph visualization
  - Lines 770-837: `generate_spec_command_handler()` - Spec generation
  - Lines 868-888: `agent_mode_command_handler()` - Agent mode setup
  - Lines 1104-1121: `generate_threat_model_command_handler()` - Threat modeling
  - Lines 2235-2369: `fidelity_command_handler()` - Fidelity tracking
  - Lines 1868-2081: `monitor_command_handler()` - Database monitoring

### 1.2 Service Layer

#### Azure Discovery Service
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/services/azure_discovery_service.py`
- **Purpose:** Discovers Azure subscriptions and resources
- **Key Methods:**
  - Lines 85-162: `discover_subscriptions()` - List tenant subscriptions with filtering
  - Lines 164-289: `discover_resources_in_subscription()` - Resource enumeration
  - Lines 291-433: `get_resource_details()` - Detailed resource properties with retries
  - Lines 455-500: `_handle_auth_fallback()` - Azure CLI credential fallback
- **Features:**
  - Credential fallback (DefaultAzureCredential → AzureCliCredential)
  - Pagination handling
  - Rate limiting and retry logic
  - API version caching
  - Subscription/resource group filtering via `FilterConfig`

#### Resource Processing Service
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/services/resource_processing_service.py` (143 lines)
- **Purpose:** Coordinates resource processing and AAD identity ingestion
- **Key Method:**
  - Lines 38-143: `process_resources()` - Main processing orchestrator
  - Lines 68-122: AAD identity import logic (full vs filtered)
- **Features:**
  - Parallel resource processing with configurable concurrency
  - Optional AAD user/group/service principal import
  - Identity filtering when resource filtering is enabled
  - Managed identity resolution
  - Progress callback support

#### AAD Graph Service
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/services/aad_graph_service.py`
- **Purpose:** Imports Azure AD identities (users, groups, service principals)
- **Integration:** Microsoft Graph API via msgraph SDK

#### Tenant Specification Service
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/services/tenant_specification_service.py`
- **Purpose:** Generates markdown specifications from graph data

### 1.3 Data Models

#### Filter Configuration
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/models/filter_config.py`
- **Purpose:** Defines subscription and resource group filtering
- **Key Features:**
  - Validates resource group name format
  - Detects graph database IDs vs real Azure names
  - Lines 123-157: `split_and_detect_ids()` - ID detection helper

#### Relationship Rules
- **Directory:** `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/`
- **Total:** 871 lines across 12 files
- **Base Class:** `relationship_rule.py` (22 lines) - Abstract base
- **Key Rules:**
  - `identity_rule.py` (225 lines) - Identity and RBAC relationships
  - `subnet_extraction_rule.py` (230 lines) - Network subnet extraction
  - `network_rule.py` (115 lines) - Network connectivity (VNet, peering)
  - `diagnostic_rule.py` (86 lines) - Diagnostic settings
  - `secret_rule.py` (37 lines) - Key Vault secrets
  - `tag_rule.py` (39 lines) - Tag propagation
  - `monitoring_rule.py` (24 lines) - Monitoring relationships
  - `depends_on_rule.py` (23 lines) - Resource dependencies
  - `creator_rule.py` (27 lines) - Creator identity
  - `region_rule.py` (22 lines) - Regional grouping

### 1.4 IaC Generation Pipeline

#### IaC CLI Handler
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/cli_handler.py`
- **Purpose:** Command-line interface for IaC generation
- **Features:**
  - Format selection (Terraform, ARM, Bicep)
  - Subset filtering (resource types, node IDs)
  - Validation toggles (subnet, name conflicts, soft-deleted resources)

#### Graph Traverser
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/traverser.py` (136 lines)
- **Purpose:** Extracts tenant infrastructure from Neo4j
- **Key Components:**
  - Lines 17-23: `TenantGraph` dataclass - Holds resources + relationships
  - Lines 24-136: `GraphTraverser` class
  - Lines 39-136: `traverse()` - Main extraction with fallback queries
- **Features:**
  - Optional Cypher filtering
  - Relationship property extraction (original_type, narrative_context)
  - Fallback query for non-:Resource nodes

#### Transformation Engine
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/engine.py` (150+ lines shown)
- **Purpose:** Transforms graph data to IaC templates
- **Key Components:**
  - Lines 26-33: `TransformationRule` dataclass
  - Lines 34-89: Rules file parsing (YAML)
  - Lines 110-150+: `generate_iac()` - Main generation pipeline
- **Features:**
  - Transformation rules from YAML
  - Subnet address space validation (Issue #333)
  - VNet address space conflict detection (Issue #334)
  - Auto-fix capabilities
  - AAD mode control (none/manual/auto)

#### IaC Emitters
- **Directory:** `/home/azureuser/src/azure-tenant-grapher/src/iac/emitters/`
- **Files:**
  - `base.py` - Abstract emitter interface
  - `terraform_emitter.py` - Terraform HCL generation
  - `bicep_emitter.py` - Bicep template generation
  - `arm_emitter.py` - ARM JSON template generation
  - `private_endpoint_emitter.py` - Private endpoint handling

#### IaC Validators
- **Directory:** `/home/azureuser/src/azure-tenant-grapher/src/iac/validators/`
- **Files:**
  - `subnet_validator.py` - Validates subnet containment (Issue #333)
  - `terraform_validator.py` - Validates Terraform syntax

#### IaC Plugins
- **Directory:** `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/`
- **Files:**
  - `base_plugin.py` - Plugin base class
  - `keyvault_plugin.py` - Key Vault handling
  - `storage_plugin.py` - Storage account handling

#### Subset Filtering
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/subset.py`
- **Purpose:** Filters graph to specific resource types or node IDs

#### Dependency Analyzer
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/dependency_analyzer.py`
- **Purpose:** Analyzes and orders resources by dependencies

#### Conflict Detector
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/conflict_detector.py`
- **Purpose:** Detects naming and configuration conflicts (Issue #336)

### 1.5 Database Layer

#### Neo4j Session Manager
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/utils/session_manager.py`
- **Purpose:** Manages Neo4j connection pooling

#### Container Manager
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/container_manager.py` (100+ lines shown)
- **Purpose:** Manages Neo4j Docker container lifecycle
- **Key Features:**
  - Lines 70-100: Container initialization with unique naming
  - Auto-start/stop capabilities
  - Data persistence and backup
  - Health checking
  - Volume management

#### Database Migrations
- **Directory:** `/home/azureuser/src/azure-tenant-grapher/migrations/`
- **Migration Files:**
  - `0002_add_core_constraints.cypher` - Core Neo4j constraints
  - `0003_backfill_subscriptions.cypher` - Subscription backfill
  - `0004_add_resource_id_index.cypher` - Resource ID indexing
  - `0004_network_topology_enrichment.cypher` - Network enrichment
  - `0005_add_last_synced_timestamp_to_subscription.cypher` - Sync tracking
  - `0005_keyvault_secrets.cypher` - Key Vault integration
  - `0006_add_diagnostic_alert_constraints.cypher` - Diagnostics
  - `0007_add_timestamp_indexes.cypher` - Timestamp indexing
  - `0008_fix_user_property_names.cypher` - User property migration
  - `0009_deployment_jobs.cypher` - Deployment tracking
  - `migrate_vnet_address_space.py` - VNet address space migration (8775 lines)

---

## 2. Control Plane Replication Flow

### Phase 1: Discovery
**Entry:** `AzureTenantGrapher.build_graph()` (src/azure_tenant_grapher.py:162-200)

1. **Subscription Discovery**
   - Service: `AzureDiscoveryService.discover_subscriptions()`
   - API: Azure Subscription Management API
   - Filtering: `FilterConfig` for subscription filtering
   - Output: List of subscription dicts

2. **Resource Discovery**
   - Service: `AzureDiscoveryService.discover_resources_in_subscription()`
   - API: Azure Resource Management API
   - Filtering: `FilterConfig` for resource group filtering
   - Pagination: Automatic continuation token handling
   - Output: List of resource metadata dicts

3. **Detailed Resource Fetching**
   - Service: `AzureDiscoveryService.get_resource_details()`
   - Concurrency: Configurable via `max_build_threads` (default: 20)
   - Retries: Configurable via `max_retries` (default: 3)
   - API Version: Cached per resource provider
   - Output: Full resource properties

### Phase 2: Processing
**Entry:** `ResourceProcessingService.process_resources()` (src/services/resource_processing_service.py:38-143)

1. **Identity Import** (Optional)
   - **Full Mode** (no filtering):
     - Service: `AADGraphService.ingest_into_graph()`
     - Imports: All users, groups, service principals
   - **Filtered Mode** (with filtering):
     - Collector: `IdentityCollector.collect_identity_references()`
     - Resolver: `ManagedIdentityResolver.resolve_identities()`
     - Service: `AADGraphService.ingest_filtered_identities()`
     - Imports: Only referenced identities

2. **Resource Processing**
   - Processor: `ResourceProcessor.process_resources()`
   - Concurrency: Configurable via `max_concurrency` (default: 5)
   - Operations:
     - Create Neo4j nodes (`:Resource` label)
     - Extract properties
     - LLM description generation (optional)
   - Progress: Callback-based progress tracking

### Phase 3: Relationship Creation
**Orchestrator:** `ResourceProcessor` applies relationship rules

**Rule Execution Order:**
1. `NetworkRule` - VNet, subnet, peering relationships
2. `SubnetExtractionRule` - Extract subnet details from resources
3. `IdentityRule` - RBAC, managed identity assignments
4. `DiagnosticRule` - Diagnostic settings links
5. `SecretRule` - Key Vault secret references
6. `MonitoringRule` - Monitoring relationships
7. `TagRule` - Tag propagation
8. `DependsOnRule` - Resource dependencies
9. `CreatorRule` - Creator identity links
10. `RegionRule` - Regional grouping

**Relationship Types Created:**
- `CONNECTED_TO` - Network connectivity
- `USES_IDENTITY` - Identity assignments
- `HAS_DIAGNOSTIC_SETTING` - Diagnostic configuration
- `USES_SECRET` - Key Vault references
- `MONITORS` - Monitoring relationships
- `HAS_TAG` - Tag relationships
- `DEPENDS_ON` - Resource dependencies
- `CREATED_BY` - Creator relationships
- `LOCATED_IN` - Regional location

### Phase 4: IaC Generation
**Entry:** `generate_iac_command_handler()` (src/cli_commands.py:813-840 via cli.py:754-840)

**Pipeline:**
1. **Graph Traversal**
   - Service: `GraphTraverser.traverse()`
   - Input: Optional Cypher filter
   - Output: `TenantGraph` (resources + relationships)

2. **Subset Filtering** (Optional)
   - Service: `SubsetSelector.apply()`
   - Filters: Resource types, node IDs
   - Output: Filtered `TenantGraph`

3. **Transformation**
   - Engine: `TransformationEngine.generate_iac()`
   - Input: `TenantGraph`, transformation rules
   - Rules: YAML-based transformation rules
   - Validations:
     - Subnet containment (Issue #333)
     - VNet address space conflicts (Issue #334)
     - Name conflicts (globally unique resources)
     - Soft-deleted resources (Key Vault)
   - Output: Transformed resource dicts

4. **Emission**
   - Emitters: `TerraformEmitter`, `BicepEmitter`, `ARMEmitter`
   - Dependency Analysis: `DependencyAnalyzer.analyze()`
   - Output: IaC files (*.tf, *.bicep, *.json)

5. **Validation** (Optional)
   - Terraform: `terraform validate`
   - Bicep: `bicep build`
   - ARM: Schema validation
   - Output: Validation report

---

## 3. Data Plane Replication

### Current State

#### Data Plane Plugin Architecture
- **File:** `/home/azureuser/src/azure-tenant-grapher/src/iac/data_plane_plugins/base.py` (20 lines)
- **Base Class:** `DataPlanePlugin` (ABC)
  - Lines 12-14: `can_handle()` - Resource type detection
  - Lines 16-19: `replicate()` - Data replication logic

**Status:** **ARCHITECTURE DEFINED, NO IMPLEMENTATIONS**
- Only `base.py` exists in `src/iac/data_plane_plugins/`
- No concrete plugin implementations
- No integration hooks in IaC generation pipeline
- No data plane replication in deployment orchestrator

### Architecture Gaps

#### Missing Data Plane Plugins
- **Storage Blob Plugin** - Copy blob containers and objects
- **Key Vault Plugin** - Replicate secrets, keys, certificates
- **Cosmos DB Plugin** - Replicate database accounts and data
- **SQL Database Plugin** - Schema and data replication
- **Event Hub Plugin** - Consumer groups and schemas
- **Service Bus Plugin** - Queues, topics, subscriptions
- **App Configuration Plugin** - Configuration keys and feature flags
- **Container Registry Plugin** - Container images
- **Cognitive Services Plugin** - Model deployments

#### Missing Integration Points
1. **IaC Generation Integration**
   - No plugin discovery mechanism
   - No data plane replication step after control plane
   - No orchestration between control and data plane

2. **Deployment Orchestrator Integration**
   - No post-deployment data replication
   - No progress tracking for data operations
   - No error handling for data plane failures

3. **Fidelity Calculation**
   - Current fidelity only measures control plane
   - No data plane metrics
   - No data consistency validation

### Proposed Extension Points

1. **Plugin Discovery** (New file: `src/iac/data_plane_plugins/registry.py`)
   - Auto-discover plugins via naming convention
   - Register plugins with resource type mappings
   - Provide plugin lifecycle management

2. **IaC Engine Integration** (Modify: `src/iac/engine.py`)
   - Add data plane replication phase after control plane
   - Generate data replication scripts alongside IaC
   - Include data plane dependencies in ordering

3. **Deployment Orchestrator Integration** (Modify: `src/deployment/orchestrator.py`)
   - Add post-deployment data replication phase
   - Track data replication progress
   - Handle data plane failures gracefully

4. **Fidelity Calculator Extension** (Modify: `src/fidelity_calculator.py`)
   - Add data plane metrics (blob counts, secret counts, etc.)
   - Calculate data consistency scores
   - Report data plane replication fidelity

---

## 4. Key Features Location Map

### 4.1 Tenant Scanning

**Entry Points:**
- CLI: `scripts/cli.py:341-393` (`build` command)
- CLI: `scripts/cli.py:395-531` (`scan` command alias)
- Handler: `src/cli_commands.py:64-245` (`build_command_handler`)

**Core Implementation:**
- Main: `src/azure_tenant_grapher.py:162-200` (`build_graph()`)
- Discovery: `src/services/azure_discovery_service.py:85-162, 164-289`
- Processing: `src/services/resource_processing_service.py:38-143`

**Key Configuration:**
- `--resource-limit`: Limit resources for testing
- `--max-llm-threads`: Parallel LLM threads (default: 5)
- `--max-build-threads`: Parallel API calls (default: 20)
- `--max-retries`: Retry failed resources (default: 3)
- `--no-dashboard`: Disable Rich TUI
- `--rebuild-edges`: Force relationship re-evaluation
- `--no-aad-import`: Disable AAD import
- `--filter-by-subscriptions`: Filter subscriptions
- `--filter-by-rgs`: Filter resource groups

### 4.2 Graph Building

**Storage:**
- Database: Neo4j (Docker container)
- Container Manager: `src/container_manager.py:70-100`
- Session Manager: `src/utils/session_manager.py`

**Node Types:**
- `:Resource` - Azure resources
- `:Subscription` - Azure subscriptions
- `:Tenant` - Azure tenant
- `:ResourceGroup` - Resource groups
- `:User` - Azure AD users
- `:Group` - Azure AD groups
- `:ServicePrincipal` - Service principals
- `:ManagedIdentity` - Managed identities

**Relationship Rules:**
- Base: `src/relationship_rules/relationship_rule.py:1-22`
- Registry: `src/relationship_rules/__init__.py:1-21`
- Total Rules: 11 concrete rules (871 lines)

### 4.3 IaC Generation

**Entry Points:**
- CLI: `scripts/cli.py:754-840` (`generate-iac` command)
- Handler: `src/iac/cli_handler.py` (`generate_iac_command_handler`)

**Pipeline:**
- Traverser: `src/iac/traverser.py:39-136` (`traverse()`)
- Engine: `src/iac/engine.py:110-150+` (`generate_iac()`)
- Emitters:
  - Terraform: `src/iac/emitters/terraform_emitter.py`
  - Bicep: `src/iac/emitters/bicep_emitter.py`
  - ARM: `src/iac/emitters/arm_emitter.py`

**Validation:**
- Subnet: `src/iac/validators/subnet_validator.py` (Issue #333)
- Terraform: `src/iac/validators/terraform_validator.py`
- Address Space: `src/validation/address_space_validator.py` (Issue #334)

**Configuration:**
- `--format`: terraform/arm/bicep
- `--output`: Output directory
- `--rules-file`: Transformation rules YAML
- `--dry-run`: Validate only
- `--resource-filters`: Filter resource types
- `--subset-filter`: Filter by types/node IDs
- `--node-id`: Specific node IDs (multiple)
- `--skip-subnet-validation`: Skip subnet validation
- `--auto-fix-subnets`: Auto-fix subnet addresses
- `--skip-name-validation`: Skip name conflict checks
- `--preserve-names`: Fail on name conflicts
- `--auto-purge-soft-deleted`: Purge soft-deleted Key Vaults
- `--check-conflicts/--no-check-conflicts`: Conflict detection (default: enabled)
- `--auto-cleanup`: Auto-run cleanup script
- `--fail-on-conflicts/--no-fail-on-conflicts`: Fail on conflicts (default: fail)

### 4.4 Deployment Orchestration

**Entry Points:**
- CLI: `scripts/cli.py:963` (`deploy` command)
- Handler: `src/commands/deploy.py` (`deploy_command`)

**Orchestrator:**
- Main: `src/deployment/orchestrator.py:50-150+`
- Dashboard: `src/deployment/deployment_dashboard.py`
- Job Tracker: `src/deployment/job_tracker.py`
- Lock Manager: `src/deployment/lock_manager.py`
- Background Manager: `src/deployment/background_manager.py`

**Deployment Types:**
- Terraform: `deploy_terraform()` (lines 50-150+)
- Bicep: `deploy_bicep()`
- ARM: `deploy_arm()`

**Features:**
- Auto-detect IaC format
- Real-time progress tracking
- Dashboard UI
- Dry-run support
- Background deployment
- Job persistence

**Related Commands:**
- `atg list-deployments` - List all deployments
- `atg undeploy` - Remove deployment
- `atg validate-deployment` - Validate deployment

### 4.5 Validation/Fidelity Calculation

**Entry Points:**
- CLI: `scripts/cli.py:1122-1198` (`fidelity` command)
- Handler: `src/cli_commands.py:2235-2369` (`fidelity_command_handler`)

**Calculator:**
- Main: `src/fidelity_calculator.py:111-150+` (`calculate_fidelity()`)
- Metrics: `FidelityMetrics` dataclass (lines 18-85)

**Metrics Calculated:**
- Resource counts (source vs target)
- Relationship counts (source vs target)
- Resource group counts
- Resource type counts
- Overall fidelity percentage
- Fidelity by resource type
- Missing resources count
- Objective compliance (target fidelity threshold)

**Features:**
- Time-series tracking to `demos/fidelity_history.jsonl`
- JSON export
- Objective checking from `OBJECTIVE.md`

**Configuration:**
- `--source-subscription`: Source subscription ID (required)
- `--target-subscription`: Target subscription ID (required)
- `--track`: Enable time-series tracking
- `--output`: JSON export path
- `--check-objective`: Path to OBJECTIVE.md

### 4.6 Threat Modeling

**Entry Points:**
- CLI: `scripts/cli.py:910-915` (`threat-model` command)
- Handler: `src/cli_commands.py:1104-1121` (`generate_threat_model_command_handler`)

**Agent:**
- Main: `src/threat_modeling_agent/agent.py:68-100+` (`run()`)
- DFD Builder: `src/threat_modeling_agent/dfd_builder.py`
- Threat Enumerator: `src/threat_modeling_agent/threat_enumerator.py`
- TMT Runner: `src/threat_modeling_agent/tmt_runner.py` (stub)
- ASB Mapper: `src/threat_modeling_agent/asb_mapper.py` (Azure Security Benchmark)

**Workflow:**
1. Load DFD graph from Neo4j (lines 28-66)
2. Build Mermaid DFD diagram (lines 79-85)
3. Invoke Microsoft Threat Modeling Tool (stub, lines 88-100+)
4. Enumerate threats
5. Map to Azure Security Benchmark controls
6. Generate markdown report

**Output:**
- Mermaid DFD diagram
- Threat list with severity
- Control mappings
- Markdown report in `outputs/`

### 4.7 Agent Mode (MCP)

**Entry Points:**
- CLI: `scripts/cli.py:969-981` (`agent-mode` command)
- Handler: `src/cli_commands.py:868-888` (`agent_mode_command_handler`)

**Implementation:**
- Main: `src/agent_mode.py:63-100+` (`run_agent_mode()`)
- MCP Server: `src/mcp_server.py`
- MCP Integration: `src/services/mcp_integration.py`

**Architecture:**
- AutoGen: Multi-agent system with `AssistantAgent`
- MCP Workbench: `autogen_ext.tools.mcp.McpWorkbench`
- Server: `mcp-neo4j-cypher` via stdio
- Tools: `get_neo4j_schema`, `read_neo4j_cypher`

**System Message:**
- Lines 26-50: Enforces strict query workflow
  1. Get Neo4j schema
  2. Execute Cypher query
  3. Provide human-readable answer

**Features:**
- Interactive chat loop
- Non-interactive mode (`--question`)
- Natural language to Cypher translation
- Schema-aware query generation
- Verbose logging toggle (`AGENT_MODE_VERBOSE=1`)

**Related:**
- `atg mcp-query` - Single NL query execution
- `atg mcp-server` - Start MCP server standalone

### 4.8 Monitoring

**Entry Points:**
- CLI: `scripts/cli.py:1024-1071` (`monitor` command)
- Handler: `src/cli_commands.py:1868-2081` (`monitor_command_handler`)

**Metrics:**
- Resource counts (per subscription)
- Relationship counts
- Resource group counts
- Resource type counts

**Modes:**
- Single check (default)
- Watch mode (`--watch`, continuous monitoring)
- Stabilization detection (`--detect-stabilization`)

**Output Formats:**
- `json` - Structured JSON output
- `table` - Tabular format with headers
- `compact` - Single-line format (default)

**Configuration:**
- `--subscription-id`: Filter by subscription
- `--interval`: Check interval seconds (default: 30)
- `--watch`: Continuous monitoring
- `--detect-stabilization`: Exit when stable
- `--threshold`: Stabilization threshold (default: 3 identical checks)
- `--format`: Output format (json/table/compact)

---

## 5. Configuration System

### 5.1 Environment Variables

**File:** `.env.example` (37 lines)

#### Neo4j Configuration
- `NEO4J_URI` - Connection URI (default: `bolt://localhost:{NEO4J_PORT}`)
- `NEO4J_PORT` - Port number (required if NEO4J_URI not set)
- `NEO4J_USER` - Username (default: `neo4j`)
- `NEO4J_PASSWORD` - Password (required)

#### Azure Credentials
- `AZURE_TENANT_ID` - Azure tenant ID (required)
- `AZURE_CLIENT_ID` - Service principal client ID (required)
- `AZURE_CLIENT_SECRET` - Service principal secret (required)

#### Azure OpenAI Configuration
- `AZURE_OPENAI_ENDPOINT` - OpenAI endpoint URL (required for LLM)
- `AZURE_OPENAI_KEY` - API key (required for LLM)
- `AZURE_OPENAI_API_VERSION` - API version (default: `2024-02-01`)
- `AZURE_OPENAI_MODEL_CHAT` - Chat model (default: `gpt-4`)
- `AZURE_OPENAI_MODEL_REASONING` - Reasoning model (default: `gpt-4`)

#### Processing Configuration
- `LOG_LEVEL` - Logging level (default: `INFO`)
- `RESOURCE_LIMIT` - Resource processing limit (optional)
- `MAX_CONCURRENCY` - Max parallel LLM threads (default: 5)
- `MAX_BUILD_THREADS` - Max parallel API calls (default: 20)
- `PROCESSING_MAX_RETRIES` - Max retries (default: 3)
- `PROCESSING_RETRY_DELAY` - Retry delay seconds (default: 1.0)
- `PROCESSING_PARALLEL` - Enable parallel processing (default: true)
- `AUTO_START_CONTAINER` - Auto-start Neo4j (default: true)
- `ENABLE_AAD_IMPORT` - Import AAD identities (default: true)

#### SPA Configuration
- `BACKEND_PORT` - Backend server port (default: 3001)
- `CREDENTIAL_MASTER_KEY` - Credential encryption key (production)

#### MCP Configuration
- `MCP_ENABLED` - Enable MCP features (default: false)
- `MCP_ENDPOINT` - MCP server endpoint

### 5.2 Config Manager

**File:** `src/config_manager.py` (200+ lines shown)

#### Configuration Classes

**Neo4jConfig** (Lines 49-76)
- URI, user, password validation
- Auto-construct URI from port if needed
- Connection string masking for logs

**AzureOpenAIConfig** (Lines 78-117)
- Endpoint, API key, model configuration
- `is_configured()` - Check if configured
- `validate()` - Validate settings
- Endpoint masking for logs

**ProcessingConfig** (Lines 119-174)
- Resource limits and concurrency settings
- Retry configuration
- Parallel processing toggle
- Container auto-start
- AAD import toggle
- Migration shim for legacy `PROCESSING_BATCH_SIZE`

**LoggingConfig** (Lines 176-200+)
- Log level, format, file output
- Level validation and conversion

#### Configuration Creation

**`create_config_from_env()`** - Full configuration from environment
**`create_neo4j_config_from_env()`** - Neo4j-only configuration
**`setup_logging()`** - Configure logging system

### 5.3 Tenant Management

**File:** `src/services/tenant_manager.py`

- Manage multiple tenant configurations
- Switch between tenants
- Store tenant-specific settings

---

## 6. Architecture Gaps & Missing Features

### 6.1 Data Plane Replication (Critical Gap)

**Status:** Architecture defined, no implementations

**Missing Components:**
1. **Concrete Plugins**
   - Storage Blob replication
   - Key Vault secret copying
   - Cosmos DB data replication
   - SQL Database schema/data
   - Event Hub configurations
   - Service Bus entities
   - App Configuration keys
   - Container Registry images

2. **Integration Points**
   - Plugin discovery/registry
   - IaC generation integration
   - Deployment orchestrator integration
   - Progress tracking
   - Error handling

3. **Fidelity Metrics**
   - Data plane fidelity calculation
   - Data consistency validation
   - Object count comparisons

**Impact:** Cannot achieve true tenant replication without data plane

### 6.2 Incomplete Features

#### IaC Generation
- **Partial:** Control plane only
- **Missing:** Data plane replication scripts
- **Gap:** No coordination between control and data plane

#### Deployment Orchestration
- **Partial:** Control plane deployment
- **Missing:** Post-deployment data replication
- **Gap:** No end-to-end deployment validation

#### Fidelity Calculation
- **Partial:** Control plane metrics only
- **Missing:** Data plane metrics
- **Gap:** Cannot measure true replication fidelity

#### Threat Modeling
- **Partial:** TMT runner is stubbed
- **Missing:** Real Microsoft Threat Modeling Tool integration
- **Gap:** Cannot generate actionable threat reports

### 6.3 Integration Gaps

#### Azure Services Coverage
**Well-Covered:**
- Compute (VMs, App Services, Functions, AKS)
- Networking (VNets, NSGs, Load Balancers)
- Identity (AAD, RBAC, Managed Identities)
- Storage (Storage Accounts - control plane)
- Key Vault (Vaults - control plane)
- Monitoring (Log Analytics, Application Insights)

**Partially Covered:**
- Key Vault Secrets (relationship tracking, no replication)
- Storage Blobs (account structure, no data replication)

**Not Covered:**
- Cosmos DB data replication
- SQL Database data replication
- Event Hub message schemas
- Service Bus queue definitions
- API Management policies
- Logic Apps workflows
- Power BI datasets

#### Relationship Rules
**Comprehensive Coverage:**
- Network topology
- Identity assignments
- RBAC relationships
- Diagnostic settings
- Secret references

**Missing:**
- Application dependencies (implicit)
- Cross-tenant relationships
- Historical relationships (changes over time)

### 6.4 Scalability Concerns

#### Neo4j Performance
- **Current:** Single-node Docker container
- **Gap:** No clustering for large tenants
- **Impact:** Performance degradation with >10k resources

#### API Rate Limiting
- **Current:** Basic retry logic
- **Gap:** No adaptive rate limiting
- **Impact:** Throttling on large scans

#### LLM Costs
- **Current:** No cost tracking
- **Gap:** No budget controls
- **Impact:** Uncontrolled OpenAI costs

### 6.5 Security & Compliance

#### Credential Management
- **Current:** Environment variables
- **Gap:** No secret rotation
- **Gap:** No Azure Key Vault integration for credentials
- **Impact:** Credential leakage risk

#### Audit Logging
- **Current:** Basic logging
- **Gap:** No audit trail for sensitive operations
- **Gap:** No compliance reporting
- **Impact:** Cannot prove compliance

#### Encryption
- **Current:** Neo4j password in environment
- **Gap:** No encryption at rest for graph data
- **Gap:** No credential encryption for SPA
- **Impact:** Data exposure risk

### 6.6 Testing & Validation

#### Test Coverage
- **Current:** 40% minimum coverage
- **Gap:** No E2E deployment tests
- **Gap:** No data plane replication tests
- **Impact:** Unknown deployment reliability

#### Validation
- **Current:** Control plane validation only
- **Gap:** No data consistency validation
- **Gap:** No end-to-end deployment validation
- **Impact:** Cannot guarantee replication fidelity

---

## 7. Architectural Strengths

### 7.1 Service-Oriented Design
- Clear separation of concerns
- Dependency injection for testing
- Pluggable components (emitters, validators, rules)

### 7.2 Relationship Rule System
- Modular, extensible architecture
- Plugin-based relationship discovery
- 871 lines across 11 specialized rules

### 7.3 IaC Multi-Format Support
- Terraform, ARM, Bicep emitters
- Shared transformation engine
- Format-agnostic dependency analysis

### 7.4 Validation Pipeline
- Subnet containment validation (Issue #333)
- Address space conflict detection (Issue #334)
- Name conflict detection
- Soft-deleted resource handling

### 7.5 Neo4j Graph Model
- Expressive relationship types
- Rich property preservation
- Cypher query flexibility
- Migration system for schema evolution

### 7.6 Interactive Interfaces
- Rich CLI with dashboard
- Electron SPA for GUI
- MCP agent mode for AI interaction
- Multiple output formats

### 7.7 Fidelity Tracking
- Time-series metrics
- Objective compliance checking
- Per-resource-type breakdown
- JSON export for automation

### 7.8 Comprehensive Filtering
- Subscription filtering
- Resource group filtering
- Resource type filtering
- Node ID filtering
- Identity filtering

---

## 8. Recommendations for Future Development

### 8.1 Priority 1: Data Plane Replication
1. Implement plugin registry (`src/iac/data_plane_plugins/registry.py`)
2. Create concrete plugins for top 5 services:
   - Storage Blob
   - Key Vault Secrets
   - Cosmos DB
   - SQL Database
   - Event Hub
3. Integrate into IaC generation pipeline
4. Add data plane to deployment orchestrator
5. Extend fidelity calculator with data metrics

### 8.2 Priority 2: Scalability Improvements
1. Implement Neo4j clustering support
2. Add adaptive rate limiting for Azure APIs
3. Implement LLM cost tracking and budgets
4. Add caching for expensive operations
5. Optimize Cypher queries for large graphs

### 8.3 Priority 3: Security Enhancements
1. Azure Key Vault integration for credentials
2. Credential rotation support
3. Audit trail for sensitive operations
4. Encryption at rest for Neo4j data
5. RBAC for SPA/API access

### 8.4 Priority 4: Testing & Validation
1. E2E deployment test suite
2. Data plane replication tests
3. Increase coverage to 70%
4. Add deployment validation framework
5. Implement canary deployments

### 8.5 Priority 5: Azure Service Coverage
1. Cosmos DB data replication
2. SQL Database data replication
3. API Management policy replication
4. Logic Apps workflow replication
5. Power BI dataset replication

---

## 9. File Reference Index

### Core Entry Points
- `/home/azureuser/src/azure-tenant-grapher/scripts/cli.py` - Main CLI (1430 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/cli_commands.py` - Command handlers (2370 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/azure_tenant_grapher.py` - Main coordinator (200+ lines)

### Service Layer
- `/home/azureuser/src/azure-tenant-grapher/src/services/azure_discovery_service.py` - Azure API discovery
- `/home/azureuser/src/azure-tenant-grapher/src/services/resource_processing_service.py` - Resource processing (143 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/services/aad_graph_service.py` - AAD identity import
- `/home/azureuser/src/azure-tenant-grapher/src/services/tenant_specification_service.py` - Spec generation
- `/home/azureuser/src/azure-tenant-grapher/src/services/identity_collector.py` - Identity extraction
- `/home/azureuser/src/azure-tenant-grapher/src/services/managed_identity_resolver.py` - MI resolution

### IaC Pipeline
- `/home/azureuser/src/azure-tenant-grapher/src/iac/cli_handler.py` - IaC CLI
- `/home/azureuser/src/azure-tenant-grapher/src/iac/traverser.py` - Graph traversal (136 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/iac/engine.py` - Transformation engine (150+ lines)
- `/home/azureuser/src/azure-tenant-grapher/src/iac/subset.py` - Subset filtering
- `/home/azureuser/src/azure-tenant-grapher/src/iac/dependency_analyzer.py` - Dependency ordering
- `/home/azureuser/src/azure-tenant-grapher/src/iac/conflict_detector.py` - Conflict detection

### IaC Emitters
- `/home/azureuser/src/azure-tenant-grapher/src/iac/emitters/base.py` - Base emitter
- `/home/azureuser/src/azure-tenant-grapher/src/iac/emitters/terraform_emitter.py` - Terraform
- `/home/azureuser/src/azure-tenant-grapher/src/iac/emitters/bicep_emitter.py` - Bicep
- `/home/azureuser/src/azure-tenant-grapher/src/iac/emitters/arm_emitter.py` - ARM
- `/home/azureuser/src/azure-tenant-grapher/src/iac/emitters/private_endpoint_emitter.py` - Private endpoints

### IaC Validators
- `/home/azureuser/src/azure-tenant-grapher/src/iac/validators/subnet_validator.py` - Subnet validation
- `/home/azureuser/src/azure-tenant-grapher/src/iac/validators/terraform_validator.py` - Terraform validation

### IaC Plugins
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/base_plugin.py` - Base plugin
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/keyvault_plugin.py` - Key Vault handling
- `/home/azureuser/src/azure-tenant-grapher/src/iac/plugins/storage_plugin.py` - Storage handling

### Data Plane (Stub)
- `/home/azureuser/src/azure-tenant-grapher/src/iac/data_plane_plugins/base.py` - Base plugin (20 lines, no implementations)

### Relationship Rules
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/relationship_rule.py` - Base rule (22 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/__init__.py` - Registry (21 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/identity_rule.py` - Identity (225 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/subnet_extraction_rule.py` - Subnets (230 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/network_rule.py` - Networking (115 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/diagnostic_rule.py` - Diagnostics (86 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/secret_rule.py` - Secrets (37 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/tag_rule.py` - Tags (39 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/monitoring_rule.py` - Monitoring (24 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/depends_on_rule.py` - Dependencies (23 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/creator_rule.py` - Creators (27 lines)
- `/home/azureuser/src/azure-tenant-grapher/src/relationship_rules/region_rule.py` - Regions (22 lines)

### Deployment
- `/home/azureuser/src/azure-tenant-grapher/src/deployment/orchestrator.py` - Main orchestrator (150+ lines)
- `/home/azureuser/src/azure-tenant-grapher/src/deployment/deployment_dashboard.py` - Dashboard UI
- `/home/azureuser/src/azure-tenant-grapher/src/deployment/job_tracker.py` - Job tracking
- `/home/azureuser/src/azure-tenant-grapher/src/deployment/lock_manager.py` - Lock management
- `/home/azureuser/src/azure-tenant-grapher/src/deployment/background_manager.py` - Background jobs

### Fidelity
- `/home/azureuser/src/azure-tenant-grapher/src/fidelity_calculator.py` - Fidelity calculation (150+ lines)

### Threat Modeling
- `/home/azureuser/src/azure-tenant-grapher/src/threat_modeling_agent/agent.py` - Main agent (100+ lines)
- `/home/azureuser/src/azure-tenant-grapher/src/threat_modeling_agent/dfd_builder.py` - DFD builder
- `/home/azureuser/src/azure-tenant-grapher/src/threat_modeling_agent/threat_enumerator.py` - Threat enumeration
- `/home/azureuser/src/azure-tenant-grapher/src/threat_modeling_agent/tmt_runner.py` - TMT integration (stub)
- `/home/azureuser/src/azure-tenant-grapher/src/threat_modeling_agent/asb_mapper.py` - ASB mapping

### Agent Mode
- `/home/azureuser/src/azure-tenant-grapher/src/agent_mode.py` - AutoGen agent (100+ lines)
- `/home/azureuser/src/azure-tenant-grapher/src/mcp_server.py` - MCP server
- `/home/azureuser/src/azure-tenant-grapher/src/services/mcp_integration.py` - MCP integration

### Configuration
- `/home/azureuser/src/azure-tenant-grapher/src/config_manager.py` - Config management (200+ lines)
- `/home/azureuser/src/azure-tenant-grapher/src/container_manager.py` - Neo4j container (100+ lines)
- `/home/azureuser/src/azure-tenant-grapher/.env.example` - Environment template (37 lines)

### Database
- `/home/azureuser/src/azure-tenant-grapher/src/utils/session_manager.py` - Neo4j session management
- `/home/azureuser/src/azure-tenant-grapher/migrations/` - Database migrations (13 files)

### Models
- `/home/azureuser/src/azure-tenant-grapher/src/models/filter_config.py` - Filter configuration

---

## 10. Conclusion

Azure Tenant Grapher is a **mature, well-architected control plane replication tool** with:

**Strengths:**
- Comprehensive Azure resource discovery
- Rich Neo4j graph modeling with 11 relationship rules
- Multi-format IaC generation (Terraform/ARM/Bicep)
- Robust validation pipeline
- Multiple interactive interfaces (CLI/SPA/MCP)
- Fidelity tracking and objective compliance

**Critical Gap:**
- **Data plane replication architecture is defined but not implemented**
- Only `base.py` exists in `src/iac/data_plane_plugins/`
- No integration points in IaC generation or deployment
- Fidelity calculation is control plane only

**Recommendation:**
Priority 1 should be implementing data plane replication plugins and integration to achieve true tenant replication capability.

---

**End of Architecture Deep Dive**
