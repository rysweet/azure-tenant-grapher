# Implementation Specification: Issue #228 - Referenced Resource Inclusion

## Status

**Implementation Phase**: Ready for TDD and building
**Date**: 2026-01-23
**Branch**: feat-issue-228-subscription-rg-filtering

## Executive Summary

Implement automatic inclusion of referenced resources (managed identities, RBAC principals) when using subscription/resource group filtering to ensure complete and accurate graph representation.

## What Already Exists ✅

1. **FilterConfig Model** (`src/models/filter_config.py`)
   - Validates subscription IDs and resource group names
   - Provides `has_filters()`, `should_include_subscription()`, `should_include_resource_group()` methods
   - Missing: `include_referenced_resources` flag

2. **DiscoveryFilterService** (`src/services/discovery_filter_service.py`)
   - Filters subscriptions and resources based on FilterConfig
   - Provides `filter_subscriptions()`, `filter_resources()`, `get_filter_summary()` methods

3. **CLI Integration** (`src/commands/scan.py`)
   - `--filter-by-subscriptions` and `--filter-by-rgs` flags exist
   - FilterConfig created and passed to `grapher.build_graph()`

4. **ManagedIdentityResolver** (`src/services/managed_identity_resolver.py`)
   - Resolves system-assigned and user-assigned managed identities
   - Handles ID abstraction for cross-tenant compatibility
   - Method: `resolve_identities(identity_refs, all_resources)`

5. **AADGraphService** (`src/services/aad_graph_service.py`)
   - Fetches users, groups, service principals from Microsoft Graph API
   - Methods: `get_users_by_ids()`, `get_groups_by_ids()`, `get_service_principals_by_ids()`
   - Includes retry logic and rate limit handling

6. **Investigation Documentation** (`.claude/docs/FILTERED_IMPORT_REFERENCED_RESOURCES.md`)
   - Complete feature documentation with examples
   - Architecture and usage patterns documented

## What Needs to Be Built ❌

### 1. ReferencedResourceCollector Service

**File**: `src/services/referenced_resource_collector.py`

**Purpose**: Collect and fetch resources that are referenced by filtered resources but fall outside the filter scope.

**Dependencies**:
- `ManagedIdentityResolver` (existing)
- `AADGraphService` (existing)
- `AzureDiscoveryService` (existing, for fetching user-assigned identities from different RGs)

**Class Structure**:

```python
class ReferencedResourceCollector:
    """Collects referenced resources for filtered imports."""

    def __init__(
        self,
        discovery_service: AzureDiscoveryService,
        identity_resolver: ManagedIdentityResolver,
        aad_graph_service: Optional[AADGraphService] = None
    ):
        """Initialize collector with required services."""

    async def collect_referenced_resources(
        self,
        filtered_resources: List[Dict[str, Any]],
        filter_config: FilterConfig
    ) -> List[Dict[str, Any]]:
        """
        Collect all referenced resources that should be included.

        Returns list of resources to add to filtered set.
        """

    def _extract_identity_references(
        self,
        resources: List[Dict[str, Any]]
    ) -> Set[str]:
        """Extract identity references from resources."""

    def _extract_rbac_principal_ids(
        self,
        resources: List[Dict[str, Any]]
    ) -> Dict[str, Set[str]]:
        """
        Extract RBAC principal IDs from resources.

        Returns dict with keys: 'users', 'groups', 'service_principals'
        """

    async def _fetch_user_assigned_identities(
        self,
        identity_resource_ids: Set[str],
        filter_config: FilterConfig
    ) -> List[Dict[str, Any]]:
        """Fetch user-assigned managed identities by resource ID."""

    async def _fetch_rbac_principals(
        self,
        principal_ids: Dict[str, Set[str]]
    ) -> List[Dict[str, Any]]:
        """Fetch RBAC principals (users, groups, SPs) from AAD."""
```

**Key Implementation Details**:

1. **Identity Reference Extraction**:
   - Parse resource `identity` property for system-assigned (principalId) and user-assigned (identities dict)
   - User-assigned identities: Resource IDs like `/subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.ManagedIdentity/userAssignedIdentities/{name}`
   - System-assigned identities: Principal IDs (GUIDs)

2. **RBAC Principal Extraction**:
   - Parse resource properties for RBAC role assignments
   - Common patterns:
     - `roleAssignments` array with `principalId` field
     - `permissions` object with `principalIds`
   - Classify by `principalType`: "User", "Group", "ServicePrincipal"

3. **Fetching Logic**:
   - User-assigned identities: Use `discovery_service.discover_resources_in_subscription()` with resource type filter
   - RBAC principals: Use `aad_graph_service.get_<type>_by_ids()` methods
   - Handle missing/inaccessible resources gracefully (log warnings, continue)

4. **Filtering Bypass**:
   - Referenced resources should NOT be filtered again
   - They are explicitly included regardless of subscription/RG

### 2. FilterConfig Extension

**File**: `src/models/filter_config.py`

**Changes**:
```python
class FilterConfig(BaseModel):
    subscription_ids: Optional[List[str]] = Field(default_factory=list)
    resource_group_names: Optional[List[str]] = Field(default_factory=list)
    include_referenced_resources: bool = True  # NEW FIELD - default True
```

**Rationale**: Allow users to disable reference inclusion with `--no-include-references` flag if needed.

### 3. CLI Flag Addition

**File**: `src/commands/scan.py`

**Changes**:
```python
@click.option(
    "--no-include-references",
    is_flag=True,
    default=False,
    help="Disable automatic inclusion of referenced resources (identities, RBAC principals)",
)
```

Update `filter_config` creation to pass `include_referenced_resources` parameter.

### 4. Integration in AzureTenantGrapher

**File**: `src/azure_tenant_grapher.py`

**Changes in `build_graph()` method**:

```python
async def build_graph(
    self,
    progress_callback: Optional[Any] = None,
    force_rebuild_edges: bool = False,
    filter_config: Optional[FilterConfig] = None,
) -> Dict[str, Any]:
    # ... existing discovery code ...

    # NEW: After filtering resources, collect referenced resources
    if filter_config and filter_config.has_filters() and filter_config.include_referenced_resources:
        logger.info("=" * 70)
        logger.info("Collecting referenced resources for filtered import...")
        logger.info("=" * 70)

        from src.services.referenced_resource_collector import ReferencedResourceCollector

        collector = ReferencedResourceCollector(
            discovery_service=self.discovery_service,
            identity_resolver=ManagedIdentityResolver(tenant_seed=self.config.tenant_id),
            aad_graph_service=self.aad_graph_service
        )

        referenced_resources = await collector.collect_referenced_resources(
            filtered_resources=all_resources,
            filter_config=filter_config
        )

        if referenced_resources:
            logger.info(f"✅ Adding {len(referenced_resources)} referenced resources to filtered import")
            all_resources.extend(referenced_resources)
        else:
            logger.info("No additional referenced resources found")

    # ... continue with processing ...
```

**Integration Point**: After resources are filtered but before they are processed and added to the graph.

### 5. Comprehensive Tests

**Files**:
- `tests/services/test_referenced_resource_collector.py`
- `tests/integration/test_filtered_import_with_references.py`

**Test Coverage**:

1. **Unit Tests for ReferencedResourceCollector**:
   - `test_extract_system_assigned_identity_references()`
   - `test_extract_user_assigned_identity_references()`
   - `test_extract_rbac_principal_ids_by_type()`
   - `test_fetch_user_assigned_identities_from_different_rg()`
   - `test_fetch_rbac_principals_from_aad()`
   - `test_collect_referenced_resources_full_flow()`
   - `test_graceful_handling_of_missing_identities()`
   - `test_no_references_when_include_flag_false()`

2. **Integration Tests**:
   - `test_filtered_build_includes_cross_rg_identity()`
   - `test_filtered_build_includes_rbac_principals()`
   - `test_filtered_build_with_no_include_references_flag()`
   - `test_unfiltered_build_unchanged()`

**Test Strategy**:
- Mock Azure SDK responses
- Use pytest fixtures for sample resources with identity references
- Verify referenced resources are added to final resource list
- Verify referenced resources are NOT re-filtered

## Implementation Order

1. ✅ **FilterConfig Extension** (simple model change)
2. ✅ **ReferencedResourceCollector Service** (core logic)
3. ✅ **CLI Flag Addition** (--no-include-references)
4. ✅ **Integration in AzureTenantGrapher** (glue code)
5. ✅ **Unit Tests** (TDD - write first!)
6. ✅ **Integration Tests** (end-to-end validation)
7. ✅ **Documentation Updates** (if needed)

## Complexity Estimate

**Lines of Code**:
- ReferencedResourceCollector: ~250 lines
- FilterConfig extension: ~5 lines
- CLI flag: ~10 lines
- Integration code: ~30 lines
- Tests: ~400 lines
**Total**: ~695 lines

**Classification**: COMPLEX (requires architecture, 50+ lines, multiple components)

**Estimated Time**: 4-6 hours (design, TDD, implementation, testing)

## Success Criteria

1. ✅ CLI accepts `--no-include-references` flag
2. ✅ FilterConfig has `include_referenced_resources` field with default True
3. ✅ ReferencedResourceCollector can extract identity and RBAC references
4. ✅ ReferencedResourceCollector can fetch user-assigned identities from different RGs
5. ✅ ReferencedResourceCollector can fetch RBAC principals from AAD
6. ✅ Integration in build_graph() works correctly
7. ✅ Referenced resources appear in filtered graphs
8. ✅ No regression in unfiltered builds
9. ✅ Comprehensive test coverage (>80%)
10. ✅ Local end-to-end testing with real Azure tenant

## Risks and Mitigation

**Risk 1**: RBAC role assignment structure may vary across resource types
- **Mitigation**: Extract common patterns, handle variations gracefully, log warnings for unknown formats

**Risk 2**: User-assigned identities may be in subscriptions not included in filter
- **Mitigation**: Fetch identities by resource ID regardless of subscription, log if inaccessible

**Risk 3**: AAD Graph API rate limits
- **Mitigation**: Batch requests, use existing retry logic in AADGraphService

**Risk 4**: Performance impact on large tenants
- **Mitigation**: Only collect when filters are active, batch API calls, cache results

## Philosophy Compliance

✅ **Ruthless Simplicity**: Reuses existing services (ManagedIdentityResolver, AADGraphService)
✅ **Modular Design**: Self-contained service with clear contract
✅ **Zero-BS Implementation**: No stubs, fully functional
✅ **Bricks & Studs**: ReferencedResourceCollector is independent, testable brick

## Next Steps

1. Mark Step 5 complete
2. Proceed to Step 5.5 (Proportionality Check) - COMPLEX classification confirmed
3. Proceed to Step 6 (Documentation) - Already exists, may need minor updates
4. Proceed to Step 7 (TDD) - Write tests first!
