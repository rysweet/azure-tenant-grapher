# Version Tracking Module

Automated version detection and validation for Azure Tenant Grapher graph construction.

## Overview

This module tracks changes to graph construction files and enforces version updates to ensure the graph database stays synchronized with the codebase.

### Key Features

- **Hash-based tracking**: Detects code changes even when version number isn't updated
- **Fast performance**: < 100ms for complete validation
- **Git integration**: Pre-commit hooks prevent commits without version updates
- **Automatic detection**: Tracks specific files that affect graph construction

## Architecture

### Components

1. **hash_tracker.py**: Calculate and validate file hashes
2. **detector.py**: Detect version/hash mismatches
3. **metadata.py**: Read/write version metadata to Neo4j
4. **rebuild.py**: Orchestrate graph rebuilds when needed

### Tracked Files

The following files trigger version bumps when modified:

```
src/relationship_rules/           # All relationship rules
src/services/azure_discovery_service.py
src/resource_processor.py
src/azure_tenant_grapher.py
```

## Usage

### Basic Workflow

1. **Make changes** to graph construction files
2. **Update version file** (.atg_graph_version)
3. **Commit changes** (pre-commit hook validates)
4. **Graph auto-detects** version mismatch on startup
5. **Rebuild if needed** (automatic or manual)

### Version File Format

`.atg_graph_version` (JSON format):

```json
{
  "version": "1.0.0",
  "last_modified": "2026-01-17T00:00:00Z",
  "description": "What changed in this version",
  "construction_hash": "abc123...",
  "tracked_paths": [
    "src/relationship_rules/",
    "src/services/azure_discovery_service.py",
    "src/resource_processor.py",
    "src/azure_tenant_grapher.py"
  ]
}
```

### Calculating Hash

Calculate current construction hash:

```python
from src.version_tracking.hash_tracker import calculate_construction_hash

# Calculate hash
current_hash = calculate_construction_hash()
print(f"Current hash: {current_hash}")
```

Or from command line:

```bash
python3 -c "from src.version_tracking.hash_tracker import calculate_construction_hash; print(calculate_construction_hash())"
```

### Validating Hash

Check if stored hash matches current code:

```python
from src.version_tracking.hash_tracker import validate_hash

# Validate
result = validate_hash(stored_hash="abc123...")

if not result.matches:
    print(f"Hash mismatch!")
    print(f"Stored:  {result.stored_hash}")
    print(f"Current: {result.current_hash}")
    print(f"Changed files:")
    for file in result.changed_files:
        print(f"  - {file}")
```

### Detecting Mismatches

Complete version and hash validation:

```python
from src.version_tracking.detector import VersionDetector
from src.services.graph_metadata_service import GraphMetadataService

# Initialize
detector = VersionDetector()
metadata_service = GraphMetadataService(neo4j_service)

# Detect mismatch
mismatch = detector.detect_mismatch(metadata_service)

if mismatch:
    print(f"Mismatch detected: {mismatch['reason']}")
    if mismatch['type'] == 'hash_mismatch':
        print(f"Changed files: {mismatch['changed_files']}")
```

## Git Hooks

### Installing Hooks

Install pre-commit hook to enforce version updates:

```bash
./scripts/install-version-hooks.sh
```

This installs a hook that:

1. Detects changes to tracked files
2. Ensures `.atg_graph_version` is also updated
3. Blocks commit if version not updated
4. Provides clear instructions on what to update

### Bypassing Hook

For legitimate reasons (docs, tests only):

```bash
git commit --no-verify
```

### Hook Behavior

When tracked files change:

```
❌ ERROR: Graph construction files changed but .atg_graph_version not updated!

Construction files modified:
  - src/relationship_rules/new_rule.py

Please update .atg_graph_version:
  1. Bump version (MAJOR.MINOR.PATCH)
  2. Update last_modified timestamp
  3. Update construction_hash (run: python3 -c '...')
  4. Add description of changes

Or skip check: git commit --no-verify
```

## API Reference

### HashTracker

Main class for hash calculation and validation.

```python
class HashTracker:
    TRACKED_PATHS = [...]  # Files/dirs to track

    def calculate_construction_hash() -> str
    def validate_hash(stored_hash, stored_files=None) -> HashValidationResult
```

### HashValidationResult

Result of hash validation.

```python
@dataclass
class HashValidationResult:
    matches: bool                    # True if hash matches
    stored_hash: Optional[str]       # Hash from version file
    current_hash: str                # Hash calculated now
    changed_files: List[str]         # Files that changed
```

### VersionDetector

Detects version and hash mismatches.

```python
class VersionDetector:
    def read_semaphore_version() -> Optional[str]
    def read_semaphore_data() -> Optional[Dict]
    def detect_mismatch(metadata_service) -> Optional[Dict]
```

## Performance

### Hash Calculation

- **Target**: < 50ms for hash calculation
- **Actual**: ~10-20ms with 10-20 tracked files
- **Method**: Chunked file reading (8KB chunks)
- **Optimization**: Files sorted for consistent ordering

### Mismatch Detection

- **Target**: < 100ms for complete check
- **Actual**: ~30-50ms (hash check) + ~20-50ms (metadata query)
- **Order**: Hash checked first (faster, no DB query)

## Testing

### Run Tests

```bash
# Hash tracker tests
uv run pytest tests/unit/version_tracking/test_hash_tracker.py -v

# Detector tests
uv run pytest tests/unit/version_tracking/test_detector_hash.py -v

# All version tracking tests
uv run pytest tests/unit/version_tracking/ -v
```

### Test Coverage

- **Hash calculation**: 23 tests
- **Detector integration**: 14 tests
- **Performance validation**: Included
- **Coverage**: 95%+ for hash_tracker.py

## Troubleshooting

### "Hash mismatch detected"

**Cause**: Code changed but version file not updated

**Solution**:
1. Calculate new hash: `python3 -c "from src.version_tracking.hash_tracker import calculate_construction_hash; print(calculate_construction_hash())"`
2. Update `.atg_graph_version` with new hash
3. Bump version number
4. Update last_modified timestamp
5. Add description of changes

### "Pre-commit hook blocks commit"

**Cause**: Changed tracked files without updating version file

**Solution**:
1. Update `.atg_graph_version` as above
2. Add version file to commit: `git add .atg_graph_version`
3. Commit again

**Alternative**: Skip hook for docs/tests only: `git commit --no-verify`

### "Hash always mismatches"

**Cause**: Unstable file system or permissions

**Check**:
1. Verify tracked files are readable
2. Check for __pycache__ pollution
3. Verify no editors creating temp files
4. Check file permissions

### Performance Issues

**Expected**: < 100ms total
**Actual**: > 500ms

**Solutions**:
1. Check number of tracked files (should be < 100)
2. Check file sizes (large files slow hash calculation)
3. Check disk I/O (slow disk affects performance)

## Design Decisions

### Why SHA256?

- Standard library (no dependencies)
- Fast enough (< 50ms for typical projects)
- Collision-resistant for code files
- Widely understood and trusted

### Why Track Paths in Hash?

Renaming files should trigger version bump. Including paths in hash ensures renames are detected.

### Why Hash Before Version Check?

Hash check is faster (no DB query) and catches the most common case (code changed, version not updated).

### Why Separate Semaphore File?

- Fast reads (no DB query needed)
- Version control friendly (easy to see in git)
- Can be updated without graph connection
- Human-readable format

## Future Enhancements

Potential improvements:

1. **Auto-bump version**: Calculate and update version file automatically
2. **Change detection**: More detailed diff of what changed
3. **Multi-repo support**: Track dependencies across repositories
4. **Performance tracking**: Monitor hash calculation time
5. **Web interface**: View version history and changes

## References

- **PHILOSOPHY.md**: Zero-BS implementation, ruthless simplicity
- **PATTERNS.md**: Testing pyramid, proportionality principle
- **Issue tracking**: See project issues for version tracking improvements
