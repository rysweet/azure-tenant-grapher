# Documentation Validation Tools

Comprehensive validation tools for maintaining documentation quality, structure, and linkage.

## Overview

This suite provides three components for documentation validation:

1. **Link Validation** (`validate_docs_links.py`) - Ensures all internal links are valid
2. **Orphan Detection** (`find_orphaned_docs.py`) - Finds unreachable documentation files
3. **Test Suite** (`tests/test_documentation.py`) - Automated tests for CI integration

## Quick Start

```bash
# Validate all documentation links
python scripts/validate_docs_links.py

# Find orphaned documentation files
python scripts/find_orphaned_docs.py

# Run comprehensive test suite
uv run pytest tests/test_documentation.py -v
```

## Tools

### 1. Link Validation Script

**Purpose**: Validates that all internal markdown links point to existing files.

**Features**:
- Extracts internal links from markdown files
- Resolves relative and absolute paths
- Checks target file existence
- Reports broken links with file:line information
- Supports fail-fast mode for CI

**Usage**:

```bash
# Basic validation
python scripts/validate_docs_links.py

# Validate specific directory
python scripts/validate_docs_links.py --docs-dir docs/guides

# Fail-fast mode (stop on first error)
python scripts/validate_docs_links.py --fail-fast

# Quiet mode (errors only)
python scripts/validate_docs_links.py --quiet
```

**Example Output**:

```
======================================================================
Documentation Link Validation Report
======================================================================

Total links found:     596
Valid internal links:  461
External links:        70
Broken links:          65

BROKEN LINKS:
----------------------------------------------------------------------

File: MONITOR_COMMAND.md:396
Text: Graph Visualization
Link: VISUALIZATION.md
Resolved: /path/to/docs/VISUALIZATION.md
Status: FILE NOT FOUND
```

### 2. Orphan Detection Script

**Purpose**: Identifies documentation files not reachable from INDEX.md through link traversal.

**Features**:
- Traverses documentation graph from INDEX.md
- Identifies orphaned (unreachable) files
- Suggests additions to INDEX.md
- Reports documentation coverage percentage
- Supports strict mode (exit with error if orphans found)

**Usage**:

```bash
# Basic orphan detection
python scripts/find_orphaned_docs.py

# Use custom index file
python scripts/find_orphaned_docs.py --index README.md

# Suggest fixes for INDEX.md
python scripts/find_orphaned_docs.py --suggest-fix

# Strict mode (fail if orphans found)
python scripts/find_orphaned_docs.py --strict
```

**Example Output**:

```
======================================================================
Orphaned Documentation Detection Report
======================================================================

Index file:        INDEX.md
Total MD files:    193
Reachable files:   37
Orphaned files:    156
Coverage:          19.2%

ORPHANED FILES (not reachable from INDEX.md):
----------------------------------------------------------------------
  - ARCHITECTURE_IMPROVEMENTS.md
  - MONITOR_COMMAND.md
  - PERFORMANCE_OPTIMIZATION_SUMMARY.md
  ...

SUGGESTED FIXES:
----------------------------------------------------------------------
Add these files to INDEX.md or link from existing docs:

- [Architecture Improvements](ARCHITECTURE_IMPROVEMENTS.md)
- [Monitor Command](MONITOR_COMMAND.md)
- [Performance Optimization Summary](PERFORMANCE_OPTIMIZATION_SUMMARY.md)
```

### 3. Test Suite

**Purpose**: Automated tests for CI/CD integration ensuring documentation quality.

**Test Coverage**:

#### Link Validation Tests
- `test_no_broken_internal_links` - All internal links are valid
- `test_link_extraction` - Link extraction works correctly
- `test_external_link_detection` - External links identified properly
- `test_relative_path_resolution` - Relative paths resolve correctly
- `test_anchor_removal` - Anchors removed from paths

#### Orphan Detection Tests
- `test_no_orphaned_documents` - All files reachable from INDEX.md
- `test_index_file_exists` - INDEX.md exists
- `test_link_traversal` - Link traversal finds connected files
- `test_internal_link_extraction` - Only internal links extracted

#### Image Reference Tests
- `test_all_images_exist` - Referenced images exist
- `test_image_alt_text_present` - Images have alt text (accessibility)

#### Markdown Syntax Tests
- `test_no_malformed_links` - No malformed markdown links
- `test_heading_hierarchy` - Heading levels don't skip (H1->H2->H3)

#### Structure Validation Tests
- `test_index_has_structure` - INDEX.md has proper structure
- `test_all_docs_have_titles` - All markdown files have H1 titles
- `test_readme_files_in_subdirectories` - Subdirectories have README/INDEX

#### Integration Tests
- `test_full_link_validation` - Complete link validation
- `test_full_orphan_detection` - Complete orphan detection
- `test_documentation_health_score` - Overall health score (95%+ required)

**Usage**:

```bash
# Run all documentation tests
uv run pytest tests/test_documentation.py -v

# Run specific test class
uv run pytest tests/test_documentation.py::TestLinkValidation -v

# Run specific test
uv run pytest tests/test_documentation.py::TestLinkValidation::test_no_broken_internal_links -v

# Run with coverage
uv run pytest tests/test_documentation.py --cov=scripts --cov-report=html
```

**Example Test Output**:

```
tests/test_documentation.py::TestLinkValidation::test_no_broken_internal_links FAILED
tests/test_documentation.py::TestLinkValidation::test_link_extraction PASSED
tests/test_documentation.py::TestLinkValidation::test_external_link_detection PASSED
tests/test_documentation.py::TestOrphanDetection::test_no_orphaned_documents FAILED
tests/test_documentation.py::TestImageReferences::test_all_images_exist PASSED
tests/test_documentation.py::TestDocumentationIntegration::test_documentation_health_score FAILED

Documentation Health Score: 78.5%
  Link Quality: 87.8%
  Coverage: 19.2%

ERROR: Documentation health score below threshold: 78.5% < 95%
```

## CI Integration

### GitHub Actions Example

```yaml
name: Documentation Validation

on: [push, pull_request]

jobs:
  validate-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Validate documentation links
        run: python scripts/validate_docs_links.py --fail-fast

      - name: Check for orphaned docs
        run: python scripts/find_orphaned_docs.py --strict

      - name: Run documentation tests
        run: uv run pytest tests/test_documentation.py -v
```

### Pre-commit Hook Example

Create `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: validate-docs-links
        name: Validate documentation links
        entry: python scripts/validate_docs_links.py
        language: system
        pass_filenames: false

      - id: check-orphaned-docs
        name: Check for orphaned documentation
        entry: python scripts/find_orphaned_docs.py --strict
        language: system
        pass_filenames: false
```

## Pytest Fixtures

The test suite provides reusable fixtures for documentation testing:

### Session-Scoped Fixtures
- `repo_root` - Repository root directory
- `docs_root` - Documentation root directory

### Test-Scoped Fixtures
- `temp_docs_dir` - Temporary documentation directory
- `sample_markdown_file` - Sample markdown file
- `documentation_tree` - Complete documentation tree structure
- `broken_links_tree` - Documentation tree with broken links
- `markdown_syntax_samples` - Various markdown syntax patterns

### Usage Example

```python
def test_custom_validation(documentation_tree):
    """Custom test using documentation tree fixture."""
    docs_dir = documentation_tree["root"]
    index = documentation_tree["index"]

    # Your test logic here
    assert index.exists()
    assert len(list(docs_dir.rglob('*.md'))) > 0
```

## Design Principles

Following amplihack philosophy:

### Ruthless Simplicity
- Single-purpose scripts with clear responsibilities
- No complex abstractions or frameworks
- Standard library preferred (pathlib, re, argparse)

### Zero-BS Implementation
- Working validation from day one
- No stubs or placeholders
- Real error messages with actionable guidance

### Modular Design (Bricks & Studs)
- `LinkValidator` - Self-contained link validation
- `OrphanDetector` - Self-contained orphan detection
- Clear public APIs via dataclasses (`ValidationResult`, `OrphanReport`)
- Regeneratable from specifications

### Testing Strategy
- 60% unit tests (fast, isolated)
- 30% integration tests (multiple components)
- 10% E2E tests (complete workflows)
- All tests pass in < 5 seconds

## Architecture

### Link Validation Flow

```
1. Find all markdown files (*.md)
   ↓
2. Extract links using regex
   ↓
3. Filter internal vs external
   ↓
4. Resolve relative paths
   ↓
5. Check file existence
   ↓
6. Report broken links
```

### Orphan Detection Flow

```
1. Start from INDEX.md
   ↓
2. Extract internal links
   ↓
3. Traverse linked files recursively
   ↓
4. Track visited/reachable files
   ↓
5. Find all markdown files
   ↓
6. Compute: orphans = all - reachable
   ↓
7. Report orphaned files
```

## Current Status

### Real Documentation Issues Found

**Link Validation**:
- 65 broken links identified
- Common issues:
  - Files referenced from docs/ with `docs/` prefix (double path)
  - Missing migration files referenced
  - Renamed/moved files not updated in links

**Orphan Detection**:
- 156 orphaned files (19.2% coverage)
- Major orphaned categories:
  - Architecture documentation
  - Bug fix documentation
  - Performance guides
  - Testing documentation

**Next Steps**:
1. Fix broken links (Issue #614)
2. Add orphaned files to INDEX.md or link from existing docs
3. Target 95%+ documentation health score

## Troubleshooting

### Issue: Scripts report false positives

**Solution**: Check for:
- Anchor-only links (`#section`) - these are valid
- External links - should be skipped
- Case sensitivity - file systems may be case-sensitive

### Issue: Tests fail with "No module named pytest"

**Solution**: Use `uv run pytest` instead of `python -m pytest`:

```bash
uv run pytest tests/test_documentation.py -v
```

### Issue: Coverage failure in tests

**Solution**: This is expected - the validation scripts themselves aren't covered by the test suite. The tests validate documentation, not the script code. To exclude from coverage:

```bash
uv run pytest tests/test_documentation.py --no-cov
```

## Best Practices

### Documentation Structure
1. Always have INDEX.md at docs root
2. Link all documentation from INDEX.md (directly or transitively)
3. Use relative links from same directory: `[Link](./file.md)`
4. Use relative links from parent: `[Link](../parent/file.md)`
5. Avoid absolute paths unless necessary

### Link Formatting
- Good: `[Text](./relative.md)` or `[Text](../parent.md)`
- Bad: `[Text](docs/docs/file.md)` (double path)
- Good: `[Text](#anchor)` (anchor-only)
- Good: `[Text](https://external.com)` (external)

### Image References
- Always include alt text: `![Description](image.png)`
- Use relative paths: `![Diagram](./images/diagram.png)`
- Keep images near markdown files or in `images/` subdirectory

### Subdirectories
- Include README.md or INDEX.md in each subdirectory
- Link subdirectory index from parent documentation
- Maintain clear navigation hierarchy

## Contributing

When adding new validation rules:

1. Add validation logic to appropriate script
2. Add unit tests to `test_documentation.py`
3. Add fixtures to `tests/conftest.py` if needed
4. Update this README with usage examples
5. Ensure all tests pass: `uv run pytest tests/test_documentation.py -v`

## References

- Architecture Design: Based on architect's design for Issue #614
- Testing Pyramid: 60% unit, 30% integration, 10% E2E
- amplihack Philosophy: `.claude/context/PHILOSOPHY.md`
- Project Patterns: `.claude/context/PATTERNS.md`
