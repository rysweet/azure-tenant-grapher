# Graph Construction Version Tracking - Refined Architecture

**Status**: Architecture Design (Post-Zen Review)
**Complexity Ratio**: 4:1 (clearly justified)
**Estimated Implementation**: ~400 lines (33% reduction from original 600)

## Philosophy Alignment

This design embodies ruthless simplicity:
- **Single responsibility**: Track when graph construction logic changes
- **Start minimal**: Only `version` and `last_scan_at` initially
- **Avoid future-proofing**: No schema_version until proven need
- **Trust in emergence**: Let requirements drive complexity, not speculation

## Problem Statement

When graph construction code changes, existing graphs become stale and potentially incorrect. Users need:
1. Detection when their graph is built with old code
2. Non-blocking warning at startup (<100ms)
3. Guided rebuild workflow with safe backup option

## Core Design (Simplified)

### 1. Metadata Node (Minimal)

```cypher
(:GraphMetadata {
  version: "1.2.3",           # Construction code version (REQUIRED)
  last_scan_at: "timestamp"   # When graph was last updated (REQUIRED)
})
```

**What We Removed**:
- ❌ `schema_version` - Let construction version handle both until proven need
- ❌ `changes[]` - Git history is the single source of truth for changelog
- ❌ Future fields - Add only when actually needed

**Philosophy**: Start with the absolute minimum. Every field must justify its existence NOW, not "just in case."

### 2. Version Detection

```python
# src/iac/graph_version/detector.py

@dataclass
class VersionInfo:
    """Minimal version information"""
    current_code_version: str
    graph_metadata_version: Optional[str]
    is_outdated: bool

def detect_version_mismatch(driver: GraphDatabase) -> VersionInfo:
    """Fast version check (<100ms)"""
    current = _get_current_version()  # From package metadata
    graph_version = _query_graph_metadata(driver)

    return VersionInfo(
        current_code_version=current,
        graph_metadata_version=graph_version,
        is_outdated=(graph_version != current if graph_version else False)
    )
```

### 3. User Workflow (Separated Concerns)

**Startup Detection** (Always runs, <100ms):
```bash
$ atg scan

⚠️  Graph built with v1.0.0, current code is v1.2.3
   Your graph may contain stale data.

   Run 'atg rebuild-check' to see what changed.
   Run 'atg rebuild --backup' to safely rebuild.

Scanning tenant...
```

**Manual Investigation** (User-initiated):
```bash
$ atg rebuild-check

Changes between v1.0.0 → v1.2.3:
  - Resource property handling updated (commit abc123)
  - Relationship inference improved (commit def456)

Run 'atg rebuild --backup' to update your graph.
```

**Safe Rebuild** (User-initiated):
```bash
$ atg backup-metadata        # NEW: Separate backup command
Backed up metadata to: ~/.atg/backups/metadata-2026-01-16.json

$ atg rebuild
Rebuilding graph with v1.2.3...
✓ Complete
```

**Key Simplifications**:
- ✅ Backup is **separate CLI command** (`atg backup-metadata`)
- ✅ Warning is **non-blocking** by default
- ✅ User controls when to investigate and rebuild
- ✅ No forced backups (user decides)

### 4. Module Structure (Brick Philosophy)

```
src/iac/graph_version/           # The brick
├── __init__.py                   # Public API (__all__)
├── README.md                     # Contract specification
├── detector.py                   # Version detection (<100ms)
├── metadata.py                   # Graph metadata operations
├── tests/
│   ├── test_detector.py          # Fast unit tests
│   └── test_metadata.py
└── examples/
    └── basic_usage.py
```

**Public Contract** (`__init__.py`):
```python
"""Graph construction version tracking.

Philosophy:
- Single responsibility: Detect construction code changes
- Standard library only (except Neo4j driver)
- Self-contained and regeneratable

Public API:
    detect_version_mismatch: Fast startup check
    get_graph_metadata: Read metadata node
    update_graph_metadata: Write metadata node
"""

__all__ = [
    "detect_version_mismatch",
    "get_graph_metadata",
    "update_graph_metadata",
    "VersionInfo"
]
```

## Implementation Priorities

### Phase 1: Core Detection (MVP)
- [ ] Metadata node queries
- [ ] Version detection at startup
- [ ] Non-blocking warning message
- [ ] Basic unit tests

### Phase 2: User Workflows
- [ ] `atg rebuild-check` command
- [ ] `atg backup-metadata` command
- [ ] Integration with rebuild workflow

### Phase 3: Polish
- [ ] Performance optimization (<100ms guarantee)
- [ ] Integration tests
- [ ] Documentation

## Testing Strategy

Following TDD pyramid (60% unit, 30% integration, 10% E2E):

**Unit Tests** (60%):
```python
def test_detect_version_mismatch_when_outdated():
    """Fast test with mocked Neo4j"""
    # Mock graph returns v1.0.0
    # Current code is v1.2.3
    result = detect_version_mismatch(mock_driver)
    assert result.is_outdated is True

def test_detect_version_mismatch_no_metadata():
    """Handle graphs without metadata gracefully"""
    result = detect_version_mismatch(mock_empty_driver)
    assert result.graph_metadata_version is None
```

**Integration Tests** (30%):
```python
def test_startup_warning_displays_correctly(real_neo4j):
    """Test with real Neo4j instance"""
    # Insert old metadata
    # Run startup check
    # Verify warning message format
```

**E2E Tests** (10%):
```python
def test_complete_rebuild_workflow(cli_runner):
    """Test full user workflow"""
    # Run atg scan (see warning)
    # Run atg rebuild-check
    # Run atg backup-metadata
    # Run atg rebuild
    # Verify metadata updated
```

## Complexity Justification

**Benefits**:
- Prevents data corruption from stale graphs (HIGH value)
- Guides users to safe rebuild workflow (HIGH value)
- Non-blocking, fast startup check (LOW friction)

**Costs**:
- ~400 lines of implementation code
- One additional Cypher query at startup (<100ms)
- New CLI commands to maintain

**Ratio**: ~4:1 benefit-to-cost (clearly justified per philosophy)

## What This Design DOESN'T Do

To maintain simplicity, we explicitly exclude:

- ❌ **Automatic schema migration** - Users control when to rebuild
- ❌ **Detailed change diff** - Git history provides this
- ❌ **Schema version tracking** - Construction version handles both initially
- ❌ **Forced backups** - User choice via separate command
- ❌ **Complex version compatibility matrix** - Simple equality check

**Remember**: It's easier to add complexity later than remove it.

## Success Metrics

- Startup check completes in <100ms
- Users can identify stale graphs at a glance
- Safe rebuild workflow is clear and documented
- Zero false positives in version detection
- Tests run in <5 seconds

## Future Considerations (NOT IMPLEMENTED NOW)

If proven need emerges, consider:
- Separate schema_version field (if construction/schema diverge)
- Optional changes[] array (if git history insufficient)
- Partial rebuild support (if full rebuild too expensive)

These are **explicitly deferred** until real-world usage proves necessity.

---

**Design Review Checklist**:
- [x] Follows brick philosophy (self-contained module)
- [x] Ruthlessly simple (minimal fields, clear purpose)
- [x] Zero-BS (all functions work, no stubs)
- [x] Proportional testing (60/30/10 pyramid)
- [x] Clear user workflows (non-blocking warnings)
- [x] Performance conscious (<100ms startup)
- [x] Regeneratable from this spec
