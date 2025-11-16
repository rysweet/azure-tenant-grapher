# Multi-Layer Graph: Implementation Checklist

**Status**: Ready for autonomous implementation
**Estimated Effort**: 3-4 days full implementation
**Priority**: HIGH - Solves critical data loss issue

## Prerequisites

- [ ] Review /home/azureuser/src/atg/docs/architecture/MULTI_LAYER_GRAPH_ARCHITECTURE.md
- [ ] Understand current dual-graph architecture
- [ ] Backup current Neo4j database

## Phase 1: Database Schema (Day 1)

### Migration File
- [ ] Create /home/azureuser/src/atg/migrations/012_add_layer_support.py
- [ ] Implement upgrade() function
  - [ ] Add layer_id='default' to existing :Resource nodes
  - [ ] Add layer_created_at timestamp
  - [ ] Create :Layer node for 'default'
  - [ ] Set is_active=true, is_baseline=true
  - [ ] Count nodes and relationships
  - [ ] Create composite constraint (id, layer_id)
  - [ ] Create layer_id index
  - [ ] Create layer_type_layer index
- [ ] Implement downgrade() function (with warnings)
- [ ] Test migration on sample data

### Schema Validation
- [ ] Verify all :Resource nodes have layer_id
- [ ] Verify no duplicate (id, layer_id) combinations
- [ ] Verify indexes created successfully
- [ ] Check query performance with layer filter

**Files to create:**
- /home/azureuser/src/atg/migrations/012_add_layer_support.py

## Phase 2: Core Services (Day 1-2)

### LayerManagementService
- [ ] Create /home/azureuser/src/atg/src/services/layer_management_service.py
- [ ] Define LayerType enum
- [ ] Define LayerMetadata dataclass
- [ ] Define LayerDiff dataclass
- [ ] Implement __init__(neo4j_driver)

#### Lifecycle Methods
- [ ] Implement create_layer()
  - [ ] Validate layer_id uniqueness
  - [ ] Create :Layer node
  - [ ] Set metadata properties
  - [ ] Return LayerMetadata
- [ ] Implement list_layers()
  - [ ] Query all :Layer nodes
  - [ ] Apply filters (tenant_id, layer_type)
  - [ ] Return sorted list
- [ ] Implement get_layer()
  - [ ] Query by layer_id
  - [ ] Return LayerMetadata or None
- [ ] Implement get_active_layer()
  - [ ] Query for is_active=true
  - [ ] Handle multiple active (error)
  - [ ] Handle no active (return default)
- [ ] Implement delete_layer()
  - [ ] Validate not active/baseline (unless force)
  - [ ] Delete all nodes with layer_id
  - [ ] Delete :Layer metadata node
  - [ ] Return success boolean

#### Active Layer Management
- [ ] Implement set_active_layer()
  - [ ] Verify layer exists
  - [ ] Unset previous active layer
  - [ ] Set new layer as active
  - [ ] Return updated LayerMetadata

#### Layer Operations
- [ ] Implement copy_layer()
  - [ ] Validate source layer exists
  - [ ] Create target :Layer metadata
  - [ ] Copy all :Resource nodes with new layer_id
  - [ ] Copy all relationships within layer
  - [ ] Preserve SCAN_SOURCE_NODE links
  - [ ] Create DERIVED_FROM relationship
  - [ ] Update node/relationship counts
- [ ] Implement compare_layers()
  - [ ] Count nodes in each layer
  - [ ] Find added nodes (in B, not in A)
  - [ ] Find removed nodes (in A, not in B)
  - [ ] Find modified nodes (same id, different properties)
  - [ ] Count relationship differences
  - [ ] Return LayerDiff
- [ ] Implement refresh_layer_stats()
  - [ ] Count :Resource nodes with layer_id
  - [ ] Count relationships within layer
  - [ ] Update :Layer metadata
  - [ ] Return updated LayerMetadata

#### Validation
- [ ] Implement validate_layer_integrity()
  - [ ] Check all :Resource nodes have SCAN_SOURCE_NODE
  - [ ] Check no cross-layer relationships
  - [ ] Verify node_count matches
  - [ ] Check for orphaned relationships
  - [ ] Return validation report

**Files to create:**
- /home/azureuser/src/atg/src/services/layer_management_service.py

### LayerAwareQueryService
- [ ] Create /home/azureuser/src/atg/src/services/layer_aware_query_service.py
- [ ] Implement __init__(neo4j_driver, layer_service)
- [ ] Implement get_resource()
  - [ ] Resolve layer_id (explicit or active)
  - [ ] Query with layer filter
  - [ ] Return resource or None
- [ ] Implement find_resources()
  - [ ] Resolve layer_id
  - [ ] Build dynamic query with filters
  - [ ] Apply layer_id filter
  - [ ] Return list of resources
- [ ] Implement traverse_relationships()
  - [ ] Resolve layer_id
  - [ ] Build traversal query with depth
  - [ ] Ensure no cross-layer traversal
  - [ ] Return connected resources
- [ ] Implement get_resource_original()
  - [ ] Resolve layer_id
  - [ ] Follow SCAN_SOURCE_NODE relationship
  - [ ] Return :Original node

**Files to create:**
- /home/azureuser/src/atg/src/services/layer_aware_query_service.py

## Phase 3: Update Existing Services (Day 2)

### ResourceProcessingService
- [ ] Open /home/azureuser/src/atg/src/services/resource_processing_service.py
- [ ] Add layer_id parameter to create_resource_node()
  - [ ] Default to "default"
  - [ ] Add to node properties
- [ ] Update batch_create_nodes() to accept layer_id
- [ ] Update create_relationship() to verify same layer

### ScaleOperationsService
- [ ] Open /home/azureuser/src/atg/src/services/scale_operations_service.py
- [ ] Add layer_service and query_service to __init__()
- [ ] Update merge_vnets()
  - [ ] Add source_layer_id parameter (default: active)
  - [ ] Add target_layer_id parameter (default: auto-generate)
  - [ ] Add make_active parameter (default: false)
  - [ ] Implement copy-then-transform pattern
  - [ ] Call layer_service.copy_layer()
  - [ ] Apply merge in new layer
  - [ ] Refresh stats
  - [ ] Optionally activate
- [ ] Update merge_subnets() (same pattern)
- [ ] Update split_vnet() (same pattern)
- [ ] Update consolidate_vms() (same pattern)

### GraphTraverser (IaC)
- [ ] Open /home/azureuser/src/atg/src/iac/traverser.py
- [ ] Add layer_id parameter to __init__()
- [ ] Resolve layer_id to active if None
- [ ] Update all Cypher queries to include layer filter
  - [ ] WHERE r.layer_id = $layer_id
  - [ ] Apply to all MATCH clauses

**Files to modify:**
- /home/azureuser/src/atg/src/services/resource_processing_service.py
- /home/azureuser/src/atg/src/services/scale_operations_service.py
- /home/azureuser/src/atg/src/iac/traverser.py

## Phase 4: CLI Commands (Day 3)

### Layer Management Commands
- [ ] Open /home/azureuser/src/atg/scripts/cli.py
- [ ] Add layer command group
- [ ] Implement atg layer list
  - [ ] Call layer_service.list_layers()
  - [ ] Format output as table
  - [ ] Show active layer highlighted
- [ ] Implement atg layer show <layer-id>
  - [ ] Call layer_service.get_layer()
  - [ ] Display detailed metadata
  - [ ] Show node/relationship counts
- [ ] Implement atg layer create
  - [ ] Accept layer_id, name, description
  - [ ] Call layer_service.create_layer()
  - [ ] Confirm creation
- [ ] Implement atg layer copy
  - [ ] Accept source and target layer_ids
  - [ ] Call layer_service.copy_layer()
  - [ ] Show progress bar
  - [ ] Confirm completion
- [ ] Implement atg layer delete
  - [ ] Accept layer_id
  - [ ] Confirm with user (unless --yes)
  - [ ] Call layer_service.delete_layer()
- [ ] Implement atg layer activate
  - [ ] Accept layer_id
  - [ ] Call layer_service.set_active_layer()
  - [ ] Confirm switch
- [ ] Implement atg layer active
  - [ ] Call layer_service.get_active_layer()
  - [ ] Display active layer info
- [ ] Implement atg layer diff
  - [ ] Accept two layer_ids
  - [ ] Call layer_service.compare_layers()
  - [ ] Format LayerDiff output
- [ ] Implement atg layer validate
  - [ ] Accept layer_id
  - [ ] Call layer_service.validate_layer_integrity()
  - [ ] Display validation report
- [ ] Implement atg layer refresh-stats
  - [ ] Accept layer_id
  - [ ] Call layer_service.refresh_layer_stats()
  - [ ] Show updated counts

### Enhanced Scale Commands
- [ ] Update atg scale merge-vnets
  - [ ] Add --source-layer option
  - [ ] Add --target-layer option
  - [ ] Add --make-active flag
  - [ ] Pass to service
- [ ] Update atg scale merge-subnets (same pattern)
- [ ] Update atg scale split-vnet (same pattern)
- [ ] Update atg scale consolidate-vms (same pattern)

### Enhanced IaC Generation
- [ ] Update atg generate-iac
  - [ ] Add --layer option
  - [ ] Default to active layer
  - [ ] Pass to GraphTraverser

### Scan Command
- [ ] Update atg scan
  - [ ] Create "default" layer if not exists
  - [ ] Set as active and baseline
  - [ ] Pass layer_id="default" to resource processing

**Files to modify:**
- /home/azureuser/src/atg/scripts/cli.py
- /home/azureuser/src/atg/src/cli_commands.py (if separate)

## Phase 5: Testing (Day 3-4)

### Unit Tests
- [ ] Create /home/azureuser/src/atg/tests/test_layer_management_service.py
  - [ ] test_create_layer()
  - [ ] test_create_layer_duplicate_id_fails()
  - [ ] test_list_layers()
  - [ ] test_get_layer()
  - [ ] test_get_active_layer()
  - [ ] test_delete_layer()
  - [ ] test_delete_active_layer_requires_force()
  - [ ] test_set_active_layer()
  - [ ] test_copy_layer()
  - [ ] test_compare_layers()
  - [ ] test_refresh_layer_stats()
  - [ ] test_validate_layer_integrity()

- [ ] Create /home/azureuser/src/atg/tests/test_layer_aware_query_service.py
  - [ ] test_get_resource_from_active_layer()
  - [ ] test_get_resource_from_specific_layer()
  - [ ] test_find_resources_with_layer_filter()
  - [ ] test_traverse_relationships_within_layer()
  - [ ] test_no_cross_layer_traversal()
  - [ ] test_get_resource_original()

### Integration Tests
- [ ] Create /home/azureuser/src/atg/tests/integration/test_layer_operations.py
  - [ ] test_copy_layer_preserves_structure()
  - [ ] test_copy_layer_preserves_relationships()
  - [ ] test_copy_layer_creates_derived_from()
  - [ ] test_layer_isolation()
  - [ ] test_active_layer_switching()

- [ ] Create /home/azureuser/src/atg/tests/integration/test_scale_with_layers.py
  - [ ] test_merge_vnets_creates_new_layer()
  - [ ] test_merge_vnets_preserves_source_layer()
  - [ ] test_merge_vnets_with_make_active()
  - [ ] test_multiple_scale_operations()

### E2E Tests
- [ ] Create /home/azureuser/src/atg/tests/e2e/test_layer_workflow.py
  - [ ] test_full_workflow_with_layers()
    - [ ] Scan (creates default layer)
    - [ ] Scale operation (creates new layer)
    - [ ] Generate IaC from both layers
    - [ ] Compare outputs
    - [ ] Switch active layer
    - [ ] Delete experimental layer

### Migration Tests
- [ ] Create /home/azureuser/src/atg/tests/test_layer_migration.py
  - [ ] test_migration_adds_layer_id()
  - [ ] test_migration_creates_default_layer()
  - [ ] test_migration_creates_indexes()
  - [ ] test_migration_idempotent()
  - [ ] test_downgrade_removes_layers()

**Files to create:**
- /home/azureuser/src/atg/tests/test_layer_management_service.py
- /home/azureuser/src/atg/tests/test_layer_aware_query_service.py
- /home/azureuser/src/atg/tests/integration/test_layer_operations.py
- /home/azureuser/src/atg/tests/integration/test_scale_with_layers.py
- /home/azureuser/src/atg/tests/e2e/test_layer_workflow.py
- /home/azureuser/src/atg/tests/test_layer_migration.py

## Phase 6: Documentation (Day 4)

### Schema Documentation
- [ ] Update /home/azureuser/src/atg/docs/NEO4J_SCHEMA_REFERENCE.md
  - [ ] Add :Layer node documentation
  - [ ] Update :Resource node with layer_id
  - [ ] Document DERIVED_FROM relationship
  - [ ] Update indexes and constraints
  - [ ] Add layer query patterns

### User Guide
- [ ] Create /home/azureuser/src/atg/docs/guides/LAYER_MANAGEMENT_GUIDE.md
  - [ ] Explain layer concept
  - [ ] Show basic workflows
  - [ ] Document CLI commands
  - [ ] Provide examples
  - [ ] Explain best practices

### CLAUDE.md Updates
- [ ] Update /home/azureuser/src/atg/CLAUDE.md
  - [ ] Add multi-layer architecture section
  - [ ] Update graph schema description
  - [ ] Add layer CLI commands
  - [ ] Update scale operations section

### Scale Operations Documentation
- [ ] Update /home/azureuser/src/atg/docs/SCALE_OPERATIONS_SPECIFICATION.md
  - [ ] Explain layer-based approach
  - [ ] Update command examples
  - [ ] Add layer workflow examples

### CLI Help Text
- [ ] Update CLI command help strings
- [ ] Add layer command group help
- [ ] Update scale command help with layer options

**Files to create/modify:**
- /home/azureuser/src/atg/docs/NEO4J_SCHEMA_REFERENCE.md (update)
- /home/azureuser/src/atg/docs/guides/LAYER_MANAGEMENT_GUIDE.md (create)
- /home/azureuser/src/atg/CLAUDE.md (update)
- /home/azureuser/src/atg/docs/SCALE_OPERATIONS_SPECIFICATION.md (update)

## Phase 7: Deployment & Validation (Day 4)

### Pre-Deployment
- [ ] Run full test suite
- [ ] Check code coverage (target: 40%+)
- [ ] Run linters (ruff, pyright)
- [ ] Test migration on staging database

### Deployment
- [ ] Backup production Neo4j database
- [ ] Run migration 012_add_layer_support.py
- [ ] Verify default layer created
- [ ] Verify all existing resources have layer_id
- [ ] Check query performance

### Post-Deployment Validation
- [ ] Test atg layer list (shows default)
- [ ] Test atg layer active (shows default)
- [ ] Test atg generate-iac (uses default)
- [ ] Test scale operation (creates new layer)
- [ ] Test layer switching
- [ ] Verify backward compatibility

### Performance Testing
- [ ] Benchmark queries with layer filter
- [ ] Test with multiple layers (5, 10, 20)
- [ ] Measure copy_layer() performance
- [ ] Check index effectiveness

## Rollback Plan

If issues arise:

1. **Stop all operations**
   ```bash
   uv run atg stop
   ```

2. **Restore database backup**
   ```bash
   # Restore Neo4j from backup
   docker exec neo4j neo4j-admin database restore --from-path=/backups/pre-layer-migration
   ```

3. **Rollback code**
   ```bash
   git revert <layer-commits>
   ```

4. **Verify system functional**
   ```bash
   uv run atg scan --dry-run
   ```

## Success Metrics

- [ ] All tests pass (unit, integration, e2e)
- [ ] Code coverage >= 40%
- [ ] Migration runs successfully on production
- [ ] Scale operations are non-destructive
- [ ] Layer switching works correctly
- [ ] Query performance degradation < 10%
- [ ] Backward compatibility maintained
- [ ] Documentation complete

## Post-Implementation Tasks

- [ ] Monitor production usage
- [ ] Gather user feedback
- [ ] Optimize slow queries
- [ ] Add layer archival feature (future)
- [ ] Consider multi-tenant active layers (future)
- [ ] Implement layer cleanup automation (future)

## Notes for Autonomous Implementation

### Key Principles
1. **Test-driven**: Write tests before implementation
2. **Incremental**: Complete each phase before moving to next
3. **Backward compatible**: Existing code must work
4. **Safe**: Never modify Original graph
5. **Validated**: Verify at each step

### Critical Points
- Composite unique constraint (id, layer_id) is essential
- All queries MUST filter by layer_id
- SCAN_SOURCE_NODE links must be preserved during copy
- Active layer must be singular (enforce in service)
- Layer deletion must be careful (check active/baseline)

### Common Pitfalls
- Forgetting layer_id in queries (cross-layer contamination)
- Not preserving SCAN_SOURCE_NODE during copy
- Allowing multiple active layers
- Deleting baseline layer accidentally
- Cross-layer relationships (must be prevented)

### Testing Focus
- Layer isolation (most critical)
- Copy operation correctness
- Query filtering effectiveness
- Active layer switching
- Migration safety

---

**Ready for Implementation**: This checklist is complete and actionable. Each task is specific, testable, and builds on previous tasks. Estimated time: 3-4 days for full implementation including testing.
