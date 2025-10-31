# Comprehensive Test Plan for PRs #222-226

## Executive Summary

This test plan verifies that all 5 PRs can be merged safely and work together correctly. The PRs have been analyzed for dependencies and conflicts.

## PR Analysis

### PR Dependencies and Conflicts

| PR | Title | Files Changed | Has Conflicts | Dependencies |
|----|-------|---------------|---------------|---------------|
| #222 | Logging consolidation fix | `src/cli_commands.py` | ❌ None | Independent |
| #223 | Agent mode TextMessage fix | `src/agent_mode.py` | ❌ None | Independent |
| #224 | README SPA instructions | `README.md`, `src/agent_mode.py` | ⚠️  Agent mode | Depends on #223 |
| #225 | Graph API permissions fix | `spa/backend/src/server.ts`, `README.md`, `src/agent_mode.py` | ⚠️  Agent mode, README | Depends on #223, #224 |
| #226 | Scan rename + tenant selector | Multiple files | ⚠️  All above files | Depends on #223, #224, #225 |

### Key Findings

1. **Independent PRs**: #222, #223 can be merged independently
2. **Chain Dependencies**: #224 → #225 → #226 form a chain that includes #223
3. **File Conflicts**: All PRs touching `src/agent_mode.py` and `README.md` need careful sequencing
4. **No Merge Conflicts**: When merged in correct order, no git conflicts occur

## Recommended Merge Order

```
1. PR #222 (Logging consolidation) - Independent, safe to merge first
2. PR #223 (Agent mode TextMessage fix) - Foundation for other PRs
3. PR #224 (README SPA instructions) - Builds on #223
4. PR #225 (Graph API permissions fix) - Builds on #223 and #224
5. PR #226 (Scan rename + tenant selector) - Final comprehensive PR
```

## Test Scenarios

### Scenario 1: SPA Logging Verification (PR #222)
**Objective**: Verify logs appear correctly in SPA after logging consolidation fix

**Prerequisites**:
- Neo4j running
- Valid Azure credentials

**Test Steps**:
1. Launch SPA: `uv run atg start`
2. Navigate to Scan tab
3. Start a scan with tenant ID
4. Navigate to Logs tab
5. **Expected**: Real-time logs appear in Logs tab
6. **Expected**: No RichHandler formatting artifacts
7. Stop scan and verify completion logs appear

**Success Criteria**:
- ✅ Logs appear in real-time in SPA Logs tab
- ✅ Log formatting is clean (no ANSI codes)
- ✅ All scan phases show in logs

### Scenario 2: Agent Mode Functionality (PR #223)
**Objective**: Verify agent mode works without TextMessage import errors

**Prerequisites**:
- Neo4j running with populated data
- Azure OpenAI credentials configured

**Test Steps**:
1. Launch SPA: `uv run atg start`
2. Navigate to Agent Mode tab
3. Click on sample query card: "What resources do I have?"
4. **Expected**: Query executes without import errors
5. **Expected**: Results display correctly
6. Try manual query: "Show me all virtual machines"
7. **Expected**: Manual queries work correctly

**Success Criteria**:
- ✅ No "Unknown message type: TextMessage" errors
- ✅ Sample queries execute successfully
- ✅ Manual queries process correctly
- ✅ Results display in UI

### Scenario 3: README Instructions Accuracy (PR #224)
**Objective**: Verify README instructions work for new users

**Prerequisites**:
- Fresh environment or container

**Test Steps**:
1. Follow Quick Start instructions from README
2. Use `azure-tenant-grapher start` (not npm commands)
3. **Expected**: SPA launches successfully
4. **Expected**: No references to deprecated npm commands in main instructions
5. Verify GUI Development section exists for developers

**Success Criteria**:
- ✅ `azure-tenant-grapher start` launches SPA correctly
- ✅ User instructions are clear and npm-free
- ✅ Developer instructions remain accessible

### Scenario 4: Graph API Permissions Check (PR #225)
**Objective**: Verify Graph API permissions are detected correctly

**Prerequisites**:
- Service principal with Directory.Read.All permissions
- Azure credentials configured

**Test Steps**:
1. Launch SPA: `uv run atg start`
2. Navigate to Status tab
3. Check Graph API permissions section
4. **Expected**: Shows "✅ All required permissions available"
5. **Expected**: Detects Directory.Read.All as sufficient
6. Test with limited permissions (User.Read.All + Group.Read.All)
7. **Expected**: Also shows as sufficient

**Success Criteria**:
- ✅ Directory.Read.All detected as sufficient
- ✅ Specific permissions (User.Read.All + Group.Read.All) detected
- ✅ Clear success/failure messages
- ✅ No false negatives for valid permissions

### Scenario 5: Scan Command and Tenant Selector (PR #226)
**Objective**: Verify scan command works and tenant selector functions

**Prerequisites**:
- Two tenant IDs configured in environment
- Neo4j running

**Test Steps**:
1. **CLI Test**: Run `uv run atg scan --help`
2. **Expected**: Shows scan command help (not build)
3. **CLI Test**: Run `uv run atg scan --tenant-id <tenant-id>`
4. **Expected**: Scan executes (same as build functionality)
5. **SPA Test**: Launch `uv run atg start`
6. Navigate to Scan tab (formerly Build tab)
7. **Expected**: UI shows "Scan Azure Tenant" not "Build"
8. Test tenant selector dropdown
9. **Expected**: Shows "Tenant 1 (Primary)" and "Tenant 2 (Simuland)"
10. Select different tenant
11. **Expected**: Tenant ID field auto-populates

**Success Criteria**:
- ✅ `atg scan` command works correctly
- ✅ All UI text uses "scan" terminology
- ✅ Tenant selector populates ID field
- ✅ Scan functionality identical to previous build
- ✅ Backward compatibility: `atg build` still works

### Scenario 6: End-to-End Integration Test
**Objective**: Verify all fixes work together in complete workflow

**Prerequisites**:
- Fresh SPA instance
- Valid Azure credentials
- Neo4j stopped initially

**Test Steps**:
1. Launch SPA: `uv run atg start`
2. **Status Check**: Verify all systems (Neo4j, Azure, Graph API)
3. **Expected**: Graph API permissions show correctly (PR #225)
4. Start Neo4j from Status tab
5. Navigate to Scan tab
6. Select tenant from dropdown (PR #226)
7. **Expected**: Tenant ID auto-populates
8. Start scan operation
9. Navigate to Logs tab during scan
10. **Expected**: Real-time logs appear (PR #222)
11. Navigate to Agent Mode tab after scan
12. Test sample query
13. **Expected**: Agent mode works correctly (PR #223)

**Success Criteria**:
- ✅ Complete workflow executes without errors
- ✅ All individual fixes function correctly
- ✅ No regressions in existing functionality
- ✅ UI terminology consistent (scan not build)

## Merge Conflict Prevention

### Pre-merge Checklist
Before merging each PR, verify:

1. **PR #222**:
   - [ ] No conflicts with `src/cli_commands.py`
   - [ ] All tests pass

2. **PR #223**:
   - [ ] No conflicts with `src/agent_mode.py`
   - [ ] Agent mode tests pass

3. **PR #224**:
   - [ ] Merges cleanly with #223 changes
   - [ ] README renders correctly
   - [ ] No conflicts in `src/agent_mode.py`

4. **PR #225**:
   - [ ] Merges cleanly with #223 and #224
   - [ ] Graph API tests pass
   - [ ] `spa/backend/src/server.ts` compiles

5. **PR #226**:
   - [ ] Merges cleanly with all previous PRs
   - [ ] All renamed files/tests still pass
   - [ ] UI shows scan terminology consistently

### Automated Testing

Run these commands after each PR merge:
```bash
# Run tests
./scripts/run_tests_with_artifacts.sh

# Lint check
uv run ruff check src scripts tests
uv run pyright

# SPA tests
cd spa && npm test && npm run test:e2e

# Integration test
uv run atg scan --help
uv run atg start
```

## Risk Assessment

### Low Risk
- **PR #222**: Single file change, well isolated
- **PR #223**: Single file change, specific import fix

### Medium Risk
- **PR #224**: Documentation changes, minimal code impact
- **PR #225**: Backend API changes, requires testing

### High Risk
- **PR #226**: Comprehensive rename across multiple files
- **Risk**: Could break references in tests or UI
- **Mitigation**: Extensive testing, backward compatibility maintained

## Emergency Rollback Plan

If issues arise after merging:

1. **Individual PR Issues**: Revert specific commit
2. **Integration Issues**: Revert to pre-merge state
3. **Critical Issues**: Revert all PRs, merge individually with testing

Each PR maintains backward compatibility, so rollback risk is minimal.

## Final Verification

After all PRs merged:

1. **Smoke Test**: Complete end-to-end scenario #6
2. **Regression Test**: Run full test suite
3. **User Acceptance**: Manual testing of each PR's core functionality
4. **Documentation**: Verify README and CLI help are consistent

---

**Test Plan Created**: 2025-09-04
**PRs Covered**: #222, #223, #224, #225, #226
**Estimated Testing Time**: 2-3 hours for full validation
