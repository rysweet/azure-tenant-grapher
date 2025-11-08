# Dual-Graph Implementation Strategy

## Overview

This document outlines the step-by-step implementation strategy for the dual-graph architecture in Azure Tenant Grapher. This is a **living document** that should be updated as implementation progresses.

## Design Documents Reference

- **Schema Design**: [DUAL_GRAPH_SCHEMA.md](./DUAL_GRAPH_SCHEMA.md) - Complete schema specification
- **Query Examples**: [DUAL_GRAPH_QUERIES.cypher](./DUAL_GRAPH_QUERIES.cypher) - Cypher query patterns
- **Code Examples**: [DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py](./DUAL_GRAPH_IMPLEMENTATION_EXAMPLE.py) - Python implementation reference
- **Migration**: [../migrations/0010_dual_graph_schema.cypher](../migrations/0010_dual_graph_schema.cypher) - Database migration

## Implementation Phases

### Phase 1: Schema and Infrastructure (Week 1)

**Goal**: Set up database schema and core abstraction services without affecting existing functionality.

#### Tasks

1. **Database Migration**
   - [x] Create migration 0010_dual_graph_schema.cypher
   - [ ] Test migration on local Neo4j
   - [ ] Test migration on CI/CD pipeline
   - [ ] Document rollback procedure

2. **Abstraction Service**
   - [ ] Create `src/services/abstraction_service.py`
     - Implement `AbstractionIDGenerator` class
     - Add type prefix mappings for common Azure resources
     - Add hash collision detection
   - [ ] Create unit tests for abstraction service
     - Test deterministic ID generation
     - Test type prefix mapping
     - Test hash collision scenarios

3. **Tenant Seed Management**
   - [ ] Add `TenantSeedManager` to `src/services/abstraction_service.py`
     - Implement seed generation
     - Implement seed retrieval
     - Add seed storage on Tenant nodes
   - [ ] Create unit tests for seed management

4. **Configuration**
   - [ ] Add feature flag to `src/config_manager.py`:
     ```python
     ENABLE_DUAL_GRAPH = os.getenv("ENABLE_DUAL_GRAPH", "false").lower() == "true"
     ABSTRACTION_HASH_LENGTH = int(os.getenv("ABSTRACTION_HASH_LENGTH", "8"))
     ```
   - [ ] Update `.env.example` with new variables
   - [ ] Update documentation

**Success Criteria**:
- Migration 0010 runs successfully on test database
- Abstraction service generates deterministic IDs
- Feature flag defaults to False (no behavior change)
- All tests pass

### Phase 2: Dual-Graph Node Creation (Week 2)

**Goal**: Implement dual-graph node creation in resource processor.

#### Tasks

1. **Database Operations Extension**
   - [ ] Extend `DatabaseOperations` class in `src/resource_processor.py`:
     - Add `upsert_dual_graph_resource()` method
     - Add `_create_original_node()` helper
     - Add `_create_abstracted_node()` helper
     - Add `_create_scan_source_relationship()` helper
   - [ ] Add transaction handling for atomicity
   - [ ] Add rollback on failure

2. **Resource Processor Integration**
   - [ ] Modify `ResourceProcessor.upsert_resource()`:
     ```python
     def upsert_resource(self, resource: Dict[str, Any]) -> bool:
         if self.config.enable_dual_graph:
             return self.db_ops.upsert_dual_graph_resource(resource)
         else:
             return self.db_ops.upsert_single_resource(resource)  # existing
     ```
   - [ ] Initialize `AbstractionIDGenerator` in constructor
   - [ ] Initialize `TenantSeedManager` in constructor

3. **Testing**
   - [ ] Unit tests for dual-graph node creation
   - [ ] Integration tests with Neo4j testcontainer
   - [ ] Test feature flag toggle (on/off)
   - [ ] Test backward compatibility (feature flag off)

**Success Criteria**:
- With feature flag ON: Both Original and Abstracted nodes created
- With feature flag OFF: Only single Resource node created (existing behavior)
- SCAN_SOURCE_NODE relationship created correctly
- All existing tests still pass

### Phase 3: Dual-Graph Relationships (Week 3)

**Goal**: Implement relationship duplication across both graphs.

#### Tasks

1. **Database Operations Helper**
   - [ ] Add `create_dual_graph_rel()` to `DatabaseOperations`:
     ```python
     def create_dual_graph_rel(
         self,
         src_original_id: str,
         rel_type: str,
         tgt_original_id: str,
         properties: Optional[Dict[str, Any]] = None,
     ) -> bool:
         # Create in both Original and Abstracted graphs
     ```
   - [ ] Add `get_abstracted_id()` lookup helper
   - [ ] Add `_create_single_rel()` helper

2. **Relationship Rules Update**
   - [ ] Update all relationship rules in `src/relationship_rules/`:
     - [ ] `network_rule.py` - Network topology relationships
     - [ ] `identity_rule.py` - Identity assignments
     - [ ] `monitoring_rule.py` - Monitoring relationships
     - [ ] `diagnostic_rule.py` - Diagnostic settings
     - [ ] `secret_rule.py` - Secret references
     - [ ] `subnet_extraction_rule.py` - Subnet relationships
     - [ ] `tag_rule.py` - Tag relationships
     - [ ] `region_rule.py` - Regional relationships
     - [ ] `depends_on_rule.py` - Dependencies
     - [ ] `creator_rule.py` - Creator relationships

   Pattern for each rule:
   ```python
   # OLD:
   db_ops.create_generic_rel(src_id, rel_type, tgt_id, "Resource", "id")

   # NEW:
   if self.config.enable_dual_graph:
       db_ops.create_dual_graph_rel(src_id, rel_type, tgt_id)
   else:
       db_ops.create_generic_rel(src_id, rel_type, tgt_id, "Resource", "id")
   ```

3. **Testing**
   - [ ] Test each relationship rule with dual-graph
   - [ ] Verify relationships exist in both graphs
   - [ ] Test relationship parity (count matches)
   - [ ] Test edge cases (missing nodes, orphans)

**Success Criteria**:
- All relationship types duplicated in both graphs
- Relationship counts match between Original and Abstracted
- No orphaned relationships
- All existing tests still pass

### Phase 4: IaC Generation Updates (Week 4)

**Goal**: Update IaC generation to use only Abstracted nodes.

#### Tasks

1. **Traverser Updates**
   - [ ] Modify `src/iac/traverser.py`:
     - Add filter to all queries: `WHERE NOT r:Original`
     - Or use explicit label: `MATCH (r:Resource:Abstracted)`
   - [ ] Add validation to reject Original nodes
   - [ ] Update query patterns in traverser methods

2. **Query Pattern Updates**
   - [ ] Review and update all Cypher queries in IaC generation:
     - `_get_resources_by_type()`
     - `_get_dependencies()`
     - `_get_resource_group_resources()`
     - Any other query methods

3. **Validation**
   - [ ] Add `_validate_node_is_abstracted()` helper
   - [ ] Raise error if Original node encountered
   - [ ] Add logging for debugging

4. **Testing**
   - [ ] Test IaC generation with dual-graph data
   - [ ] Verify only Abstracted nodes used
   - [ ] Test generated Terraform/ARM/Bicep
   - [ ] Compare output with single-graph mode (should be equivalent)

**Success Criteria**:
- IaC generation only queries Abstracted nodes
- Generated IaC uses abstracted IDs
- Output is deterministic and reproducible
- All IaC tests pass

### Phase 5: Validation and Monitoring (Week 5)

**Goal**: Add validation, debugging, and monitoring capabilities.

#### Tasks

1. **Validation Queries**
   - [ ] Create `src/utils/dual_graph_validator.py`:
     - Check for orphaned nodes
     - Check for hash collisions
     - Verify relationship parity
     - Check seed consistency
   - [ ] Add validation to scan completion
   - [ ] Add validation CLI command: `atg validate-graph`

2. **Debugging Tools**
   - [ ] Add debug logging throughout dual-graph code
   - [ ] Create debugging CLI commands:
     - `atg debug graph-stats` - Show node/relationship counts
     - `atg debug find-orphans` - Find orphaned nodes
     - `atg debug check-parity` - Verify relationship parity
   - [ ] Add troubleshooting guide to documentation

3. **Monitoring**
   - [ ] Add metrics for dual-graph operations:
     - Node creation success/failure rates
     - Relationship duplication rates
     - Hash collision counts
     - Query performance metrics
   - [ ] Add health checks in CLI dashboard

4. **Documentation**
   - [ ] Update `CLAUDE.md` with dual-graph information
   - [ ] Update `README.md` with feature description
   - [ ] Create operator runbook for common issues
   - [ ] Add troubleshooting section to docs

**Success Criteria**:
- Validation catches common issues
- Debugging tools help operators troubleshoot
- Monitoring provides visibility into system health
- Documentation is complete and accurate

### Phase 6: Staging and Production Rollout (Week 6)

**Goal**: Deploy to staging and production with minimal risk.

#### Tasks

1. **Staging Deployment**
   - [ ] Deploy code to staging with `ENABLE_DUAL_GRAPH=false`
   - [ ] Run migration 0010 on staging database
   - [ ] Enable feature flag: `ENABLE_DUAL_GRAPH=true`
   - [ ] Run full scan on staging tenant
   - [ ] Validate results with validation tools
   - [ ] Run IaC generation and compare outputs
   - [ ] Monitor for 48 hours

2. **Production Preparation**
   - [ ] Create rollback plan
   - [ ] Prepare monitoring dashboards
   - [ ] Create incident response plan
   - [ ] Schedule maintenance window

3. **Production Deployment**
   - [ ] Deploy code to production with `ENABLE_DUAL_GRAPH=false`
   - [ ] Run migration 0010 on production database
   - [ ] Verify migration success
   - [ ] Enable feature flag on subset of tenants (canary)
   - [ ] Monitor canary tenants for 72 hours
   - [ ] Gradually roll out to all tenants
   - [ ] Monitor for issues

4. **Post-Deployment**
   - [ ] Run validation on all tenants
   - [ ] Verify IaC generation
   - [ ] Check performance metrics
   - [ ] Collect feedback from users
   - [ ] Address any issues

**Success Criteria**:
- Staging deployment successful with no critical issues
- Canary deployment shows no regression
- Full production rollout completes without incidents
- Performance metrics within acceptable range
- Users report no issues

### Phase 7: Optimization and Cleanup (Week 7+)

**Goal**: Optimize performance and clean up technical debt.

#### Tasks

1. **Performance Optimization**
   - [ ] Profile query performance
   - [ ] Optimize slow queries
   - [ ] Add additional indexes if needed
   - [ ] Tune batch sizes for relationship creation
   - [ ] Consider caching strategies

2. **Code Cleanup**
   - [ ] Remove feature flag (make dual-graph default)
   - [ ] Remove old single-graph code paths
   - [ ] Consolidate duplicate code
   - [ ] Improve error handling

3. **Future Enhancements**
   - [ ] Consider selective abstraction (allow users to choose which resources)
   - [ ] Add confidence scoring for abstraction mappings
   - [ ] Implement temporal abstraction (track changes over time)
   - [ ] Add cross-tenant comparison features

**Success Criteria**:
- Query performance improved or maintained
- Code is clean and maintainable
- Technical debt reduced
- Future enhancement roadmap defined

## Risk Mitigation

### Risk 1: Data Corruption During Migration

**Risk**: Migration could corrupt existing data or fail partway through.

**Mitigation**:
- Test migration extensively on development and staging
- Backup database before production migration
- Use `IF NOT EXISTS` clauses in migration
- Provide rollback script
- Monitor migration progress
- Have emergency rollback plan

### Risk 2: Performance Degradation

**Risk**: Dual-graph creation doubles write load, potentially slowing scans.

**Mitigation**:
- Profile performance during development
- Use transactions for atomicity (reduces round-trips)
- Batch relationship creation where possible
- Add indexes proactively
- Monitor performance metrics
- Have rollback plan if performance unacceptable

### Risk 3: Hash Collisions

**Risk**: Two different resources might hash to the same ID.

**Mitigation**:
- Use 8-character hex (4 billion combinations)
- Include type prefix to reduce collision space
- Implement collision detection
- Log collisions and alert
- Have strategy to handle collisions (append counter)

### Risk 4: Feature Flag Issues

**Risk**: Feature flag might not work correctly, causing inconsistent behavior.

**Mitigation**:
- Test feature flag thoroughly in development
- Add integration tests for both modes
- Validate configuration in CLI startup
- Log current mode clearly
- Have emergency disable mechanism

### Risk 5: Relationship Parity Issues

**Risk**: Relationships might not be duplicated correctly between graphs.

**Mitigation**:
- Implement validation queries
- Add automated checks during scan
- Monitor relationship counts
- Have repair scripts ready
- Test thoroughly with relationship rules

## Testing Strategy

### Unit Tests

```bash
# Test abstraction service
uv run pytest tests/test_abstraction_service.py -v

# Test dual-graph database operations
uv run pytest tests/test_dual_graph_operations.py -v

# Test relationship rules
uv run pytest tests/test_dual_graph_relationships.py -v
```

### Integration Tests

```bash
# Test with Neo4j testcontainer
uv run pytest tests/integration/test_dual_graph_integration.py -v

# Test feature flag toggle
uv run pytest tests/integration/test_feature_flag.py -v

# Test backward compatibility
uv run pytest tests/integration/test_backward_compatibility.py -v
```

### End-to-End Tests

```bash
# Full scan with dual-graph enabled
uv run atg scan --tenant-id <TENANT_ID> --enable-dual-graph

# Validate graph structure
uv run atg validate-graph --tenant-id <TENANT_ID>

# Generate IaC and verify
uv run atg generate-iac --tenant-id <TENANT_ID> --format terraform

# Compare with single-graph mode
uv run atg scan --tenant-id <TENANT_ID> --no-dual-graph
```

### Performance Tests

```bash
# Benchmark scan performance
time uv run atg scan --tenant-id <TENANT_ID> --enable-dual-graph

# Benchmark query performance
uv run pytest tests/performance/test_query_performance.py -v

# Profile relationship creation
uv run python -m cProfile -o profile.stats scripts/profile_relationships.py
```

## Rollback Plan

If critical issues are discovered in production:

### Immediate Rollback (< 1 hour)

1. **Disable Feature Flag**
   ```bash
   # Set environment variable
   export ENABLE_DUAL_GRAPH=false

   # Restart application
   systemctl restart azure-tenant-grapher
   ```

2. **Verify Single-Graph Mode**
   ```bash
   # Check that only single nodes are created
   uv run atg scan --tenant-id <TENANT_ID>
   ```

### Full Rollback (< 4 hours)

1. **Restore Database Backup**
   ```bash
   # Stop Neo4j
   docker stop neo4j

   # Restore from backup (before migration)
   docker run --rm -v neo4j_data:/data -v /path/to/backup:/backup \
     neo4j:5.9.0 neo4j-admin restore --from=/backup

   # Start Neo4j
   docker start neo4j
   ```

2. **Rollback Code Deployment**
   ```bash
   # Deploy previous version
   git checkout <previous-tag>
   ./scripts/deploy.sh
   ```

3. **Verify System Health**
   ```bash
   # Run health checks
   uv run atg doctor

   # Run validation
   uv run atg validate-graph --tenant-id <TENANT_ID>
   ```

## Success Metrics

### Functional Metrics

- [ ] 100% of resources have both Original and Abstracted nodes
- [ ] 100% of relationships duplicated in both graphs
- [ ] 0 hash collisions detected
- [ ] 0 orphaned nodes detected
- [ ] IaC generation output is deterministic

### Performance Metrics

- [ ] Scan time increase < 20% (vs single-graph)
- [ ] Query performance within 10% of single-graph
- [ ] Database size increase < 2.5x (expect ~2x for two graphs)
- [ ] Memory usage increase < 30%

### Quality Metrics

- [ ] Test coverage > 80% for new code
- [ ] All linting checks pass
- [ ] All type checks pass
- [ ] Security scan passes
- [ ] Code review approved

### Operational Metrics

- [ ] 0 critical bugs in production
- [ ] Mean time to resolution < 4 hours for any issues
- [ ] User satisfaction maintained or improved
- [ ] No user-reported data corruption

## Timeline Summary

| Phase | Duration | Start Date | End Date | Status |
|-------|----------|------------|----------|--------|
| Phase 1: Schema and Infrastructure | 1 week | TBD | TBD | Not Started |
| Phase 2: Dual-Graph Node Creation | 1 week | TBD | TBD | Not Started |
| Phase 3: Dual-Graph Relationships | 1 week | TBD | TBD | Not Started |
| Phase 4: IaC Generation Updates | 1 week | TBD | TBD | Not Started |
| Phase 5: Validation and Monitoring | 1 week | TBD | TBD | Not Started |
| Phase 6: Staging and Production Rollout | 1 week | TBD | TBD | Not Started |
| Phase 7: Optimization and Cleanup | Ongoing | TBD | TBD | Not Started |

**Total Estimated Duration**: 6-7 weeks

## Stakeholder Communication

### Weekly Status Updates

- Progress on current phase
- Blockers and issues
- Risk updates
- Next week's plan

### Go/No-Go Decision Points

1. **Before Phase 2**: Schema and infrastructure validated
2. **Before Phase 4**: Node creation and relationships working
3. **Before Phase 6**: All validation passing, staging successful
4. **Before Full Rollout**: Canary deployment successful

### Escalation Path

- **Minor Issues**: Engineering team resolves within SLA
- **Major Issues**: Engineering lead decides on rollback
- **Critical Issues**: Immediate rollback, incident response activated

## Conclusion

This implementation strategy provides a structured, phased approach to implementing the dual-graph architecture with minimal risk. Each phase builds on the previous one, with clear success criteria and testing at every step.

The feature flag approach allows us to:
- Deploy incrementally with easy rollback
- Test thoroughly in staging before production
- Monitor impact on performance and stability
- Maintain backward compatibility throughout

By following this strategy, we can confidently implement the dual-graph architecture while maintaining system stability and user trust.

---

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Owner**: Engineering Team
**Status**: Draft - Pending Review
