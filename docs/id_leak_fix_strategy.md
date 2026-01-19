# ID Leakage Fix Strategy - Issue #475

## Executive Summary

**Problem**: Source tenant IDs (principalId, tenantId, clientId, subscription IDs) leak into Neo4j graph and IaC output, preventing cross-tenant deployment.

**Root Cause**: ID extraction happens in multiple places without consistent abstraction layer.

**Solution**: Implement centralized ID abstraction at extraction points (services layer) and ensure translators are called in all emitters.

## Verified Leak Points (Based on Code Scan)

### CRITICAL - Graph Layer Leaks (Data Collection)

These leak into Neo4j graph, polluting the data source:

1. **services/identity_collector.py** (Lines 126, 155, 194)
   - Extracts `principalId` without abstraction
   - Goes directly into graph
   - **Fix**: Abstract principal_id before storing in graph

2. **services/managed_identity_resolver.py** (Lines 50-91)
   - Extracts `principalId`, `clientId`, `tenantId` without abstraction
   - Returns raw IDs in resolved identity dict
   - **Fix**: Abstract IDs before returning

3. **services/resource_processing/node_manager.py** (Lines 423, 432)
   - Already has SOME abstraction code but may be incomplete
   - **Fix**: Verify abstraction is comprehensive

### HIGH - IaC Emitter Leaks (Output Generation)

These leak into generated IaC files:

4. **iac/emitters/terraform/handlers/keyvault/vault.py** (Line 86)
   - Falls back to raw `properties.get("tenantId")` if target not set
   - **Fix**: ALWAYS translate tenant_id, never use source

5. **iac/emitters/arm_emitter.py** (Line 81)
   - Extracts `principalId` for logging/validation
   - May not always translate
   - **Fix**: Verify translation is applied

6. **iac/emitters/bicep_emitter.py** (Line 178)
   - Same issue as ARM emitter
   - **Fix**: Verify translation is applied

### MEDIUM - Relationship Layer Leaks

These may leak into graph relationships:

7. **relationship_rules/identity_rule.py** (Lines 65, 73, 170, 241)
   - Multiple `principalId` extractions
   - **Fix**: Ensure abstracted IDs are used

8. **relationship_rules/creator_rule.py** (Line 51)
   - Extracts `principalId` from created_by
   - **Fix**: Use abstracted ID

## Fix Implementation Plan

### Phase 1: Core Abstraction Service (FOUNDATION)

**Goal**: Ensure abstraction happens at data collection layer

**Files to Fix**:
- `src/services/identity_collector.py`
- `src/services/managed_identity_resolver.py`
- `src/services/resource_processing/node_manager.py`

**Approach**:
1. Create/enhance ID abstraction utility function
2. Call abstraction BEFORE storing in Neo4j
3. Ensure all identity objects use abstracted IDs

### Phase 2: IaC Emitter Hardening (OUTPUT PROTECTION)

**Goal**: Ensure NO raw IDs escape to IaC

**Files to Fix**:
- `src/iac/emitters/terraform/handlers/keyvault/vault.py`
- `src/iac/emitters/arm_emitter.py`
- `src/iac/emitters/bicep_emitter.py`

**Approach**:
1. NEVER use raw `properties.get("tenantId/principalId")` in final output
2. ALWAYS call translator for tenant_id
3. Verify role assignment translation is comprehensive

### Phase 3: Relationship Layer Protection (RELATIONSHIP INTEGRITY)

**Goal**: Ensure relationships use abstracted IDs

**Files to Fix**:
- `src/relationship_rules/identity_rule.py`
- `src/relationship_rules/creator_rule.py`

**Approach**:
1. Modify rules to pull abstracted IDs from node properties
2. If ID abstraction missed, add fallback abstraction

## Testing Strategy

### Unit Tests

For each fixed file, create test verifying:
1. Source ID input
2. Abstracted ID output
3. No raw IDs in result

### Integration Tests

1. **Graph Test**: Scan mock tenant, verify Neo4j has no raw GUIDs
2. **IaC Test**: Generate IaC, verify no source tenant/subscription/principal IDs
3. **Cross-Tenant Test**: Verify IaC deployable to different tenant

## Success Criteria

1. All 29 potential leak points reviewed
2. All CRITICAL and HIGH leaks fixed
3. Tests pass demonstrating no ID leakage
4. IaC generated from abstracted graph deploys to different tenant
5. No raw source IDs in Neo4j properties or relationships

## Estimated Complexity

- **Lines Changed**: ~200-300 (mostly adding abstraction calls)
- **Files Modified**: ~8-10 files
- **Test Files**: ~5-8 new test files
- **Complexity**: MODERATE (existing abstraction infrastructure exists, need to apply consistently)

## Rollout

1. Fix Phase 1 (graph layer) FIRST - prevents pollution at source
2. Fix Phase 2 (emitters) - protects output
3. Fix Phase 3 (relationships) - ensures graph integrity
4. Comprehensive testing
5. PR with detailed validation results

## Notes

- Existing `EntraIdTranslator` already handles translation logic
- Existing Bug #67, #69, #70 fixes show pattern to follow
- Issue #475 audit likely based on older codebase - some fixes may already exist
- Focus on VERIFYING current state and fixing remaining gaps
