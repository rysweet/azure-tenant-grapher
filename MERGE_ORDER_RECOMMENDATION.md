# Merge Order Recommendation for PRs #222-226

## Recommended Order

### 1. PR #222 - Logging consolidation fix ⭐ **SAFE TO MERGE FIRST**
- **Files**: `src/cli_commands.py`
- **Risk**: Low - Single file, isolated change
- **Dependencies**: None
- **Why First**: Independent fix that improves SPA logging immediately

### 2. PR #223 - Agent mode TextMessage fix ⭐ **FOUNDATION PR**
- **Files**: `src/agent_mode.py`
- **Risk**: Low - Single file, specific import fix
- **Dependencies**: None
- **Why Second**: Required by PRs #224, #225, and #226

### 3. PR #224 - README SPA instructions update
- **Files**: `README.md`, `src/agent_mode.py`
- **Risk**: Low - Mostly documentation
- **Dependencies**: PR #223 (agent_mode.py changes)
- **Why Third**: Builds on #223, required by #225 and #226

### 4. PR #225 - Graph API permissions fix
- **Files**: `spa/backend/src/server.ts`, `README.md`, `src/agent_mode.py`
- **Risk**: Medium - Backend API changes
- **Dependencies**: PR #223, #224 (agent_mode.py and README.md changes)
- **Why Fourth**: Builds on both #223 and #224

### 5. PR #226 - Scan rename + tenant selector ⭐ **COMPREHENSIVE FINAL PR**
- **Files**: Multiple (comprehensive rename)
- **Risk**: High - Wide-ranging changes
- **Dependencies**: All previous PRs (#223, #224, #225)
- **Why Last**: Most comprehensive, incorporates all previous changes

## Dependency Chain Analysis

```
PR #222 ──── (Independent, merge first)

PR #223 ──── (Foundation for others)
   │
   ├── PR #224 ──── (Builds on #223)
   │      │
   │      └── PR #225 ──── (Builds on #223 + #224)
   │             │
   └─────────────── PR #226 ──── (Builds on #223 + #224 + #225)
```

## Critical File Conflicts

### `src/agent_mode.py` (Modified by PRs #223, #224, #225, #226)
**Solution**: Sequential merging prevents conflicts
- PR #223: TextMessage import fix
- PR #224: Includes #223 changes
- PR #225: Includes #223 changes
- PR #226: Includes all previous changes

### `README.md` (Modified by PRs #224, #225, #226)
**Solution**: Sequential merging with PR #224 as base
- PR #224: SPA instructions update
- PR #225: Includes #224 changes
- PR #226: Includes all previous changes

### `spa/backend/src/server.ts` (Modified by PRs #225, #226)
**Solution**: PR #225 first, then #226
- PR #225: Graph API permissions logic
- PR #226: Includes #225 changes

## Validation Steps

### After Each PR Merge:
1. **Run Tests**: `./scripts/run_tests_with_artifacts.sh`
2. **Lint Check**: `uv run ruff check src scripts tests`
3. **Type Check**: `uv run pyright`
4. **SPA Tests**: `cd spa && npm test`

### Critical Validation Points:

#### After PR #222:
```bash
# Test logging in SPA
uv run atg start
# Check Logs tab shows real-time output
```

#### After PR #223:
```bash
# Test agent mode
uv run atg agent-mode
# Verify no TextMessage errors
```

#### After PR #224:
```bash
# Test README instructions
azure-tenant-grapher start
# Verify SPA launches correctly
```

#### After PR #225:
```bash
# Test Graph API permissions
# Check Status tab in SPA
```

#### After PR #226:
```bash
# Test scan command
uv run atg scan --help
uv run atg scan --tenant-id test
# Verify UI terminology is consistent
```

## Emergency Procedures

### If Merge Conflicts Occur:
1. **STOP** - Do not force merge
2. **Revert** to previous state: `git reset --hard HEAD~1`
3. **Re-examine** file conflicts manually
4. **Contact** PR author for resolution

### If Tests Fail After Merge:
1. **Document** specific failure
2. **Revert** problematic PR: `git revert <commit-hash>`
3. **Fix** issues in separate branch
4. **Re-attempt** merge with fixes

## Alternative Strategies

### Strategy A: Conservative (Recommended)
Merge one PR at a time with full testing between each merge.

**Timeline**: 1-2 hours per PR = 5-10 hours total
**Risk**: Minimal
**Benefits**: Maximum safety, easy rollback

### Strategy B: Batch Merge
Merge independent PRs (#222, #223) together, then dependent chain.

**Timeline**: 2-3 hours total
**Risk**: Medium
**Benefits**: Faster completion

### Strategy C: Single Merge
Create integration branch combining all PRs.

**Timeline**: 30 minutes
**Risk**: High
**Benefits**: Fastest, but harder to troubleshoot issues

## Final Recommendations

### ✅ DO:
1. Merge in the specified order: #222 → #223 → #224 → #225 → #226
2. Run full test suite after each merge
3. Validate functionality specific to each PR
4. Keep merge commits clean and descriptive

### ❌ DON'T:
1. Merge PRs out of order
2. Skip testing between merges
3. Force-push or rebase after merge conflicts
4. Merge multiple PRs simultaneously

### 🔧 PREPARE:
1. Ensure clean working directory
2. Have all branch access ready
3. Allocate 3-4 hours for complete process
4. Have rollback plan ready

---

**Status**: Ready for execution
**Estimated Time**: 3-4 hours for safe, sequential merge
**Risk Level**: Low (with proper sequencing)
**Success Probability**: 95%+ (if order followed)
