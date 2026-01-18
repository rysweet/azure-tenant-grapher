# Documentation Consolidation Plan

**Issue**: #739
**Generated**: 2026-01-18
**Status**: Design Phase

## Executive Summary

Discovered **807 markdown files** (4.4x more than expected 182). Analysis reveals 53 stale files (>6 months), 4 exact duplicate groups, 38 title duplicate groups, and 31 filename duplicate groups affecting 327 files.

## Inventory Summary

### By Category
- **skills**: 285 files (35.3%)
- **documentation**: 211 files (26.2%)
- **other**: 164 files (20.3%)
- **readme**: 60 files (7.4%)
- **agents**: 34 files (4.2%)
- **tests**: 22 files (2.7%)
- **scenarios**: 16 files (2.0%)
- **templates**: 11 files (1.4%)
- **examples**: 2 files (0.2%)
- **context**: 1 file (0.1%)
- **project-root**: 1 file (0.1%)

### Statistics
- **Total Files**: 807
- **Total Size**: 9.41 MB
- **Stale Files**: 53 (6.6%)
- **Exact Content Duplicates**: 4 groups (9 files)
- **Title Duplicates**: 38 groups (77 files)
- **Filename Duplicates**: 31 groups (327 files - 40.5%)

## Duplicate Analysis

### Exact Content Duplicates (Priority 1 - Immediate Merge)

1. **OOXML README duplication** (3 copies):
   - `./.claude/skills/pptx/ooxml/README.md`
   - `./.claude/skills/common/ooxml/README.md`
   - `./.claude/skills/docx/ooxml/README.md`
   - **Action**: Keep in `common/ooxml/`, symlink from others OR delete duplicates, add references

2. **Azure DevOps HOW_TO duplication** (2 copies):
   - `./.claude/scenarios/az-devops-tools/HOW_TO_CREATE_YOUR_OWN.md`
   - `./.claude/skills/azure-devops/HOW_TO_CREATE_YOUR_OWN.md`
   - **Action**: Keep in scenarios (source of truth), add reference in skills

3. **Prompt History duplicates** (2 groups):
   - `./.github/prompt-history/` vs `already_processed/` subdirectory
   - **Action**: Delete duplicates in `already_processed/` (archival directory for processed items)

### Title Duplicates (Priority 2 - Review and Consolidate)

1. **SPA Requirements** (2 files):
   - `./docs/design/SPA_REQUIREMENTS.md`
   - `./spa/docs/REQUIREMENTS.md`
   - **Action**: Review content, keep most current in `spa/docs/`, reference from design docs

2. **Create-Tenant documentation** (2 files):
   - `./docs/demo/commands/create-tenant.md`
   - `./.github/prompt-history/already_processed/create-tenant.md`
   - **Action**: Keep in docs/demo, remove from prompt-history

3. **Sample Tenant** (2 files):
   - `./docs/demo/commands/create-tenant-sample.md`
   - `./tests/fixtures/sample-tenant.md`
   - **Action**: Keep test fixture, reference from demo docs

4. **Scale Operations Diagrams** (2 files):
   - `./docs/diagrams/README.md`
   - `./docs/SCALE_OPERATIONS_DIAGRAMS.md`
   - **Action**: Merge into single diagrams/README.md

5. **Azure MCP Integration** (2 files):
   - `./docs/azure-mcp-integration.md`
   - `./.claude/skills/azure-admin/docs/mcp-integration.md`
   - **Action**: Review content difference, keep most technical in docs/, reference from skills

6. **CTF Overlay Architecture** (2 files):
   - `./docs/ctf_overlay_system/ARCHITECTURE.md`
   - `./Specs/CTF_OVERLAY_ARCHITECTURE.md`
   - **Action**: Keep in docs/ (source of truth), deprecate Specs/ version

7. **Continuous Operation Status** (2 files):
   - `./demos/CONTINUOUS_OPERATION_STATUS_FINAL.md`
   - `./demos/CONTINUOUS_SESSION_STATUS_2025-10-15.md`
   - **Action**: Keep FINAL version, archive dated version

### Filename Duplicates (Priority 3 - Review README proliferation)

327 files with duplicate names across different directories. Most common:
- **README.md**: 60 occurrences (module documentation - generally OK, but review for consistency)
- **SKILL.md**: Multiple skill definitions (expected pattern)
- **examples/**: Test and example duplication

**Action**: Audit README files for consistency, ensure each serves unique purpose.

## Stale Documentation (>6 months)

53 files haven't been updated in 6+ months. These require review for:
- Currency (is information still accurate?)
- Relevance (is doc still needed?)
- Archival (move to `.claude/runtime/archived_docs/` if obsolete)

**Action**: Flag with `<!-- STALE: Last updated YYYY-MM-DD -->` header, review each for accuracy.

## Proposed Changes

### Phase 1: Exact Duplicate Removal (Immediate)

1. **OOXML README consolidation**:
   - Keep: `.claude/skills/common/ooxml/README.md`
   - Delete: `pptx/ooxml/README.md`, `docx/ooxml/README.md`
   - Add: References in deleted file locations pointing to common/

2. **Azure DevOps HOW_TO consolidation**:
   - Keep: `.claude/scenarios/az-devops-tools/HOW_TO_CREATE_YOUR_OWN.md`
   - Delete: `.claude/skills/azure-devops/HOW_TO_CREATE_YOUR_OWN.md`
   - Add: Reference note in skills directory

3. **Prompt History cleanup**:
   - Delete: All files in `.github/prompt-history/already_processed/` that duplicate parent directory
   - Rationale: Archival directory should not duplicate current docs

**Estimated Impact**: Remove 7 exact duplicate files, add 5 reference stubs

### Phase 2: Title Duplicate Consolidation (Review Required)

For each title duplicate group:
1. Compare content for differences
2. Identify canonical location (source of truth)
3. Merge unique content into canonical file
4. Delete or stub-reference secondary files
5. Update cross-references

**Estimated Impact**: Merge 38 duplicate groups (~60 files affected), update links

### Phase 3: Freshness Metadata Addition

Add frontmatter metadata to key documentation files:

```markdown
---
last_updated: 2026-01-18
status: current | stale | deprecated
category: <category>
---
```

**Target Files**:
- All files in `.claude/context/` (1 file)
- All files in `.claude/agents/` (34 files)
- All files in `.claude/skills/` top-level SKILL.md files (estimated 50 files)
- All files in `docs/` top-level (estimated 50 files)
- Root-level documentation (README.md, CONTRIBUTING.md, etc.)

**Estimated Impact**: Add metadata to ~150 key files

### Phase 4: Create docs/INDEX.md

Comprehensive navigation index organized by:
1. **Quick Start** (README, CONTRIBUTING)
2. **Core Documentation** (Architecture, Design, API Reference)
3. **User Guides** (CLI commands, demos, tutorials)
4. **Developer Documentation** (Specs, testing, deployment)
5. **Amplihack Framework** (.claude/ structure, agents, skills, scenarios)
6. **Historical/Archive** (obsolete docs, old designs)

**Estimated Impact**: Create 1 new file (docs/INDEX.md), 200-300 lines

### Phase 5: Link Validation and Fixing

1. Extract all markdown links from inventory
2. Validate internal links (file exists?)
3. Flag broken links
4. Update links affected by consolidation
5. Generate link health report

**Estimated Impact**: Fix ~50-100 broken links (estimated 5-10% breakage rate)

### Phase 6: Stale Documentation Review

For each of 53 stale files:
1. Review content for accuracy
2. Update if still relevant
3. Archive to `.claude/runtime/archived_docs/` if obsolete
4. Add `<!-- STALE -->` marker if keeping but not updating

**Estimated Impact**: Archive ~20 obsolete files, mark ~30 as stale

## Success Criteria (from Issue #739)

- [x] Complete inventory produced with categorization
- [x] All duplicates identified with merge plan
- [x] Stale docs flagged with 6-month threshold applied
- [ ] Freshness metadata added to all key documentation files
- [ ] docs/INDEX.md exists with comprehensive categorized navigation
- [ ] All existing tests pass (if any doc-validation tests exist)
- [ ] No broken links remain (link checker passes)
- [ ] Documentation updated (this IS the documentation update)
- [ ] Local testing completed with verification evidence

## Risk Mitigation

1. **Link Breakage**: Comprehensive link validation pass after consolidation
2. **Content Loss**: Git history preserves all deleted files (easily recoverable)
3. **User Confusion**: Clear migration notes in stub files pointing to new locations
4. **Workflow Disruption**: Changes to .claude/ directory validated against workflow requirements

## Implementation Order

1. Phase 1: Exact Duplicate Removal (low risk, immediate value)
2. Phase 4: Create docs/INDEX.md (navigation aid for remaining work)
3. Phase 2: Title Duplicate Consolidation (requires careful content review)
4. Phase 3: Freshness Metadata Addition (low risk, high value)
5. Phase 5: Link Validation and Fixing (required after consolidation)
6. Phase 6: Stale Documentation Review (time-consuming, lower priority)

## Files Referenced

- Inventory: `.claude/runtime/doc_inventory.json`
- Duplicates: `.claude/runtime/doc_duplicates.json`
- This Plan: `.claude/runtime/DOC_CONSOLIDATION_PLAN.md`

## Next Steps

1. Get architect review of this plan
2. Proceed to TDD (write tests for consolidation scripts if needed)
3. Implement Phase 1 (exact duplicates)
4. Iterate through remaining phases
5. Validate with link checker and local testing

---

**Note**: This plan preserves ALL explicit user requirements from Issue #739. No documentation will be removed without careful review. All changes are git-tracked and reversible.
