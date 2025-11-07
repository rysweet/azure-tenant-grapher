# IaC Codebase TODOs Analysis
**Generated**: 2025-11-07 13:30 UTC

## Summary
- **Total TODOs Found**: 14
- **Critical for Faithful Replica**: 0 (all are feature enhancements)
- **Impact on Current Work**: None (ROOT CAUSE FIX is primary blocker)

## TODO Breakdown by Category

### Identity Mapping (1 TODO)
- **File**: src/iac/translators/keyvault_translator.py
- **TODO**: Phase 3: Load and parse identity mapping file
- **Impact**: Low - identity mapping already works without this
- **Priority**: Future enhancement

### Size/Metrics Collection (1 TODO)
- **File**: src/iac/plugins/sql_plugin.py
- **TODO**: Get actual size for SQL databases
- **Impact**: Cosmetic - doesn't affect deployment
- **Priority**: Low

### Documentation Placeholders (6 TODOs)
- **Files**: keyvault_plugin.py (3), appservice_plugin.py (1), cosmosdb_plugin.py (2)
- **Type**: Comment placeholders in generated IaC
- **Impact**: None - these are template comments for users
- **Priority**: Cosmetic

### Feature Implementations (4 TODOs)
1. Key Vault soft-delete conflict detection (keyvault_handler.py)
   - **Status**: Known issue, documented in session reports
   - **Impact**: Causes some vault errors but not blocking
   
2. Complete emitter registry (emitters/__init__.py)
   - **Status**: Current emitters work fine
   - **Impact**: Future extensibility only
   
3. Additional dependency extraction (dependency_analyzer.py)
   - **Status**: Current dependency handling sufficient
   - **Impact**: Could improve ordering slightly
   
4. Subscription ID from config (cli_handler.py)
   - **Status**: Works with command-line args
   - **Impact**: Convenience feature only

## Recommendations

### For Faithful Replica Objective
**Action**: SKIP all TODOs
**Reasoning**: 
- ROOT CAUSE FIX (all_resources strategy) is the critical blocker
- All TODOs are enhancements, not blockers
- Current code successfully deploys resources
- Focus should remain on iteration loop, not feature additions

### For Future Sessions
**Potential improvements** (after reaching 90% target):
1. Implement Key Vault soft-delete handling (reduces vault errors)
2. Add subscription ID to config (improves UX)
3. Extract additional dependencies (improves ordering)

## Decision
**DO NOT PURSUE** these TODOs in current session.
**REASON**: They don't advance the faithful replica objective.
**FOCUS**: Continue autonomous iteration loop with ROOT CAUSE FIX deployed.

---
**Analysis**: Complete ✅
**Action**: Continue with iteration 15 and auto-launch loop 🏴‍☠️
